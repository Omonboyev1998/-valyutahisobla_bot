import time
import socket
import logging
from typing import Optional, Dict, Any, Tuple
import aiohttp

logger = logging.getLogger(__name__)

# O'zbekiston viloyatlari markazlari koordinatalari va xalqaro nomlari
UZB_REGIONS = {
    "Toshkent": {"coords": (41.2995, 69.2401), "intl": "Tashkent"},
    "Samarqand": {"coords": (39.6542, 66.9597), "intl": "Samarkand"},
    "Buxoro": {"coords": (39.7747, 64.4286), "intl": "Bukhara"},
    "Andijon": {"coords": (40.7821, 72.3442), "intl": "Andijan"},
    "Farg'ona": {"coords": (40.3842, 71.7843), "intl": "Fergana"},
    "Namangan": {"coords": (40.9983, 71.6726), "intl": "Namangan"},
    "Qarshi": {"coords": (38.8606, 65.7891), "intl": "Karshi"},
    "Termiz": {"coords": (37.2242, 67.2783), "intl": "Termez"},
    "Nukus": {"coords": (42.4602, 59.6074), "intl": "Nukus"},
    "Urganch": {"coords": (41.5500, 60.6333), "intl": "Urgench"},
    "Xiva": {"coords": (41.3783, 60.3639), "intl": "Khiva"},
    "Navoiy": {"coords": (40.0844, 65.3792), "intl": "Navoi"},
    "Jizzax": {"coords": (40.1158, 67.8422), "intl": "Jizzakh"},
    "Guliston": {"coords": (40.4897, 68.7842), "intl": "Gulistan"}
}

MET_SYMBOLS = {
    "clearsky_day": ("Musaffo osmon", "☀️"),
    "clearsky_night": ("Musaffo osmon", "🌙"),
    "fair_day": ("Ochiq havo", "🌤"),
    "fair_night": ("Ochiq havo", "🌤"),
    "partlycloudy_day": ("Qisman bulutli", "⛅"),
    "partlycloudy_night": ("Qisman bulutli", "⛅"),
    "cloudy": ("Bulutli", "☁️"),
    "rain": ("Yomg'ir", "🌧"),
    "lightrain": ("Yengil yomg'ir", "🌦"),
    "heavyrain": ("Kuchli yomg'ir", "🌧"),
    "rainshowers_day": ("Qisqa yomg'ir", "🌦"),
    "rainshowers_night": ("Qisqa yomg'ir", "🌦"),
    "thunderstorm": ("Momaqaldiroq", "⛈"),
    "snow": ("Qor", "❄️"),
    "lightsnow": ("Yengil qor", "🌨"),
    "heavysnow": ("Kuchli qor", "❄️"),
    "fog": ("Tuman", "🌫")
}

def translate_met_symbol(code: str) -> Tuple[str, str]:
    base = code.split("_")[0] if "_" in code else code
    if code in MET_SYMBOLS:
        return MET_SYMBOLS[code]
    for k, v in MET_SYMBOLS.items():
        if base in k:
            return v
    return ("O'zgaruvchan havo", "⛅")

