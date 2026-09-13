#This code was published by @MightyAyush on github.com/mightyayush
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from pyrogram.enums import ChatType, ButtonStyle
import logging
import config
from Client.cache import USER_IDS_CACHE, GROUP_IDS_CACHE
from Client.premium import premium_button

logger = logging.getLogger("BioLinkRemover.Start")

def get_start_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [
            premium_button("Add to Group", "add", ButtonStyle.SUCCESS, url=f"https://t.me/{bot_username}?startgroup=true")
        ],
        [
            premium_button("Help", "help", ButtonStyle.PRIMARY, callback_data="help_pm"),
            premium_button("Support", "support", ButtonStyle.PRIMARY, url="https://t.me/ayush_support")
        ]
    ])

@Client.on_message(filters.command("start"))
async def start_cmd(client: Client, message: Message):
    chat_type = message.chat.type
    bot_user = await client.get_me()

    if chat_type == ChatType.PRIVATE:
        user_id = message.from_user.id

        if user_id not in USER_IDS_CACHE:
            try:
                await client.db.add_user(user_id, message.from_user.username)
                USER_IDS_CACHE.add(user_id)
                logger.info(f"Registered user via /start: {user_id}")
            except Exception as e:
                logger.error(f"Error registering user in DB via start: {e}")

        welcome_text = (
            f"<tg-emoji emoji-id='5355051922862653659'>👋</tg-emoji> <b>Hello {message.from_user.first_name}!</b>\n\n"
            f"I am <b>BioLinkRemover</b>, a security bot designed to protect your groups "
            f"from spam by scanning user bios for links, dirty words, and suspicious websites.\n\n"
            f"If a user without approval sends a message, I will scan their profile's bio. "
            f"If they violate your rules, I will apply the configured punishment (mute, kick, ban) and delete the message.\n\n"
            f"Use the buttons below to add me to your group or explore my options."
        )
        await message.reply_text(welcome_text, reply_markup=get_start_keyboard(bot_user.username))

    else:
        chat_id = message.chat.id

        if chat_id not in GROUP_IDS_CACHE:
            try:
                await client.db.add_group(chat_id, message.chat.title)
                GROUP_IDS_CACHE.add(chat_id)
                logger.info(f"Registered group via /start: {chat_id}")
            except Exception as e:
                logger.error(f"Error registering group in DB via start: {e}")

        keyboard = InlineKeyboardMarkup([
            [
                premium_button("Start in Private", "add", ButtonStyle.SUCCESS, url=f"https://t.me/{bot_user.username}?start=start")
            ]
        ])

        await message.reply_text(
            f"<tg-emoji emoji-id='5355051922862653659'>👋</tg-emoji> <b>Welcome!</b>\n\n"
            f"Please run the `/start` command in my private messages to see my instructions, "
            f"or click the button below to start the chat.",
            reply_markup=keyboard
        )

@Client.on_callback_query(filters.regex("^start_pm$"))
async def start_pm_callback(client: Client, callback_query: CallbackQuery):
    bot_user = await client.get_me()
    welcome_text = (
        f"<tg-emoji emoji-id='5355051922862653659'>👋</tg-emoji> <b>Hello {callback_query.from_user.first_name}!</b>\n\n"
        f"I am <b>BioLinkRemover</b>, a security bot designed to protect your groups "
        f"from spam by scanning user bios for links, dirty words, and suspicious websites.\n\n"
        f"If a user without approval sends a message, I will scan their profile's bio. "
        f"If they violate your rules, I will apply the configured punishment (mute, kick, ban) and delete the message.\n\n"
        f"Use the buttons below to add me to your group or explore my options."
    )
    await callback_query.answer()
    await callback_query.edit_message_text(
        text=welcome_text,
        reply_markup=get_start_keyboard(bot_user.username)
    )

@Client.on_callback_query(filters.regex("^help_pm$"))
async def help_pm_callback(client: Client, callback_query: CallbackQuery):
    help_text = (
        "<b><tg-emoji emoji-id='5350396951407895212'>📚</tg-emoji> Help & Commands Directory</b>\n\n"
        "Here are the commands you can use with this bot:\n\n"
        "<b><tg-emoji emoji-id='5767288287001580715'>👮</tg-emoji> Group Admin Commands:</b>\n"
        "• <code>/approve</code> - Whitelist a user (reply to their message or pass user ID/username) to bypass bio scans.\n"
        "• <code>/unapprove</code> - Remove a user from the whitelist.\n"
        "• <code>/unapproveall</code> - Clear all whitelisted users in the group.\n"
        "• <code>/approved</code> - See the list of all approved users in the group.\n"
        "• <code>/config</code> - View or change the punishment mode (ban, mute, kick).\n"
        "• <code>/help</code> - Get this help menu.\n\n"
        "<b><tg-emoji emoji-id='5217822164362739968'>👑</tg-emoji> Owner Commands (Private Chat only):</b>\n"
        "• <code>/stats</code> - Show bot usage statistics.\n"
        "• <code>/gcast</code> - Broadcast a message to all registered groups.\n"
        "• <code>/ucast</code> - Broadcast a message to all users who started the bot."
    )
    keyboard = InlineKeyboardMarkup([
        [
            premium_button("Back", "back", ButtonStyle.PRIMARY, callback_data="start_pm")
        ]
    ])
    await callback_query.answer()
    await callback_query.edit_message_text(text=help_text, reply_markup=keyboard)
