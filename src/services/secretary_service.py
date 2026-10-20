import time
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone, timedelta
from src.database import get_secretary_last_sender_time

SECRETARY_MODES = {
    "schedule": {
        "title": "⏰ Vaqt jadvallari (Avtomatik)",
        "desc": "Turli vaqtda turli avto-javoblar yuboradi",
        "default_text": "Assalomu alaykum! Hozir xabaringizga javob bera olmayapman."
    },
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
    def get_current_tashkent_time_str() -> str:
        """Toshkent vaqti (UTC+5) bo'yicha joriy HH:MM ni oladi"""
        tz_tashkent = timezone(timedelta(hours=5))
        now_dt = datetime.now(tz_tashkent)
        return now_dt.strftime("%H:%M")

    @staticmethod
    def get_active_scheduled_reply(user_id: int, now_time_str: str = None) -> Optional[Dict[str, Any]]:
        """Hozirgi vaqt oralig'iga mos keluvchi faol jadvalni aniqlaydi"""
        from src.database import get_secretary_schedules
        schedules = get_secretary_schedules(user_id)
        if not schedules:
            return None

        if not now_time_str:
            now_time_str = SecretaryService.get_current_tashkent_time_str()

        matching = []
        for s in schedules:
            if not s.get("is_active"):
                continue
            start = s.get("start_time", "00:00")
            end = s.get("end_time", "23:59")

            is_match = False
            if start <= end:
                is_match = (start <= now_time_str <= end)
                dur = (int(end[:2]) * 60 + int(end[3:5])) - (int(start[:2]) * 60 + int(start[3:5]))
            else:
                # Kechasi aylanuvchi oralig' (masalan: 23:00 - 08:00)
                is_match = (now_time_str >= start) or (now_time_str <= end)
                dur = (24 * 60 - (int(start[:2]) * 60 + int(start[3:5]))) + (int(end[:2]) * 60 + int(end[3:5]))

            if is_match:
                matching.append((dur, s))

        if matching:
            # Eng qisqa/aniq vaqt oralig'i birinchi o'ringa qo'yiladi
            matching.sort(key=lambda x: x[0])
            return matching[0][1]

        return None

    @staticmethod
    def generate_auto_reply(
        mode: str,
        custom_text: str,
        message_text: str,
        sender_name: str,
        ai_instructions: str = "",
        user_id: Optional[int] = None
    ) -> str:
        """Tanlangan rejim yoki vaqt jadvali bo'yicha avtojavob matnini tayyorlaydi"""
        # 1. Agar vaqt jadvallari rejimi tanlangan bo'lsa (yoki user_id berilgan bo'lsa)
        if mode == "schedule" and user_id:
            sched = SecretaryService.get_active_scheduled_reply(user_id)
            if sched and sched.get("reply_text"):
                sched_title = sched.get("title") or f"{sched.get('start_time')} - {sched.get('end_time')}"
                return f"🤖 [Avto-Kotib • {sched_title}]\n{sched['reply_text']}"

        # 2. Shaxsiy matn
        if mode == "custom" and custom_text.strip():
            return custom_text.strip()

        # 3. AI Kotib
        if mode == "ai":
            return (
                f"🤖 Assalomu alaykum, {sender_name}!\n\n"
                f"Men shaxsiy AI-kotibman. Hozirda akkaunt egasi band bo'lganligi sababli "
                f"xabaringizni qabul qilib oldim va unga yetkazdim.\n"
                f"U bo'shashi bilanoq sizga shaxsan javob qaytaradi."
            )

        # 4. Standart rejimlar
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

    @staticmethod
    def format_schedules_text(schedules: List[Dict[str, Any]]) -> str:
        """Vaqt jadvallari ro'yxatini matn ko'rinishida formatlaydi"""
        now_time = SecretaryService.get_current_tashkent_time_str()
        res = f"⏰ <b>Vaqt Oraliqlari Bo'yicha Avto-Javoblar:</b>\n"
        res += f"<i>(Hozirgi vaqt: <b>{now_time}</b>)</i>\n\n"

        if not schedules:
            res += "<i>Hozircha faol vaqt oraliqlari mavjud emas. Yangi oralig' qo'shishingiz mumkin.</i>"
            return res

        for idx, s in enumerate(schedules, 1):
            status = "🟢" if s.get("is_active") else "⚪️ (o'chiq)"
            title = s.get("title", "Oraliq")
            start = s.get("start_time")
            end = s.get("end_time")
            reply = s.get("reply_text", "")
            preview = (reply[:60] + "...") if len(reply) > 60 else reply
            res += f"{idx}. {status} <b>{start} - {end}</b> • <b>{title}</b>\n"
            res += f"   💬 <i>\"{preview}\"</i>\n\n"

        res += "<i>💡 Har bir vaqt oralig'ida o'sha vaqtga mos maxsus javob avtomatik yuboriladi.</i>"
        return res

secretary_service = SecretaryService()
