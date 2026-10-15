from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from src.services.football_service import football_service, LEAGUES
from src.keyboards.football import (
    get_leagues_keyboard,
    get_league_actions_keyboard,
    get_football_back_keyboard
)

router = Router(name="football")

@router.message(Command("futbol"))
@router.message(F.text.contains("Futbol"))
async def show_football_menu(message: Message):
    text = (
        "⚽️ <b>Futbol olamiga xush kelibsiz!</b>\n\n"
        "Quyidagi mashhur chempionatlardan birini tanlang va "
        "turnir jadvali hamda o'yinlar natijalari/taqvimi bilan tanishing:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_leagues_keyboard())

@router.callback_query(F.data == "fb_leagues")
async def show_leagues_callback(callback: CallbackQuery):
    text = (
        "⚽️ <b>Top chempionatlar ro'yxati:</b>\n\n"
        "Kerakli chempionatni tanlang:"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_leagues_keyboard())
    await callback.answer()

@router.callback_query(F.data.startswith("fb_menu:"))
async def show_league_menu_callback(callback: CallbackQuery):
    league_code = callback.data.split(":")[1]
    info = LEAGUES.get(league_code, {})
    name = info.get("name", league_code)
    flag = info.get("flag", "⚽")

    text = (
        f"{flag} <b>{name} bo'limi</b>\n\n"
        "Kerakli ma'lumot turini tanlang:"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_league_actions_keyboard(league_code))
    await callback.answer()

@router.callback_query(F.data.startswith("fb_table:"))
async def show_table_callback(callback: CallbackQuery):
    league_code = callback.data.split(":")[1]
    await callback.answer("Turnir jadvali yuklanmoqda...")

    data = await football_service.get_standings(league_code)
    if not data or not data.get("table"):
        await callback.message.edit_text(
            "⚠️ Turnir jadvali ma'lumotlarini yuklab bo'lmadi.",
            reply_markup=get_football_back_keyboard(league_code)
        )
        return

    league_name = data["league"]
    flag = data["flag"]
    table = data["table"]

    text = f"🏆 <b>{flag} {league_name} — Turnir jadvali (Top 10):</b>\n\n"
    text += "<code>O'rin Jamoa           O'yin Ochko</code>\n"
    text += "───────────────────────────\n"

    for row in table:
        rank = f"{row['rank']}.".ljust(4)
        team = row['team'][:13].ljust(14)
        played = str(row['played']).center(5)
        points = str(row['points']).rjust(4)
        text += f"<code>{rank}{team}{played}{points}</code>\n"

    text += "\n<i>(To'liq jadval va ochkolar)</i>"

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_football_back_keyboard(league_code)
    )

@router.callback_query(F.data.startswith("fb_matches:"))
async def show_matches_callback(callback: CallbackQuery):
    league_code = callback.data.split(":")[1]
    await callback.answer("O'yinlar natijalari yuklanmoqda...")

    data = await football_service.get_matches(league_code)
    if not data or not data.get("matches"):
        await callback.message.edit_text(
            "⚠️ Hozirda ushbu liga bo'yicha o'yinlar jadvali topilmadi.",
            reply_markup=get_football_back_keyboard(league_code)
        )
        return

    league_name = data["league"]
    flag = data["flag"]
    matches = data["matches"]

    text = f"⚽️ <b>{flag} {league_name} — O'yinlar va natijalar:</b>\n\n"
    for item in matches:
        text += f"• {item['match']}\n   └ <i>Holati: {item['status']}</i>\n\n"

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_football_back_keyboard(league_code)
    )
