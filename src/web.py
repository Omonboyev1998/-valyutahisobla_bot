import os
import time
import logging
import hmac
import hashlib
import urllib.parse
import json
from aiohttp import web
import asyncio
from typing import Optional, Any, Dict, List
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from src.config import ADMIN_ID, ADMIN_IDS, BOT_TOKEN
from src.services.cbu_service import cbu_service
from src.services.prayer_service import prayer_service
from src.services.football_service import football_service
from src.services.weather_service import weather_service
from src.services.secretary_service import SECRETARY_MODES
from src.database import (
    get_secretary_settings, update_secretary_settings, get_secretary_logs,
    get_secretary_schedules, add_secretary_schedule, delete_secretary_schedule,
    toggle_secretary_schedule, seed_default_secretary_schedules_if_empty,
    clear_all_secretary_schedules
)

logger = logging.getLogger(__name__)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
HTML_FILE = os.path.join(STATIC_DIR, "webapp.html")

# initData yangiligi (freshness) chegaralari. Maxfiy ma'lumot emas, oddiy sozlama.
INIT_DATA_MAX_AGE_SEC = int(os.getenv("INIT_DATA_MAX_AGE_SEC", "86400"))  # 24 soat
INIT_DATA_FUTURE_SKEW_SEC = int(os.getenv("INIT_DATA_FUTURE_SKEW_SEC", "300"))  # 5 daqiqa


# CORS siyosati: ochiq ma'lumot uchun wildcard, shaxsiy/yozuv javoblari uchun yo'q.
# Mini App sahifasi shu serverdan beriladi, shuning uchun shaxsiy so'rovlar same-origin.
PUBLIC_CORS = {"Access-Control-Allow-Origin": "*"}
PRIVATE_CORS = {"Vary": "Origin", "Cache-Control": "no-store"}


def _is_fresh_auth_date(raw_auth_date: Optional[str]) -> bool:
    """auth_date mavjud, raqamli va ruxsat etilgan vaqt oynasida ekanligini tekshirish"""
    if raw_auth_date is None:
        return False
    try:
        auth_ts = int(str(raw_auth_date).strip())
    except (TypeError, ValueError):
        return False
    age = time.time() - auth_ts
    if age > INIT_DATA_MAX_AGE_SEC:
        return False
    if age < -INIT_DATA_FUTURE_SKEW_SEC:
        return False
    return True


def validate_telegram_init_data(init_data: str) -> Optional[Dict[str, Any]]:
    """Telegram WebApp initData ni HMAC-SHA256 va auth_date yangiligi bilan tekshirish"""
    if not init_data or not BOT_TOKEN:
        return None
    try:
        parsed_data = dict(urllib.parse.parse_qsl(init_data, keep_blank_values=True))
        if "hash" not in parsed_data:
            return None
        received_hash = parsed_data.pop("hash")
        
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed_data.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
        
        if hmac.compare_digest(calculated_hash, received_hash):
            if not _is_fresh_auth_date(parsed_data.get("auth_date")):
                logger.warning("Telegram initData rad etildi: auth_date yaroqsiz yoki muddati o'tgan")
                return None
            if "user" in parsed_data:
                try:
                    parsed_data["user"] = json.loads(parsed_data["user"])
                except Exception:
                    pass
            return parsed_data
    except Exception as e:
        logger.warning(f"Telegram initData tekshirishda xatolik: {e}")
    return None

def get_auth_user(request: web.Request) -> Optional[Dict[str, Any]]:
    """So'rovdan tekshirilgan va xavfsiz Telegram foydalanuvchisini olish"""
    init_data = request.headers.get("X-Telegram-Init-Data") or request.query.get("init_data")
    if init_data:
        res = validate_telegram_init_data(init_data)
        if res and isinstance(res.get("user"), dict):
            return res["user"]
    return None

_rate_limit_cache: Dict[str, List[float]] = {}

def check_rate_limit(key: str, max_calls: int = 5, window_sec: int = 600) -> bool:
    """Belgilangan vaqt ichida so'rovlar sonini cheklash (Spam va suiste'moldan himoya)"""
    now = time.time()
    calls = _rate_limit_cache.get(key, [])
    valid_calls = [c for c in calls if now - c < window_sec]
    if len(valid_calls) >= max_calls:
        _rate_limit_cache[key] = valid_calls
        return False
    valid_calls.append(now)
    _rate_limit_cache[key] = valid_calls
    return True

