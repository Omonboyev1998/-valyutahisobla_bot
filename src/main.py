import asyncio
import logging
import os
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand, MenuButtonWebApp, WebAppInfo
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

from src.config import BOT_TOKEN, WEB_APP_URL, TG_API_ID, TG_API_HASH, USERBOT_SESSION, TG_SESSION_STRING
from src.database import init_db
from src.handlers import start, rates, convert, notifications, admin, weather, football, referral, prayer, services, secretary, books
from src.services.scheduler import morning_scheduler_task
from src.web import create_web_app

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

async def set_commands(bot: Bot):
    commands = [
        BotCommand(command="start", description="Botni ishga tushirish"),
        BotCommand(command="app", description="Mini Ilova (Grafiklar & Soat)"),
        BotCommand(command="kurslar", description="Valyuta kurslari va hisoblagich"),
        BotCommand(command="namoz", description="Namoz vaqtlari va taqvim"),
        BotCommand(command="obhavo", description="Ob-havo ma'lumotlari"),
        BotCommand(command="futbol", description="Futbol jadvallari va natijalari"),
        BotCommand(command="xizmatlar", description="Maishiy xizmatlar va ustalar"),
        BotCommand(command="sekretar", description="Shaxsiy Kotib / Sekretar Rejim"),
        BotCommand(command="kitob", description="📚 Kitoblar Kutubxonasi"),
        BotCommand(command="ref", description="Do'stlarni taklif qilish"),
        BotCommand(command="help", description="Yordam va qo'llanma"),
        BotCommand(command="admin", description="Admin paneli (Faqat admin)"),
    ]
    try:
        await bot.set_my_commands(commands)
        await bot.set_chat_menu_button(
            menu_button=MenuButtonWebApp(text="📱 Mini App", web_app=WebAppInfo(url=WEB_APP_URL))
        )
    except Exception as e:
        logger.warning(f"Buyruqlarni yoki MenuButtonni o'rnatishda xatolik: {e}")

async def start_web_server(bot: Bot):
    """Render va boshqa bepul serverlarda uxlab qolmaslik uchun yengil web-server"""
    port = int(os.getenv("PORT", 8000))
    app = create_web_app(bot=bot)
    runner = web.AppRunner(app)
    await runner.setup()
    try:
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"Keep-alive web server muvaffaqiyatli ishga tushdi: http://0.0.0.0:{port}")
    except OSError:
        fallback_port = 8088
        logger.warning(f"Port {port} band. Zaxira port {fallback_port} ishlatilmoqda.")
        site = web.TCPSite(runner, "0.0.0.0", fallback_port)
        await site.start()
        logger.info(f"Keep-alive web server muvaffaqiyatli ishga tushdi: http://0.0.0.0:{fallback_port}")
    return runner

async def main():
    logger.info("Universal Bot ishga tushirilmoqda...")
    
    # 1. Bazani initsializatsiya qilish
    init_db()

    # 2. Bot sessiyasini sozlash
    session = AiohttpSession(timeout=30)
    bot = Bot(
        token=BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )

    # 3. Web-serverni ishga tushirish (Render port check va bot bildirishnomalari uchun)
    runner = await start_web_server(bot)
    dp = Dispatcher()

    # Routerlarni ulash
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(rates.router)
    dp.include_router(weather.router)
    dp.include_router(prayer.router)
    dp.include_router(football.router)
    dp.include_router(referral.router)
    dp.include_router(services.router)
    dp.include_router(books.router)
    dp.include_router(secretary.router)
    dp.include_router(notifications.router)
    dp.include_router(convert.router)

    # 4. Eslatmalar va namoz ogohlantirishlari (scheduler)
    scheduler_task = asyncio.create_task(morning_scheduler_task(bot))

    # 5. Userbot guruh kuzatuvchisini fon jarayoni sifatida ishga tushirish (agar avtorizatsiya qilingan bo'lsa)
    userbot_task = None
    session_file = f"{USERBOT_SESSION}.session"
    if TG_API_ID and TG_API_HASH and (TG_SESSION_STRING or os.path.exists(session_file)):
        try:
            from src.userbot.listener import start_userbot
            userbot_task = asyncio.create_task(start_userbot(scan_history=False))
            logger.info("Userbot (Guruh kuzatuvchi) fonda muvaffaqiyatli ishga tushirildi.")
        except Exception as e:
            logger.warning(f"Userbotni fonda ishga tushirishda xatolik: {e}")

    # Telegram API ga ulanish va polling
    while True:
        try:
            me = await bot.get_me()
            logger.info(f"Bot muvaffaqiyatli ulandi: @{me.username} ({me.full_name})")
            await set_commands(bot)
            await bot.delete_webhook(drop_pending_updates=True)
            logger.info("Polling boshlanmoqda...")
            await dp.start_polling(bot)
            break
        except Exception as e:
            logger.warning(f"Telegram API ga ulanishda vaqtinchalik xatolik: {e}. 5 soniyadan so'ng qayta uriniladi...")
            await asyncio.sleep(5)

    if userbot_task:
        userbot_task.cancel()
    scheduler_task.cancel()
    await runner.cleanup()
    await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
