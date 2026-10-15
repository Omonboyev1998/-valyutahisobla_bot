import asyncio
import logging
from datetime import datetime, timezone, timedelta
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from src.database import get_all_subscribed_users, set_subscription
from src.services.cbu_service import cbu_service
from src.handlers.rates import build_popular_rates_message

logger = logging.getLogger(__name__)

# O'zbekiston vaqti (UTC+5)
TASHKENT_TZ = timezone(timedelta(hours=5))
TARGET_HOUR = 9
TARGET_MINUTE = 0

async def send_morning_broadcast(bot: Bot):
    """Barcha obuna bo'lgan foydalanuvchilarga tonggi kurslarni yuboradi"""
    logger.info("Tonggi kurslar xabarnomasini yuborish boshlanmoqda...")
    # Kurslarni yangilaymiz
    await cbu_service.get_all_rates(force_refresh=True)
    rates_text = await build_popular_rates_message()
    
    message_text = (
        "🌅 <b>Xayrli tong! Kunlik valyuta kurslari:</b>\n\n"
        f"{rates_text}\n\n"
        "<i>⚙️ Kunlik eslatmalarni menyudagi '🔔 Eslatmalar' orqali boshqarishingiz mumkin.</i>"
    )

    user_ids = get_all_subscribed_users()
    logger.info(f"{len(user_ids)} ta foydalanuvchiga xabar yuboriladi.")

    sent_count = 0
    for uid in user_ids:
        try:
            await bot.send_message(chat_id=uid, text=message_text, parse_mode="HTML")
            sent_count += 1
            await asyncio.sleep(0.05)  # Telegram limitiga rioya qilish
        except TelegramForbiddenError:
            # Foydalanuvchi botni bloklagan bo'lsa, obunadan chiqaramiz
            logger.info(f"Foydalanuvchi {uid} botni bloklagan, obunadan chiqarildi.")
            set_subscription(uid, False)
        except TelegramBadRequest as e:
            logger.warning(f"Foydalanuvchi {uid} ga yuborib bo'lmadi: {e}")
        except Exception as e:
            logger.error(f"Xabar yuborishda kutilmagan xatolik ({uid}): {e}")

    logger.info(f"Tonggi xabarnoma yakunlandi. {sent_count}/{len(user_ids)} kishiga yuborildi.")

def get_seconds_until_next_run(hour: int = TARGET_HOUR, minute: int = TARGET_MINUTE) -> float:
    """Keyingi soat 09:00 gacha qolgan soniyani hisoblaydi"""
    now = datetime.now(TASHKENT_TZ)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if now >= target:
        # Bugungi vaqt o'tib ketgan bo'lsa, ertangi kunga o'tkazamiz
        target += timedelta(days=1)
    return (target - now).total_seconds()

async def morning_scheduler_task(bot: Bot):
    """Har kuni ertalab 09:00 da avtomatik ishga tushuvchi fon jarayoni"""
    logger.info("Kunlik tonggi eslatmalar rejalashtiruvchisi (Scheduler) faollashtirildi.")
    while True:
        try:
            seconds_to_wait = get_seconds_until_next_run()
            hours_left = seconds_to_wait / 3600
            logger.info(f"Keyingi tonggi eslatmagacha qolgan vaqt: {hours_left:.2f} soat ({int(seconds_to_wait)} soniya).")
            
            await asyncio.sleep(seconds_to_wait)
            await send_morning_broadcast(bot)
        except asyncio.CancelledError:
            logger.info("Scheduler to'xtatildi.")
            break
        except Exception as e:
            logger.error(f"Scheduler xatoligi: {e}. 60 soniyadan so'ng qayta tekshiriladi.")
            await asyncio.sleep(60)