async def ping_handler(request: web.Request) -> web.Response:
    """Serverni uxlab qolmasligi uchun (keep-alive / healthcheck) javob beruvchi endpoint"""
    return web.json_response({
        "status": "ok",
        "service": "valyutabot",
        "timestamp": time.time(),
        "message": "Universal Bot is alive and running 24/7!"
    })

async def webapp_html_handler(request: web.Request) -> web.Response:
    """Telegram Mini App sahifasini uzatuvchi handler"""
    try:
        with open(HTML_FILE, "r", encoding="utf-8") as f:
            html_content = f.read()
        return web.Response(
            text=html_content,
            content_type="text/html",
            charset="utf-8",
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "no-cache"
            }
        )
    except Exception as e:
        logger.error(f"HTML faylni o'qishda xatolik: {e}")
        return web.Response(text="Mini App fayli topilmadi", status=404)

async def api_rates_history(request: web.Request) -> web.Response:
    """Valyuta grafiklari uchun tarixiy ma'lumotlar"""
    ccy = request.query.get("ccy", "USD").upper()
    try:
        days = int(request.query.get("days", "7"))
    except ValueError:
        days = 7

    data = await cbu_service.get_currency_history(ccy=ccy, days=days)
    if data and "points" in data:
        data["rates"] = data["points"]
    return web.json_response(data, headers=PUBLIC_CORS)

async def api_rates_current(request: web.Request) -> web.Response:
    """Barcha valyutalar joriy kursi (ro'yxat va xarita formatida)"""
    rates_dict = await cbu_service.get_all_rates()
    rates_list = []
    for ccy_code, r in rates_dict.items():
        item = dict(r)
        item["Ccy"] = ccy_code
        item["Rate"] = str(r["rate"])
        rates_list.append(item)
    return web.json_response(rates_list, headers=PUBLIC_CORS)

async def api_prayer(request: web.Request) -> web.Response:
    """Namoz vaqtlari API"""
    city = request.query.get("city", "Toshkent")
    data = await prayer_service.get_prayer_times(city_name=city)
    if data:
        data = dict(data)
        data["times"] = {
            "tong": data.get("fajr"),
            "quyosh": data.get("sunrise"),
            "peshin": data.get("dhuhr"),
            "asr": data.get("asr"),
            "shom": data.get("maghrib"),
            "xufton": data.get("isha")
        }
    return web.json_response(data or {}, headers=PUBLIC_CORS)

async def api_football_standings(request: web.Request) -> web.Response:
    """Futbol turnir jadvali API"""
    league = request.query.get("league", "eng.1")
    try:
        limit = int(request.query.get("limit", "15"))
    except ValueError:
        limit = 15
    data = await football_service.get_standings(league_code=league, limit=limit)
    if data:
        data = dict(data)
        data["league_name"] = data.get("league", "Turnir")
        table = data.get("table", [])
        standings = []
        for row in table:
            r = dict(row)
            r["name"] = r.get("team", "")
            standings.append(r)
        data["standings"] = standings
    return web.json_response(data or {}, headers=PUBLIC_CORS)

async def api_football_matches(request: web.Request) -> web.Response:
    """Futbol o'yinlari API"""
    league = request.query.get("league", "eng.1")
    data = await football_service.get_matches(league_code=league)
    return web.json_response(data or {}, headers=PUBLIC_CORS)

from src.database import get_football_streams, add_football_stream, delete_football_stream

