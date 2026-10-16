from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from src.config import WEB_APP_URL

def get_main_keyboard() -> ReplyKeyboardMarkup:
    keyboard = [
        [
            KeyboardButton(text="📱 Mini Ilova (Grafiklar & Soat)", web_app=WebAppInfo(url=WEB_APP_URL))
        ],
        [
            KeyboardButton(text="💵 Valyuta kurslari"),
            KeyboardButton(text="🕌 Namoz vaqtlari")
        ],
        [
            KeyboardButton(text="🌤 Ob-havo"),
            KeyboardButton(text="⚽️ Futbol olami")
        ],
        [
            KeyboardButton(text="🛠 Maishiy xizmatlar (Ustalar)")
        ],
        [
            KeyboardButton(text="🎁 Do'stlarni taklif qilish"),
            KeyboardButton(text="🔔 Eslatmalar")
        ],
        [
            KeyboardButton(text="❓ Yordam")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)

def get_weather_location_keyboard() -> ReplyKeyboardMarkup:
    """Ob-havoda geolokatsiya yuborish uchun reply keyboard"""
    keyboard = [
        [
            KeyboardButton(text="📍 Mening joylashuvim", request_location=True)
        ],
        [
            KeyboardButton(text="🔙 Asosiy menyu")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True)
