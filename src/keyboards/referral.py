import urllib.parse
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_referral_keyboard(bot_username: str, user_id: int) -> InlineKeyboardMarkup:
    """Do'stlarga ulashish va statistika inline tugmalari"""
    ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
    share_text = (
        "🌟 Valyuta kurslari, aniq ob-havo va futbol natijalarini kuzatish uchun juda qulay universal bot!\n\n"
        "Sizga ham tavsiya qilaman, bepul ulaning: 👇"
    )
    encoded_text = urllib.parse.quote(share_text)
    encoded_url = urllib.parse.quote(ref_link)
    share_url = f"https://t.me/share/url?url={encoded_url}&text={encoded_text}"

    buttons = [
        [
            InlineKeyboardButton(text="📲 Do'stlarga ulashish", url=share_url)
        ],
        [
            InlineKeyboardButton(text="🏆 Top taklif qiluvchilar", callback_data="ref_leaderboard")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_leaderboard_back_keyboard() -> InlineKeyboardMarkup:
    """Reytingdan orqaga qaytish"""
    buttons = [
        [
            InlineKeyboardButton(text="◀️ Ortga", callback_data="ref_back")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