async def api_football_streams(request: web.Request) -> web.Response:
    """Futbol jonli translatsiyalari va real o'yinlar ro'yxati API"""
    try:
        # 1. Barcha real o'yinlar (UEFA Champions League, APL, La Liga, Serie A va b.)
        real_matches = await football_service.get_all_live_and_today_matches()

        # 2. Baza streams (Telekanallar va admin qo'shgan maxsus oqimlar)
        db_streams = get_football_streams()

        # Custom stream URL'larni real o'yinlar bilan birlashtiramiz
        custom_urls = {s["title"].lower(): s["stream_url"] for s in db_streams if s.get("stream_url")}
        for m in real_matches:
            t_lower = m["title"].lower()
            for c_title, c_url in custom_urls.items():
                if c_title in t_lower or t_lower in c_title:
                    m["stream_url"] = c_url
                    break

        # Barcha elementlar: real o'yinlar va telekanallar
        all_items = real_matches + [s for s in db_streams if not any(s["title"].lower() == m["title"].lower() for m in real_matches)]

        live_only = request.query.get("live_only", "0") == "1"
        if live_only:
            all_items = [s for s in all_items if s.get("is_live") == 1]

        return web.json_response(all_items, headers=PUBLIC_CORS)
    except Exception as e:
        logger.error(f"Translatsiyalarni olishda xatolik: {e}")
        return web.json_response([], headers=PUBLIC_CORS)

async def api_tv_channels(request: web.Request) -> web.Response:
    """Famelack barcha telekanallar (O'zbekiston + Dunyo sport) katalogi API"""
    try:
        json_path = os.path.join(STATIC_DIR, "tv_channels.json")
        if not os.path.exists(json_path):
            json_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "tv_channels.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return web.json_response(data, headers=PUBLIC_CORS)
    except Exception as e:
        logger.error(f"Telekanallar JSON faylini o'qishda xatolik: {e}")
    return web.json_response({"uz_channels": [], "sports_channels": []}, headers=PUBLIC_CORS)

async def api_add_football_stream(request: web.Request) -> web.Response:
    """Yangi translatsiya qo'shish API (Faqat Administrator uchun)"""
    auth_user = get_auth_user(request)
    if not auth_user or int(auth_user.get("id", 0)) not in ADMIN_IDS:
        return web.json_response({"success": False, "error": "Ruxsat etilmagan: faqat administratorlar uchun"}, status=403, headers=PRIVATE_CORS)

    try:
        data = await request.json()
        title = data.get("title", "").strip()
        stream_url = data.get("stream_url", "").strip()
        if not title or not stream_url:
            return web.json_response({"success": False, "error": "Sarlavha va stream havolasi majburiy!"}, status=400, headers=PRIVATE_CORS)
        
        league = data.get("league", "APL")
        channel_name = data.get("channel_name", "Sport TV")
        match_time = data.get("match_time", "🔴 Jonli efir")
        is_live = int(data.get("is_live", 1))
        home_team = data.get("home_team", "")
        away_team = data.get("away_team", "")
        home_logo = data.get("home_logo", "")
        away_logo = data.get("away_logo", "")
        score = data.get("score", "vs")

        s_id = add_football_stream(
            title=title,
            stream_url=stream_url,
            league=league,
            channel_name=channel_name,
            match_time=match_time,
            is_live=is_live,
            home_team=home_team,
            away_team=away_team,
            home_logo=home_logo,
            away_logo=away_logo,
            score=score
        )
        return web.json_response({"success": True, "id": s_id}, headers=PRIVATE_CORS)
    except Exception as e:
        logger.error(f"Translatsiya qo'shishda xatolik: {e}")
        return web.json_response({"success": False, "error": "Translatsiyani saqlashda xatolik yuz berdi"}, status=500, headers=PRIVATE_CORS)

async def api_delete_football_stream(request: web.Request) -> web.Response:
    """Translatsiyani o'chirish API (Faqat Administrator uchun)"""
    auth_user = get_auth_user(request)
    if not auth_user or int(auth_user.get("id", 0)) not in ADMIN_IDS:
        return web.json_response({"success": False, "error": "Ruxsat etilmagan: faqat administratorlar uchun"}, status=403, headers=PRIVATE_CORS)

    try:
        s_id = request.match_info.get("id")
        if s_id:
            delete_football_stream(int(s_id))
            return web.json_response({"success": True}, headers=PRIVATE_CORS)
    except Exception as e:
        logger.error(f"Translatsiyani o'chirishda xatolik: {e}")
    return web.json_response({"success": False, "error": "O'chirishda xatolik yuz berdi"}, status=400, headers=PRIVATE_CORS)

