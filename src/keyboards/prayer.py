from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_prayer_keyboard(sub_alert: bool) -> InlineKeyboardMarkup:
    """Namoz vaqtlari boshqaruv tugmalari"""
    alert_status = "✅ Yoqilgan" if sub_alert else "❌ O'chirilgan"
    buttons = [
        [
            InlineKeyboardButton(text="🤲 Saharlik va Iftorlik duolari", callback_data="prayer:duas")
        ],
        [
            InlineKeyboardButton(text=f"🔔 15 daqiqa oldin eslatma: {alert_status}", callback_data="prayer:toggle_alert")
        ],
        [
            InlineKeyboardButton(text="📍 Hududni o'zgartirish", callback_data="prayer:change_city"),
            InlineKeyboardButton(text="🔄 Yangilash", callback_data="prayer:refresh")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

from src.keyboards.regions import get_regions_keyboard

def get_prayer_city_keyboard() -> InlineKeyboardMarkup:
    """Namoz vaqtlari uchun shahar tanlash (barcha 14 ta hudud)"""
    return get_regions_keyboard(callback_prefix="set_pr_city:", back_callback="prayer:back")

def get_duas_back_keyboard() -> InlineKeyboardMarkup:
    """Duolardan orqaga qaytish"""
    buttons = [
        [
            InlineKeyboardButton(text="◀️ Namoz vaqtlariga qaytish", callback_data="prayer:back")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
