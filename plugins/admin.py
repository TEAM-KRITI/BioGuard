#This code was published by @MightyAyush on github.com/mightyayush
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatType, ButtonStyle
from pyrogram.errors import FloodWait
import asyncio
import logging
import config
from Client.cache import GROUP_CONFIG_CACHE, APPROVED_USERS_CACHE
from Client.helpers import get_group_config, get_approved_users, is_user_admin
from Client.premium import premium_button

logger = logging.getLogger("BioLinkRemover.Admin")

async def get_target_user(client: Client, message: Message) -> tuple[int, str]:
    if message.reply_to_message and message.reply_to_message.from_user:
        user = message.reply_to_message.from_user
        return user.id, user.mention

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        raise Exception("Please reply to a user's message or specify a user ID / username.")

    target = parts[1].strip()

    if target.isdigit() or (target.startswith("-") and target[1:].isdigit()):
        user_id = int(target)
        try:
            user = await client.get_users(user_id)
            return user.id, user.mention
        except Exception:
            return user_id, f"User ID <code>{user_id}</code>"

    username = target.lstrip("@")
    try:
        user = await client.get_users(username)
        return user.id, user.mention
    except Exception as e:
        raise Exception(f"Failed to resolve username @{username}: {e}")

@Client.on_message(filters.command("approve") & filters.group)
async def approve_user_cmd(client: Client, message: Message):
    if not await is_user_admin(client, message.chat.id, message.from_user.id):
        await message.reply_text("<tg-emoji emoji-id='6041720006973067267'>❌</tg-emoji> <b>Access Denied:</b> This command is restricted to group administrators.")
        return

    try:
        user_id, mention = await get_target_user(client, message)
    except Exception as e:
        await message.reply_text(f"<tg-emoji emoji-id='6041720006973067267'>❌</tg-emoji> <b>Error:</b> {e}")
        return

    await client.db.approve_user(message.chat.id, user_id)
    approved_set = await get_approved_users(client, message.chat.id)
    approved_set.add(user_id)
    await message.reply_text(f"<tg-emoji emoji-id='5463122435425448565'>✅</tg-emoji> {mention} has been <b>approved</b>. Their bio will not be scanned in this group.")

@Client.on_message(filters.command("unapprove") & filters.group)
async def unapprove_user_cmd(client: Client, message: Message):
    if not await is_user_admin(client, message.chat.id, message.from_user.id):
        await message.reply_text("<tg-emoji emoji-id='6041720006973067267'>❌</tg-emoji> <b>Access Denied:</b> This command is restricted to group administrators.")
        return

    try:
        user_id, mention = await get_target_user(client, message)
    except Exception as e:
        await message.reply_text(f"<tg-emoji emoji-id='6041720006973067267'>❌</tg-emoji> <b>Error:</b> {e}")
        return

    await client.db.unapprove_user(message.chat.id, user_id)
    approved_set = await get_approved_users(client, message.chat.id)
    approved_set.discard(user_id)
    await message.reply_text(f"<tg-emoji emoji-id='5463122435425448565'>✅</tg-emoji> {mention} has been <b>unapproved</b>. Their bio will now be scanned.")

@Client.on_message(filters.command("unapproveall") & filters.group)
async def unapprove_all_cmd(client: Client, message: Message):
    if not await is_user_admin(client, message.chat.id, message.from_user.id):
        await message.reply_text("<tg-emoji emoji-id='6041720006973067267'>❌</tg-emoji> <b>Access Denied:</b> This command is restricted to group administrators.")
        return

    await client.db.unapprove_all(message.chat.id)
    APPROVED_USERS_CACHE[message.chat.id] = set()
    await message.reply_text("<tg-emoji emoji-id='5463122435425448565'>✅</tg-emoji> All approved users have been cleared from this group. Everyone (except admins) will be scanned.")

@Client.on_message(filters.command("approved") & filters.group)
async def list_approved_cmd(client: Client, message: Message):
    approved_set = await get_approved_users(client, message.chat.id)
    if not approved_set:
        await message.reply_text("<tg-emoji emoji-id='5350396951407895212'>ℹ️</tg-emoji> No users are currently whitelisted in this group.")
        return

    status_msg = await message.reply_text("<tg-emoji emoji-id='5409186957676785646'>🔎</tg-emoji> Fetching whitelisted users list...")
    text = "<b><tg-emoji emoji-id='5408843502027033965'>📋</tg-emoji> Whitelisted Users in this group:</b>\n\n"
    for idx, uid in enumerate(approved_set, 1):
        try:
            user = await client.get_users(uid)
            text += f"{idx}. {user.mention} (ID: <code>{uid}</code>)\n"
        except Exception:
            text += f"{idx}. User ID <code>{uid}</code>\n"
    await status_msg.edit_text(text)