async def api_weather(request: web.Request) -> web.Response:
    """Ob-havo API"""
    city = request.query.get("city", "Toshkent")
    coords = await weather_service.get_coordinates_by_city(city)
    if coords:
        lat, lon, real_name, intl_name = coords
        data = await weather_service.get_weather(lat, lon, real_name, intl_name)
        if data:
            return web.json_response(data, headers=PUBLIC_CORS)
    return web.json_response({"error": "Ob-havo ma'lumoti topilmadi"}, status=404, headers=PUBLIC_CORS)

from src.database import get_services, count_services, get_service_by_id

async def api_services(request: web.Request) -> web.Response:
    """Maishiy xizmatlar va ustalar ro'yxati API"""
    category = request.query.get("category", "")
    region = request.query.get("region", "")
    search = request.query.get("search", "")
    try:
        limit = int(request.query.get("limit", "20"))
    except ValueError:
        limit = 20
    try:
        offset = int(request.query.get("offset", "0"))
    except ValueError:
        offset = 0

    services = get_services(
        category=category if category and category != "Barchasi" else None,
        region=region if region and region != "Barcha hududlar" else None,
        search_query=search if search else None,
        limit=limit,
        offset=offset
    )
    total = count_services(
        category=category if category and category != "Barchasi" else None,
        region=region if region and region != "Barcha hududlar" else None,
        search_query=search if search else None
    )
    return web.json_response({
        "services": services,
        "total": total
    }, headers=PUBLIC_CORS)

from src.database import get_services, count_services, get_service_by_id, add_service

async def api_add_service(request: web.Request) -> web.Response:
    """Mini App orqali to'g'ridan-to'g'ri yangi xizmat qo'shish API (Spamdan himoyalangan)"""
    client_ip = request.remote or "unknown"
    if not check_rate_limit(f"srv_add:{client_ip}", max_calls=4, window_sec=600):
        return web.json_response({
            "success": False,
            "error": "Juda ko'p so'rov yuborildi. Iltimos, 10 daqiqadan so'ng qayta urinib ko'ring."
        }, status=429, headers=PRIVATE_CORS)

    # E'lon joylash uchun tekshirilgan Telegram shaxsi majburiy; body'dagi user_id'ga ishonilmaydi.
    auth_user = get_auth_user(request)
    if not auth_user or not auth_user.get("id"):
        return web.json_response({
            "success": False,
            "error": "Avtorizatsiyadan o'tilmagan. Iltimos, ilovani Telegram orqali oching."
        }, status=401, headers=PRIVATE_CORS)
    user_id = int(auth_user["id"])

    try:
        data = await request.json()
        title = (data.get("title") or "").strip()
        master_name = (data.get("master_name") or "Usta").strip()
        phone = (data.get("phone") or "").strip()
        category = (data.get("category") or "Usta / Ta'mirlash").strip()
        region = (data.get("region") or "Barcha hududlar").strip()
        price = (data.get("price") or "Kelishilgan holda").strip()
        description = (data.get("description") or "").strip()
        username = (data.get("username") or "").replace("@", "").strip()

        if not title or not phone:
            return web.json_response({
                "success": False,
                "error": "Sarlavha va telefon raqami kiritilishi shart!"
            }, status=400, headers=PRIVATE_CORS)

        service_id = add_service(
            user_id=user_id,
            master_name=master_name,
            phone=phone,
            username=username,
            category=category,
            title=title,
            description=description,
            region=region,
            price=price,
            photo_id=None
        )

        # Adminga Telegram orqali xabarnoma yuborish (moderatsiya uchun)
        bot = request.app.get("bot")
        if bot and ADMIN_ID:
            try:
                admin_text = (
                    "🆕 <b>Yangi e'lon qo'shildi (Mini App orqali)!</b>\n\n"
                    f"👤 <b>Usta:</b> {master_name}\n"
                    f"📌 <b>Sarlavha:</b> {title}\n"
                    f"🛠 <b>Toifa:</b> {category}\n"
                    f"📍 <b>Hudud:</b> {region}\n"
                    f"📞 <b>Telefon:</b> {phone}\n"
                    f"💰 <b>Narx:</b> {price}\n"
                    + (f"💬 <b>Telegram:</b> @{username}\n" if username else "")
                    + (f"📝 <b>Tavsif:</b> {description}\n" if description else "")
                )
                markup = InlineKeyboardMarkup(inline_keyboard=[
                    [
                        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"admin_srv_ok:{service_id}"),
                        InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"admin_srv_del:{service_id}")
                    ],
                    [
                        InlineKeyboardButton(text="👁 Batafsil ko'rish", callback_data=f"srv_view:{service_id}:all:all:0")
                    ]
                ])
                asyncio.create_task(bot.send_message(
                    chat_id=ADMIN_ID,
                    text=admin_text,
                    parse_mode="HTML",
                    reply_markup=markup
                ))
            except Exception as ex:
                logger.warning(f"Adminga xabarnoma yuborishda xatolik: {ex}")

        return web.json_response({
            "success": True,
            "service_id": service_id,
            "message": "Xizmat muvaffaqiyatli qo'shildi!"
        }, headers=PRIVATE_CORS)
    except Exception as e:
        logger.error(f"Xizmat qo'shishda xatolik: {e}")
        return web.json_response({"success": False, "error": "Xizmat qo'shishda xatolik yuz berdi"}, status=500, headers=PRIVATE_CORS)

