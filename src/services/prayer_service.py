import time
import socket
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, Tuple
import aiohttp

from src.services.weather_service import UZB_REGIONS

logger = logging.getLogger(__name__)

TASHKENT_TZ = timezone(timedelta(hours=5))

SAHARLIK_DUO = (
    "🤲 <b>Saharlik (Og'iz yopish) duosi:</b>\n\n"
    "<i>Navaytu an asuma sovma shahri ramazona minal fajri ilal mag'ribi, xolisan lillahi ta'ala. Allohu akbar.</i>\n\n"
    "<b>Ma'nosi:</b> Ramazon oyining ro'zasini tongdan to quyosh botguncha, Alloh taolo uchun xolis tutishni niyat qildim. Alloh buyukdir."
)

IFTORLIK_DUO = (
    "🤲 <b>Iftorlik (Og'iz ochish) duosi:</b>\n\n"
    "<i>Allohumma laka sumtu va bika amantu va a'layka tavakkaltu va a'la rizqika aftartu, fag'firli ya g'offaru ma qoddamtu va ma axxortu.</i>\n\n"
    "<b>Ma'nosi:</b> Ey Allohim, ushbu ro'zamni Sen uchun tutdim va Senga iymon keltirdim va Senga tavakkal qildim va bergan rizqing bilan iftor qildim. Ey kechirguvchi Zot, mening avvalgi va keyingi gunohlarimni kechirgin."
)

class PrayerService:
    def __init__(self, cache_ttl: int = 14400):  # 4 soat kesh
        self.cache_ttl = cache_ttl
        self._cache: Dict[str, Tuple[float, Dict[str, Any]]] = {}

    def get_next_prayer(self, timings: Dict[str, str]) -> Tuple[str, str, str]:
        """Keyingi kiradigan namoz va unga qancha vaqt qolganini hisoblaydi"""
        now = datetime.now(TASHKENT_TZ)
        now_minutes = now.hour * 60 + now.minute

        prayers = [
            ("Tong (Bomdod)", timings["Fajr"]),
            ("Peshin", timings["Dhuhr"]),
            ("Asr", timings["Asr"]),
            ("Shom (Iftor)", timings["Maghrib"]),
            ("Xufton", timings["Isha"])
        ]

        for name, time_str in prayers:
            p_hour, p_min = map(int, time_str.split(":"))
            p_minutes = p_hour * 60 + p_min
            if p_minutes > now_minutes:
                diff = p_minutes - now_minutes
                h = diff // 60
                m = diff % 60
                remaining = f"{h} soat {m} daqiqa" if h > 0 else f"{m} daqiqa"
                return name, time_str, remaining

        # Agar barcha namozlar o'tgan bo'lsa, keyingi kun tonggi namoz
        f_hour, f_min = map(int, timings["Fajr"].split(":"))
        diff = (24 * 60 - now_minutes) + (f_hour * 60 + f_min)
        h = diff // 60
        m = diff % 60
        remaining = f"{h} soat {m} daqiqa" if h > 0 else f"{m} daqiqa"
        return "Tong (Bomdod)", timings["Fajr"], remaining

    async def get_prayer_times(self, city_name: str = "Toshkent") -> Optional[Dict[str, Any]]:
        """Tanlangan shahar uchun bugungi 5 mahal namoz vaqtlarini oladi"""
        clean_city = city_name.strip()
        region_info = UZB_REGIONS.get(clean_city)
        if not region_info:
            for name, data in UZB_REGIONS.items():
                if clean_city.lower() in name.lower() or name.lower() in clean_city.lower():
                    clean_city = name
                    region_info = data
                    break

        if not region_info:
            clean_city = "Toshkent"
            region_info = UZB_REGIONS["Toshkent"]

        lat, lon = region_info["coords"]
        today_str = datetime.now(TASHKENT_TZ).strftime("%Y-%m-%d")
        cache_key = f"{clean_city}_{today_str}"
        now = time.time()

        if cache_key in self._cache:
            cached_time, cached_data = self._cache[cache_key]
            if now - cached_time < self.cache_ttl:
                # Keyingi namozgacha qolgan vaqtni jonli yangilab qaytaramiz
                next_name, next_time, remaining = self.get_next_prayer(cached_data["raw_timings"])
                cached_data["next_prayer"] = {
                    "name": next_name,
                    "time": next_time,
                    "remaining": remaining
                }
                return cached_data

        url = f"https://api.aladhan.com/v1/timings?latitude={lat}&longitude={lon}&method=3&school=1"
        try:
            connector = aiohttp.TCPConnector(family=socket.AF_INET)
            async with aiohttp.ClientSession(connector=connector, headers={"User-Agent": "ValyutaBot/1.0"}) as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        d = data.get("data", {})
                        timings = d.get("timings", {})
                        date_info = d.get("date", {})
                        hijri = date_info.get("hijri", {})

                        hijri_str = f"{hijri.get('day', '')} {hijri.get('month', {}).get('en', '')} {hijri.get('year', '')}-yil"
                        gregorian_str = datetime.now(TASHKENT_TZ).strftime("%d.%m.%Y")

                        next_name, next_time, remaining = self.get_next_prayer(timings)

                        result = {
                            "city": clean_city,
                            "gregorian_date": gregorian_str,
                            "hijri_date": hijri_str,
                            "fajr": timings.get("Fajr"),        # Tong / Saharlik
                            "sunrise": timings.get("Sunrise"),  # Quyosh
                            "dhuhr": timings.get("Dhuhr"),      # Peshin
                            "asr": timings.get("Asr"),          # Asr
                            "maghrib": timings.get("Maghrib"),  # Shom / Iftorlik
                            "isha": timings.get("Isha"),        # Xufton
                            "raw_timings": timings,
                            "next_prayer": {
                                "name": next_name,
                                "time": next_time,
                                "remaining": remaining
                            }
                        }

                        self._cache[cache_key] = (now, result)
                        return result
                    else:
                        logger.warning(f"Aladhan status kodi: {resp.status}")
        except Exception as e:
            logger.error(f"Namoz vaqtlarini olishda xatolik ({clean_city}): {e}")

        return None

prayer_service = PrayerService()