@Client.on_message(filters.command("config") & filters.group)
async def config_group_cmd(client: Client, message: Message):
    if not await is_user_admin(client, message.chat.id, message.from_user.id):
        await message.reply_text("<tg-emoji emoji-id='6041720006973067267'>❌</tg-emoji> <b>Access Denied:</b> This command is restricted to group administrators.")
        return

    current_mode = await get_group_config(client, message.chat.id)
    parts = message.text.split()
    if len(parts) > 1:
        new_mode = parts[1].strip().lower()
        if new_mode in ["ban", "mute", "kick"]:
            await client.db.set_group_config(message.chat.id, new_mode)
            GROUP_CONFIG_CACHE[message.chat.id] = new_mode
            await message.reply_text(f"<tg-emoji emoji-id='5463122435425448565'>✅</tg-emoji> Punishment mode successfully set to: <b>{new_mode.upper()}</b>")
            return
        else:
            await message.reply_text("<tg-emoji emoji-id='6041720006973067267'>❌</tg-emoji> Invalid mode. Please choose between: `ban`, `mute`, or `kick`.")
            return

    keyboard = InlineKeyboardMarkup([
        [
            premium_button("Ban", "cancel", ButtonStyle.DANGER, callback_data=f"set_cfg:ban:{message.chat.id}"),
            premium_button("Mute", "default", ButtonStyle.PRIMARY, callback_data=f"set_cfg:mute:{message.chat.id}"),
            premium_button("Kick", "cancel", ButtonStyle.DANGER, callback_data=f"set_cfg:kick:{message.chat.id}")
        ]
    ])

    await message.reply_text(
        f"<tg-emoji emoji-id='6100546468924364734'>⚙️</tg-emoji> <b>BioLinkRemover Configuration</b>\n\n"
        f"Group: <b>{message.chat.title}</b>\n"
        f"Current Punishment: <b>{current_mode.upper()}</b>\n\n"
        f"Select a punishment button below to toggle settings for link spam violations:",
        reply_markup=keyboard
    )

@Client.on_callback_query(filters.regex(r"^set_cfg:(ban|mute|kick):(-?\d+)$"))
async def config_callback_handler(client: Client, callback_query: CallbackQuery):
    mode = callback_query.data.split(":")[1]
    chat_id = int(callback_query.data.split(":")[2])
    clicker_id = callback_query.from_user.id

    if not await is_user_admin(client, chat_id, clicker_id):
        await callback_query.answer("❌ You are not authorized to edit this group's configuration.", show_alert=True)
        return

    await client.db.set_group_config(chat_id, mode)
    GROUP_CONFIG_CACHE[chat_id] = mode
    await callback_query.answer(f"✅ Config updated to {mode.upper()}", show_alert=True)

    try:
        chat = await client.get_chat(chat_id)
        chat_title = chat.title
    except Exception:
        chat_title = "Group Settings"

    keyboard = InlineKeyboardMarkup([
        [
            premium_button("Ban", "cancel", ButtonStyle.DANGER, callback_data=f"set_cfg:ban:{chat_id}"),
            premium_button("Mute", "default", ButtonStyle.PRIMARY, callback_data=f"set_cfg:mute:{chat_id}"),
            premium_button("Kick", "cancel", ButtonStyle.DANGER, callback_data=f"set_cfg:kick:{chat_id}")
        ]
    ])

    await callback_query.edit_message_text(
        f"<tg-emoji emoji-id='6100546468924364734'>⚙️</tg-emoji> <b>BioLinkRemover Configuration</b>\n\n"
        f"Group: <b>{chat_title}</b>\n"
        f"Current Punishment: <b>{mode.upper()}</b>\n\n"
        f"<tg-emoji emoji-id='5463122435425448565'>✅</tg-emoji> Mode updated successfully!",
        reply_markup=keyboard
    )

@Client.on_message(filters.command("stats") & filters.private)
async def stats_owner_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id != config.OWNER_ID and user_id not in config.SUDO_USERS:
        return

    users_count, groups_count = await client.db.get_stats()
    await message.reply_text(
        f"<tg-emoji emoji-id='6100546468924364734'>📊</tg-emoji> <b>Bot Usage Statistics</b>\n\n"
        f"<tg-emoji emoji-id='6021618194228187816'>👤</tg-emoji> <b>Total Registered Users:</b> {users_count}\n"
        f"<tg-emoji emoji-id='5767288287001580715'>👥</tg-emoji> <b>Total Registered Groups:</b> {groups_count}"
    )

