import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, Any
from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from src.database import get_users_for_time, set_subscription
from src.services.cbu_service import cbu_service
from src.services.weather_service import weather_service
from src.services.football_service import football_service

logger = logging.getLogger(__name__)

# O'zbekiston vaqti (UTC+5)
TASHKENT_TZ = timezone(timedelta(hours=5))

async def build_personalized_digest(settings: Dict[str, Any]) -> str:
    """Foydalanuvchi tanlagan sohalar bo'yicha shaxsiy xabarnoma tayyorlaydi"""
    sections = []
    
    # 1. Valyuta bo'limi
    if settings.get("sub_currency", True):
        popular = await cbu_service.get_popular_rates()
        if popular:
            lines = []
            for item in popular[:4]:  # USD, EUR, RUB, KZT
                trend = f"📈+{item['diff']}" if item['diff'] > 0 else (f"📉{item['diff']}" if item['diff'] < 0 else "➖0")
                lines.append(f"• <b>{item['ccy']}</b>: {item['rate']:,.2f} UZS ({trend})")
            sections.append(
                "💵 <b>Valyuta kurslari (CBU):</b>\n" + "\n".join(lines)
            )

    # 2. Ob-havo bo'limi
    if settings.get("sub_weather", True):
        city = settings.get("weather_city", "Toshkent")
        coords = await weather_service.get_coordinates_by_city(city)
        if coords:
            lat, lon, real_name, intl_name = coords
            w_data = await weather_service.get_weather(lat, lon, real_name, intl_name)
            if w_data:
                temp = w_data["temp"]
                sign = "+" if temp and temp > 0 else ""
                today_forecast = w_data.get("forecast", [{}])[0]
                max_t = today_forecast.get("max", temp)
                min_t = today_forecast.get("min", temp)
                sections.append(
                    f"🌤 <b>Bugungi ob-havo ({real_name}):</b>\n"
                    f"• {w_data['emoji']} {w_data['desc']}\n"
                    f"• Harorat: <b>{sign}{temp}°C</b> (kunduzi: +{max_t}°C, kechasi: {min_t}°C)\n"
                    f"• Shamol: {w_data['wind_speed']} m/s, Namlik: {w_data['humidity']}%"
                )

    # 3. Futbol bo'limi
    if settings.get("sub_football", True):
        matches_data = await football_service.get_matches("eng.1")
        if matches_data and matches_data.get("matches"):
            match_lines = []
            for m in matches_data["matches"][:3]:
                match_lines.append(f"• {m['match']} ({m['status']})")
            sections.append(
                "⚽️ <b>Futbol yangiliklari (APL):</b>\n" + "\n".join(match_lines)
            )

    if not sections:
        return "Sizda barcha eslatma sohalari o'chirilgan."

    header = "🌅 <b>Xayrli kun! Siz uchun kunlik sarhisob:</b>\n\n"
    footer = "\n\n<i>⚙️ Sozlamalarni menyudagi '🔔 Eslatmalar' orqali o'zgartirishingiz mumkin.</i>"
    return header + "\n\n".join(sections) + footer

async def morning_scheduler_task(bot: Bot):
    """Har daqiqada tekshirib, foydalanuvchi belgilagan vaqtda xabar yuboruvchi scheduler"""
    logger.info("Universal eslatmalar rejalashtiruvchisi (Scheduler) faollashtirildi.")
    last_processed_minute = ""

    while True:
        try:
            now = datetime.now(TASHKENT_TZ)
            current_minute = now.strftime("%H:%M")

            # Har bir daqiqada faqat 1 marta ishlaydi
            if current_minute != last_processed_minute:
                last_processed_minute = current_minute
                users_to_notify = get_users_for_time(current_minute)

                if users_to_notify:
                    logger.info(f"Soat {current_minute}: {len(users_to_notify)} ta foydalanuvchiga xabar yuborilmoqda.")
                    for u in users_to_notify:
                        uid = u["user_id"]
                        try:
                            msg_text = await build_personalized_digest(u)
                            await bot.send_message(chat_id=uid, text=msg_text, parse_mode="HTML")
                            await asyncio.sleep(0.04)  # Telegram rate limit
                        except TelegramForbiddenError:
                            logger.info(f"Foydalanuvchi {uid} botni bloklagan.")
                            set_subscription(uid, False)
                        except TelegramBadRequest as e:
                            logger.warning(f"Xabar yuborib bo'lmadi ({uid}): {e}")
                        except Exception as e:
                            logger.error(f"Eslatma yuborishda xatolik ({uid}): {e}")

            # Keyingi daqiqa boshlanishigacha kutamiz
            seconds_to_wait = 60 - now.second
            await asyncio.sleep(max(1, seconds_to_wait))

        except asyncio.CancelledError:
            logger.info("Scheduler to'xtatildi.")
            break
        except Exception as e:
            logger.error(f"Scheduler fon jarayonida xatolik: {e}")
            await asyncio.sleep(10)
