"""Paid Girl / Adult DP Guard for BioGuard.

Checks a member's current Telegram profile photo when they send a group message.
Only high-confidence adult/sexualized detections are acted on. Detection failures
are fail-open and never punish a user.
"""

from __future__ import annotations

import asyncio
import logging
import os
import tempfile
import time
from collections import defaultdict
from typing import Any

from pyrogram import Client, filters
from pyrogram.enums import ButtonStyle
from pyrogram.errors import ChatAdminRequired, FloodWait, RPCError, UserAdminInvalid
from pyrogram.types import CallbackQuery, ChatPermissions, InlineKeyboardMarkup, Message
from pyrogram.raw.functions.channels import EditBanned
from pyrogram.raw.types import ChatBannedRights, InputChannel

import config

from Client.helpers import get_approved_users, is_user_admin
from Client.premium import premium_button, premium_emoji

logger = logging.getLogger("BioLinkRemover.PaidGirl")

# Guard is opt-in per group.
CACHE_TTL = max(30, int(os.getenv("BIOGUARD_PAIDGIRL_CACHE_TTL", "300")))
STRICT_SCORE = float(os.getenv("BIOGUARD_PAIDGIRL_SCORE", "0.55"))
BRA_SCORE = float(os.getenv("BIOGUARD_PAIDGIRL_BRA_SCORE", "0.60"))

_detector = None
_detector_lock = asyncio.Lock()
_dp_cache: dict[tuple[int, int], tuple[float, str, bool, str | None]] = {}
_user_locks: defaultdict[tuple[int, int], asyncio.Lock] = defaultdict(asyncio.Lock)

EXPLICIT_LABELS = {
    "FEMALE_GENITALIA_EXPOSED",
    "MALE_GENITALIA_EXPOSED",
    "ANUS_EXPOSED",
}
EXPOSED_LABELS = {
    "FEMALE_BREAST_EXPOSED",
    "BUTTOCKS_EXPOSED",
    "MALE_BREAST_EXPOSED",
}
COVERED_BREAST_LABEL = "FEMALE_BREAST_COVERED"
SUPPORT_LABELS = {
    "BELLY_EXPOSED",
    "ARMPITS_EXPOSED",
}


async def _get_detector():
    """Load NudeNet only when Paid Girl Guard is actually used."""
    global _detector
    if _detector is not None:
        return _detector

    async with _detector_lock:
        if _detector is not None:
            return _detector
        try:
            from nudenet import NudeDetector
        except ImportError:
            logger.exception(
                "Paid Girl Guard requires NudeNet. Install requirements.txt "
                "(nudenet>=3.4.2,<4)."
            )
            return None

        try:
            _detector = NudeDetector()
            logger.info("Paid Girl Guard NudeNet detector loaded.")
        except Exception:
            logger.exception("Failed to initialise NudeNet detector.")
            _detector = None
        return _detector


def _result_from_detections(detections: Any) -> tuple[bool, str | None]:
    """Convert NudeNet detections into a conservative moderation decision."""
    if not isinstance(detections, list):
        return False, None

    best: dict[str, float] = {}
    for item in detections:
        if not isinstance(item, dict):
            continue
        label = str(item.get("class") or item.get("label") or "").upper()
        try:
            score = float(item.get("score", item.get("confidence", 0)))
        except (TypeError, ValueError):
            continue
        best[label] = max(best.get(label, 0.0), score)

    # Explicit nudity: high-confidence single-label decision.
    for label in EXPLICIT_LABELS:
        score = best.get(label, 0.0)
        if score >= STRICT_SCORE:
            return True, f"explicit adult content ({score:.0%})"

    # Clearly exposed breasts/buttocks.
    for label in EXPOSED_LABELS:
        score = best.get(label, 0.0)
        if score >= STRICT_SCORE:
            return True, f"adult nudity ({score:.0%})"

    # Bra / covered-breast case. NudeNet exposes a dedicated
    # FEMALE_BREAST_COVERED label, so use it together with body-exposure
    # signals, while also allowing a strong covered-breast detection by itself.
    covered = best.get(COVERED_BREAST_LABEL, 0.0)
    belly = best.get("BELLY_EXPOSED", 0.0)
    armpits = best.get("ARMPITS_EXPOSED", 0.0)
    if covered >= BRA_SCORE:
        return True, f"bra/underwear-style DP ({covered:.0%})"
    if covered >= 0.50 and (belly >= 0.45 or armpits >= 0.45):
        return True, f"bra/underwear-style DP ({covered:.0%})"

    return False, None


