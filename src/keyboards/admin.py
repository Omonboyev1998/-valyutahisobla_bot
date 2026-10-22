from typing import List, Dict, Any, Set
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

def get_admin_main_keyboard() -> InlineKeyboardMarkup:
    """Admin boshqaruv paneli tugmalari"""
    buttons = [
        [
            InlineKeyboardButton(text="📊 To'liq Statistika", callback_data="admin:stats"),
            InlineKeyboardButton(text="📢 Xabar tarqatish", callback_data="admin:broadcast")
        ],
        [
            InlineKeyboardButton(text="📡 Kuzatiladigan guruhlar (Userbot)", callback_data="admin:userbot_chats")
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

def get_userbot_chats_menu_keyboard(auto_dm_enabled: bool = True) -> InlineKeyboardMarkup:
    """Userbot guruhlar boshqaruv menyusi"""
    dm_status = "✅ Yoqilgan" if auto_dm_enabled else "❌ O'chirilgan"
    buttons = [
        [
            InlineKeyboardButton(text="📋 Guruhlarni yoqish / o'chirish", callback_data="ub:dialogs:0")
        ],
        [
            InlineKeyboardButton(text="➕ Havola orqali guruhga qo'shilish", callback_data="ub:join_prompt")
        ],
        [
            InlineKeyboardButton(text="🔍 Guruh tarixini skanerlash", callback_data="ub:scan_menu:0")
        ],
        [
            InlineKeyboardButton(text=f"💬 Ustaga avto-xabar: {dm_status}", callback_data="ub:toggle_autodm")
        ],
        [
            InlineKeyboardButton(text="✏️ Avto-xabar matnini tahrirlash", callback_data="ub:edit_dm_template")
        ],
        [
            InlineKeyboardButton(text="◀️ Admin panelga qaytish", callback_data="admin:back")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_userbot_groups_toggle_keyboard(
    groups: List[Dict[str, Any]],
    active_chat_ids: Set[int],
    page: int = 0,
    page_size: int = 6
) -> InlineKeyboardMarkup:
    """Akkaunt a'zo bo'lgan guruhlarni sahifalab yoqish/o'chirish klaviaturasi"""
    total_pages = max(1, (len(groups) + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))
    start_idx = page * page_size
    current_page_groups = groups[start_idx:start_idx + page_size]

    buttons = []
    for g in current_page_groups:
        is_active = g["id"] in active_chat_ids
        icon = "✅" if is_active else "➕"
        status_text = f"{icon} {g['title'][:25]}"
        cb = f"ub:toggle:{g['id']}:{page}"
        buttons.append([InlineKeyboardButton(text=status_text, callback_data=cb)])

    # Pagination buttons
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"ub:dialogs:{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"ub:dialogs:{page + 1}"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([
        InlineKeyboardButton(text="◀️ Ortga", callback_data="admin:userbot_chats")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_userbot_scan_selection_keyboard(
    groups: List[Dict[str, Any]],
    page: int = 0,
    page_size: int = 6
) -> InlineKeyboardMarkup:
    """Tarixini skanerlash uchun guruh tanlash"""
    total_pages = max(1, (len(groups) + page_size - 1) // page_size)
    page = max(0, min(page, total_pages - 1))
    start_idx = page * page_size
    current_page_groups = groups[start_idx:start_idx + page_size]

    buttons = []
    for g in current_page_groups:
        title = f"🔍 {g['title'][:25]}"
        cb = f"ub:scan_pick:{g['id']}"
        buttons.append([InlineKeyboardButton(text=title, callback_data=cb)])

    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"ub:scan_menu:{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"📄 {page + 1}/{total_pages}", callback_data="noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"ub:scan_menu:{page + 1}"))
    if nav_row:
        buttons.append(nav_row)

    buttons.append([
        InlineKeyboardButton(text="◀️ Ortga", callback_data="admin:userbot_chats")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_scan_confirm_keyboard(chat_id: int) -> InlineKeyboardMarkup:
    """Nechta xabarni skanerlashni tanlash"""
    buttons = [
        [
            InlineKeyboardButton(text="⚡️ Oxirgi 30 ta xabar", callback_data=f"ub:do_scan:{chat_id}:30"),
            InlineKeyboardButton(text="⚡️ Oxirgi 50 ta xabar", callback_data=f"ub:do_scan:{chat_id}:50")
        ],
        [
            InlineKeyboardButton(text="🚀 Oxirgi 100 ta xabar", callback_data=f"ub:do_scan:{chat_id}:100")
        ],
        [
            InlineKeyboardButton(text="◀️ Bekor qilish", callback_data="ub:scan_menu:0")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_broadcast_confirm_keyboard(with_app_btn: bool = False) -> InlineKeyboardMarkup:
    """Xabar tarqatishni tasdiqlash tugmalari"""
    toggle_text = "📱 Mini App tugmasi: ✅ Qo'shilgan" if with_app_btn else "📱 Mini App tugmasi: ❌ Qo'shilmagan"
    buttons = [
        [
            InlineKeyboardButton(text=toggle_text, callback_data="broadcast:toggle_btn")
        ],
        [
            InlineKeyboardButton(text="🚀 Ha, barchaga yuborilsin", callback_data="broadcast:confirm"),
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