async def api_service_detail(request: web.Request) -> web.Response:
    """Bitta xizmat tafsilotlari API"""
    s_id = request.match_info.get("id")
    try:
        service = get_service_by_id(int(s_id))
        if service:
            return web.json_response(service, headers=PUBLIC_CORS)
    except Exception:
        pass
    return web.json_response({"error": "Xizmat topilmadi"}, status=404, headers=PUBLIC_CORS)

async def api_get_secretary_settings(request: web.Request) -> web.Response:
    """Foydalanuvchining kotib sozlamalarini olish API (Faqat avtorizatsiyalangan foydalanuvchi)"""
    auth_user = get_auth_user(request)
    if not auth_user or not auth_user.get("id"):
        return web.json_response({"success": False, "error": "Avtorizatsiyadan o'tilmagan. Iltimos, ilovani Telegram orqali oching."}, status=401, headers=PRIVATE_CORS)
    user_id = int(auth_user["id"])

    try:
        settings = get_secretary_settings(user_id)
        return web.json_response({"success": True, "settings": settings, "modes": SECRETARY_MODES}, headers=PRIVATE_CORS)
    except Exception as e:
        logger.error(f"Error api_get_secretary_settings: {e}")
        return web.json_response({"success": False, "error": "Sozlamalarni olishda xatolik yuz berdi"}, status=500, headers=PRIVATE_CORS)

async def api_save_secretary_settings(request: web.Request) -> web.Response:
    """Foydalanuvchining kotib sozlamalarini yangilash API"""
    auth_user = get_auth_user(request)
    if not auth_user or not auth_user.get("id"):
        return web.json_response({"success": False, "error": "Avtorizatsiyadan o'tilmagan. Iltimos, ilovani Telegram orqali oching."}, status=401, headers=PRIVATE_CORS)
    user_id = int(auth_user["id"])

    try:
        data = await request.json()
        updates = {}
        if "is_enabled" in data:
            updates["is_enabled"] = int(data["is_enabled"])
        if "mode" in data and data["mode"] in SECRETARY_MODES:
            updates["mode"] = data["mode"]
        if "custom_text" in data:
            updates["custom_text"] = str(data["custom_text"]).strip()
        if "urgent_alerts" in data:
            updates["urgent_alerts"] = int(data["urgent_alerts"])
        if "ai_instructions" in data:
            updates["ai_instructions"] = str(data["ai_instructions"]).strip()
        if "busy_reason" in data:
            updates["busy_reason"] = str(data["busy_reason"]).strip()
        if "emergency_phone" in data:
            updates["emergency_phone"] = str(data["emergency_phone"]).strip()
        if "enable_phone_escalation" in data:
            updates["enable_phone_escalation"] = int(data["enable_phone_escalation"])
        if "whitelist" in data:
            updates["whitelist"] = str(data["whitelist"]).strip()
        if "filter_spam" in data:
            updates["filter_spam"] = int(data["filter_spam"])

        update_secretary_settings(user_id, **updates)
        new_settings = get_secretary_settings(user_id)
        return web.json_response({"success": True, "settings": new_settings, "modes": SECRETARY_MODES}, headers=PRIVATE_CORS)
    except Exception as e:
        logger.error(f"Error api_save_secretary_settings: {e}")
        return web.json_response({"success": False, "error": "Sozlamalarni saqlashda xatolik yuz berdi"}, status=500, headers=PRIVATE_CORS)

