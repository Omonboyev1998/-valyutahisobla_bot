from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from src.database import get_referral_count, get_top_referrers
from src.keyboards.referral import get_referral_keyboard, get_leaderboard_back_keyboard

router = Router(name="referral")

async def build_referral_text(bot: Bot, user_id: int) -> str:
    me = await bot.get_me()
    count = get_referral_count(user_id)
    ref_link = f"https://t.me/{me.username}?start=ref_{user_id}"

    return (
        "🎁 <b>Do'stlarni taklif qilish va ulashish</b>\n\n"
        "Botdan do'stlaringiz ham foydalanishini istaysizmi? "
        "Unda o'zingizning maxsus havolangizni ular bilan ulashing!\n\n"
        f"🔗 <b>Sizning shaxsiy havolangiz:</b>\n"
        f"👉 <code>{ref_link}</code>\n\n"
        f"👥 <b>Siz taklif qilgan do'stlar soni:</b> <b>{count}</b> ta\n\n"
        "Quyidagi <b>'📲 Do'stlarga ulashish'</b> tugmasini bosib, xabarni bir zumda do'stlaringiz va guruhlaringizga yuborishingiz mumkin:"
    )

@router.message(F.text.contains("taklif"))
@router.message(Command("ref"))
async def show_referral_menu(message: Message, bot: Bot):
    user_id = message.from_user.id
    me = await bot.get_me()
    text = await build_referral_text(bot, user_id)
    await message.answer(text, parse_mode="HTML", reply_markup=get_referral_keyboard(me.username, user_id))

@router.callback_query(F.data == "ref_back")
async def back_to_ref_callback(callback: CallbackQuery, bot: Bot):
    user_id = callback.from_user.id
    me = await bot.get_me()
    text = await build_referral_text(bot, user_id)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_referral_keyboard(me.username, user_id))
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data == "ref_leaderboard")
async def show_leaderboard_callback(callback: CallbackQuery):
    top_users = get_top_referrers(10)

    text = "🏆 <b>Eng ko'p do'st taklif qilgan foydalanuvchilar (Top 10):</b>\n\n"
    if not top_users:
        text += "<i>Hozircha takliflar mavjud emas. Birinchi bo'lib do'stlaringizni taklif qiling!</i>"
    else:
        for idx, (name, count) in enumerate(top_users, 1):
            medal = "🥇" if idx == 1 else "🥈" if idx == 2 else "🥉" if idx == 3 else f"{idx}."
            text += f"{medal} <b>{name}</b> — <b>{count}</b> ta do'st\n"

    text += "\n<i>Siz ham do'stlaringizni taklif qilib, reytingda yuqori o'ringa ko'tariling! 🚀</i>"
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_leaderboard_back_keyboard())
    except Exception:
        pass
    await callback.answer()