class WeatherService:
    def __init__(self, cache_ttl: int = 600):
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

    async def get_coordinates_by_city(self, city_name: str) -> Optional[Tuple[float, float, str, str]]:
        clean_name = city_name.strip()
        for name, data in UZB_REGIONS.items():
            if clean_name.lower() in name.lower() or name.lower() in clean_name.lower():
                return data["coords"][0], data["coords"][1], name, data["intl"]

        # Geocoding orqali qidirish
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={clean_name}&count=1&language=uz&format=json"
        try:
            connector = aiohttp.TCPConnector(family=socket.AF_INET)
            async with aiohttp.ClientSession(connector=connector, headers={"User-Agent": "ValyutaBot/1.0"}) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("results")
                        if results:
                            item = results[0]
                            return float(item["latitude"]), float(item["longitude"]), item.get("name", clean_name), clean_name
        except Exception as e:
            logger.error(f"Geocoding xatoligi ({city_name}): {e}")
        return None

    async def get_weather(self, lat: float, lon: float, location_name: str = "Sizning hududingiz", intl_name: str = "") -> Optional[Dict[str, Any]]:
        """Ko'p platformali ob-havo dvijogi: MET Norway -> Open-Meteo -> wttr.in"""
        cache_key = f"{round(lat, 2)}_{round(lon, 2)}"
        now = time.time()
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if now - cached_time < self.cache_ttl:
                cached_data["location_name"] = location_name
                return cached_data

        # 1-PLATFORMA: MET Norway (yr.no) — Eng barqaror davlat meteorologiya instituti
        met_data = await self._get_met_norway(lat, lon, location_name)
        if met_data:
            self._cache[cache_key] = (now, met_data)
            return met_data

        # 2-PLATFORMA: Open-Meteo
        om_data = await self._get_open_meteo(lat, lon, location_name)
        if om_data:
            self._cache[cache_key] = (now, om_data)
            return om_data

        # 3-PLATFORMA: wttr.in (Zaxira)
        fallback_query = f"{round(lat, 4)},{round(lon, 4)}" if not intl_name else intl_name
        return await self._get_wttr(location_name, fallback_query)

    async def _get_met_norway(self, lat: float, lon: float, location_name: str) -> Optional[Dict[str, Any]]:
        """MET Norway (yr.no) API"""
        url = f"https://api.met.no/weatherapi/locationforecast/2.0/compact?lat={round(lat, 4)}&lon={round(lon, 4)}"
        headers = {"User-Agent": "ValyutaBotTelegram/2.0 (contact@valyutabot.uz)"}
        try:
            connector = aiohttp.TCPConnector(family=socket.AF_INET)
            async with aiohttp.ClientSession(connector=connector, headers=headers) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        timeseries = data.get("properties", {}).get("timeseries", [])
                        if timeseries:
                            current = timeseries[0]
                            instant = current.get("data", {}).get("instant", {}).get("details", {})
                            temp = round(float(instant.get("air_temperature", 0)), 1)
                            humidity = int(instant.get("relative_humidity", 0))
                            wind = round(float(instant.get("wind_speed", 0)), 1)

                            summary = current.get("data", {}).get("next_1_hours", {}).get("summary", {})
                            if not summary:
                                summary = current.get("data", {}).get("next_6_hours", {}).get("summary", {})
                            symbol = summary.get("symbol_code", "clearsky_day")
                            desc, emoji = translate_met_symbol(symbol)

                            # Keyingi soatlar / kunlar
                            forecast = []
                            # 24 va 48 soatdan keyingi prognozni olamiz
                            for offset, label in [(12, "Ertaga"), (24, "Indinga")]:
                                if len(timeseries) > offset:
                                    f_point = timeseries[offset]
                                    f_temp = round(float(f_point.get("data", {}).get("instant", {}).get("details", {}).get("air_temperature", temp)), 1)
                                    f_sym = f_point.get("data", {}).get("next_6_hours", {}).get("summary", {}).get("symbol_code", symbol)
                                    f_desc, f_emoji = translate_met_symbol(f_sym)
                                    forecast.append({
                                        "date": label,
                                        "max": f_temp,
                                        "min": round(f_temp - 8, 1),
                                        "desc": f_desc,
                                        "emoji": f_emoji
                                    })

                            return {
                                "location_name": location_name,
                                "temp": temp,
                                "apparent_temp": temp,
                                "humidity": humidity,
                                "wind_speed": wind,
                                "desc": desc,
                                "emoji": emoji,
                                "forecast": forecast
                            }
        except Exception as e:
            logger.error(f"MET Norway xatoligi: {e}")
        return None

    async def _get_open_meteo(self, lat: float, lon: float, location_name: str) -> Optional[Dict[str, Any]]:
        """Open-Meteo API"""
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,weather_code,wind_speed_10m"
            f"&daily=weather_code,temperature_2m_max,temperature_2m_min"
            f"&timezone=auto"
        )
        try:
            connector = aiohttp.TCPConnector(family=socket.AF_INET)
            async with aiohttp.ClientSession(connector=connector, headers={"User-Agent": "ValyutaBot/1.0"}) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        current = data.get("current", {})
                        daily = data.get("daily", {})

                        temp = current.get("temperature_2m")
                        app_temp = current.get("apparent_temperature", temp)
                        humidity = current.get("relative_humidity_2m", 0)
                        wind = current.get("wind_speed_10m", 0)

                        forecast = []
                        dates = daily.get("time", [])
                        max_temps = daily.get("temperature_2m_max", [])
                        min_temps = daily.get("temperature_2m_min", [])

                        for i in range(min(3, len(dates))):
                            forecast.append({
                                "date": dates[i],
                                "max": max_temps[i] if i < len(max_temps) else temp,
                                "min": min_temps[i] if i < len(min_temps) else temp - 7,
                                "desc": "Ochiq",
                                "emoji": "☀️"
                            })

                        return {
                            "location_name": location_name,
                            "temp": temp,
                            "apparent_temp": app_temp,
                            "humidity": humidity,
                            "wind_speed": wind,
                            "desc": "Ochiq havo",
                            "emoji": "☀️",
                            "forecast": forecast
                        }
        except Exception as e:
            logger.error(f"Open-Meteo xatoligi: {e}")
        return None

    async def _get_wttr(self, location_name: str, query: str) -> Optional[Dict[str, Any]]:
        """wttr.in zaxira provayderi"""
        url = f"https://wttr.in/{query}?format=j1"
        try:
            connector = aiohttp.TCPConnector(family=socket.AF_INET)
            async with aiohttp.ClientSession(connector=connector, headers={"User-Agent": "curl/7.68.0"}) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        current = data["current_condition"][0]
                        temp = float(current.get("temp_C", 0))
                        humidity = int(current.get("humidity", 0))
                        wind = round(float(current.get("windspeedKmph", 0)) / 3.6, 1)

                        return {
                            "location_name": location_name,
                            "temp": temp,
                            "apparent_temp": temp,
                            "humidity": humidity,
                            "wind_speed": wind,
                            "desc": "Musaffo osmon",
                            "emoji": "☀️",
                            "forecast": []
                        }
        except Exception as e:
            logger.error(f"wttr.in xatoligi: {e}")
        return None

weather_service = WeatherService()
