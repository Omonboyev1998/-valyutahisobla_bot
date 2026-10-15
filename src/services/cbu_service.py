import time
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
import aiohttp
from src.config import CBU_API_URL

logger = logging.getLogger(__name__)

class CBUService:
    def __init__(self, cache_ttl_seconds: int = 600):
        self.cache_ttl = cache_ttl_seconds
        self._cached_rates: Dict[str, Dict[str, Any]] = {}
        self._history_cache: Dict[str, Any] = {}
        self._last_fetched_at: float = 0
        self._date: str = ""

    async def get_all_rates(self, force_refresh: bool = False) -> Dict[str, Dict[str, Any]]:
        """Barcha valyutalar kurslarini oladi (kesh bilan)"""
        now = time.time()
        if not force_refresh and self._cached_rates and (now - self._last_fetched_at < self.cache_ttl):
            return self._cached_rates

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(CBU_API_URL, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        rates_dict = {}
                        for item in data:
                            ccy = item.get("Ccy", "").upper()
                            try:
                                nominal = float(item.get("Nominal", 1))
                                rate = float(item.get("Rate", 0))
                                diff = float(item.get("Diff", 0))
                            except (ValueError, TypeError):
                                nominal = 1.0
                                rate = 0.0
                                diff = 0.0

                            rates_dict[ccy] = {
                                "id": item.get("id"),
                                "code": item.get("Code"),
                                "ccy": ccy,
                                "name_uz": item.get("CcyNm_UZ", ""),
                                "name_ru": item.get("CcyNm_RU", ""),
                                "name_en": item.get("CcyNm_EN", ""),
                                "nominal": nominal,
                                "rate": rate,
                                "unit_rate": rate / nominal if nominal else rate,
                                "diff": diff,
                                "date": item.get("Date", "")
                            }
                            if not self._date and item.get("Date"):
                                self._date = item.get("Date")

                        self._cached_rates = rates_dict
                        self._last_fetched_at = now
                        logger.info("CBU valyuta kurslari muvaffaqiyatli yangilandi.")
                        return self._cached_rates
                    else:
                        logger.error(f"CBU API xatolik kodi qaytardi: {resp.status}")
        except Exception as e:
            logger.error(f"CBU API ga ulanishda xatolik: {e}")

        # Agar yangilashda xato bo'lsa, mavjud keshni qaytaramiz
        return self._cached_rates

    async def get_rate(self, ccy: str) -> Optional[Dict[str, Any]]:
        """Muayyan valyuta ma'lumotlarini qaytaradi"""
        rates = await self.get_all_rates()
        return rates.get(ccy.upper())

    async def get_popular_rates(self) -> List[Dict[str, Any]]:
        """Eng ommabop valyutalar ro'yxatini qaytaradi"""
        rates = await self.get_all_rates()
        popular_codes = ["USD", "EUR", "RUB", "KZT", "CNY", "TRY", "GBP", "AED"]
        return [rates[c] for c in popular_codes if c in rates]

    async def convert(self, amount: float, from_ccy: str, to_ccy: str) -> Optional[Dict[str, Any]]:
        """
        amount miqdorini from_ccy dan to_ccy ga o'giradi.
        Masalan: convert(100, 'USD', 'UZS') yoki convert(1000000, 'UZS', 'USD')
        """
        from_ccy = from_ccy.upper()
        to_ccy = to_ccy.upper()

        if from_ccy == to_ccy:
            return {
                "amount": amount,
                "from_ccy": from_ccy,
                "to_ccy": to_ccy,
                "result": amount,
                "rate": 1.0
            }

        rates = await self.get_all_rates()

        # Bir valyuta UZS bo'lgan holat
        if to_ccy == "UZS":
            if from_ccy not in rates:
                return None
            info = rates[from_ccy]
            unit_rate = info["unit_rate"]
            result = amount * unit_rate
            return {
                "amount": amount,
                "from_ccy": from_ccy,
                "to_ccy": to_ccy,
                "result": result,
                "unit_rate": unit_rate,
                "info": info
            }

        if from_ccy == "UZS":
            if to_ccy not in rates:
                return None
            info = rates[to_ccy]
            unit_rate = info["unit_rate"]
            result = amount / unit_rate if unit_rate else 0
            return {
                "amount": amount,
                "from_ccy": from_ccy,
                "to_ccy": to_ccy,
                "result": result,
                "unit_rate": unit_rate,
                "info": info
            }

        # Ikkala valyuta ham chet el valyutasi (Kross-kurs)
        if from_ccy in rates and to_ccy in rates:
            from_info = rates[from_ccy]
            to_info = rates[to_ccy]
            from_unit_rate = from_info["unit_rate"]
            to_unit_rate = to_info["unit_rate"]
            result = (amount * from_unit_rate) / to_unit_rate if to_unit_rate else 0
            return {
                "amount": amount,
                "from_ccy": from_ccy,
                "to_ccy": to_ccy,
                "result": result,
                "cross_rate": from_unit_rate / to_unit_rate if to_unit_rate else 0,
                "from_info": from_info,
                "to_info": to_info
            }

        return None

    async def get_currency_history(self, ccy: str = "USD", days: int = 7) -> Dict[str, Any]:
        """Valyutaning so'nggi N kunlik kurslar dinamikasini qaytaradi (kesh bilan)"""
        ccy = ccy.upper()
        now = datetime.now()
        cache_key = f"{ccy}_{days}_{now.strftime('%Y-%m-%d')}"
        if cache_key in self._history_cache:
            return self._history_cache[cache_key]

        num_points = 7 if days <= 7 else min(days, 30)
        dates = [(now - timedelta(days=i)).strftime("%Y-%m-%d") for i in range(num_points)]
        dates.reverse()

        async with aiohttp.ClientSession() as session:
            async def fetch_one(d_str: str):
                url = f"https://cbu.uz/uz/arkhiv-kursov-valyut/json/{ccy}/{d_str}/"
                try:
                    async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            if data and isinstance(data, list) and len(data) > 0:
                                return {"date": d_str, "rate": float(data[0].get("Rate", 0))}
                except Exception:
                    pass
                return {"date": d_str, "rate": None}

            results = await asyncio.gather(*[fetch_one(d) for d in dates])

        valid_points = []
        last_known = None
        for item in results:
            if item["rate"] is not None and item["rate"] > 0:
                last_known = item["rate"]
                # Display date: DD.MM
                parts = item["date"].split("-")
                disp = f"{parts[2]}.{parts[1]}"
                valid_points.append({"date": disp, "full_date": item["date"], "rate": item["rate"]})
            elif last_known is not None:
                parts = item["date"].split("-")
                disp = f"{parts[2]}.{parts[1]}"
                valid_points.append({"date": disp, "full_date": item["date"], "rate": last_known})

        rates_list = [p["rate"] for p in valid_points]
        min_rate = min(rates_list) if rates_list else 0
        max_rate = max(rates_list) if rates_list else 0
        current_rate = rates_list[-1] if rates_list else 0
        first_rate = rates_list[0] if rates_list else current_rate
        diff = current_rate - first_rate
        diff_pct = (diff / first_rate * 100) if first_rate else 0

        res = {
            "ccy": ccy,
            "days": days,
            "points": valid_points,
            "current_rate": current_rate,
            "min_rate": min_rate,
            "max_rate": max_rate,
            "diff": round(diff, 2),
            "diff_pct": round(diff_pct, 2)
        }
        self._history_cache[cache_key] = res
        return res

cbu_service = CBUService()
