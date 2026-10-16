from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from src.keyboards.reply import get_main_keyboard
from src.keyboards.regions import get_regions_keyboard
from src.database import add_user, get_referral_count, is_new_user, get_user_weather_city, set_user_weather_city
from src.config import WEB_APP_URL

router = Router(name="start")

HELP_TEXT = (
    "🌟 <b>Universal Yordamchi Botga xush kelibsiz!</b>\n\n"
    "Bu bot orqali quyidagi barcha foydali xizmatlardan bir joyda foydalanishingiz mumkin:\n\n"
    "📌 <b>Asosiy bo'limlar:</b>\n"
    "• 💵 <b>Valyuta kurslari</b> — Markaziy Bank rasmiy kurslari va aqlli kalkulyator.\n"
    "• 🕌 <b>Namoz vaqtlari</b> — 5 mahal namoz, saharlik/iftorlik duolari va 15 daqiqa oldin eslatmalar.\n"
    "• 🌤 <b>Ob-havo</b> — Siz turgan joy yoki istalgan shahar bo'yicha aniq harorat va prognoz.\n"
    "• ⚽️ <b>Futbol olami</b> — APL, La Liga, Serie A va Chempionlar ligasi turnir jadvallari hamda o'yinlar natijalari.\n"
    "• 🛠 <b>Maishiy xizmatlar (Ustalar)</b> — Santexnik, elektrchi, uy ta'miri, qo'y yungini olish va boshqa xizmatlarni topish yoki o'z e'loningizni joylashtirish.\n"
    "• 🎁 <b>Do'stlarni taklif qilish</b> — O'z havolangizni do'stlarga ulashish va reytingda ko'tarilish.\n"
    "• 🔔 <b>Eslatmalar</b> — O'zingiz belgilagan vaqtda shaxsiy xabarlarni avtomatik olish.\n\n"
    "💡 <b>Tezkor hisoblash:</b>\n"
    "Shunchaki botga <code>100 USD</code>, <code>500000 som</code> yoki <code>50 EUR</code> deb yozsangiz ham hisoblab beradi!"
)

@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, bot: Bot):
    user = message.from_user
    referrer_id = None
    if command.args and command.args.startswith("ref_"):
        try:
            referrer_id = int(command.args.replace("ref_", ""))
        except ValueError:
            referrer_id = None

    was_new = is_new_user(user.id)
    is_new_referral = add_user(user.id, user.full_name or "Foydalanuvchi", user.username, referrer_id)

    # Agar xizmatni ko'rish havolasi bilan kelgan bo'lsa (masalan: /start srv_5)
    if command.args and (command.args.startswith("srv_") or command.args.startswith("service_")):
        try:
            clean_arg = command.args.replace("service_", "").replace("srv_", "")
            s_id = int(clean_arg)
            from src.database import get_service_by_id
            from src.handlers.services import format_service_detail_text
            from src.keyboards.services import get_service_detail_keyboard
            service = get_service_by_id(s_id)
            if service:
                detail_text = format_service_detail_text(service)
                markup = get_service_detail_keyboard(service)
                photo_id = service.get("photo_id")
                if photo_id:
                    try:
                        await message.answer_photo(photo=photo_id, caption=detail_text, parse_mode="HTML", reply_markup=markup)
                        return
                    except Exception:
                        pass
                await message.answer(detail_text, parse_mode="HTML", reply_markup=markup)
                return
        except Exception:
            pass

    # Agar yangi do'st referal orqali kirgan bo'lsa, taklif qiluvchini tabriklaymiz
    if is_new_referral and referrer_id:
        try:
            ref_count = get_referral_count(referrer_id)
            await bot.send_message(
                chat_id=referrer_id,
                text=(
                    f"🎉 <b>Yangi do'st qo'shildi!</b>\n\n"
                    f"Sizning taklif havolangiz orqali <b>{user.full_name}</b> botga kirdi!\n\n"
                    f"👥 Jami taklif qilgan do'stlaringiz soni: <b>{ref_count}</b> ta."
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass

    name = user.full_name or "Foydalanuvchi"

    # Yangi foydalanuvchi birinchi marta kirganda o'z hududini tanlaydi
    if was_new:
        start_region_kb = get_regions_keyboard(callback_prefix="set_reg:")
        await message.answer(
            f"Assalomu alaykum, <b>{name}</b>!\n\n"
            f"🌟 <b>Universal Yordamchi Botga xush kelibsiz!</b>\n\n"
            f"📍 <b>Iltimos, o'zingiz yashaydigan viloyatni tanlang:</b>\n"
            f"<i>Bu hudud Namoz vaqtlari va Ob-havo ma'lumotlari uchun doimiy saqlanadi va botdan har foydalanganingizda o'zgarmasdan turadi.</i>",
            parse_mode="HTML",
            reply_markup=start_region_kb
        )
        return

    saved_city = get_user_weather_city(user.id)
    text = (
        f"Assalomu alaykum, <b>{name}</b>!\n\n"
        f"📍 <b>Sizning doimiy hududingiz:</b> <b>{saved_city}</b>\n"
        f"<i>(Namoz vaqtlari va Ob-havo ushbu hudud bo'yicha ko'rsatiladi)</i>\n\n"
        f"{HELP_TEXT}"
    )
    change_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"📍 Hududni o'zgartirish ({saved_city})", callback_data="start_change_city")]
    ])
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())
    await message.answer(
        f"📍 Joriy hududingiz: <b>{saved_city}</b>.\nBoshqa viloyatni tanlash uchun pastdagi tugmani bosing:",
        parse_mode="HTML",
        reply_markup=change_kb
    )