async def api_get_secretary_logs(request: web.Request) -> web.Response:
    """Kotib qabul qilgan so'nggi xabarlar jurnali API"""
    auth_user = get_auth_user(request)
    if not auth_user or not auth_user.get("id"):
        return web.json_response({"success": False, "error": "Avtorizatsiyadan o'tilmagan. Iltimos, ilovani Telegram orqali oching."}, status=401, headers=PRIVATE_CORS)
    user_id = int(auth_user["id"])

    try:
        logs = get_secretary_logs(user_id, limit=20)
        return web.json_response({"success": True, "logs": logs}, headers=PRIVATE_CORS)
    except Exception as e:
        logger.error(f"Error api_get_secretary_logs: {e}")
        return web.json_response({"success": False, "error": "Xabarlar jurnalini olishda xatolik yuz berdi"}, status=500, headers=PRIVATE_CORS)

async def api_get_secretary_schedules(request: web.Request) -> web.Response:
    """Vaqt jadvallari ro'yxati API"""
    auth_user = get_auth_user(request)
    if not auth_user or not auth_user.get("id"):
        return web.json_response({"success": False, "error": "Avtorizatsiyadan o'tilmagan. Iltimos, ilovani Telegram orqali oching."}, status=401, headers=PRIVATE_CORS)
    user_id = int(auth_user["id"])

    try:
        seed_default_secretary_schedules_if_empty(user_id)
        schedules = get_secretary_schedules(user_id)
        return web.json_response({"success": True, "schedules": schedules}, headers=PRIVATE_CORS)
    except Exception as e:
        logger.error(f"Error api_get_secretary_schedules: {e}")
        return web.json_response({"success": False, "error": "Jadvallarni olishda xatolik yuz berdi"}, status=500, headers=PRIVATE_CORS)

async def api_save_secretary_schedule(request: web.Request) -> web.Response:
    """Yangi vaqt oralig'i qo'shish API"""
    auth_user = get_auth_user(request)
    if not auth_user or not auth_user.get("id"):
        return web.json_response({"success": False, "error": "Avtorizatsiyadan o'tilmagan. Iltimos, ilovani Telegram orqali oching."}, status=401, headers=PRIVATE_CORS)
    user_id = int(auth_user["id"])

    try:
        data = await request.json()
        title = str(data.get("title", "Oraliq")).strip()
        start_time = str(data.get("start_time", "09:00")).strip()
        end_time = str(data.get("end_time", "18:00")).strip()
        reply_text = str(data.get("reply_text", "")).strip()

        if not reply_text:
            return web.json_response({"success": False, "error": "Javob matni kiritilishi shart"}, status=400, headers=PRIVATE_CORS)

        new_id = add_secretary_schedule(
            user_id=user_id,
            title=title,
            start_time=start_time,
            end_time=end_time,
            reply_text=reply_text,
            is_active=1
        )
        schedules = get_secretary_schedules(user_id)
        return web.json_response({"success": True, "id": new_id, "schedules": schedules}, headers=PRIVATE_CORS)
    except Exception as e:
        logger.error(f"Error api_save_secretary_schedule: {e}")
        return web.json_response({"success": False, "error": "Jadvalni saqlashda xatolik yuz berdi"}, status=500, headers=PRIVATE_CORS)

async def api_toggle_secretary_schedule(request: web.Request) -> web.Response:
    """Vaqt oralig'i holatini (faol/nofaol) o'zgartirish API"""
    auth_user = get_auth_user(request)
    if not auth_user or not auth_user.get("id"):
        return web.json_response({"success": False, "error": "Avtorizatsiyadan o'tilmagan. Iltimos, ilovani Telegram orqali oching."}, status=401, headers=PRIVATE_CORS)
    user_id = int(auth_user["id"])

    try:
        schedule_id = int(request.match_info["id"])
        toggle_secretary_schedule(schedule_id, user_id)
        schedules = get_secretary_schedules(user_id)
        return web.json_response({"success": True, "schedules": schedules}, headers=PRIVATE_CORS)
    except Exception as e:
        logger.error(f"Error api_toggle_secretary_schedule: {e}")
        return web.json_response({"success": False, "error": "Jadval holatini o'zgartirishda xatolik yuz berdi"}, status=500, headers=PRIVATE_CORS)

