from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_converter_quick_keyboard() -> InlineKeyboardMarkup:
    """Tezkor konvertatsiya yo'nalishlari"""
    buttons = [
        [
            InlineKeyboardButton(text="🇺🇸 USD ➡️ 🇺🇿 UZS", callback_data="conv:USD:UZS"),
            InlineKeyboardButton(text="🇺🇿 UZS ➡️ 🇺🇸 USD", callback_data="conv:UZS:USD"),
        ],
        [
            InlineKeyboardButton(text="🇪🇺 EUR ➡️ 🇺🇿 UZS", callback_data="conv:EUR:UZS"),
            InlineKeyboardButton(text="🇺🇿 UZS ➡️ 🇪🇺 EUR", callback_data="conv:UZS:EUR"),
        ],
        [
            InlineKeyboardButton(text="🇷🇺 RUB ➡️ 🇺🇿 UZS", callback_data="conv:RUB:UZS"),
            InlineKeyboardButton(text="🇺🇿 UZS ➡️ 🇷🇺 RUB", callback_data="conv:UZS:RUB"),
        ],
        [
            InlineKeyboardButton(text="🇰🇿 KZT ➡️ 🇺🇿 UZS", callback_data="conv:KZT:UZS"),
            InlineKeyboardButton(text="🇨🇳 CNY ➡️ 🇺🇿 UZS", callback_data="conv:CNY:UZS"),
        ],
        [
            InlineKeyboardButton(text="🔄 Barcha valyutalar ro'yxati", callback_data="all_currencies")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_rates_keyboard() -> InlineKeyboardMarkup:
    """Kurslar yangilash tugmasi"""
    buttons = [
        [
            InlineKeyboardButton(text="🔄 Yangilash", callback_data="refresh_rates"),
            InlineKeyboardButton(text="🧮 Hisoblash", callback_data="open_calc")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    """Bekor qilish tugmasi"""
    return InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="❌ Bekor qilish", callback_data="cancel_action")]]
    )
