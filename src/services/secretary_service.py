import time
import re
from typing import Dict, Any, Optional, List
from src.database import get_secretary_last_sender_time

SECRETARY_MODES = {
    "busy": {
        "title": "⏳ Bandman",
        "desc": "Telefon yonida emasman, bo'shashim bilan javob beraman",
        "default_text": "Assalomu alaykum! Hozir biroz bandman va telefon yonida emasman. Xabaringizni ko'rib albatta javob yozaman."
    },
    "meeting": {
        "title": "💼 Yig'ilishda",
        "desc": "Muhim uchrashuvdaman, tez orada bog'lanaman",
        "default_text": "Assalomu alaykum! Hozir muhim uchrashuvdaman. Xabaringiz yetkazildi, uchrashuv tugashi bilan sizga aloqaga chiqaman."
    },
    "driving": {
        "title": "🚗 Ruldaman",
        "desc": "Avtomobil boshqarayapman, xavfsizlik uchun yozolmayman",
        "default_text": "Salom! Hozir rulda ketyapman. Yo'l xavfsizligi sababli yoza olmayapman, to'xtashim bilan javob qaytaraman."
    },
    "night": {
        "title": "🌙 Dam olish / Tun",
        "desc": "Dam olish vaqtida, ertalab javob qaytariladi",
        "default_text": "Assalomu alaykum! Hozir dam olish vaqti bo'lganligi sababli javob bera olmayapman. Ertalab birinchilardan bo'lib javob qaytaraman."
    },
    "vacation": {
        "title": "🏖 Ta'tildaman",
        "desc": "Ta'tildaman, shoshilinch bo'lsa belgilang",
        "default_text": "Assalomu alaykum! Hozir ta'tildaman. Xabaringizni qaytganimdan so'ng ko'rib chiqaman. Agar juda shoshilinch bo'lsa, 'SHOSHILINCH' deb yozing."
    },
    "ai": {
        "title": "🤖 AI Kotib (Aqlli)",
        "desc": "Sun'iy intellekt xabarga mos xushmuomala javob qaytaradi",
        "default_text": ""
    },
    "custom": {
        "title": "✏️ Shaxsiy matn",
        "desc": "Foydalanuvchi o'zi kiritgan maxsus matn",
        "default_text": "Salom! Men hozir xabaringizga javob bera olmayapman. Tez orada bog'lanaman."
    }
}

URGENT_KEYWORDS = [
    "shoshilinch", "shoshilinch!", "shoshilinchlik",
    "muhim", "muhim!",
    "tezkor", "tezda", "zudlik", "zudlik bilan",
    "avariya", "tez yordam", "hospital",
    "to'lov", "oplata", "pul o'tkazma",
    "urgent", "asap", "emergency",
    "срочно", "срочно!", "важно", "важно!"
]

class SecretaryService:
    """Shaxsiy Kotib / Sekretar Rejim xizmati"""

    @staticmethod
    def is_urgent_message(text: str) -> bool:
        """Xabarda shoshilinch kalit so'zlar bor-yo'qligini aniqlaydi"""
        if not text:
            return False
        text_lower = text.lower()
        for kw in URGENT_KEYWORDS:
            if re.search(r'\b' + re.escape(kw) + r'\b', text_lower) or kw in text_lower:
                return True
        return False

    @staticmethod
    def should_respond_to_sender(owner_id: int, sender_id: int, cooldown_seconds: int = 1800) -> bool:
        """Bir xil suhbatdoshga intervaldan (cooldown) tezroq qayta javob bermaslik"""
        last_time = get_secretary_last_sender_time(owner_id, sender_id)
        if last_time is None:
            return True
        now = time.time()
        return (now - last_time) >= cooldown_seconds

    @staticmethod
    def generate_auto_reply(
        mode: str,
        custom_text: str,
        message_text: str,
        sender_name: str,
        ai_instructions: str = ""
    ) -> str:
        """Tanlangan rejim bo'yicha avtojavob matnini tayyorlaydi"""
        if mode == "custom" and custom_text.strip():
            return custom_text.strip()

        if mode == "ai":
            # AI rejimida moslashuvchan javob
            prompt_context = ai_instructions.strip() if ai_instructions else "Men egam nomidan javob beruvchi shaxsiy kotibman."
            # Aqlli xushmuomala avtojavob
            return (
                f"🤖 Assalomu alaykum, {sender_name}!\n\n"
                f"Men shaxsiy AI-kotibman. Hozirda akkaunt egasi band bo'lganligi sababli "
                f"xabaringizni qabul qilib oldim va unga yetkazdim.\n"
                f"U bo'shashi bilanoq sizga shaxsan javob qaytaradi."
            )

        mode_info = SECRETARY_MODES.get(mode, SECRETARY_MODES["busy"])
        text = mode_info["default_text"]
        return f"🤖 [Avto-Kotib]\n{text}"

    @staticmethod
    def format_logs_digest(logs: List[Dict[str, Any]]) -> str:
        """Qabul qilingan xabarlar hisobotini tayyorlaydi"""
        if not logs:
            return "📭 Hozircha kotib tomonidan qayd etilgan xabarlar mavjud emas."

        res = f"📋 <b>Kotib qabul qilgan so'nggi {len(logs)} ta xabar:</b>\n\n"
        for idx, l in enumerate(logs, 1):
            urgent_badge = "🚨 <b>[SHOSHILINCH]</b> " if l.get("is_urgent") else ""
            sender = l.get("sender_name", "Noma'lum")
            username = f" (@{l.get('sender_username')})" if l.get("sender_username") else ""
            msg = (l.get("message_text") or "")[:70]
            if len(l.get("message_text") or "") > 70:
                msg += "..."
            dt = l.get("created_at", "")[:16]
            res += f"{idx}. {urgent_badge}<b>{sender}</b>{username} <i>({dt})</i>\n"
            res += f"   💬 <i>\"{msg}\"</i>\n\n"
        return res

secretary_service = SecretaryService()
