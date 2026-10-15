from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_admin_main_keyboard() -> InlineKeyboardMarkup:
    """Admin boshqaruv paneli tugmalari"""
    buttons = [
        [
            InlineKeyboardButton(text="📊 To'liq Statistika", callback_data="admin:stats"),
            InlineKeyboardButton(text="📢 Xabar tarqatish", callback_data="admin:broadcast")
        ],
        [
            InlineKeyboardButton(text="📥 Baza eksport (CSV)", callback_data="admin:export"),
            InlineKeyboardButton(text="🔄 CBU kurslarini yangilash", callback_data="admin:refresh_cbu")
        ],
        [
            InlineKeyboardButton(text="❌ Yopish", callback_data="admin:close")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_broadcast_confirm_keyboard() -> InlineKeyboardMarkup:
    """Xabar tarqatishni tasdiqlash tugmalari"""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Ha, barchaga yuborilsin", callback_data="broadcast:confirm"),
            InlineKeyboardButton(text="❌ Bekor qilish", callback_data="broadcast:cancel")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_admin_back_keyboard() -> InlineKeyboardMarkup:
    """Admin panelga qaytish tugmasi"""
    buttons = [
        [
            InlineKeyboardButton(text="◀️ Admin panelga qaytish", callback_data="admin:back")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
