# ============================================================
# BIO LINK RESTRICTOR — START MODULE
# ============================================================

import logging

from pyrogram import Client, filters
from pyrogram.types import (
    Message,
    InlineKeyboardMarkup,
    CallbackQuery,
)
from pyrogram.enums import ChatType, ButtonStyle

from Client.cache import USER_IDS_CACHE, GROUP_IDS_CACHE
from Client.premium import premium_button, premium_emoji


logger = logging.getLogger("BioLinkRemover.Start")


# ============================================================
# CONFIG
# ============================================================

SUPPORT_URL = "https://t.me/ArchonCare"

# Apni START IMAGE URL yahan lagao
START_IMAGE = "https://example.com/start.jpg"


# ============================================================
# START KEYBOARD
# ============================================================

def get_start_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                premium_button(
                    "˹ᴧᴅᴅ ϻᴇ˼",
                    "add",
                    ButtonStyle.SUCCESS,
                    url=f"https://t.me/{bot_username}?startgroup=true",
                )
            ],
            [
                premium_button(
                    "˹υᴘᴅᴧᴛᴇs˼",
                    "updates",
                    ButtonStyle.DANGER,
                    callback_data="updates_page",
                ),
                premium_button(
                    "˹sυᴘᴘᴏʀᴛ˼",
                    "support",
                    ButtonStyle.PRIMARY,
                    url=SUPPORT_URL,
                ),
            ],
            [
                premium_button(
                    "˹υsᴇʀ ɢυɪᴅᴇ˼",
                    "language",
                    ButtonStyle.PRIMARY,
                    callback_data="user_guide",
                ),
                premium_button(
                    "˹ᴧʙᴏυᴛ ʙᴏᴛ˼",
                    "source",
                    ButtonStyle.DANGER,
                    callback_data="about_bot",
                ),
            ],
            [
                premium_button(
                    "˹ʜᴇʟᴘ˼",
                    "help",
                    ButtonStyle.SUCCESS,
                    callback_data="help_pm",
                )
            ],
        ]
    )


# ============================================================
# BACK KEYBOARD
# ============================================================

def back_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                premium_button(
                    "˹ʙᴧᴄᴋ˼",
                    "back",
                    ButtonStyle.DANGER,
                    callback_data="start_pm",
                )
            ]
        ]
    )


# ============================================================
# MAIN START TEXT
# ============================================================

def get_welcome_text(first_name: str) -> str:
    return (
        f"{premium_emoji('home', '👋')} "
        f"<b>˹ʜᴇʟʟᴏ {first_name}!˼</b>\n\n"

        f"<b>˹ʙɪᴏ ʟɪɴᴋ ʀᴇsᴛʀɪᴄᴛᴏʀ˼</b>\n\n"

        f"˹ɪ ᴧϻ ᴧ ᴛᴇʟᴇɢʀᴧϻ sᴇᴄυʀɪᴛʏ ʙᴏᴛ "
        f"ᴅᴇsɪɢɴᴇᴅ ᴛᴏ ᴘʀᴏᴛᴇᴄᴛ ʏᴏυʀ ɢʀᴏυᴘs "
        f"ғʀᴏϻ sᴘᴧϻ, υɴᴡᴧɴᴛᴇᴅ ʟɪɴᴋs ᴧɴᴅ "
        f"sυsᴘɪᴄɪᴏυs ᴡᴇʙsɪᴛᴇs.˼\n\n"

        f"˹🔗 ʙɪᴏ sᴄᴧɴɴɪɴɢ˼\n"
        f"˹ɪ ᴄʜᴇᴄᴋ υsᴇʀ ʙɪᴏs ғᴏʀ sυsᴘɪᴄɪᴏυs "
        f"ʟɪɴᴋs, ᴡᴇʙsɪᴛᴇs ᴧɴᴅ ʀᴇsᴛʀɪᴄᴛᴇᴅ ᴡᴏʀᴅs.˼\n\n"

        f"˹🛡️ ᴧυᴛᴏ ϻᴏᴅᴇʀᴧᴛɪᴏɴ˼\n"
        f"˹ɪғ ᴧ υsᴇʀ ᴠɪᴏʟᴧᴛᴇs ʏᴏυʀ ʀυʟᴇs, "
        f"ᴛʜᴇ ᴄᴏɴғɪɢυʀᴇᴅ ᴘυɴɪsʜϻᴇɴᴛ ᴡɪʟʟ "
        f"ʙᴇ ᴧᴘᴘʟɪᴇᴅ ᴧυᴛᴏϻᴧᴛɪᴄᴧʟʟʏ.˼\n\n"

        f"˹⚡ ғᴧsᴛ • sϻᴧʀᴛ • sᴇᴄυʀᴇ˼\n\n"

        f"˹υsᴇ ᴛʜᴇ ʙυᴛᴛᴏɴs ʙᴇʟᴏᴡ ᴛᴏ ᴧᴅᴅ ϻᴇ "
        f"ᴛᴏ ʏᴏυʀ ɢʀᴏυᴘ ᴏʀ ᴇxᴘʟᴏʀᴇ ϻʏ ғᴇᴧᴛυʀᴇs.˼"
    )


