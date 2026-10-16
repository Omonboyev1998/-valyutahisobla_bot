from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from typing import Optional, List

UZB_REGION_LIST = [
    "Toshkent",
    "Samarqand",
    "Buxoro",
    "Andijon",
    "Farg'ona",
    "Namangan",
    "Qarshi",
    "Termiz",
    "Urganch",
    "Xiva",
    "Nukus",
    "Navoiy",
    "Jizzax",
    "Guliston"
]

def get_regions_keyboard(callback_prefix: str = "set_reg:", back_callback: Optional[str] = None) -> InlineKeyboardMarkup:
    """Barcha 14 ta hudud uchun ixcham 2 ustunli inline klaviatura"""
    buttons: List[List[InlineKeyboardButton]] = []
    
    # 2 tadan juftlab qatorlarga ajratamiz
    for i in range(0, len(UZB_REGION_LIST), 2):
        row = [
            InlineKeyboardButton(text=f"📍 {UZB_REGION_LIST[i]}", callback_data=f"{callback_prefix}{UZB_REGION_LIST[i]}")
        ]
        if i + 1 < len(UZB_REGION_LIST):
            row.append(
                InlineKeyboardButton(text=f"📍 {UZB_REGION_LIST[i+1]}", callback_data=f"{callback_prefix}{UZB_REGION_LIST[i+1]}")
            )
        buttons.append(row)

    if back_callback:
        buttons.append([
            InlineKeyboardButton(text="◀️ Ortga", callback_data=back_callback)
        ])

    return InlineKeyboardMarkup(inline_keyboard=buttons)
