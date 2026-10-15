import logging
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.exceptions import TelegramBadRequest

from src.services.weather_service import weather_service, get_nearest_region
from src.keyboards.weather import get_cities_keyboard
from src.keyboards.reply import get_main_keyboard, get_weather_location_keyboard
from src.database import get_user_weather_city, set_user_weather_city

logger = logging.getLogger(__name__)

router = Router(name="weather")

def format_weather_message(data: dict) -> str:
    loc = data["location_name"]
    temp = data["temp"]
    app_temp = data["apparent_temp"]
    humidity = data["humidity"]
    wind = data["wind_speed"]
    desc = data["desc"]
    emoji = data["emoji"]

    sign = "+" if temp and temp > 0 else ""
    app_sign = "+" if app_temp and app_temp > 0 else ""

    text = (
        f"🌤 <b>{loc} bo'yicha ob-havo ma'lumoti:</b>\n\n"
        f"{emoji} <b>Holat:</b> {desc}\n"
        f"🌡 <b>Harorat:</b> {sign}{temp}°C (hiss qilinishi: {app_sign}{app_temp}°C)\n"
        f"💧 <b>Namlik:</b> {humidity}%\n"
        f"💨 <b>Shamol tezligi:</b> {wind} m/s\n\n"
        f"📅 <b>Yaqin kunlar prognozi:</b>\n"
    )

    for item in data.get("forecast", [])[:3]:
        d_sign_max = "+" if item["max"] > 0 else ""
        d_sign_min = "+" if item["min"] > 0 else ""
        text += (
            f"• <b>{item['date']}</b>: {item['emoji']} "
            f"kunduzi {d_sign_max}{item['max']}°C, kechasi {d_sign_min}{item['min']}°C ({item['desc']})\n"
        )

    return text

@router.message(F.text.contains("Ob-havo"))
async def show_weather_menu(message: Message):
    user_id = message.from_user.id
    saved_city = get_user_weather_city(user_id)

    # Doimiy hudud ob-havosini avtomatik olamiz
    coords = await weather_service.get_coordinates_by_city(saved_city)
    weather_part = ""
    if coords:
        lat, lon, real_name, intl_name = coords
        data = await weather_service.get_weather(lat, lon, real_name, intl_name)
        if data:
            weather_part = f"{format_weather_message(data)}\n"

    text = (
        f"📌 <b>Sizning doimiy hududingiz: {saved_city}</b>\n\n"
        f"{weather_part}"
        "<i>Hududni o'zgartirish uchun pastdagi tugmalardan boshqa viloyatni tanlang yoki joylashuvingizni yuboring:</i>"
    )

    await message.answer("Joylashuvingizni yuborishingiz mumkin:", reply_markup=get_weather_location_keyboard())
    await message.answer(text, parse_mode="HTML", reply_markup=get_cities_keyboard())

@router.message(F.text == "🔙 Asosiy menyu")
async def back_to_main_menu(message: Message):
    await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=get_main_keyboard())

@router.message(F.location)
async def process_location_weather(message: Message):
    lat = message.location.latitude
    lon = message.location.longitude
    user_id = message.from_user.id

    status_msg = await message.answer("⏳ Hududingiz bo'yicha ob-havo aniqlanmoqda...")
    
    # Koordinataga eng yaqin viloyatni aniqlaymiz va doimiy qilib saqlaymiz
    nearest_region = get_nearest_region(lat, lon)
    set_user_weather_city(user_id, nearest_region)

    data = await weather_service.get_weather(lat, lon, f"Siz turgan joy ({nearest_region})")

    if not data:
        await status_msg.edit_text("⚠️ Ob-havo ma'lumotini olishda xatolik yuz berdi. Qayta urinib ko'ring.")
        return

    msg = (
        f"✅ <b>{nearest_region} sizning doimiy hududingiz sifatida saqlandi!</b>\n\n"
        f"{format_weather_message(data)}"
    )
    await status_msg.edit_text(msg, parse_mode="HTML")

@router.callback_query(F.data.startswith("weather:"))
async def process_city_weather_callback(callback: CallbackQuery):
    city_name = callback.data.split(":")[1]
    user_id = callback.from_user.id
    await callback.answer("Ob-havo yuklanmoqda...")

    coords = await weather_service.get_coordinates_by_city(city_name)
    if not coords:
        await callback.message.answer(f"⚠️ {city_name} koordinatalari topilmadi.")
        return

    lat, lon, real_name, intl_name = coords
    
    # Tanlangan hududni foydalanuvchining doimiy hududi sifatida saqlaymiz!
    set_user_weather_city(user_id, real_name)

    data = await weather_service.get_weather(lat, lon, real_name, intl_name)
    if not data:
        await callback.message.answer(f"⚠️ {real_name} bo'yicha ob-havo ma'lumotlarini yuklab bo'lmadi. Qayta urinib ko'ring.")
        return

    msg = (
        f"✅ <b>{real_name} sizning doimiy hududingiz sifatida saqlandi!</b>\n\n"
        f"{format_weather_message(data)}\n"
        "<i>Hududni o'zgartirish uchun boshqa viloyatni tanlashingiz mumkin:</i>"
    )
    try:
        await callback.message.edit_text(msg, parse_mode="HTML", reply_markup=get_cities_keyboard())
    except TelegramBadRequest:
        pass
    except Exception as e:
        logger.error(f"Xabarni tahrirlashda xatolik: {e}")
        await callback.message.answer(msg, parse_mode="HTML", reply_markup=get_cities_keyboard())