# ============================================================
# /START
# ============================================================

@Client.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):

    bot_user = await client.get_me()

    # ========================================================
    # PRIVATE
    # ========================================================

    if message.chat.type == ChatType.PRIVATE:

        user_id = message.from_user.id

        if user_id not in USER_IDS_CACHE:

            try:
                await client.db.add_user(
                    user_id,
                    message.from_user.username,
                )

                USER_IDS_CACHE.add(user_id)

                logger.info(
                    f"Registered user via /start: {user_id}"
                )

            except Exception as e:

                logger.error(
                    f"Error registering user via start: {e}"
                )

        welcome_text = get_welcome_text(
            message.from_user.first_name
        )

        try:

            await message.reply_photo(
                photo=START_IMAGE,
                caption=welcome_text,
                reply_markup=get_start_keyboard(
                    bot_user.username
                ),
            )

        except Exception as e:

            logger.error(
                f"START_IMAGE error: {e}"
            )

            # Fallback
            await message.reply_text(
                welcome_text,
                reply_markup=get_start_keyboard(
                    bot_user.username
                ),
            )

        return

    # ========================================================
    # GROUP
    # ========================================================

    chat_id = message.chat.id

    if chat_id not in GROUP_IDS_CACHE:

        try:

            await client.db.add_group(
                chat_id,
                message.chat.title,
            )

            GROUP_IDS_CACHE.add(chat_id)

            logger.info(
                f"Registered group via /start: {chat_id}"
            )

        except Exception as e:

            logger.error(
                f"Error registering group via start: {e}"
            )

    keyboard = InlineKeyboardMarkup(
        [
            [
                premium_button(
                    "˹sᴛᴧʀᴛ ɪɴ ᴘʀɪᴠᴧᴛᴇ˼",
                    "add",
                    ButtonStyle.SUCCESS,
                    url=f"https://t.me/"
                        f"{bot_user.username}?start=start",
                )
            ]
        ]
    )

    await message.reply_text(
        f"{premium_emoji('home', '👋')} "
        f"<b>˹ᴡᴇʟᴄᴏϻᴇ!˼</b>\n\n"

        f"˹ᴘʟᴇᴧsᴇ ʀυɴ <code>/start</code> "
        f"ɪɴ ϻʏ ᴘʀɪᴠᴧᴛᴇ ᴍᴇssᴧɢᴇs ᴛᴏ sᴇᴇ "
        f"ϻʏ ɪɴsᴛʀυᴄᴛɪᴏɴs.˼",

        reply_markup=keyboard,
    )


# ============================================================
# BACK / START PAGE
# ============================================================

