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
    def should_respond_to_sender(
        owner_id: int,
        sender_id: int,
        cooldown_seconds: int = 300,
        message_text: str = "",
        mode: str = "busy"
    ) -> bool:
        """Bir xil suhbatdoshga intervaldan (cooldown) tezroq qayta javob bermaslik va aqlli filtrlash"""
        from src.services.ai_secretary_service import is_acknowledgment_only, is_meaningful_query_or_question

        # 1. Agar xabar faqat qisqa minnatdorchilik yoki oddiy reaksiya bo'lsa (rahmat, ok, hop, emoji), javob bermaymiz
        if is_acknowledgment_only(message_text):
            return False

        last_time = get_secretary_last_sender_time(owner_id, sender_id)
        if last_time is None:
            return True

        now = time.time()
        elapsed = now - last_time

        # 2. Agar belgilangan tanaffus (cooldown) vaqti to'liq o'tgan bo'lsa, javob beramiz
        if elapsed >= cooldown_seconds:
            return True

        # 3. Agar AI rejimida bo'lsa va suhbatdosh aniq savol yoki muhim so'rov berayotgan bo'lsa,
        # kamida 4 soniya o'tganidan so'ng javob berishga ruxsat beramiz
        if mode == "ai" and elapsed >= 4 and is_meaningful_query_or_question(message_text):
            return True

        return False

    @staticmethod
    def get_current_tashkent_time_str() -> str:
        """Toshkent vaqti (UTC+5) bo'yicha joriy HH:MM ni oladi"""
        tz_tashkent = timezone(timedelta(hours=5))
        now_dt = datetime.now(tz_tashkent)
        return now_dt.strftime("%H:%M")

    @staticmethod
    def get_detailed_time_context() -> Dict[str, Any]:
        """Toshkent vaqti bo'yicha soat, sutka qismi va haftaning kunini oladi"""
        tz_tashkent = timezone(timedelta(hours=5))
        now = datetime.now(tz_tashkent)
        hour = now.hour
        weekday_idx = now.weekday()
        days_uz = ["Dushanba", "Seshanba", "Chorshanba", "Payshanba", "Juma", "Shanba", "Yakshanba"]
        day_name = days_uz[weekday_idx]
        is_weekend = (weekday_idx in [5, 6])

        if 5 <= hour < 11:
            time_period = "tong"
            period_name = "ertalabki vaqt"
            period_greeting = "Xayrli tong!"
            period_note = "Hozir ertalabki reja va yo'l vaqti."
        elif 11 <= hour < 18:
            time_period = "kunduz"
            period_name = "faol ish/dars vaqti"
            period_greeting = "Assalomu alaykum!"
            period_note = "Hozir faol ish / dars vaqti."
        elif 18 <= hour < 23:
            time_period = "oqshom"
            period_name = "kechki vaqt"
            period_greeting = "Xayrli kech!"
            period_note = "Hozir ishdan keyingi kechki vaqt."
        else:
            time_period = "tun"
            period_name = "dam olish / uyqu vaqti"
            period_greeting = "Assalomu alaykum!"
            period_note = "Hozir tun, dam olish va uyqu vaqti."

        return {
            "time_str": now.strftime("%H:%M"),
            "date_str": now.strftime("%Y-%m-%d"),
            "day_name": day_name,
            "is_weekend": is_weekend,
            "time_period": time_period,
            "period_name": period_name,
            "period_greeting": period_greeting,
            "period_note": period_note
        }

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
    async def generate_auto_reply(
        mode: str,
        custom_text: str,
        message_text: str,
        sender_name: str,
        ai_instructions: str = "",
        user_id: Optional[int] = None,
        owner_name: str = "Akkaunt egasi",
        chat_history: Optional[List[Dict[str, str]]] = None,
        busy_reason: str = "",
        emergency_phone: str = "",
        is_urgent: bool = False,
        time_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """Tanlangan rejim yoki vaqt jadvali bo'yicha avtojavob matnini tayyorlaydi"""
        if not time_info:
            time_info = SecretaryService.get_detailed_time_context()

        # 1. Agar vaqt jadvallari rejimi tanlangan bo'lsa (yoki user_id berilgan bo'lsa)
        if mode == "schedule" and user_id:
            sched = SecretaryService.get_active_scheduled_reply(user_id)
            if sched and sched.get("reply_text"):
                sched_title = sched.get("title") or f"{sched.get('start_time')} - {sched.get('end_time')}"
                return f"🤖 [Avto-Kotib • {sched_title}]\n{sched['reply_text']}"

        # 2. Shaxsiy matn
        if mode == "custom" and custom_text.strip():
            return custom_text.strip()

        # 3. AI Kotib (Google Gemini 1.5 Flash)
        if mode == "ai":
            try:
                from src.services.ai_secretary_service import ai_secretary_service
                return await ai_secretary_service.generate_ai_reply(
                    sender_name=sender_name,
                    message_text=message_text,
                    ai_instructions=ai_instructions,
                    owner_name=owner_name,
                    chat_history=chat_history,
                    time_info=time_info,
                    busy_reason=busy_reason,
                    emergency_phone=emergency_phone,
                    is_urgent=is_urgent
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"AI auto reply xatoligi: {e}")

        # 4. Standart rejimlar
        mode_info = SECRETARY_MODES.get(mode, SECRETARY_MODES["busy"])
        text = mode_info["default_text"]
        phone_part = f"\n\n📞 Shoshilinch bo'lsa: {emergency_phone}" if (is_urgent and emergency_phone) else ""
        return f"🤖 [Avto-Kotib]\n{text}{phone_part}"

    @staticmethod
    async def generate_auto_voice_reply(
        mode: str,
        custom_text: str,
        sender_name: str,
        audio_bytes: bytes,
        mime_type: str = "audio/ogg",
        ai_instructions: str = "",
        user_id: Optional[int] = None,
        owner_name: str = "Akkaunt egasi",
        chat_history: Optional[List[Dict[str, str]]] = None,
        busy_reason: str = "",
        emergency_phone: str = "",
        is_urgent: bool = False,
        time_info: Optional[Dict[str, Any]] = None
    ) -> str:
        """Kelgan ovozli xabarga rejim bo'yicha mos avtojavob tayyorlaydi"""
        if not time_info:
            time_info = SecretaryService.get_detailed_time_context()

        # 1. AI Rejimi bo'lsa - Gemini 1.5 ga audioni to'g'ridan-to'g'ri yuboramiz
        if mode == "ai":
            try:
                from src.services.ai_secretary_service import ai_secretary_service
                return await ai_secretary_service.generate_ai_voice_reply(
                    sender_name=sender_name,
                    audio_bytes=audio_bytes,
                    mime_type=mime_type,
                    ai_instructions=ai_instructions,
                    owner_name=owner_name,
                    chat_history=chat_history,
                    time_info=time_info,
                    busy_reason=busy_reason,
                    emergency_phone=emergency_phone,
                    is_urgent=is_urgent
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"AI voice auto reply xatoligi: {e}")

        # 2. Vaqt jadvali bo'lsa
        if mode == "schedule" and user_id:
            sched = SecretaryService.get_active_scheduled_reply(user_id)
            if sched and sched.get("reply_text"):
                sched_title = sched.get("title") or f"{sched.get('start_time')} - {sched.get('end_time')}"
                return f"🤖 [Avto-Kotib • {sched_title}]\n🎙 Ovozli xabaringiz qabul qilindi.\n{sched['reply_text']}"

        # 3. Shaxsiy matn
        if mode == "custom" and custom_text.strip():
            return f"🤖 [Avto-Kotib]\n🎙 Ovozli xabaringiz qabul qilindi.\n{custom_text.strip()}"

        # 4. Standart rejimlar
        mode_info = SECRETARY_MODES.get(mode, SECRETARY_MODES["busy"])
        text = mode_info["default_text"]
        phone_part = f"\n\n📞 Shoshilinch bo'lsa: {emergency_phone}" if (is_urgent and emergency_phone) else ""
        return f"🤖 [Avto-Kotib]\n🎙 Ovozli xabaringiz qabul qilindi. {text}{phone_part}"



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
