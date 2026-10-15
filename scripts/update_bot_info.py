import asyncio
from aiogram import Bot
from aiogram.types import BotCommand
from src.config import BOT_TOKEN

async def update_bot_info():
    bot = Bot(token=BOT_TOKEN)
    me = await bot.get_me()
    print(f"Connected to bot: @{me.username} ({me.first_name})")

    # 1. Short description (shown on bot profile page / share link, max 120 chars)
    short_desc = "Valyuta kurslari, namoz vaqtlari, ob-havo va futbol natijalari bo'yicha qulay yordamchi bot."
    print(f"Setting short description ({len(short_desc)} chars)...")
    ok1 = await bot.set_my_short_description(short_description=short_desc)
    print(f"Short description status: {ok1}")

    # 2. Description (shown on 'What can this bot do?' screen before starting, max 512 chars)
    desc = (
        "Universal Yordamchi Botga xush kelibsiz!\n\n"
        "Ushbu bot sizga har kuni kerak bo'ladigan eng muhim ma'lumotlarni taqdim etadi:\n\n"
        "• Markaziy Bank rasmiy valyuta kurslari va tezkor hisoblagich\n"
        "• 5 mahal namoz vaqtlari, duolar va 15 daqiqa oldin eslatmalar\n"
        "• O'zbekiston viloyatlari bo'yicha aniq ob-havo ma'lumoti\n"
        "• Top futbol ligalari jadvallari va o'yin natijalari\n"
        "• Shaxsiy eslatmalar va do'stlarni taklif qilish\n\n"
        "Boshlash uchun pastdagi Start tugmasini bosing!"
    )
    print(f"Setting description ({len(desc)} chars)...")
    ok2 = await bot.set_my_description(description=desc)
    print(f"Description status: {ok2}")

    # 3. Bot commands
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="kurslar", description="Valyuta kurslari va hisoblagich"),
        BotCommand(command="namoz", description="Namoz vaqtlari va taqvim"),
        BotCommand(command="obhavo", description="Ob-havo ma'lumotlari"),
        BotCommand(command="futbol", description="Futbol jadvallari va natijalari"),
        BotCommand(command="ref", description="Do'stlarni taklif qilish"),
        BotCommand(command="help", description="Yordam va qo'llanma"),
        BotCommand(command="admin", description="Admin paneli"),
    ]
    print("Setting commands...")
    ok3 = await bot.set_my_commands(commands)
    print(f"Commands status: {ok3}")

    await bot.session.close()
    print("All bot profile details updated successfully!")

if __name__ == "__main__":
    asyncio.run(update_bot_info())
