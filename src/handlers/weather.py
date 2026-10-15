from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from src.services.weather_service import weather_service
from src.keyboards.weather import get_cities_keyboard
from src.keyboards.reply import get_main_keyboard, get_weather_location_keyboard

router = Router(name="weather")

def format_weather_message(data: dict) -> str:
    loc = data["location_name"]
    temp = data["temp"]
    app_temp = data["apparent_temp"]
    humidity = data["humidity"]
    wind = data["wind_speed"]
    desc = data["desc"]
    emoji = data["emoji"]

    sign = "+" if temp > 0 else ""
    app_sign = "+" if app_temp > 0 else ""

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
    text = (
        "🌤 <b>Ob-havo ma'lumotlari bo'limi</b>\n\n"
        "O'zingiz turgan joy ob-havosini bilish uchun pastdagi <b>'📍 Mening joylashuvim'</b> tugmasini bosing,\n"
        "yoki quyidagi shaharlardan birini tanlang:\n\n"
        "<i>(Shuningdek, istalgan shahar nomini ham yozib yuborishingiz mumkin, masalan: <code>Samarqand</code>)</i>"
    )
    # Joylashuv yuborish reply klaviaturasi
    await message.answer("Joylashuvingizni yuborishingiz mumkin:", reply_markup=get_weather_location_keyboard())
    # Shaharlar inline tugmalari
    await message.answer(text, parse_mode="HTML", reply_markup=get_cities_keyboard())

@router.message(F.text == "🔙 Asosiy menyu")
async def back_to_main_menu(message: Message):
    await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=get_main_keyboard())

@router.message(F.location)
async def process_location_weather(message: Message):
    lat = message.location.latitude
    lon = message.location.longitude

    status_msg = await message.answer("⏳ Hududingiz bo'yicha ob-havo aniqlanmoqda...")
    data = await weather_service.get_weather(lat, lon, "Siz turgan joy")

    if not data:
        await status_msg.edit_text("⚠️ Ob-havo ma'lumotini olishda xatolik yuz berdi. Qayta urinib ko'ring.")
        return

    msg = format_weather_message(data)
    await status_msg.edit_text(msg, parse_mode="HTML")

@router.callback_query(F.data.startswith("weather:"))
async def process_city_weather_callback(callback: CallbackQuery):
    city_name = callback.data.split(":")[1]
    coords = await weather_service.get_coordinates_by_city(city_name)
    if not coords:
        await callback.answer("Shahar topilmadi", show_alert=True)
        return

    lat, lon, real_name = coords
    data = await weather_service.get_weather(lat, lon, real_name)
    if not data:
        await callback.answer("Ob-havoni yuklab bo'lmadi", show_alert=True)
        return

    msg = format_weather_message(data)
    await callback.message.edit_text(msg, parse_mode="HTML", reply_markup=get_cities_keyboard())
    await callback.answer()
