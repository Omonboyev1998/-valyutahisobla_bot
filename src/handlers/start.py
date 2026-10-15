from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command, CommandObject
from aiogram.types import Message
from src.keyboards.reply import get_main_keyboard
from src.database import add_user, get_referral_count

router = Router(name="start")

HELP_TEXT = (
    "🌟 <b>Universal Yordamchi Botga xush kelibsiz!</b>\n\n"
    "Bu bot orqali quyidagi barcha foydali xizmatlardan bir joyda foydalanishingiz mumkin:\n\n"
    "📌 <b>Asosiy bo'limlar:</b>\n"
    "• 💵 <b>Valyuta kurslari</b> — Markaziy Bank rasmiy kurslari va aqlli kalkulyator.\n"
    "• 🌤 <b>Ob-havo</b> — Siz turgan joy yoki istalgan shahar bo'yicha aniq harorat va prognoz.\n"
    "• ⚽️ <b>Futbol olami</b> — APL, La Liga, Serie A va Chempionlar ligasi turnir jadvallari hamda o'yinlar natijalari.\n"
    "• 🎁 <b>Do'stlarni taklif qilish</b> — O'z havolangizni do'stlarga ulashish va reytingda ko'tarilish.\n"
    "• 🔔 <b>Eslatmalar</b> — Har kuni ertalab 09:00 da kunlik muhim xabarlarni avtomatik olish.\n\n"
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

    is_new_referral = add_user(user.id, user.full_name or "Foydalanuvchi", user.username, referrer_id)

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
    text = (
        f"Assalomu alaykum, <b>{name}</b>!\n\n"
        f"{HELP_TEXT}"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())

@router.message(Command("help"))
@router.message(F.text == "❓ Yordam")
async def cmd_help(message: Message):
    await message.answer(HELP_TEXT, parse_mode="HTML", reply_markup=get_main_keyboard())