@Client.on_callback_query(
    filters.regex("^start_pm$")
)
async def start_pm_callback(
    client: Client,
    callback_query: CallbackQuery,
):

    bot_user = await client.get_me()

    await callback_query.answer()

    text = (
        f"{premium_emoji('home', '👋')} "
        f"<b>˹ʜᴇʟʟᴏ "
        f"{callback_query.from_user.first_name}!˼</b>\n\n"

        f"<b>˹ʙɪᴏ ʟɪɴᴋ ʀᴇsᴛʀɪᴄᴛᴏʀ˼</b>\n\n"

        f"˹ɪ ʜᴇʟᴘ ᴋᴇᴇᴘ ʏᴏυʀ ɢʀᴏυᴘs sᴧғᴇ "
        f"ʙʏ ᴄʜᴇᴄᴋɪɴɢ υsᴇʀ ʙɪᴏs ғᴏʀ "
        f"υɴᴡᴧɴᴛᴇᴅ ʟɪɴᴋs, sυsᴘɪᴄɪᴏυs "
        f"ᴡᴇʙsɪᴛᴇs ᴧɴᴅ ʙʟᴧᴄᴋʟɪsᴛᴇᴅ ᴡᴏʀᴅs.˼\n\n"

        f"˹⚙️ ᴠɪᴏʟᴧᴛɪᴏɴs ᴄᴧɴ ʙᴇ "
        f"ᴧυᴛᴏϻᴧᴛɪᴄᴧʟʟʏ ʀᴇϻᴏᴠᴇᴅ "
        f"ᴡɪᴛʜ ʏᴏυʀ ᴄᴏɴғɪɢυʀᴇᴅ ᴘυɴɪsʜϻᴇɴᴛ.˼\n\n"

        f"˹👆 υsᴇ ᴛʜᴇ ʜᴇʟᴘ ʙυᴛᴛᴏɴ "
        f"ᴛᴏ ᴇxᴘʟᴏʀᴇ ϻʏ ғᴇᴧᴛυʀᴇs.˼"
    )

    try:

        await callback_query.edit_message_caption(
            caption=text,
            reply_markup=get_start_keyboard(
                bot_user.username
            ),
        )

    except Exception:

        await callback_query.edit_message_text(
            text=text,
            reply_markup=get_start_keyboard(
                bot_user.username
            ),
        )


# ============================================================
# UPDATES
# ============================================================

@Client.on_callback_query(
    filters.regex("^updates_page$")
)
async def updates_callback(
    client: Client,
    callback_query: CallbackQuery,
):

    await callback_query.answer()

    text = (
        f"{premium_emoji('updates', '📢')} "
        f"<b>˹υᴘᴅᴧᴛᴇs˼</b>\n\n"

        f"{premium_emoji('source', '💡')} "
        f"˹ʙᴏᴛ υᴘᴅᴧᴛᴇs ᴧɴᴅ ᴧɴɴᴏυɴᴄᴇϻᴇɴᴛs "
        f"ᴡɪʟʟ ᴧᴘᴘᴇᴧʀ ʜᴇʀᴇ.˼\n\n"

        f"˹ᴄʜᴇᴄᴋ ʙᴧᴄᴋ ʜᴇʀᴇ ғᴏʀ ɴᴇᴡ "
        f"ғᴇᴧᴛυʀᴇs ᴧɴᴅ ɪϻᴘᴏʀᴛᴧɴᴛ ᴄʜᴧɴɢᴇs.˼"
    )

    try:

        await callback_query.edit_message_caption(
            caption=text,
            reply_markup=back_keyboard(),
        )

    except Exception:

        await callback_query.edit_message_text(
            text=text,
            reply_markup=back_keyboard(),
        )


# ============================================================
# USER GUIDE
# ============================================================

