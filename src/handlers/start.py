from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from src.keyboards.reply import get_main_keyboard

router = Router(name="start")

HELP_TEXT = (
    "🇺🇿 <b>Valyuta Kurslari Botiga xush kelibsiz!</b>\n\n"
    "Bu bot orqali O'zbekiston Respublikasi Markaziy Bankining rasmiy "
    "valyuta kurslarini kuzatishingiz va tezkor hisob-kitob qilishingiz mumkin.\n\n"
    "📌 <b>Asosiy buyruqlar va imkoniyatlar:</b>\n"
    "• 💵 <b>Bugungi kurslar</b> — asosiy valyutalar (USD, EUR, RUB va h.k.) kursi.\n"
    "• 🔄 <b>Valyuta hisoblash</b> — interaktiv kalkulyator.\n"
    "• 📊 <b>Ommabop valyutalar</b> — kengaytirilgan jadval.\n\n"
    "💡 <b>Tezkor hisoblash:</b>\n"
    "Siz shunchaki istalgan summani yozib yuborishingiz mumkin:\n"
    " Masalan:\n"
    "  👉 <code>100 USD</code> yoki <code>100 dollar</code>\n"
    "  👉 <code>500000 UZS</code> yoki <code>500 000 so'm</code>\n"
    "  👉 <code>50 EUR</code> yoki <code>1000 RUB</code>\n\n"
    "Bot avtomatik tarzda hisoblab beradi! 🚀"
)

@router.message(CommandStart())
async def cmd_start(message: Message):
    name = message.from_user.full_name or "Foydalanuvchi"
    text = (
        f"Assalomu alaykum, <b>{name}</b>!\n\n"
        f"{HELP_TEXT}"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@router.message(Command("help"))
@router.message(F.text == "❓ Yordam")
async def cmd_help(message: Message):
    await message.answer(HELP_TEXT, parse_mode="HTML", reply_markup=get_main_keyboard())
