import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from src.services.prayer_service import prayer_service, SAHARLIK_DUO, IFTORLIK_DUO
from src.database import get_user_weather_city, set_user_weather_city, get_user_settings, toggle_user_topic
from src.keyboards.prayer import (
    get_prayer_keyboard,
    get_prayer_city_keyboard,
    get_duas_back_keyboard
)

logger = logging.getLogger(__name__)

router = Router(name="prayer")

def format_prayer_message(data: dict) -> str:
    city = data["city"]
    greg_date = data["gregorian_date"]
    hijri_date = data["hijri_date"]
    next_p = data.get("next_prayer", {})

    text = (
        f"🕌 <b>Namoz vaqtlari — {city}</b>\n"
        f"📍 <i>Doimiy belgilangan hududingiz</i>\n\n"
        f"📅 Sana: <b>{greg_date}</b> | Hijriy: <b>{hijri_date}</b>\n\n"
        f"⏳ <b>Keyingi namoz:</b> <b>{next_p.get('name')}</b> ({next_p.get('time')})\n"
        f"   └ <i>{next_p.get('remaining')} qoldi</i>\n\n"
        "────────────────────────\n"
        f"🌌 <b>Tong (Saharlik):</b>  <code>{data['fajr']}</code>\n"
        f"🌅 <b>Quyosh chiqishi:</b>  <code>{data['sunrise']}</code>\n"
        f"☀️ <b>Peshin:</b>           <code>{data['dhuhr']}</code>\n"
        f"⛅️ <b>Asr:</b>             <code>{data['asr']}</code>\n"
        f"🌇 <b>Shom (Iftorlik):</b>  <code>{data['maghrib']}</code>\n"
        f"🌙 <b>Xufton:</b>           <code>{data['isha']}</code>\n"
        "────────────────────────\n"
        "<i>Eslatma: Vaqtlar O'zbekiston Musulmonlari Idorasi va Hanafiy mazhabiga muvofiq hisoblangan.</i>"
    )
    return text

@router.message(F.text.contains("Namoz"))
@router.message(Command("namoz"))
async def show_prayer_times(message: Message):
    user_id = message.from_user.id
    city = get_user_weather_city(user_id)
    settings = get_user_settings(user_id)
    sub_alert = settings.get("sub_prayer", True)

    data = await prayer_service.get_prayer_times(city)
    if not data:
        await message.answer("⚠️ Namoz vaqtlarini yuklab bo'lmadi. Iltimos, qayta urinib ko'ring.")
        return

    msg = format_prayer_message(data)
    await message.answer(msg, parse_mode="HTML", reply_markup=get_prayer_keyboard(sub_alert))

@router.callback_query(F.data == "prayer:back")
@router.callback_query(F.data == "prayer:refresh")
async def refresh_prayer_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    city = get_user_weather_city(user_id)
    settings = get_user_settings(user_id)
    sub_alert = settings.get("sub_prayer", True)

    data = await prayer_service.get_prayer_times(city)
    if not data:
        await callback.answer("Vaqtlarni yuklab bo'lmadi", show_alert=True)
        return

    msg = format_prayer_message(data)
    try:
        await callback.message.edit_text(msg, parse_mode="HTML", reply_markup=get_prayer_keyboard(sub_alert))
    except TelegramBadRequest:
        pass
    await callback.answer("Namoz vaqtlari yangilandi! ✅")

@router.callback_query(F.data == "prayer:duas")
async def show_duas_callback(callback: CallbackQuery):
    duas_text = f"{SAHARLIK_DUO}\n\n────────────────────────\n\n{IFTORLIK_DUO}"
    try:
        await callback.message.edit_text(duas_text, parse_mode="HTML", reply_markup=get_duas_back_keyboard())
    except TelegramBadRequest:
        pass
    await callback.answer()

@router.callback_query(F.data == "prayer:toggle_alert")
async def toggle_prayer_alert_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    new_state = toggle_user_topic(user_id, "prayer")
    alert_text = "Namozdan 15 daqiqa oldin eslatma yoqildi! 🔔" if new_state else "Namoz eslatmalari o'chirildi! 🔕"

    city = get_user_weather_city(user_id)
    data = await prayer_service.get_prayer_times(city)
    if data:
        msg = format_prayer_message(data)
        try:
            await callback.message.edit_text(msg, parse_mode="HTML", reply_markup=get_prayer_keyboard(new_state))
        except TelegramBadRequest:
            pass

    await callback.answer(alert_text, show_alert=True)

@router.callback_query(F.data == "prayer:change_city")
async def change_city_callback(callback: CallbackQuery):
    text = (
        "📍 <b>Hududingizni tanlang:</b>\n\n"
        "O'zingiz yashaydigan viloyatni tanlang (u <b>Namoz vaqtlari</b> va <b>Ob-havo</b> uchun doimiy saqlanadi):"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_prayer_city_keyboard())
    except TelegramBadRequest:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("set_pr_city:"))
async def set_prayer_city_callback(callback: CallbackQuery):
    city = callback.data.split(":")[1]
    user_id = callback.from_user.id
    set_user_weather_city(user_id, city)

    settings = get_user_settings(user_id)
    sub_alert = settings.get("sub_prayer", True)

    data = await prayer_service.get_prayer_times(city)
    if not data:
        await callback.answer(f"{city} vaqtlari topilmadi", show_alert=True)
        return

    msg = format_prayer_message(data)
    try:
        await callback.message.edit_text(msg, parse_mode="HTML", reply_markup=get_prayer_keyboard(sub_alert))
    except TelegramBadRequest:
        pass
    await callback.answer(f"✅ {city} doimiy hudud qilib belgilandi! Namoz va Ob-havo shu hududga sozlandi.", show_alert=True)
