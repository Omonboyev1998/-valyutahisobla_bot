from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [
            KeyboardButton(text="💵 Bugungi kurslar"),
            KeyboardButton(text="📊 Ommabop valyutalar")
        ],
        [
            KeyboardButton(text="🔄 Valyuta hisoblash"),
            KeyboardButton(text="❓ Yordam")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
