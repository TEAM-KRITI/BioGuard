from pyrogram.types import InlineKeyboardButton

PREMIUM_EMOJIS = {
    "play": "5409025823388741707", "pause": "5408916593780470262", "replay": "6023773095284707791",
    "skip": "5215480011322042129", "stop": "6271674836628541366", "autoplay": "5260687681733533075",
    "autoplay_disable": "5408916593780470262", "autoplay_status": "5776182936638329359", "add": "6100125944381444896",
    "close": "5258389041006518073", "back": "6030657343744644592", "home": "5413694143601842851",
    "help": "5350396951407895212", "source": "5409186957676785646", "support": "5443038326535759644",
    "owner": "5217822164362739968", "language": "5260512129240276089", "queue": "5283202115047545146",
    "stats": "6100546468924364734", "admins": "5767288287001580715", "auth": "6021618194228187816",
    "blacklist": "5850346984501680054", "sudo": "6100514338274020922", "vclogger": "6030657343744644592",
    "ping": "5318840353510408444", "confirm": "5463122435425448565", "cancel": "6041720006973067267",
    "copy": "5355051922862653659", "youtube": "6172312314423808834", "updates": "6271537028307881531",
    "force_play": "6170455814810112778", "default": "5275969776668134187"
}

def premium_emoji(emoji_key="default", fallback="✨"):
    emoji_id = PREMIUM_EMOJIS.get(emoji_key, PREMIUM_EMOJIS["default"])
    return f"<tg-emoji emoji-id='{emoji_id}'>{fallback}</tg-emoji>"

def premium_button(text, emoji_key="default", style=None, **kwargs):
    kwargs["icon_custom_emoji_id"] = PREMIUM_EMOJIS.get(emoji_key, PREMIUM_EMOJIS["default"])
    if style is not None:
        kwargs["style"] = style
    return InlineKeyboardButton(text=text, **kwargs)