async def api_delete_secretary_schedule(request: web.Request) -> web.Response:
    """Vaqt oralig'ini o'chirish API"""
    auth_user = get_auth_user(request)
    if not auth_user or not auth_user.get("id"):
        return web.json_response({"success": False, "error": "Avtorizatsiyadan o'tilmagan. Iltimos, ilovani Telegram orqali oching."}, status=401, headers=PRIVATE_CORS)
    user_id = int(auth_user["id"])

    try:
        schedule_id = int(request.match_info["id"])
        delete_secretary_schedule(schedule_id, user_id)
        schedules = get_secretary_schedules(user_id)
        return web.json_response({"success": True, "schedules": schedules}, headers=PRIVATE_CORS)
    except Exception as e:
        logger.error(f"Error api_delete_secretary_schedule: {e}")
        return web.json_response({"success": False, "error": "Jadvalni o'chirishda xatolik yuz berdi"}, status=500, headers=PRIVATE_CORS)

async def api_reset_secretary_schedules(request: web.Request) -> web.Response:
    """Standart jadvallarni qayta tiklash API"""
    auth_user = get_auth_user(request)
    if not auth_user or not auth_user.get("id"):
        return web.json_response({"success": False, "error": "Avtorizatsiyadan o'tilmagan. Iltimos, ilovani Telegram orqali oching."}, status=401, headers=PRIVATE_CORS)
    user_id = int(auth_user["id"])

    try:
        seed_default_secretary_schedules_if_empty(user_id, force_reset=True)
        schedules = get_secretary_schedules(user_id)
        return web.json_response({"success": True, "schedules": schedules}, headers=PRIVATE_CORS)
    except Exception as e:
        logger.error(f"Error api_reset_secretary_schedules: {e}")
        return web.json_response({"success": False, "error": "Jadvallarni tiklashda xatolik yuz berdi"}, status=500, headers=PRIVATE_CORS)

async def api_clear_secretary_schedules(request: web.Request) -> web.Response:
    """Barcha jadvallarni tozalash API"""
    auth_user = get_auth_user(request)
    if not auth_user or not auth_user.get("id"):
        return web.json_response({"success": False, "error": "Avtorizatsiyadan o'tilmagan. Iltimos, ilovani Telegram orqali oching."}, status=401, headers=PRIVATE_CORS)
    user_id = int(auth_user["id"])

    try:
        clear_all_secretary_schedules(user_id)
        return web.json_response({"success": True, "schedules": []}, headers=PRIVATE_CORS)
    except Exception as e:
        logger.error(f"Error api_clear_secretary_schedules: {e}")
        return web.json_response({"success": False, "error": "Jadvallarni tozalashda xatolik yuz berdi"}, status=500, headers=PRIVATE_CORS)

async def api_test_secretary_ai(request: web.Request) -> web.Response:
    """Mini App orqali AI javobini sinab ko'rish API (Avtorizatsiyalangan & Rate-limited)"""
    auth_user = get_auth_user(request)
    if not auth_user or not auth_user.get("id"):
        return web.json_response({"success": False, "error": "Avtorizatsiyadan o'tilmagan. Iltimos, ilovani Telegram orqali oching."}, status=401, headers=PRIVATE_CORS)
    user_id = int(auth_user["id"])

    if not check_rate_limit(f"ai_test:{user_id}", max_calls=6, window_sec=60):
        return web.json_response({
            "success": False,
            "error": "AI sinov chegarasiga yetildi. 1 daqiqadan so'ng qayta urinib ko'ring."
        }, status=429, headers=PRIVATE_CORS)

    try:
        from src.services.ai_secretary_service import generate_ai_reply
        from src.services.secretary_service import secretary_service
        data = await request.json()
        query_text = (data.get("message") or "Assalomu alaykum, sizda xizmat narxlari qancha?").strip()
        settings = get_secretary_settings(user_id)
        ai_inst = data.get("ai_instructions") if "ai_instructions" in data else settings.get("ai_instructions", "")
        busy_reason = data.get("busy_reason") if "busy_reason" in data else settings.get("busy_reason", "")
        emergency_phone = data.get("emergency_phone") if "emergency_phone" in data else settings.get("emergency_phone", "")
        time_info = secretary_service.get_detailed_time_context()
        reply = await generate_ai_reply(
            sender_name="Mijoz (Sinov)",
            message_text=query_text,
            ai_instructions=ai_inst,
            owner_name="Akkaunt egasi",
            busy_reason=busy_reason,
            emergency_phone=emergency_phone,
            time_info=time_info
        )
        return web.json_response({"success": True, "reply": reply}, headers=PRIVATE_CORS)
    except Exception as e:
        logger.error(f"Error api_test_secretary_ai: {e}")
        return web.json_response({"success": False, "error": "AI sinovida xatolik yuz berdi"}, status=500, headers=PRIVATE_CORS)