@router.message(Command("hudud"))
@router.message(Command("shahar"))
@router.callback_query(F.data == "start_change_city")
async def cmd_change_region(event: Message | CallbackQuery):
    text = (
        "📍 <b>O'z viloyatingizni tanlang:</b>\n\n"
        "Tanlangan viloyat <b>Namoz vaqtlari</b> va <b>Ob-havo</b> bo'limlari uchun doimiy saqlanadi va qayta o'zgarmaydi."
    )
    kb = get_regions_keyboard(callback_prefix="set_reg:")
    if isinstance(event, CallbackQuery):
        try:
            await event.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        except Exception:
            await event.message.answer(text, parse_mode="HTML", reply_markup=kb)
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data.startswith("set_reg:"))
async def process_global_region_callback(callback: CallbackQuery):
    city = callback.data.split(":")[1]
    user_id = callback.from_user.id
    set_user_weather_city(user_id, city)

    text = (
        f"✅ <b>Sizning doimiy hududingiz: {city}!</b>\n\n"
        f"🕌 <b>Namoz vaqtlari</b> va 🌤 <b>Ob-havo</b> bo'limlarida har doim <b>{city}</b> ma'lumotlari taqdim etiladi.\n"
        f"Ushbu hudud bazada doimiy saqlandi va qayta o'zgarmaydi."
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        pass
    await callback.message.answer(
        f"Botdan to'liq foydalanishingiz mumkin:\n\n{HELP_TEXT}",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )
    await callback.answer(f"{city} doimiy hududingiz qilib belgilandi! ✅", show_alert=True)

@router.message(Command("help"))
@router.message(F.text == "❓ Yordam")
async def cmd_help(message: Message):
    await message.answer(HELP_TEXT, parse_mode="HTML", reply_markup=get_main_keyboard())

@router.message(Command("app"))
@router.message(F.text.contains("Mini Ilova"))
async def cmd_webapp(message: Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📱 Mini Ilovani ochish", web_app=WebAppInfo(url=WEB_APP_URL))
        ]
    ])
    await message.answer(
        "📱 <b>Universal Telegram Mini App</b>\n\n"
        "Quyidagi tugmani bosing va botning zamonaviy interaktiv ilovasidan bahramand bo'ling:\n\n"
        "• 📈 <b>Valyuta kurslari:</b> 7 va 30 kunlik chiroyli grafiklar\n"
        "• 🕌 <b>Namoz vaqtlari:</b> Jonli orqaga sanash taymeri va soat\n"
        "• ⚽️ <b>Futbol:</b> Top ligalar jadvallari va klub logotiplari\n"
        "• 🌤 <b>Ob-havo:</b> Harorat va 3 kunlik prognoz kartalari",
        parse_mode="HTML",
        reply_markup=keyboard
    )
