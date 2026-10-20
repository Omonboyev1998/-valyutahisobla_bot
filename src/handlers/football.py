from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from src.services.football_service import football_service, LEAGUES
from src.database import get_football_streams
from src.keyboards.football import (
    get_leagues_keyboard,
    get_league_actions_keyboard,
    get_football_back_keyboard,
    get_streams_keyboard,
    get_tv_sub_keyboard
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

@router.message(Command("tv"))
@router.message(Command("translatsiya"))
@router.message(Command("stream"))
@router.callback_query(F.data == "fb_streams")
async def show_streams_callback(event: Message | CallbackQuery):
    text = (
        "📺 <b>Famelack Jonli TV Kanallar Katalogi (205 ta kanal)</b>\n\n"
        "Dunyoning istalgan joyidan turib telekanallarni uzluksiz tomosha qiling:\n\n"
        "🇺🇿 <b>O'zbekiston telekanallari (35 ta):</b>\n"
        "• ⚽️ Sport: <i>Futbol TV, Sport TV, UzReport TV</i>\n"
        "• 🎬 Kinolar: <i>Zo'r TV, Sevimli TV, Milliy TV, MY5, Kinoteatr, BIZ Cinema...</i>\n"
        "• 👶 Bolalar: <i>Bolajon, Aqlvoy, MiMi TV</i>\n"
        "• 🎵 Musiqa: <i>FTV, Navo, BIZ Music, Muz TV Uz...</i>\n"
        "• 📰 Yangiliklar: <i>O'zbekiston 24, O'zbekiston, Dunyo bo'ylab...</i>\n"
        "• 📍 Hududiy: <i>Toshkent TV, Yoshlar, Makon TV, MTRK...</i>\n\n"
        "⚽️ <b>Dunyo sport kanallari (170 ta):</b>\n"
        "• 🇪🇸 Ispaniya: <i>Real Madrid TV, Esport3, Teledeporte...</i>\n"
        "• 🇮🇹 Italiya: <i>Inter TV, Lazio Style, Sportitalia...</i>\n"
        "• 🇹🇷 Turkiya: <i>beIN Sports 1-5, A Spor, Eurosport...</i>\n"
        "• 🇷🇺 Rossiya: <i>Match! Ultra 4K, Sportivnyy, viju+...</i>\n"
        "• 🇺🇸 AQSH: <i>ESPN 1-8, CBS Sports Golazo, NBA TV, F1...</i>\n"
        "• 🇦🇷 Lotin Amerikasi: <i>TyC Sports, ESPN Premium...</i>\n"
        "• 🇬🇧 Jahon: <i>MUTV (Manchester United), QazSport...</i>\n\n"
        "<i>💡 Mini App ichidagi qulay pleyer orqali to'liq ekranda, qotmasdan tomosha qilishingiz mumkin!</i>"
    )
    kb = get_streams_keyboard()
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=kb)

@router.callback_query(F.data.startswith("tv_sub:"))
async def show_tv_sub_callback(callback: CallbackQuery):
    sub_type = callback.data.split(":")[1]
    if sub_type == "uz":
        text = (
            "🇺🇿 <b>O'zbekistonning Barcha Jonli Telekanallari (35 ta):</b>\n\n"
            "Quyidagi mashhur kanallarni to'g'ridan-to'g'ri ochishingiz yoki pastdagi "
            "<b>'📱 Mini Appda Jonli Pleyerni Ochish'</b> tugmasi orqali barcha 35 ta kanalni "
            "(Zo'r TV, Sevimli, Milliy, MY5, Kinoteatr, Bolajon, O'zbekiston 24 va h.k.) "
            "uzluksiz tomosha qilishingiz mumkin:"
        )
    else:
        text = (
            "⚽️ <b>Dunyo Davlatlarining Sport Telekanallari (170 ta):</b>\n\n"
            "Turkiya, Rossiya, Ispaniya, Italiya, AQSH, Angliya va boshqa barcha davlatlarning "
            "jonli sport kanallari jamlangan.\n\n"
            "<i>💡 Mini Appda kanallarni davlatlar bo'yicha saralash va tezkor qidiruv mavjud!</i>"
        )
    kb = get_tv_sub_keyboard(sub_type)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    await callback.answer()

