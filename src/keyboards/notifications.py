from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Dict, Any

def get_notifications_settings_keyboard(settings: Dict[str, Any]) -> InlineKeyboardMarkup:
    """Eslatmalar bo'yicha interaktiv boshqaruv paneli"""
    is_sub = settings.get("is_subscribed", True)
    c_status = "✅" if settings.get("sub_currency", True) else "❌"
    w_status = "✅" if settings.get("sub_weather", True) else "❌"
    f_status = "✅" if settings.get("sub_football", True) else "❌"
    p_status = "✅" if settings.get("sub_prayer", True) else "❌"
    curr_time = settings.get("notify_time", "09:00")
    curr_city = settings.get("weather_city", "Toshkent")

    buttons = [
        [
            InlineKeyboardButton(text=f"🕌 Namoz: {p_status}", callback_data="notif_toggle:prayer"),
            InlineKeyboardButton(text=f"💵 Valyuta: {c_status}", callback_data="notif_toggle:currency")
        ],
        [
            InlineKeyboardButton(text=f"🌤 Ob-havo: {w_status}", callback_data="notif_toggle:weather"),
            InlineKeyboardButton(text=f"⚽️ Futbol: {f_status}", callback_data="notif_toggle:football")
        ],
        [
            InlineKeyboardButton(text=f"🏙 Shahar: {curr_city}", callback_data="notif_choose_city"),
            InlineKeyboardButton(text=f"⏰ Vaqt: {curr_time}", callback_data="notif_choose_time")
        ],
        [
            InlineKeyboardButton(text="🧪 Hoziroq sinab ko'rish (Test)", callback_data="notif_test")
        ],
        [
            InlineKeyboardButton(
                text="🔕 Hammasini to'xtatish" if is_sub else "🔔 Eslatmalarni qayta yoqish",
                callback_data="notif_toggle_all"
            )
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_time_selection_keyboard() -> InlineKeyboardMarkup:
    """Xabar vaqtini tanlash tugmalari"""
    buttons = [
        [
            InlineKeyboardButton(text="🌅 07:00", callback_data="set_time:07:00"),
            InlineKeyboardButton(text="🕗 08:00", callback_data="set_time:08:00"),
            InlineKeyboardButton(text="🕘 09:00", callback_data="set_time:09:00")
        ],
        [
            InlineKeyboardButton(text="🕙 10:00", callback_data="set_time:10:00"),
            InlineKeyboardButton(text="🕐 13:00", callback_data="set_time:13:00"),
            InlineKeyboardButton(text="🕕 18:00", callback_data="set_time:18:00")
        ],
        [
            InlineKeyboardButton(text="🕗 20:00", callback_data="set_time:20:00"),
            InlineKeyboardButton(text="🕙 22:00", callback_data="set_time:22:00")
        ],
        [
            InlineKeyboardButton(text="◀️ Ortga", callback_data="notif_back")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

from src.keyboards.regions import get_regions_keyboard

def get_city_selection_keyboard() -> InlineKeyboardMarkup:
    """Ob-havo va Namoz eslatmasi uchun shahar tanlash (barcha 14 ta hudud)"""
    return get_regions_keyboard(callback_prefix="set_city:", back_callback="notif_back")
