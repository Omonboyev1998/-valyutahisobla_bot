from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from src.database import (
    get_user_settings,
    toggle_user_topic,
    set_user_notify_time,
    set_user_weather_city,
    set_subscription,
    add_user
)
from src.keyboards.notifications import (
    get_notifications_settings_keyboard,
    get_time_selection_keyboard,
    get_city_selection_keyboard
)
from src.services.scheduler import build_personalized_digest

router = Router(name="notifications")

def build_settings_text(settings: dict) -> str:
    is_sub = settings.get("is_subscribed", True)
    if not is_sub:
        status_text = "❌ <b>Barcha eslatmalar butunlay o'chirilgan.</b>"
    else:
        c_status = "✅ Yoqilgan" if settings.get("sub_currency", True) else "❌ O'chirilgan"
        w_status = "✅ Yoqilgan" if settings.get("sub_weather", True) else "❌ O'chirilgan"
        f_status = "✅ Yoqilgan" if settings.get("sub_football", True) else "❌ O'chirilgan"
        p_status = "✅ Yoqilgan" if settings.get("sub_prayer", True) else "❌ O'chirilgan"
        city = settings.get("weather_city", "Toshkent")
        curr_time = settings.get("notify_time", "09:00")

        status_text = (
            f"📌 <b>Yoqilgan sohalar:</b>\n"
            f"• 🕌 Namoz vaqtlari (15 daqiqa oldin): <b>{p_status}</b>\n"
            f"• 💵 Valyuta kurslari: <b>{c_status}</b>\n"
            f"• 🌤 Ob-havo ({city}): <b>{w_status}</b>\n"
            f"• ⚽️ Futbol yangiliklari: <b>{f_status}</b>\n\n"
            f"⏰ <b>Xabar kelish vaqti:</b> <b>{curr_time}</b> (Toshkent vaqti)\n\n"
            f"<i>Quyidagi tugmalar orqali sohalarni yoqib-o'chirishingiz, shahar va xabar vaqtini o'zgartirishingiz mumkin:</i>"
        )

    return (
        "🔔 <b>Shaxsiy Eslatmalar Boshqaruvi</b>\n\n"
        f"{status_text}"
    )

@router.message(F.text.contains("Eslatmalar"))
async def show_notifications_settings(message: Message):
    user = message.from_user
    add_user(user.id, user.full_name or "Foydalanuvchi", user.username)
    settings = get_user_settings(user.id)
    text = build_settings_text(settings)
    await message.answer(text, parse_mode="HTML", reply_markup=get_notifications_settings_keyboard(settings))

@router.callback_query(F.data == "notif_back")
async def back_to_settings_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    settings = get_user_settings(user_id)
    text = build_settings_text(settings)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_notifications_settings_keyboard(settings))
    except TelegramBadRequest:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("notif_toggle:"))
async def toggle_topic_callback(callback: CallbackQuery):
    topic = callback.data.split(":")[1]
    user_id = callback.from_user.id
    new_state = toggle_user_topic(user_id, topic)

    topic_names = {
        "currency": "Valyuta kurslari",
        "weather": "Ob-havo",
        "football": "Futbol",
        "prayer": "Namoz vaqtlari"
    }
    name = topic_names.get(topic, topic)
    status_str = "yoqildi ✅" if new_state else "o'chirildi ❌"
    
    settings = get_user_settings(user_id)
    text = build_settings_text(settings)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_notifications_settings_keyboard(settings))
    except TelegramBadRequest:
        pass
    await callback.answer(f"{name} {status_str}")

@router.callback_query(F.data == "notif_toggle_all")
async def toggle_all_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    settings = get_user_settings(user_id)
    new_status = not settings.get("is_subscribed", True)
    set_subscription(user_id, new_status)

    alert_text = "Eslatmalar qayta yoqildi! 🔔" if new_status else "Barcha eslatmalar to'xtatildi! 🔕"
    settings = get_user_settings(user_id)
    text = build_settings_text(settings)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_notifications_settings_keyboard(settings))
    except TelegramBadRequest:
        pass
    await callback.answer(alert_text, show_alert=True)

@router.callback_query(F.data == "notif_choose_time")
async def choose_time_callback(callback: CallbackQuery):
    text = (
        "⏰ <b>Xabar kelish vaqtini tanlang:</b>\n\n"
        "O'zingizga qulay vaqt tugmasini bosing:"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_time_selection_keyboard())
    except TelegramBadRequest:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("set_time:"))
async def set_time_callback(callback: CallbackQuery):
    selected_time = callback.data.split(":")[1] + ":" + callback.data.split(":")[2]
    user_id = callback.from_user.id
    set_user_notify_time(user_id, selected_time)

    await callback.answer(f"Vaqt {selected_time} ga belgilandi! ✅", show_alert=True)
    settings = get_user_settings(user_id)
    text = build_settings_text(settings)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_notifications_settings_keyboard(settings))
    except TelegramBadRequest:
        pass

@router.callback_query(F.data == "notif_choose_city")
async def choose_city_callback(callback: CallbackQuery):
    text = (
        "📍 <b>Hududingizni tanlang:</b>\n\n"
        "Tanlangan viloyat <b>Namoz vaqtlari</b> va <b>Ob-havo</b> uchun doimiy saqlanadi:"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_city_selection_keyboard())
    except TelegramBadRequest:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("set_city:"))
async def set_city_callback(callback: CallbackQuery):
    city = callback.data.split(":")[1]
    user_id = callback.from_user.id
    set_user_weather_city(user_id, city)

    await callback.answer(f"✅ {city} doimiy hudud qilib belgilandi! Namoz va Ob-havo shu hududga sozlandi.", show_alert=True)
    settings = get_user_settings(user_id)
    text = build_settings_text(settings)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_notifications_settings_keyboard(settings))
    except TelegramBadRequest:
        pass

@router.callback_query(F.data == "notif_test")
async def test_digest_callback(callback: CallbackQuery):
    await callback.answer("Sinov xabari tayyorlanmoqda...")
    user_id = callback.from_user.id
    settings = get_user_settings(user_id)
    digest_text = await build_personalized_digest(settings)
    test_msg = f"🧪 <b>[SINOV XABARI]</b>\n\n{digest_text}"
    await callback.message.answer(test_msg, parse_mode="HTML")