async def _detect_file(path: str) -> tuple[bool, str | None]:
    detector = await _get_detector()
    if detector is None:
        return False, None

    try:
        detections = await asyncio.to_thread(detector.detect, path)
        return _result_from_detections(detections)
    except Exception:
        logger.exception("NudeNet detection failed for %s", path)
        return False, None


async def check_paidgirl_dp(
    client: Client, chat_id: int, user_id: int
) -> tuple[bool, str | None]:
    """Check the user's newest profile photo and cache only the inference result."""
    cache_key = (chat_id, user_id)
    lock = _user_locks[cache_key]

    async with lock:
        now = time.monotonic()
        temp_path = None
        downloaded_path = None
        try:
            # Always ask Telegram for the newest photo so a recently changed DP
            # is not hidden behind the inference cache.
            photo = None
            async for item in client.get_chat_photos(user_id, limit=1):
                photo = item
                break

            if photo is None:
                _dp_cache[cache_key] = (now, "", False, None)
                return False, None

            photo_key = getattr(photo, "file_unique_id", None) or getattr(
                photo, "file_id", ""
            )
            cached = _dp_cache.get(cache_key)
            if cached and cached[1] == str(photo_key) and now - cached[0] < CACHE_TTL:
                return cached[2], cached[3]

            temp_path = os.path.join(
                tempfile.gettempdir(),
                f"bioguard_paidgirl_{chat_id}_{user_id}_{int(now * 1000)}.jpg",
            )
            downloaded = await client.download_media(
                photo.file_id, file_name=temp_path
            )
            downloaded_path = downloaded
            if not downloaded or not os.path.exists(downloaded):
                _dp_cache[cache_key] = (now, str(photo_key), False, None)
                return False, None

            is_adult, reason = await _detect_file(downloaded)
            if os.getenv("BIOGUARD_PAIDGIRL_DEBUG", "false").lower() in {"1", "true", "yes", "on"}:
                logger.info(
                    "Paid Girl DP result chat=%s user=%s photo=%s adult=%s reason=%s",
                    chat_id, user_id, photo_key, is_adult, reason,
                )
            _dp_cache[cache_key] = (now, str(photo_key), is_adult, reason)
            return is_adult, reason

        except (FloodWait, RPCError):
            raise
        except Exception:
            logger.exception(
                "Failed to inspect DP of user %s in chat %s", user_id, chat_id
            )
            return False, None
        finally:
            for cleanup_path in {temp_path, downloaded_path}:
                if cleanup_path:
                    try:
                        if os.path.exists(cleanup_path):
                            os.remove(cleanup_path)
                    except OSError:
                        pass

def paidgirl_keyboard(chat_id: int, enabled: bool) -> InlineKeyboardMarkup:
    toggle_text = "Disable Guard" if enabled else "Enable Guard"
    toggle_emoji = "cancel" if enabled else "confirm"
    toggle_data = f"paidgirl:toggle:{chat_id}"
    return InlineKeyboardMarkup(
        [
            [
                premium_button(
                    toggle_text,
                    toggle_emoji,
                    ButtonStyle.DANGER if enabled else ButtonStyle.SUCCESS,
                    callback_data=toggle_data,
                )
            ],
            [
                premium_button(
                    "Allowed Users",
                    "admins",
                    ButtonStyle.PRIMARY,
                    callback_data=f"paidgirl:list:{chat_id}",
                ),
                premium_button(
                    "Clear Allowed",
                    "cancel",
                    ButtonStyle.DANGER,
                    callback_data=f"paidgirl:clear:{chat_id}",
                ),
            ],
        ]
    )


