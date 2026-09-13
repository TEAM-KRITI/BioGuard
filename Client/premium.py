from pyrogram.types import InlineKeyboardButton

PREMIUM_EMOJIS = {
    "add": "6100125944381444896", "back": "6030657343744644592", "home": "5355051922862653659",
    "help": "5350396951407895212", "source": "5409186957676785646", "support": "5443038326535759644",
    "owner": "5217822164362739968", "queue": "5408843502027033965", "stats": "6100546468924364734",
    "admins": "5767288287001580715", "auth": "6021618194228187816", "confirm": "5463122435425448565",
    "cancel": "6041720006973067267", "copy": "5355051922862653659", "updates": "6271537028307881531",
    "replay": "6023773095284707791", "default": "5275969776668134187",
}

def premium_button(text, emoji_key="default", style=None, **kwargs):
    kwargs["icon_custom_emoji_id"] = PREMIUM_EMOJIS.get(emoji_key, PREMIUM_EMOJIS["default"])
    if style is not None:
        kwargs["style"] = style
    return InlineKeyboardButton(text=text, **kwargs)