def create_web_app(bot: Optional[Any] = None) -> web.Application:
    app = web.Application()
    if bot:
        app["bot"] = bot

    # Ping & Health check
    app.router.add_get("/", webapp_html_handler)
    app.router.add_get("/ping", ping_handler)
    app.router.add_get("/health", ping_handler)

    # WebApp Single Page Application
    app.router.add_get("/app", webapp_html_handler)
    app.router.add_get("/webapp", webapp_html_handler)

    # REST APIs
    app.router.add_get("/api/rates/history", api_rates_history)
    app.router.add_get("/api/rates/current", api_rates_current)
    app.router.add_get("/api/prayer", api_prayer)
    app.router.add_get("/api/football/standings", api_football_standings)
    app.router.add_get("/api/football/matches", api_football_matches)
    app.router.add_get("/api/football/streams", api_football_streams)
    app.router.add_get("/api/tv/channels", api_tv_channels)
    app.router.add_post("/api/football/streams", api_add_football_stream)
    app.router.add_delete("/api/football/streams/{id}", api_delete_football_stream)
    app.router.add_get("/api/weather", api_weather)
    app.router.add_get("/api/services", api_services)
    app.router.add_post("/api/services", api_add_service)
    app.router.add_get("/api/services/{id}", api_service_detail)
    app.router.add_get("/api/secretary/settings", api_get_secretary_settings)
    app.router.add_post("/api/secretary/settings", api_save_secretary_settings)
    app.router.add_post("/api/secretary/test_ai", api_test_secretary_ai)
    app.router.add_get("/api/secretary/logs", api_get_secretary_logs)
    app.router.add_get("/api/secretary/schedules", api_get_secretary_schedules)
    app.router.add_post("/api/secretary/schedules", api_save_secretary_schedule)
    app.router.add_post("/api/secretary/schedules/reset", api_reset_secretary_schedules)
    app.router.add_post("/api/secretary/schedules/clear", api_clear_secretary_schedules)
    app.router.add_post("/api/secretary/schedules/{id}/toggle", api_toggle_secretary_schedule)
    app.router.add_delete("/api/secretary/schedules/{id}", api_delete_secretary_schedule)
    app.router.add_get("/api/copier_status", api_copier_status)

    return app

async def api_copier_status(request: web.Request) -> web.Response:
    """Kitoblar nusxalash jarayoni holati (Faqat Administrator uchun - ichki diagnostika)"""
    auth_user = get_auth_user(request)
    if not auth_user or not auth_user.get("id"):
        return web.json_response({"success": False, "error": "Avtorizatsiyadan o'tilmagan"}, status=401, headers=PRIVATE_CORS)
    if int(auth_user.get("id", 0)) not in ADMIN_IDS:
        return web.json_response({"success": False, "error": "Ruxsat etilmagan: faqat administratorlar uchun"}, status=403, headers=PRIVATE_CORS)
    try:
        from src.services.book_service import get_copier_debug_status
        return web.json_response(get_copier_debug_status(), headers=PRIVATE_CORS)
    except Exception as e:
        logger.error(f"api_copier_status error: {e}")
        return web.json_response({"error": "Holatni tekshirishda xatolik yuz berdi"}, status=500, headers=PRIVATE_CORS)

