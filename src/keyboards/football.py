from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_leagues_keyboard() -> InlineKeyboardMarkup:
    """Chempionatlar ro'yxati inline tugmalari"""
    buttons = [
        [
            InlineKeyboardButton(text="🏴󠁧󠁢󠁥󠁮󠁧󠁿 APL (Angliya)", callback_data="fb_menu:eng.1"),
            InlineKeyboardButton(text="🇪🇸 La Liga (Ispaniya)", callback_data="fb_menu:esp.1")
        ],
        [
            InlineKeyboardButton(text="🇮🇹 Serie A (Italiya)", callback_data="fb_menu:ita.1"),
            InlineKeyboardButton(text="🇩🇪 Bundesliga (Germaniya)", callback_data="fb_menu:ger.1")
        ],
        [
            InlineKeyboardButton(text="🏆 Chempionlar Ligasi", callback_data="fb_menu:uefa.champions")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_league_actions_keyboard(league_code: str) -> InlineKeyboardMarkup:
    """Tanlangan liga uchun menyu"""
    buttons = [
        [
            InlineKeyboardButton(text="🏆 Turnir jadvali", callback_data=f"fb_table:{league_code}"),
            InlineKeyboardButton(text="⚽️ O'yinlar & Natijalar", callback_data=f"fb_matches:{league_code}")
        ],
        [
            InlineKeyboardButton(text="◀️ Boshqa chempionatlar", callback_data="fb_leagues")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_football_back_keyboard(league_code: str) -> InlineKeyboardMarkup:
    """Liganing asosiy bo'limiga qaytish"""
    buttons = [
        [
            InlineKeyboardButton(text="◀️ Ortga", callback_data=f"fb_menu:{league_code}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