def _status_text(chat_title: str, enabled: bool) -> str:
    status = "ENABLED" if enabled else "DISABLED"
    status_emoji = premium_emoji("confirm", "✅") if enabled else premium_emoji("cancel", "❌")
    return (
        f"{premium_emoji('auth', '🛡️')} <b>Paid Girl DP Guard</b>\n\n"
        f"{premium_emoji('source', '👥')} <b>Group:</b> {chat_title}\n"
        f"{premium_emoji('queue', '⚙️')} <b>Status:</b> {status_emoji} <b>{status}</b>\n\n"
        f"{premium_emoji('help', '💡')} When enabled, the bot checks a member's "
        f"current profile photo when they send a message.\n"
        f"{premium_emoji('confirm', '🔎')} High-confidence adult/sexualized DPs, "
        f"including strongly detected bra/underwear-style images, are muted.\n"
        f"{premium_emoji('cancel', '🛡️')} Admins and allowed users are always exempt."
    )


async def _allowed(client: Client, chat_id: int, user_id: int) -> bool:
    try:
        cfg = await client.db.get_paidgirl_config(chat_id)
        return user_id in cfg.get("allowed_users", [])
    except Exception:
        logger.exception("Failed to read Paid Girl allow list.")
        return False


@Client.on_message(filters.command("paidgirl") & filters.group)
async def paidgirl_command(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    if not await is_user_admin(client, message.chat.id, user_id):
        await message.reply_text(
            f"{premium_emoji('cancel', '❌')} <b>Access Denied:</b> "
            "Only group administrators can manage Paid Girl DP Guard."
        )
        return

    chat_id = message.chat.id
    parts = (message.text or "").split()
    action = parts[1].lower() if len(parts) > 1 else "panel"

    if action in {"on", "enable"}:
        await client.db.set_paidgirl_guard(chat_id, True)
        enabled = True
    elif action in {"off", "disable"}:
        await client.db.set_paidgirl_guard(chat_id, False)
        enabled = False
    elif action in {"allow", "unallow"}:
        if len(parts) < 3 and not message.reply_to_message:
            await message.reply_text(
                f"{premium_emoji('cancel', '❌')} Use <code>/paidgirl {action} USER_ID</code> "
                "or reply to that user's message."
            )
            return
        try:
            if message.reply_to_message and message.reply_to_message.from_user:
                target_id = message.reply_to_message.from_user.id
            else:
                target_id = int(parts[2].lstrip("@"))
            if action == "allow":
                await client.db.paidgirl_allow_user(chat_id, target_id)
                text = f"{premium_emoji('confirm', '✅')} User <code>{target_id}</code> is now allowed."
            else:
                await client.db.paidgirl_unallow_user(chat_id, target_id)
                text = f"{premium_emoji('confirm', '✅')} User <code>{target_id}</code> was removed from the allowed list."
            await message.reply_text(text)
        except ValueError:
            await message.reply_text(
                f"{premium_emoji('cancel', '❌')} Please provide a numeric Telegram user ID."
            )
        return
    elif action in {"allowed", "list"}:
        cfg = await client.db.get_paidgirl_config(chat_id)
        users = cfg.get("allowed_users", [])
        if not users:
            await message.reply_text(
                f"{premium_emoji('source', 'ℹ️')} <b>Paid Girl Allowed Users</b>\n\nNo users are currently allowed."
            )
            return
        lines = []
        for uid in users:
            try:
                u = await client.get_users(uid)
                lines.append(f"• {u.mention} — <code>{uid}</code>")
            except Exception:
                lines.append(f"• <code>{uid}</code>")
        await message.reply_text(
            f"{premium_emoji('admins', '👥')} <b>Paid Girl Allowed Users</b>\n\n"
            + "\n".join(lines)
        )
        return
    elif action == "clear":
        await client.db.paidgirl_clear_allowed(chat_id)
        await message.reply_text(
            f"{premium_emoji('confirm', '✅')} <b>Paid Girl allowed list cleared.</b>"
        )
        return
    elif action not in {"panel", "status"}:
        await message.reply_text(
            f"{premium_emoji('help', '💡')} <b>Paid Girl commands</b>\n\n"
            "<code>/paidgirl</code> — Open settings\n"
            "<code>/paidgirl on</code> — Enable\n"
            "<code>/paidgirl off</code> — Disable\n"
            "<code>/paidgirl allow USER_ID</code> — Allow a user\n"
            "<code>/paidgirl unallow USER_ID</code> — Remove allowed user\n"
            "<code>/paidgirl allowed</code> — Show allowed users\n"
            "<code>/paidgirl clear</code> — Clear allowed users"
        )
        return

    cfg = await client.db.get_paidgirl_config(chat_id)
    await message.reply_text(
        _status_text(message.chat.title or "Group", cfg["enabled"]),
        reply_markup=paidgirl_keyboard(chat_id, cfg["enabled"]),
    )


async def _safe_edit_callback(callback_query: CallbackQuery, text: str, reply_markup=None):
    """Edit a callback message without failing when Telegram reports no change."""
    try:
        return await callback_query.edit_message_text(text, reply_markup=reply_markup)
    except RPCError as exc:
        if "MESSAGE_NOT_MODIFIED" in str(exc).upper():
            return None
        raise


@Client.on_callback_query(filters.regex(r"^paidgirl:(toggle|list|clear):(-?\d+)$"))
async def paidgirl_settings_callback(client: Client, callback_query: CallbackQuery):
    action = callback_query.data.split(":")[1]
    chat_id = int(callback_query.data.split(":")[2])
    clicker_id = callback_query.from_user.id

    if not await is_user_admin(client, chat_id, clicker_id):
        await callback_query.answer("Only group administrators can use this panel.", show_alert=True)
        return

    if action == "toggle":
        cfg = await client.db.get_paidgirl_config(chat_id)
        enabled = not cfg["enabled"]
        await client.db.set_paidgirl_guard(chat_id, enabled)
        await callback_query.answer(
            f"Paid Girl Guard {'enabled' if enabled else 'disabled'}.",
            show_alert=True,
        )
    elif action == "clear":
        await client.db.paidgirl_clear_allowed(chat_id)
        await callback_query.answer("Allowed list cleared.", show_alert=True)
    else:
        cfg = await client.db.get_paidgirl_config(chat_id)
        users = cfg.get("allowed_users", [])
        if not users:
            await callback_query.answer("No allowed users.", show_alert=True)
            return
        await callback_query.answer(
            "Allowed: " + ", ".join(str(uid) for uid in users[:15]),
            show_alert=True,
        )

    cfg = await client.db.get_paidgirl_config(chat_id)
    try:
        chat = await client.get_chat(chat_id)
        title = chat.title or "Group"
    except Exception:
        title = "Group"
    await _safe_edit_callback(
        callback_query,
        _status_text(title, cfg["enabled"]),
        reply_markup=paidgirl_keyboard(chat_id, cfg["enabled"]),
    )


@Client.on_callback_query(filters.regex(r"^paidgirl_allow:(-?\d+):(-?\d+)$"))
async def paidgirl_allow_callback(client: Client, callback_query: CallbackQuery):
    chat_id = int(callback_query.data.split(":")[1])
    target_id = int(callback_query.data.split(":")[2])

    if not await is_user_admin(client, chat_id, callback_query.from_user.id):
        await callback_query.answer("Only group administrators can allow users.", show_alert=True)
        return

    await client.db.paidgirl_allow_user(chat_id, target_id)
    await callback_query.answer("User allowed for Paid Girl Guard.", show_alert=True)

    try:
        user = await client.get_users(target_id)
        mention = user.mention
    except Exception:
        mention = f"User <code>{target_id}</code>"

    await _safe_edit_callback(
        callback_query,
        f"{premium_emoji('auth', '🛡️')} <b>Paid Girl DP Guard</b>\n\n"
        f"{premium_emoji('admins', '👤')} {mention} is now <b>ALLOWED</b>.\n"
        f"{premium_emoji('confirm', '✅')} Their DP will no longer be checked in this group."
    )


@Client.on_callback_query(filters.regex(r"^paidgirl_dismiss:(-?\d+)$"))
async def paidgirl_dismiss_callback(client: Client, callback_query: CallbackQuery):
    chat_id = callback_query.message.chat.id
    if not await is_user_admin(client, chat_id, callback_query.from_user.id):
        await callback_query.answer("Only group administrators can dismiss this alert.", show_alert=True)
        return
    await callback_query.answer("Alert dismissed.")
    try:
        await callback_query.message.delete()
    except Exception:
        pass


@Client.on_message(filters.group & ~filters.service, group=-1)
async def paidgirl_scan_message(client: Client, message: Message):
    """Inspect every normal group message when Paid Girl Guard is enabled."""
    logger.info(
        "Paid Girl handler received message chat=%s user=%s message_id=%s",
        getattr(message.chat, "id", None),
        getattr(message.from_user, "id", None),
        getattr(message, "id", None),
    )
    if not message.from_user:
        logger.info("Paid Girl handler skipped: message has no from_user")
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    try:
        cfg = await client.db.get_paidgirl_config(chat_id)
        if not cfg["enabled"]:
            logger.info("Paid Girl skipped: disabled chat=%s", chat_id)
            return

        if await is_user_admin(client, chat_id, user_id):
            logger.info("Paid Girl skipped: admin chat=%s user=%s", chat_id, user_id)
            return

        if await _allowed(client, chat_id, user_id):
            logger.info("Paid Girl skipped: allowed chat=%s user=%s", chat_id, user_id)
            return

        # Existing BioGuard approvals also act as a global exemption.
        if user_id in await get_approved_users(client, chat_id):
            logger.info("Paid Girl skipped: approved chat=%s user=%s", chat_id, user_id)
            return

        is_adult, reason = await check_paidgirl_dp(client, chat_id, user_id)
        logger.info(
            "Paid Girl scan chat=%s user=%s detected=%s reason=%s",
            chat_id, user_id, is_adult, reason,
        )
        if not is_adult:
            return

        try:
            await message.delete()
        except Exception:
            pass

        # Apply the restriction through the high-level API first, then use
        # MTProto as a fallback. The raw fallback is important for Kurigram/Pyrogram
        # builds where a high-level permission argument can differ between versions.
        mute_permissions = ChatPermissions(
            can_send_messages=False,
            can_send_audios=False,
            can_send_documents=False,
            can_send_photos=False,
            can_send_videos=False,
            can_send_video_notes=False,
            can_send_voice_notes=False,
            can_send_polls=False,
            can_send_other_messages=False,
            can_add_web_page_previews=False,
        )

        async def _high_level_mute():
            try:
                await client.restrict_chat_member(
                    chat_id,
                    user_id,
                    permissions=mute_permissions,
                    use_independent_chat_permissions=True,
                )
            except TypeError:
                await client.restrict_chat_member(
                    chat_id,
                    user_id,
                    permissions=mute_permissions,
                )

        async def _raw_mute():
            chat_peer = await client.resolve_peer(chat_id)
            user_peer = await client.resolve_peer(user_id)
            if not hasattr(chat_peer, "channel_id") or not hasattr(chat_peer, "access_hash"):
                raise RuntimeError("Paid Girl raw mute requires a supergroup/channel peer")
            channel_peer = InputChannel(
                channel_id=chat_peer.channel_id,
                access_hash=chat_peer.access_hash,
            )
            rights = ChatBannedRights(
                send_messages=True,
                send_media=True,
                send_stickers=True,
                send_gifs=True,
                send_games=True,
                send_inline=True,
                embed_links=True,
                send_polls=True,
                send_photos=True,
                send_videos=True,
                send_roundvideos=True,
                send_audios=True,
                send_voices=True,
                send_docs=True,
                send_plain=True,
                send_reactions=True,
                until_date=0,
            )
            await client.invoke(
                EditBanned(
                    channel=channel_peer,
                    participant=user_peer,
                    banned_rights=rights,
                )
            )

        mute_applied = False
        try:
            await _high_level_mute()
            mute_applied = True
        except FloodWait as fw:
            await asyncio.sleep(fw.value)
            await _high_level_mute()
            mute_applied = True
        except (UserAdminInvalid, ChatAdminRequired, RPCError) as exc:
            logger.warning(
                "High-level Paid Girl mute failed for user=%s chat=%s: %s; trying MTProto fallback.",
                user_id, chat_id, exc,
            )

        if not mute_applied:
            try:
                await _raw_mute()
                mute_applied = True
            except FloodWait as fw:
                await asyncio.sleep(fw.value)
                await _raw_mute()
                mute_applied = True
            except Exception as exc:
                logger.exception(
                    "MTProto Paid Girl mute fallback failed for user=%s chat=%s: %s",
                    user_id, chat_id, exc,
                )
                return

        # Verify Telegram actually applied the restriction before announcing
        # the action. This catches API/library incompatibilities immediately.
        try:
            member = await client.get_chat_member(chat_id, user_id)
            permissions = getattr(member, "permissions", None)
            status_obj = getattr(member, "status", "")
            status = str(getattr(status_obj, "value", status_obj)).lower()
            can_send = getattr(permissions, "can_send_messages", None)
            if "restricted" not in status or can_send is not False:
                logger.warning(
                    "Paid Girl Guard mute verification failed after first attempt: "
                    "chat=%s user=%s status=%s can_send_messages=%r; retrying raw MTProto.",
                    chat_id, user_id, status, can_send,
                )
                try:
                    await _raw_mute()
                    await asyncio.sleep(0.5)
                    member = await client.get_chat_member(chat_id, user_id)
                    permissions = getattr(member, "permissions", None)
                    status_obj = getattr(member, "status", "")
                    status = str(getattr(status_obj, "value", status_obj)).lower()
                    can_send = getattr(permissions, "can_send_messages", None)
                except Exception:
                    logger.exception(
                        "Paid Girl Guard raw verification retry failed: chat=%s user=%s",
                        chat_id, user_id,
                    )
                if "restricted" not in status or can_send is not False:
                    logger.error(
                        "Paid Girl Guard mute verification failed: chat=%s user=%s "
                        "status=%s can_send_messages=%r",
                        chat_id, user_id, status, can_send,
                    )
                    return
        except Exception as exc:
            logger.exception(
                "Paid Girl Guard could not verify mute for user=%s chat=%s: %s",
                user_id, chat_id, exc,
            )
            return

        mention = message.from_user.mention
        text = (
            f"{premium_emoji('auth', '🛡️')} <b>Paid Girl DP Guard</b>\n\n"
            f"{premium_emoji('admins', '👤')} <b>User:</b> {mention} "
            f"(<code>{user_id}</code>)\n"
            f"{premium_emoji('cancel', '🔞')} <b>Action:</b> MUTED\n"
            f"{premium_emoji('source', '📝')} <b>Reason:</b> {reason}\n\n"
            f"{premium_emoji('help', '⚠️')} Admins can allow this user if the detection was incorrect."
        )
        markup = InlineKeyboardMarkup(
            [
                [
                    premium_button(
                        "Allow User",
                        "confirm",
                        ButtonStyle.SUCCESS,
                        callback_data=f"paidgirl_allow:{chat_id}:{user_id}",
                    ),
                    premium_button(
                        "Dismiss",
                        "cancel",
                        ButtonStyle.DANGER,
                        callback_data=f"paidgirl_dismiss:{chat_id}",
                    ),
                ]
            ]
        )
        await client.send_message(chat_id, text, reply_markup=markup)

        if config.LOGGER_GROUP:
            await client.send_message(
                config.LOGGER_GROUP,
                f"{premium_emoji('auth', '🛡️')} <b>[PAID GIRL DP GUARD]</b>\n\n"
                f"{premium_emoji('admins', '👥')} <b>Group:</b> {message.chat.title} "
                f"(<code>{chat_id}</code>)\n"
                f"{premium_emoji('source', '👤')} <b>User:</b> {mention} "
                f"(<code>{user_id}</code>)\n"
                f"{premium_emoji('cancel', '🔞')} <b>Action:</b> MUTED\n"
                f"{premium_emoji('help', '📝')} <b>Reason:</b> {reason}"
            )

    except FloodWait as fw:
        await asyncio.sleep(fw.value)
    except Exception:
        logger.exception("Unexpected Paid Girl Guard error in chat %s.", chat_id)
