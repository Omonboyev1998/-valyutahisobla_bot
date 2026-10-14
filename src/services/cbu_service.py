import time
import logging
from typing import Optional, Dict, List, Any
import aiohttp
from src.config import CBU_API_URL

logger = logging.getLogger(__name__)

class CBUService:
    def __init__(self, cache_ttl_seconds: int = 600):
        self.cache_ttl = cache_ttl_seconds
        self._cached_rates: Dict[str, Dict[str, Any]] = {}
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

cbu_service = CBUService()
