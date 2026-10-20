from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from src.config import WEB_APP_URL
from src.services.secretary_service import SECRETARY_MODES

def get_secretary_main_keyboard(settings: dict) -> InlineKeyboardMarkup:
    """Kotib asosiy sozlamalar klaviaturasi"""
    is_enabled = settings.get("is_enabled", 0) == 1
    status_icon = "✅ YOQILGAN" if is_enabled else "❌ O'CHIRILGAN"
    current_mode = settings.get("mode", "busy")
    mode_title = SECRETARY_MODES.get(current_mode, {}).get("title", "⏳ Bandman")
    urgent_icon = "✅ Yoqilgan" if settings.get("urgent_alerts", 1) == 1 else "❌ O'chirilgan"

    buttons = [
        [
            InlineKeyboardButton(text=f"🔘 Holat: {status_icon}", callback_data="sec:toggle")
        ],
        [
            InlineKeyboardButton(text=f"🎭 Rejim: {mode_title}", callback_data="sec:modes")
        ],
        [
            InlineKeyboardButton(text=f"🚨 Shoshilinch xabar filtri: {urgent_icon}", callback_data="sec:toggle_urgent")
        ],
        [
            InlineKeyboardButton(text="✏️ Avto-javob matnini sozlash", callback_data="sec:set_text")
        ],
        [
            InlineKeyboardButton(text="📋 Kelgan xabarlar tarixi", callback_data="sec:logs"),
            InlineKeyboardButton(text="ℹ️ Bog'lash qo'llanmasi", callback_data="sec:guide")
        ],
        [
            InlineKeyboardButton(text="📱 Mini Appda Sozlash", web_app=WebAppInfo(url=WEB_APP_URL))
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_secretary_modes_keyboard(current_mode: str) -> InlineKeyboardMarkup:
    """Rejimni tanlash klaviaturasi"""
    buttons = []
    for mode_key, mode_val in SECRETARY_MODES.items():
        active = " ✅" if mode_key == current_mode else ""
        buttons.append([
            InlineKeyboardButton(
                text=f"{mode_val['title']}{active}",
                callback_data=f"sec_mode:{mode_key}"
            )
        ])
    buttons.append([
        InlineKeyboardButton(text="◀️ Ortga", callback_data="sec:back")
    ])
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_secretary_logs_keyboard() -> InlineKeyboardMarkup:
    """Xabarlar tarixi klaviaturasi"""
    buttons = [
        [
            InlineKeyboardButton(text="🔄 Yangilash", callback_data="sec:logs"),
            InlineKeyboardButton(text="🗑 Tarixni tozalash", callback_data="sec:clear_logs")
        ],
        [
            InlineKeyboardButton(text="◀️ Kotib menyusiga qaytish", callback_data="sec:back")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_secretary_back_keyboard() -> InlineKeyboardMarkup:
    """Ortga qaytish klaviaturasi"""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="◀️ Ortga", callback_data="sec:back")]
    ])
