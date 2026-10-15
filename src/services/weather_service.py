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

WMO_WEATHER_CODES = {
    0: ("Musaffo osmon", "☀️"),
    1: ("Asosan ochiq", "🌤"),
    2: ("Qisman bulutli", "⛅"),
    3: ("Bulutli", "☁️"),
    45: ("Tuman", "🌫"),
    48: ("Muzli tuman", "🌫"),
    51: ("Yengil shivalagan yomg'ir", "🌦"),
    53: ("O'rtacha yomg'ir", "🌧"),
    55: ("Kuchli yomg'ir", "🌧"),
    61: ("Yengil yomg'ir", "🌧"),
    63: ("Yomg'ir", "🌧"),
    65: ("Kuchli jala", "⛈"),
    71: ("Yengil qor", "🌨"),
    73: ("Qor", "❄️"),
    75: ("Kuchli qor", "❄️"),
    77: ("Qor donalari", "🌨"),
    80: ("Qisqa muddatli yomg'ir", "🌦"),
    81: ("Kuchli qisqa yomg'ir", "🌧"),
    82: ("Shiddatli jala", "⛈"),
    85: ("Yengil qor bo'roni", "🌨"),
    86: ("Kuchli qor bo'roni", "❄️"),
    95: ("Momaqaldiroq", "⛈"),
    96: ("Do'l aralash momaqaldiroq", "⛈"),
    99: ("Kuchli do'lli momaqaldiroq", "⛈")
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

def get_weather_desc(code: int) -> Tuple[str, str]:
    return WMO_WEATHER_CODES.get(code, ("O'zgaruvchan", "⛅"))

class WeatherService:
    def __init__(self, cache_ttl: int = 600):
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

    async def get_coordinates_by_city(self, city_name: str) -> Optional[Tuple[float, float, str, str]]:
        """Shahar nomidan koordinatalarni topadi. Qaytaradi: (lat, lon, uz_name, intl_name)"""
        clean_name = city_name.strip()
        for name, data in UZB_REGIONS.items():
            if clean_name.lower() in name.lower() or name.lower() in clean_name.lower():
                return data["coords"][0], data["coords"][1], name, data["intl"]

        url = f"https://geocoding-api.open-meteo.com/v1/search?name={clean_name}&count=1&language=uz&format=json"
        try:
            connector = aiohttp.TCPConnector(family=socket.AF_INET)
            async with aiohttp.ClientSession(connector=connector, headers=HEADERS) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
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
        """Koordinatalar bo'yicha aniq ob-havo ma'lumotlarini oladi (kesh va ikkilamchi zaxira bilan)"""
        cache_key = f"{round(lat, 2)}_{round(lon, 2)}"
        now = time.time()
        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if now - cached_time < self.cache_ttl:
                # Keshdan qaytaramiz (nomini yangilab)
                cached_data["location_name"] = location_name
                return cached_data

        # 1. Asosiy provayder: Open-Meteo
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m"
            f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum"
            f"&timezone=auto"
        )
        try:
            connector = aiohttp.TCPConnector(family=socket.AF_INET)
            async with aiohttp.ClientSession(connector=connector, headers=HEADERS) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        current = data.get("current", {})
                        daily = data.get("daily", {})

                        w_code = current.get("weather_code", 0)
                        desc, emoji = get_weather_desc(w_code)

                        forecast = []
                        dates = daily.get("time", [])
                        max_temps = daily.get("temperature_2m_max", [])
                        min_temps = daily.get("temperature_2m_min", [])
                        codes = daily.get("weather_code", [])

                        for i in range(min(4, len(dates))):
                            d_desc, d_emoji = get_weather_desc(codes[i] if i < len(codes) else 0)
                            forecast.append({
                                "date": dates[i],
                                "max": max_temps[i] if i < len(max_temps) else 0,
                                "min": min_temps[i] if i < len(min_temps) else 0,
                                "desc": d_desc,
                                "emoji": d_emoji
                            })

                        result = {
                            "location_name": location_name,
                            "temp": current.get("temperature_2m"),
                            "apparent_temp": current.get("apparent_temperature"),
                            "humidity": current.get("relative_humidity_2m"),
                            "wind_speed": current.get("wind_speed_10m"),
                            "precipitation": current.get("precipitation"),
                            "desc": desc,
                            "emoji": emoji,
                            "forecast": forecast
                        }
                        self._cache[cache_key] = (now, result)
                        return result
                    else:
                        logger.warning(f"Open-Meteo status kodi: {resp.status}")
        except Exception as e:
            logger.error(f"Open-Meteo xatoligi ({lat}, {lon}): {e}")

        # 2. Zaxira provayder: wttr.in
        fallback_city = intl_name or location_name
        return await self._get_weather_wttr(location_name, fallback_city)

    async def _get_weather_wttr(self, location_name: str, query_city: str) -> Optional[Dict[str, Any]]:
        """Zaxira ob-havo provayderi (wttr.in)"""
        url = f"https://wttr.in/{query_city}?format=j1"
        try:
            connector = aiohttp.TCPConnector(family=socket.AF_INET)
            async with aiohttp.ClientSession(connector=connector, headers={"User-Agent": "curl/7.68.0"}) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        current = data["current_condition"][0]
                        weather_days = data.get("weather", [])

                        temp = float(current.get("temp_C", 0))
                        app_temp = float(current.get("FeelsLikeC", 0))
                        humidity = int(current.get("humidity", 0))
                        wind = round(float(current.get("windspeedKmph", 0)) / 3.6, 1)

                        forecast = []
                        for day in weather_days[:3]:
                            forecast.append({
                                "date": day.get("date", ""),
                                "max": float(day.get("maxtempC", 0)),
                                "min": float(day.get("mintempC", 0)),
                                "desc": "Ochiq havo",
                                "emoji": "☀️"
                            })

                        return {
                            "location_name": location_name,
                            "temp": temp,
                            "apparent_temp": app_temp,
                            "humidity": humidity,
                            "wind_speed": wind,
                            "desc": "Musaffo osmon",
                            "emoji": "☀️",
                            "forecast": forecast
                        }
        except Exception as e:
            logger.error(f"wttr.in zaxira xatoligi ({query_city}): {e}")
        return None

weather_service = WeatherService()
