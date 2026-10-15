from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from src.services.cbu_service import cbu_service
from src.keyboards.inline import get_rates_keyboard

router = Router(name="rates")

FLAGS = {
    "USD": "🇺🇸",
    "EUR": "🇪🇺",
    "RUB": "🇷🇺",
    "KZT": "🇰🇿",
    "CNY": "🇨🇳",
    "TRY": "🇹🇷",
    "GBP": "🇬🇧",
    "AED": "🇦🇪",
    "JPY": "🇯🇵",
    "KRW": "🇰🇷",
    "CHF": "🇨🇭",
    "INR": "🇮🇳",
    "CAD": "🇨🇦",
}

def format_rate_line(item: dict) -> str:
    ccy = item["ccy"]
    flag = FLAGS.get(ccy, "🌐")
    nominal = int(item["nominal"]) if item["nominal"].is_integer() else item["nominal"]
    rate = item["rate"]
    diff = item["diff"]

    if diff > 0:
        trend = f"📈 +{diff:,.2f}"
    elif diff < 0:
        trend = f"📉 {diff:,.2f}"
    else:
        trend = "➖ 0.00"

    nominal_str = f"{nominal} " if nominal != 1 else ""
    return (
        f"{flag} <b>{nominal_str}{ccy}</b> ({item['name_uz']}):\n"
        f"   └ <b>{rate:,.2f}</b> UZS ({trend})\n"
    )

async def build_popular_rates_message() -> str:
    popular = await cbu_service.get_popular_rates()
    date_str = popular[0]["date"] if popular else ""
    
    text = f"📅 <b>Markaziy Bank rasmiy kurslari ({date_str}):</b>\n\n"
    for item in popular:
        text += format_rate_line(item)

    text += "\n💡 <i>Hisoblash uchun quyidagi tugmadan yoki to'g'ridan-to'g'ri (masalan: 100 USD) foydalaning.</i>"
    return text

@router.message(Command("kurslar"))
@router.message(F.text.in_(["💵 Valyuta kurslari", "💵 Bugungi kurslar", "📊 Ommabop valyutalar"]))
async def show_rates_message(message: Message):
    text = await build_popular_rates_message()
    await message.answer(text, parse_mode="HTML", reply_markup=get_rates_keyboard())

@router.callback_query(F.data == "refresh_rates")
async def refresh_rates_callback(callback: CallbackQuery):
    await cbu_service.get_all_rates(force_refresh=True)
    text = await build_popular_rates_message()
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_rates_keyboard())
        await callback.answer("Kurslar yangilandi! ✅")
    except Exception:
        await callback.answer("Kurslar allaqachon eng so'nggi holatda!")

@router.callback_query(F.data == "all_currencies")
async def all_currencies_callback(callback: CallbackQuery):
    all_rates = await cbu_service.get_all_rates()
    if not all_rates:
        await callback.answer("Ma'lumot topilmadi", show_alert=True)
        return

    text = "📋 <b>Barcha mavjud valyutalar:</b>\n\n"
    count = 0
    for ccy, item in all_rates.items():
        flag = FLAGS.get(ccy, "🌐")
        rate = item["rate"]
        nom = int(item["nominal"]) if item["nominal"].is_integer() else item["nominal"]
        nom_txt = f"{nom} " if nom != 1 else ""
        text += f"{flag} <b>{nom_txt}{ccy}</b>: {rate:,.2f} UZS\n"
        count += 1
        # Har 30 ta valyutani alohida xabar qilib yuborish (Telegram 4096 belgi limiti uchun)
        if count % 35 == 0:
            await callback.message.answer(text, parse_mode="HTML")
            text = ""

    if text:
        await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()
