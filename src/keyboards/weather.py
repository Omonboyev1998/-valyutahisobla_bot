from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_cities_keyboard() -> InlineKeyboardMarkup:
    """Viloyat markazlari inline tugmalari"""
    buttons = [
        [
            InlineKeyboardButton(text="📍 Toshkent", callback_data="weather:Toshkent"),
            InlineKeyboardButton(text="📍 Samarqand", callback_data="weather:Samarqand")
        ],
        [
            InlineKeyboardButton(text="📍 Buxoro", callback_data="weather:Buxoro"),
            InlineKeyboardButton(text="📍 Andijon", callback_data="weather:Andijon")
        ],
        [
            InlineKeyboardButton(text="📍 Farg'ona", callback_data="weather:Farg'ona"),
            InlineKeyboardButton(text="📍 Namangan", callback_data="weather:Namangan")
        ],
        [
            InlineKeyboardButton(text="📍 Qarshi", callback_data="weather:Qarshi"),
            InlineKeyboardButton(text="📍 Termiz", callback_data="weather:Termiz")
        ],
        [
            InlineKeyboardButton(text="📍 Urganch", callback_data="weather:Urganch"),
            InlineKeyboardButton(text="📍 Nukus", callback_data="weather:Nukus")
        ],
        [
            InlineKeyboardButton(text="📍 Navoiy", callback_data="weather:Navoiy"),
            InlineKeyboardButton(text="📍 Jizzax", callback_data="weather:Jizzax")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
