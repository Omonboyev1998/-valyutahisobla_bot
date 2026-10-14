import asyncio
import logging
import os
import sys
from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.types import BotCommand
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.client.session.aiohttp import AiohttpSession

from src.config import BOT_TOKEN
from src.handlers import start, rates, convert
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
        BotCommand(command="help", description="Yordam va qo'llanma"),
    ]
    await bot.set_my_commands(commands)

async def start_web_server():
    """Render va boshqa bepul serverlarda uxlab qolmaslik uchun yengil web-server"""
    port = int(os.getenv("PORT", 8000))
    app = create_web_app()
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
    logger.info("Valyuta bot ishga tushirilmoqda...")
    
    # Web-serverni dastlab ishga tushiramiz (cloud platformalarda port tekshiruvi o'tishi uchun)
    runner = await start_web_server()

    # Bot sessiyasini sozlash (timeout bilan)
    session = AiohttpSession(timeout=30)
    bot = Bot(
        token=BOT_TOKEN,
        session=session,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()

    dp.include_router(start.router)
    dp.include_router(rates.router)
    dp.include_router(convert.router)

    # Telegram API ga qayta ulanish mantiqi
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
            
    await runner.cleanup()
    await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi.")
