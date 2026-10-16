import os
import time
import logging
from aiohttp import web
from src.services.cbu_service import cbu_service
from src.services.prayer_service import prayer_service
from src.services.football_service import football_service
from src.services.weather_service import weather_service

logger = logging.getLogger(__name__)

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
HTML_FILE = os.path.join(STATIC_DIR, "webapp.html")

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
    return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})

async def api_rates_current(request: web.Request) -> web.Response:
    """Barcha valyutalar joriy kursi (ro'yxat va xarita formatida)"""
    rates_dict = await cbu_service.get_all_rates()
    rates_list = []
    for ccy_code, r in rates_dict.items():
        item = dict(r)
        item["Ccy"] = ccy_code
        item["Rate"] = str(r["rate"])
        rates_list.append(item)
    return web.json_response(rates_list, headers={"Access-Control-Allow-Origin": "*"})

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
    return web.json_response(data or {}, headers={"Access-Control-Allow-Origin": "*"})

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
    return web.json_response(data or {}, headers={"Access-Control-Allow-Origin": "*"})

async def api_football_matches(request: web.Request) -> web.Response:
    """Futbol o'yinlari API"""
    league = request.query.get("league", "eng.1")
    data = await football_service.get_matches(league_code=league)
    return web.json_response(data or {}, headers={"Access-Control-Allow-Origin": "*"})

async def api_weather(request: web.Request) -> web.Response:
    """Ob-havo API"""
    city = request.query.get("city", "Toshkent")
    coords = await weather_service.get_coordinates_by_city(city)
    if coords:
        lat, lon, real_name, intl_name = coords
        data = await weather_service.get_weather(lat, lon, real_name, intl_name)
        if data:
            return web.json_response(data, headers={"Access-Control-Allow-Origin": "*"})
    return web.json_response({"error": "Ob-havo ma'lumoti topilmadi"}, status=404, headers={"Access-Control-Allow-Origin": "*"})

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
    }, headers={"Access-Control-Allow-Origin": "*"})

async def api_service_detail(request: web.Request) -> web.Response:
    """Bitta xizmat tafsilotlari API"""
    s_id = request.match_info.get("id")
    try:
        service = get_service_by_id(int(s_id))
        if service:
            return web.json_response(service, headers={"Access-Control-Allow-Origin": "*"})
    except Exception:
        pass
    return web.json_response({"error": "Xizmat topilmadi"}, status=404, headers={"Access-Control-Allow-Origin": "*"})

def create_web_app() -> web.Application:
    app = web.Application()
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
    app.router.add_get("/api/weather", api_weather)
    app.router.add_get("/api/services", api_services)
    app.router.add_get("/api/services/{id}", api_service_detail)

    return app
