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

def get_prayer_city_keyboard() -> InlineKeyboardMarkup:
    """Namoz vaqtlari uchun shahar tanlash"""
    buttons = [
        [
            InlineKeyboardButton(text="Toshkent", callback_data="set_pr_city:Toshkent"),
            InlineKeyboardButton(text="Samarqand", callback_data="set_pr_city:Samarqand")
        ],
        [
            InlineKeyboardButton(text="Buxoro", callback_data="set_pr_city:Buxoro"),
            InlineKeyboardButton(text="Andijon", callback_data="set_pr_city:Andijon")
        ],
        [
            InlineKeyboardButton(text="Farg'ona", callback_data="set_pr_city:Farg'ona"),
            InlineKeyboardButton(text="Namangan", callback_data="set_pr_city:Namangan")
        ],
        [
            InlineKeyboardButton(text="Qarshi", callback_data="set_pr_city:Qarshi"),
            InlineKeyboardButton(text="Termiz", callback_data="set_pr_city:Termiz")
        ],
        [
            InlineKeyboardButton(text="Urganch", callback_data="set_pr_city:Urganch"),
            InlineKeyboardButton(text="Nukus", callback_data="set_pr_city:Nukus")
        ],
        [
            InlineKeyboardButton(text="Navoiy", callback_data="set_pr_city:Navoiy"),
            InlineKeyboardButton(text="Jizzax", callback_data="set_pr_city:Jizzax")
        ],
        [
            InlineKeyboardButton(text="Guliston", callback_data="set_pr_city:Guliston")
        ],
        [
            InlineKeyboardButton(text="◀️ Ortga", callback_data="prayer:back")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_duas_back_keyboard() -> InlineKeyboardMarkup:
    """Duolardan orqaga qaytish"""
    buttons = [
        [
            InlineKeyboardButton(text="◀️ Namoz vaqtlariga qaytish", callback_data="prayer:back")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
