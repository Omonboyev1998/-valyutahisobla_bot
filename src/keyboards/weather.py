from aiogram.types import InlineKeyboardMarkup
from src.keyboards.regions import get_regions_keyboard

def get_cities_keyboard() -> InlineKeyboardMarkup:
    """Viloyat markazlari inline tugmalari (barcha 14 ta hudud)"""
    return get_regions_keyboard(callback_prefix="weather:")