@Client.on_message(filters.command("help"))
async def help_cmd(client: Client, message: Message):
    user_id = message.from_user.id if message.from_user else 0
    is_owner = (user_id == config.OWNER_ID or user_id in config.SUDO_USERS)

    if message.chat.type == ChatType.PRIVATE:
        help_text = (
            "<b><tg-emoji emoji-id='5350396951407895212'>📚</tg-emoji> Help & Commands Guide</b>\n\n"
            "<b><tg-emoji emoji-id='5767288287001580715'>👮</tg-emoji> Admin Commands (in groups):</b>\n"
            "• <code>/approve</code> (reply or ID) - Approve user to bypass bio checks.\n"
            "• <code>/unapprove</code> (reply or ID) - Revoke bypass approval.\n"
            "• <code>/unapproveall</code> - Clear all approved users.\n"
            "• <code>/approved</code> - List approved users in the group.\n"
            "• <code>/config</code> - Configure punishment mode (mute/kick/ban).\n"
        )
        if is_owner:
            help_text += (
                "\n<b><tg-emoji emoji-id='5217822164362739968'>👑</tg-emoji> Owner Commands (Private Chat):</b>\n"
                "• <code>/stats</code> - Show bot usage stats.\n"
                "• <code>/gcast</code> - Broadcast a message to all groups.\n"
                "• <code>/ucast</code> - Broadcast a message to all users who started PM."
            )
        await message.reply_text(help_text)
    else:
        is_admin = await is_user_admin(client, message.chat.id, user_id)
        if is_admin or is_owner:
            await message.reply_text(
                "<b><tg-emoji emoji-id='5350396951407895212'>📚</tg-emoji> Admin Help Guide</b>\n\n"
                "You have administrative rights to moderate this group with BioLinkRemover.\n\n"
                "<b><tg-emoji emoji-id='5767288287001580715'>👮</tg-emoji> Admin Commands:</b>\n"
                "• <code>/approve</code> (reply/ID) - Whitelist a user to bypass checks.\n"
                "• <code>/unapprove</code> (reply/ID) - Remove user from whitelist.\n"
                "• <code>/unapproveall</code> - Reset all group whitelists.\n"
                "• <code>/approved</code> - View whitelisted members.\n"
                "• <code>/config</code> - Configure punishment setting (mute/kick/ban)."
            )
        else:
            await message.reply_text("<tg-emoji emoji-id='6041720006973067267'>❌</tg-emoji> Only administrators can request the admin help menu.")

@Client.on_message(filters.command("gcast") & filters.private)
async def gcast_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id != config.OWNER_ID and user_id not in config.SUDO_USERS:
        return

    broadcast_msg = message.reply_to_message
    text_only = False
    text_to_send = ""

    if not broadcast_msg:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("<tg-emoji emoji-id='6041720006973067267'>❌</tg-emoji> Please reply to a message or provide text to broadcast.")
            return
        text_only = True
        text_to_send = parts[1].strip()

    status_msg = await message.reply_text("<tg-emoji emoji-id='6271537028307881531'>📢</tg-emoji> Starting group broadcast...")
    group_ids = await client.db.get_all_group_ids()

    success, failure = 0, 0
    for gid in group_ids:
        try:
            if text_only:
                await client.send_message(gid, text_to_send)
            else:
                await broadcast_msg.copy(gid)
            success += 1
            await asyncio.sleep(0.1)
        except FloodWait as fw:
            await asyncio.sleep(fw.value)
            try:
                if text_only:
                    await client.send_message(gid, text_to_send)
                else:
                    await broadcast_msg.copy(gid)
                success += 1
            except Exception:
                failure += 1
        except Exception:
            failure += 1

    await status_msg.edit_text(
        f"<tg-emoji emoji-id='5463122435425448565'>✅</tg-emoji> <b>Group Broadcast Completed!</b>\n\n"
        f"<tg-emoji emoji-id='6100546468924364734'>📈</tg-emoji> <b>Success:</b> {success}\n"
        f"<tg-emoji emoji-id='6100546468924364734'>📉</tg-emoji> <b>Failed:</b> {failure}"
    )

@Client.on_message(filters.command("ucast") & filters.private)
async def ucast_cmd(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id != config.OWNER_ID and user_id not in config.SUDO_USERS:
        return

    broadcast_msg = message.reply_to_message
    text_only = False
    text_to_send = ""

    if not broadcast_msg:
        parts = message.text.split(maxsplit=1)
        if len(parts) < 2:
            await message.reply_text("<tg-emoji emoji-id='6041720006973067267'>❌</tg-emoji> Please reply to a message or provide text to broadcast.")
            return
        text_only = True
        text_to_send = parts[1].strip()

    status_msg = await message.reply_text("<tg-emoji emoji-id='6271537028307881531'>📢</tg-emoji> Starting user broadcast...")
    user_ids = await client.db.get_all_user_ids()

    success, failure = 0, 0
    for uid in user_ids:
        try:
            if text_only:
                await client.send_message(uid, text_to_send)
            else:
                await broadcast_msg.copy(uid)
            success += 1
            await asyncio.sleep(0.1)
        except FloodWait as fw:
            await asyncio.sleep(fw.value)
            try:
                if text_only:
                    await client.send_message(uid, text_to_send)
                else:
                    await broadcast_msg.copy(uid)
                success += 1
            except Exception:
                failure += 1
        except Exception:
            failure += 1

    await status_msg.edit_text(
        f"<tg-emoji emoji-id='5463122435425448565'>✅</tg-emoji> <b>User Broadcast Completed!</b>\n\n"
        f"<tg-emoji emoji-id='6100546468924364734'>📈</tg-emoji> <b>Success:</b> {success}\n"
        f"<tg-emoji emoji-id='6100546468924364734'>📉</tg-emoji> <b>Failed:</b> {failure}"
    )