@Client.on_callback_query(
    filters.regex("^user_guide$")
)
async def user_guide_callback(
    client: Client,
    callback_query: CallbackQuery,
):

    await callback_query.answer()

    text = (
        f"{premium_emoji('language', '📚')} "
        f"<b>˹υsᴇʀ ɢυɪᴅᴇ˼</b>\n\n"

        f"{premium_emoji('add', '➕')} "
        f"˹𝟷. ᴧᴅᴅ ϻᴇ ᴛᴏ ʏᴏυʀ ɢʀᴏυᴘ "
        f"ᴧɴᴅ ɢɪᴠᴇ ᴛʜᴇ ʀᴇǫυɪʀᴇᴅ "
        f"ᴧᴅϻɪɴ ᴘᴇʀϻɪssɪᴏɴs.˼\n\n"

        f"{premium_emoji('admins', '👮')} "
        f"˹𝟸. ᴧᴘᴘʀᴏᴠᴇ ᴛʀυsᴛᴇᴅ υsᴇʀs "
        f"ᴜsɪɴɢ <code>/approve</code>.˼\n\n"

        f"{premium_emoji('auth', '🛡️')} "
        f"˹𝟹. ᴄᴏɴғɪɢυʀᴇ ϻᴏᴅᴇʀᴧᴛɪᴏɴ "
        f"ᴜsɪɴɢ <code>/config</code>.˼\n\n"

        f"{premium_emoji('help', '💡')} "
        f"˹𝟺. ᴜsᴇ <code>/help</code> "
        f"ғᴏʀ ᴛʜᴇ ᴄᴏϻᴘʟᴇᴛᴇ ɢυɪᴅᴇ.˼"
    )

    try:

        await callback_query.edit_message_caption(
            caption=text,
            reply_markup=back_keyboard(),
        )

    except Exception:

        await callback_query.edit_message_text(
            text=text,
            reply_markup=back_keyboard(),
        )


# ============================================================
# ABOUT BOT
# ============================================================

@Client.on_callback_query(
    filters.regex("^about_bot$")
)
async def about_bot_callback(
    client: Client,
    callback_query: CallbackQuery,
):

    await callback_query.answer()

    text = (
        f"{premium_emoji('source', '🛡️')} "
        f"<b>˹ʙɪᴏ ʟɪɴᴋ ʀᴇsᴛʀɪᴄᴛᴏʀ˼</b>\n\n"

        f"˹ʙɪᴏ ʟɪɴᴋ ʀᴇsᴛʀɪᴄᴛᴏʀ ɪs ᴧ "
        f"ᴛᴇʟᴇɢʀᴧϻ ɢʀᴏυᴘ sᴇᴄυʀɪᴛʏ ʙᴏᴛ "
        f"ᴛʜᴧᴛ ʜᴇʟᴘs ᴅᴇᴛᴇᴄᴛ sυsᴘɪᴄɪᴏυs "
        f"ʟɪɴᴋs, ʙʟᴧᴄᴋʟɪsᴛᴇᴅ ᴡᴏʀᴅs ᴧɴᴅ "
        f"υɴᴡᴧɴᴛᴇᴅ ᴡᴇʙsɪᴛᴇs ɪɴ υsᴇʀ ʙɪᴏs.˼\n\n"

        f"{premium_emoji('auth', '⚙️')} "
        f"˹ɪᴛ ᴄᴧɴ ᴧυᴛᴏϻᴧᴛɪᴄᴧʟʟʏ ʀᴇϻᴏᴠᴇ "
        f"ᴠɪᴏʟᴧᴛɪɴɢ ϻᴇssᴧɢᴇs ᴧɴᴅ ᴧᴘᴘʟʏ "
        f"ᴛʜᴇ ɢʀᴏυᴘ's ᴄᴏɴғɪɢυʀᴇᴅ "
        f"ᴘυɴɪsʜϻᴇɴᴛ.˼\n\n"

        f"{premium_emoji('help', '📚')} "
        f"˹ᴜsᴇ <code>/help</code> ᴛᴏ ᴇxᴘʟᴏʀᴇ "
        f"ᴛʜᴇ ᴄᴏϻᴘʟᴇᴛᴇ ᴄᴏϻϻᴧɴᴅ ɢυɪᴅᴇ.˼"
    )

    try:

        await callback_query.edit_message_caption(
            caption=text,
            reply_markup=back_keyboard(),
        )

    except Exception:

        await callback_query.edit_message_text(
            text=text,
            reply_markup=back_keyboard(),
        )
