from typing import List, Optional, Dict, Any
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton

SERVICE_CATEGORIES = [
    "🔧 Santexnika va quvurlar",
    "⚡️ Elektr montaj va usta",
    "🔨 Uy ta'miri va qurilish",
    "🐑 Qo'y yungini olish & Chorva",
    "❄️ Konditsioner & Maishiy texnika",
    "🧹 Tozalash & Klining",
    "🚗 Avtoulov ta'miri va usta",
    "📦 Yuk tashish & Haydovchilik",
    "🌱 Bog'bonlik va payvandlash",
    "🗂 Boshqa maishiy xizmatlar"
]

SERVICE_REGIONS = [
    "Barcha hududlar",
    "Toshkent shahri",
    "Toshkent viloyati",
    "Samarqand",
    "Farg'ona",
    "Andijon",
    "Namangan",
    "Buxoro",
    "Qashqadaryo",
    "Surxondaryo",
    "Xorazm",
    "Navoiy",
    "Jizzax",
    "Sirdaryo",
    "Qoraqalpog'iston"
]

def get_services_menu_keyboard() -> InlineKeyboardMarkup:
    """Maishiy xizmatlar asosiy menyusi"""
    buttons = [
        [
            InlineKeyboardButton(text="📋 Barcha xizmatlarni ko'rish", callback_data="srv_browse")
        ],
        [
            InlineKeyboardButton(text="➕ O'z xizmatingizni qo'shish", callback_data="srv_add"),
            InlineKeyboardButton(text="👤 Mening e'lonlarim", callback_data="srv_my")
        ],
        [
            InlineKeyboardButton(text="🔍 Qidiruv", callback_data="srv_search"),
            InlineKeyboardButton(text="📍 Hududni tanlash", callback_data="srv_filter_region")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_categories_keyboard(prefix: str = "srv_cat") -> InlineKeyboardMarkup:
    """Kategoriyalar ro'yxati inline keyboardi"""
    buttons = []
    for i in range(0, len(SERVICE_CATEGORIES), 2):
        row = []
        c1 = SERVICE_CATEGORIES[i]
        row.append(InlineKeyboardButton(text=c1, callback_data=f"{prefix}:{i}"))
        if i + 1 < len(SERVICE_CATEGORIES):
            c2 = SERVICE_CATEGORIES[i + 1]
            row.append(InlineKeyboardButton(text=c2, callback_data=f"{prefix}:{i + 1}"))
        buttons.append(row)

    if prefix == "srv_cat":
        buttons.insert(0, [InlineKeyboardButton(text="🗂 Barcha toifalar", callback_data="srv_cat:all")])
        buttons.append([InlineKeyboardButton(text="🔙 Xizmatlar menyusi", callback_data="srv_main")])
    elif prefix == "srv_add_cat":
        buttons.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="srv_cancel")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_regions_keyboard(prefix: str = "srv_reg") -> InlineKeyboardMarkup:
    """Viloyatlar ro'yxati inline keyboardi"""
    buttons = []
    for i in range(0, len(SERVICE_REGIONS), 2):
        row = []
        r1 = SERVICE_REGIONS[i]
        row.append(InlineKeyboardButton(text=r1, callback_data=f"{prefix}:{i}"))
        if i + 1 < len(SERVICE_REGIONS):
            r2 = SERVICE_REGIONS[i + 1]
            row.append(InlineKeyboardButton(text=r2, callback_data=f"{prefix}:{i + 1}"))
        buttons.append(row)

    if prefix == "srv_reg" or prefix == "srv_filter_reg":
        buttons.append([InlineKeyboardButton(text="🔙 Orqaga", callback_data="srv_main")])
    elif prefix == "srv_add_reg":
        buttons.append([InlineKeyboardButton(text="❌ Bekor qilish", callback_data="srv_cancel")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_services_list_keyboard(
    services: List[Dict[str, Any]],
    page: int,
    total_pages: int,
    cat_code: str = "all",
    reg_code: str = "all",
    search_q: str = ""
) -> InlineKeyboardMarkup:
    """Ustalar ro'yxati (List view) uchun tugmalar"""
    buttons = []

    # 1. Har bir usta uchun alohida bosish tugmasi
    for idx, s in enumerate(services, 1):
        s_id = s["id"]
        master = s.get("master_name", "Usta")
        title = s.get("title", "")
        # Qisqartirilgan nom
        short_title = title[:24] + "..." if len(title) > 24 else title
        rating = s.get("rating", 5.0)
        btn_text = f"{idx}. 🛠 {master} (⭐ {rating}) — {short_title}"
        buttons.append([InlineKeyboardButton(text=btn_text, callback_data=f"srv_view:{s_id}:{cat_code}:{reg_code}:{page}")])

    # 2. Pagination (Oldingi / Keyingi)
    nav_row = []
    if page > 0:
        nav_row.append(InlineKeyboardButton(text="⬅️ Oldingi", callback_data=f"srv_page:{cat_code}:{reg_code}:{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"{page + 1}/{max(total_pages, 1)}", callback_data="srv_noop"))
    if page < total_pages - 1:
        nav_row.append(InlineKeyboardButton(text="Keyingi ➡️", callback_data=f"srv_page:{cat_code}:{reg_code}:{page + 1}"))
    if nav_row:
        buttons.append(nav_row)

    # 3. Filtrlash va menyu
    buttons.append([
        InlineKeyboardButton(text="🗂 Toifalar", callback_data="srv_browse"),
        InlineKeyboardButton(text="📍 Hududlar", callback_data="srv_filter_region")
    ])
    buttons.append([
        InlineKeyboardButton(text="🔙 Asosiy xizmatlar menyusi", callback_data="srv_main")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_service_detail_keyboard(
    service: dict,
    cat_code: str = "all",
    reg_code: str = "all",
    back_page: int = 0
) -> InlineKeyboardMarkup:
    """Usta kartochkasi to'liq ko'rinishi tugmalari"""
    buttons = []
    s_id = service.get("id")

    # 1. Aloqa tugmalari
    contact_row = []
    phone = service.get("phone", "").strip()
    if phone:
        contact_row.append(InlineKeyboardButton(text="📞 Telefon raqami", callback_data=f"srv_contact:{s_id}"))

    username = service.get("username")
    if username:
        clean_user = username.replace("@", "")
        contact_row.append(InlineKeyboardButton(text="💬 Telegram", url=f"https://t.me/{clean_user}"))
    elif phone:
        clean_p = phone.replace("+", "").replace(" ", "").replace("-", "")
        contact_row.append(InlineKeyboardButton(text="💬 Telegram", url=f"https://t.me/+{clean_p}"))

    if contact_row:
        buttons.append(contact_row)

    # 2. Buyurtma berish & Baholash
    action_row = [
        InlineKeyboardButton(text="📩 Buyurtma qoldirish", callback_data=f"srv_order:{s_id}"),
        InlineKeyboardButton(text="⭐ Baho berish", callback_data=f"srv_rate:{s_id}")
    ]
    buttons.append(action_row)

    # 3. Orqaga qaytish
    buttons.append([
        InlineKeyboardButton(text="⬅️ Ro'yxatga qaytish", callback_data=f"srv_page:{cat_code}:{reg_code}:{back_page}")
    ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_rating_keyboard(service_id: int) -> InlineKeyboardMarkup:
    """1 dan 5 gacha baholash tugmalari"""
    buttons = [
        [
            InlineKeyboardButton(text="⭐ 1", callback_data=f"srv_star:{service_id}:1"),
            InlineKeyboardButton(text="⭐ 2", callback_data=f"srv_star:{service_id}:2"),
            InlineKeyboardButton(text="⭐ 3", callback_data=f"srv_star:{service_id}:3"),
            InlineKeyboardButton(text="⭐ 4", callback_data=f"srv_star:{service_id}:4"),
            InlineKeyboardButton(text="⭐ 5", callback_data=f"srv_star:{service_id}:5")
        ],
        [
            InlineKeyboardButton(text="🔙 Bekor qilish", callback_data=f"srv_rate_cancel:{service_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_my_service_item_keyboard(service_id: int, is_active: int) -> InlineKeyboardMarkup:
    """Usta o'z e'lonini boshqarishi uchun keyboard"""
    status_text = "⏸ To'xtatish" if is_active == 1 else "▶️ Faollashtirish"
    buttons = [
        [
            InlineKeyboardButton(text=status_text, callback_data=f"srv_toggle:{service_id}"),
            InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"srv_del:{service_id}")
        ]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_phone_request_keyboard() -> ReplyKeyboardMarkup:
    """Telefon raqamini yuborish uchun reply keyboard"""
    keyboard = [
        [
            KeyboardButton(text="📞 Telefon raqamimni yuborish", request_contact=True)
        ],
        [
            KeyboardButton(text="❌ Bekor qilish")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)

def get_photo_request_keyboard() -> ReplyKeyboardMarkup:
    """Rasm yuklash yoki o'tkazib yuborish keyboardi"""
    keyboard = [
        [
            KeyboardButton(text="⏭ O'tkazib yuborish (Rasmsiz)")
        ],
        [
            KeyboardButton(text="❌ Bekor qilish")
        ]
    ]
    return ReplyKeyboardMarkup(keyboard=keyboard, resize_keyboard=True, one_time_keyboard=True)

def get_cancel_reply_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="❌ Bekor qilish")]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
