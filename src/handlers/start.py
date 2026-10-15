from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from src.keyboards.reply import get_main_keyboard
from src.database import add_user

router = Router(name="start")

HELP_TEXT = (
    "🌟 <b>Universal Yordamchi Botga xush kelibsiz!</b>\n\n"
    "Bu bot orqali quyidagi barcha foydali xizmatlardan bir joyda foydalanishingiz mumkin:\n\n"
    "📌 <b>Asosiy bo'limlar:</b>\n"
    "• 💵 <b>Valyuta kurslari</b> — Markaziy Bank rasmiy kurslari va aqlli kalkulyator.\n"
    "• 🌤 <b>Ob-havo</b> — Siz turgan joy yoki istalgan shahar bo'yicha aniq harorat va prognoz.\n"
    "• ⚽️ <b>Futbol olami</b> — APL, La Liga, Serie A va Chempionlar ligasi turnir jadvallari hamda o'yinlar natijalari.\n"
    "• 🔔 <b>Eslatmalar</b> — Har kuni ertalab 09:00 da kunlik muhim xabarlarni avtomatik olish.\n\n"
    "💡 <b>Tezkor hisoblash:</b>\n"
    "Shunchaki botga <code>100 USD</code>, <code>500000 som</code> yoki <code>50 EUR</code> deb yozsangiz ham hisoblab beradi!"
)

@router.message(CommandStart())
async def cmd_start(message: Message):
    # Foydalanuvchini bazaga qo'shamiz (kunlik eslatmalar uchun)
    user = message.from_user
    add_user(user.id, user.full_name or "Foydalanuvchi", user.username)

    name = user.full_name or "Foydalanuvchi"
    text = (
        f"Assalomu alaykum, <b>{name}</b>!\n\n"
        f"{HELP_TEXT}"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@router.message(Command("help"))
@router.message(F.text == "❓ Yordam")
async def cmd_help(message: Message):
    await message.answer(HELP_TEXT, parse_mode="HTML", reply_markup=get_main_keyboard())
