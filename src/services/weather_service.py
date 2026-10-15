import logging
from typing import Optional, Dict, Any, Tuple
import aiohttp

logger = logging.getLogger(__name__)

# O'zbekiston viloyatlari markazlari koordinatalari (tezkor yuklash uchun)
UZB_REGIONS = {
    "Toshkent": (41.2995, 69.2401),
    "Samarqand": (39.6542, 66.9597),
    "Buxoro": (39.7747, 64.4286),
    "Andijon": (40.7821, 72.3442),
    "Farg'ona": (40.3842, 71.7843),
    "Namangan": (40.9983, 71.6726),
    "Qarshi": (38.8606, 65.7891),
    "Termiz": (37.2242, 67.2783),
    "Nukus": (42.4602, 59.6074),
    "Urganch": (41.5500, 60.6333),
    "Xiva": (41.3783, 60.3639),
    "Navoiy": (40.0844, 65.3792),
    "Jizzax": (40.1158, 67.8422),
    "Guliston": (40.4897, 68.7842)
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

def get_weather_desc(code: int) -> Tuple[str, str]:
    return WMO_WEATHER_CODES.get(code, ("O'zgaruvchan", "⛅"))

class WeatherService:
    async def get_coordinates_by_city(self, city_name: str) -> Optional[Tuple[float, float, str]]:
        """Shahar nomidan koordinatalarni topadi"""
        # Avval mahalliy ro'yxatdan tekshiramiz
        for name, coords in UZB_REGIONS.items():
            if city_name.strip().lower() in name.lower():
                return coords[0], coords[1], name

        # Aks holda Open-Meteo Geocoding API orqali qidiramiz
        url = f"https://geocoding-api.open-meteo.com/v1/search?name={city_name}&count=1&language=uz&format=json"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        results = data.get("results")
                        if results:
                            item = results[0]
                            return float(item["latitude"]), float(item["longitude"]), item.get("name", city_name)
        except Exception as e:
            logger.error(f"Geocoding xatoligi ({city_name}): {e}")
        return None

    async def get_weather(self, lat: float, lon: float, location_name: str = "Sizning hududingiz") -> Optional[Dict[str, Any]]:
        """Koordinatalar bo'yicha aniq ob-havo ma'lumotlarini oladi"""
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={lat}&longitude={lon}"
            f"&current=temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,weather_code,wind_speed_10m"
            f"&daily=weather_code,temperature_2m_max,temperature_2m_min,precipitation_sum"
            f"&timezone=auto"
        )
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        current = data.get("current", {})
                        daily = data.get("daily", {})

                        w_code = current.get("weather_code", 0)
                        desc, emoji = get_weather_desc(w_code)

                        # 3 kunlik prognoz
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

                        return {
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
        except Exception as e:
            logger.error(f"Ob-havo olishda xatolik ({lat}, {lon}): {e}")
        return None

weather_service = WeatherService()
