import logging
import json
import re
import base64
import aiohttp
from typing import Optional, List, Dict, Any
from src.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

# Qisqa minnatdorchilik va reaktsiya so'zlari (avto-javob talab qilmaydi)
ACKNOWLEDGMENT_WORDS = {
    "rahmat", "katta rahmat", "raxmat", "tashakkur", "spasibo", "spasib", "thanks", "thank you", "thx",
    "ok", "okk", "oke", "xop", "hop", "mayli", "tushundim", "yaxshi", "boldi", "bo'ldi",
    "tushunarli", "ha", "xa", "yoq", "yo'q", "da", "net", "aha", "mhm", "bopti", "kelishdik",
    "kettik", "qoyil", "gap yoq", "gap yo'q", "sog", "boling", "salomat", "katta"
}

# Aniq savol yoki muhim murojaat kalit so'zlari
QUESTION_KEYWORDS = {
    "narx", "narxi", "qancha", "nechi", "necha", "qachon", "qayerda", "qayer", "qanday",
    "nima", "nimaga", "nega", "sabab", "kim", "qaysi", "pochemu", "zachem", "chto",
    "bormi", "mumkinmi", "boladimi", "bo'ladimi", "telefon", "nomer", "manzil", "buyurtma",
    "zakaz", "skolko", "cena", "stoit", "kogda", "gde", "kak", "mojno", "nomera", "adres",
    "usluga", "xizmat", "sayt", "bot", "dastur", "kurs", "kursi", "dollor", "dollar", "som",
    "so'm", "variant", "tolov", "to'lov", "bepul", "chegirma", "aloqa", "ishlaydimi", "qilasizmi"
}

# Suhbatdosh munosabatini aniqlovchi kalit so'zlar
FAMILY_KEYWORDS = [
    "ona", "onam", "onajon", "ota", "otam", "otajon", "dada", "dadam", "dadajon",
    "oyi", "oyijon", "bolam", "o'g'lim", "oglim", "qizim", "uyga", "kelasanmi",
    "dori", "bozorlik", "ovqat"
]

FRIEND_KEYWORDS = [
    "brat", "jigar", "jo'ra", "jora", "qattasan", "bormisan", "qalesan", "tinchmi",
    "choyxona", "osh", "gap", "o'rtoq", "ortoq", "og'ayni", "ogayni", "oshna"
]

STUDENT_KEYWORDS = [
    "domla", "ustoz", "muallim", "dars", "vazifa", "para", "oraliq",
    "imtihon", "baho", "topshiriq", "konspekt", "yakuniy", "nb"
]

COLLEAGUE_KEYWORDS = [
    "yig'ilish", "majlis", "loyiha", "hisobot", "xodim", "hujjat", "reja", "otchet"
]

def clean_text_for_matching(text: str) -> str:
    """Belgilarni olib tashlab, toza kichik harfli matn qaytaradi"""
    if not text:
        return ""
    cleaned = re.sub(r'[^\w\s]', '', text.lower()).strip()
    return cleaned

def is_acknowledgment_only(text: str) -> bool:
    """Xabar faqat qisqa minnatdorchilik yoki oddiy reaktsiya ekanini tekshiradi"""
    if not text:
        return True
    
    clean = clean_text_for_matching(text)
    if not clean:
        return True
    
    words = clean.split()
    if len(words) <= 5:
        if clean in ACKNOWLEDGMENT_WORDS:
            return True
        if all(w in ACKNOWLEDGMENT_WORDS for w in words):
            return True

    return False

def is_meaningful_query_or_question(text: str) -> bool:
    """Xabarda savol yoki muhim mazmun bor-yo'qligini tekshiradi"""
    if not text:
        return False
    
    if "?" in text:
        return True
    
    clean = clean_text_for_matching(text)
    words = set(clean.split())

    if words.intersection(QUESTION_KEYWORDS):
        return True
    
    if any(w in clean for w in ["nimaga", "qachon", "qayerda", "narx", "domla"]):
        return True

    if len(words) >= 4 and len(text.strip()) >= 15:
        return True

    return False

def build_adaptive_system_prompt(owner_name: str, sender_name: str, ai_instructions: str) -> str:
    """Suhbatdosh toifasini tushunuvchi aqlli moslashuvchan tizim yo'riqnomasi"""
    inst_text = ai_instructions.strip() if ai_instructions else "Hozircha maxsus yo'riqnoma yo'q."
    return (
        f"Siz {owner_name}ning shaxsiy Telegram akkauntiga kelgan xabarlarga javob beruvchi nihoyatda fahmli, samimiy va aqlli yordamchisiz.\n\n"
        f"DIQQAT! Sizga yozayotgan har bir inson mijoz EMAS! Yozgan odamning munosabatini (kimligini) xabar mazmuni, murojaat so'zlari va ohangidan ANQLANG va shunga mos ohangda javob bering:\n\n"
        f"1. 👨‍👩‍👧 OILA VA OTA-ONA (Murojaatda: ona, ota, bolam, o'g'lim, qizim, dada, oyi, uyga, kelasanmi, qayerdasan, dori, bozor... bo'lsa):\n"
        f"   - Ohang: Juda mehrli, iliq, samimiy va hurmat bilan.\n"
        f"   - HECH QACHON «Men AI-kotibman», «Hurmat bilan AI-kotib» deb robotdek yozmang! Ota-onani cho'chitmaslik kerak.\n"
        f"   - Javob namunasi: «Assalomu alaykum, Onajon/Dadajon! Xabaringizni ko'rdilar, hozir biroz band edilar. Bo'shashlari bilanoq darhol o'zlari sizga telefon qiladilar.»\n\n"
        f"2. 🤝 DO'STLAR VA OG'AYNILAR (Murojaatda: brat, jigar, jo'ra, qattasan, bormisan, qalesan, tinchmi, choyxona, o'rtoq, oshna... bo'lsa):\n"
        f"   - Ohang: Norasmiy, sodda, do'stona, qisqa.\n"
        f"   - Hech qanday rasmiy imzo qo'ymang.\n"
        f"   - Javob namunasi: «Salom! Hozir qo'li band edi, bo'shashi bilan o'zi aloqaga chiqadi / telefon qiladi.»\n\n"
        f"3. 🎓 TALABALAR VA SHOGIRDLAR (Murojaatda: domla, ustoz, muallim, dars, vazifa, para, oraliq, imtihon, baho, topshiriq... bo'lsa):\n"
        f"   - Ohang: Madaniyatli, ustoz-shogird munosabatiga mos, jiddiy va xushmuomala.\n"
        f"   - Javob namunasi: «Assalomu alaykum! Xabaringiz yetkazildi, domla/ustoz hozir band edilar, bo'shashlari bilan dars/vazifa bo'yicha javob beradilar.»\n\n"
        f"4. 💼 HAMKASBLAR VA ISHCHILAR (Murojaatda: yig'ilish, majlis, loyiha, hisobot, xodim, hujjat, reja, otchet... bo'lsa):\n"
        f"   - Ohang: Professional, ishchan va hurmat bilan.\n"
        f"   - Javob namunasi: «Assalomu alaykum! Xabaringiz qabul qilindi, hozir ish jarayonida band bo'lganliklari sababli bo'shashlari bilan aloqaga chiqadilar.»\n\n"
        f"5. 🛍 MIJOZLAR VA NOMA'LUM SHAXSLAR (Narx, xizmat, buyurtma, sotib olish, dastur, shartnoma haqida so'rasa):\n"
        f"   - Ohang: Xushmuomala, professional va yordam beruvchi.\n"
        f"   - Quyidagi shaxsiy yo'riqnomadan foydalanib qisqa ma'lumot bering.\n"
        f"   - Xabar oxirida «Hurmat bilan, {owner_name} yordamchisi 🤖» deb yakunlashingiz mumkin.\n\n"
        f"--- EGASINING YO'RIQNOMASI VA SOHASI ---\n"
        f"{inst_text}\n"
        f"----------------------------------------\n"
        f"UMUMIY QOIDALAR:\n"
        f"- Agar avvalgi xabarlarda salomlashilgan bo'lsa, qayta salom bermang!\n"
        f"- Hech qachon o'zingizdan moliyaviy va'da bermang, qarz bermang, pul masalasini egasining o'zi bilan gaplashishni ayting.\n"
        f"- Xabar qaysi tilda (o'zbek, rus yoki ingliz) kelgan bo'lsa, xuddi o'sha tilda javob bering.\n"
        f"- Javob juda cho'zilib ketmasin (ko'pi bilan 1-2 ta tabiiy va samimiy gap).\n"
    )

class AISecretaryService:
    """Google Gemini 1.5 Flash asosidagi Shaxsiy AI Kotib xizmati"""

    @staticmethod
    async def generate_ai_reply(
        sender_name: str,
        message_text: str,
        ai_instructions: str = "",
        owner_name: str = "Akkaunt egasi",
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """Kelgan xabarga mos aqlli, xushmuomala va kontekstual avto-javob tayyorlaydi"""
        api_key = GEMINI_API_KEY.strip() if GEMINI_API_KEY else ""

        if api_key:
            try:
                system_prompt = build_adaptive_system_prompt(owner_name, sender_name, ai_instructions)

                contents: List[Dict[str, Any]] = []
                if chat_history:
                    last_role = None
                    for turn in chat_history[-4:]:
                        r = "user" if turn.get("role") == "user" else "model"
                        t = (turn.get("text") or "").strip()
                        if not t:
                            continue
                        if r == last_role:
                            contents[-1]["parts"][0]["text"] += f"\n{t}"
                        else:
                            contents.append({"role": r, "parts": [{"text": t}]})
                            last_role = r

                    while contents and contents[0]["role"] != "user":
                        contents.pop(0)

                current_text = f"Suhbatdosh ({sender_name}): \"{message_text}\""
                if contents and contents[-1]["role"] == "user":
                    contents[-1]["parts"][0]["text"] += f"\n{current_text}"
                else:
                    contents.append({
                        "role": "user",
                        "parts": [{"text": current_text}]
                    })

                payload = {
                    "contents": contents,
                    "systemInstruction": {
                        "parts": [{"text": system_prompt}]
                    },
                    "generationConfig": {
                        "temperature": 0.6,
                        "maxOutputTokens": 250,
                        "topP": 0.95
                    }
                }

                url = f"{GEMINI_API_URL}?key={api_key}"
                timeout = aiohttp.ClientTimeout(total=7)

                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, json=payload) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            candidates = data.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                if parts:
                                    reply_text = parts[0].get("text", "").strip()
                                    if reply_text:
                                        return reply_text
                        else:
                            err_txt = await resp.text()
                            logger.warning(f"Gemini API xatosi ({resp.status}): {err_txt[:200]}")
            except Exception as e:
                logger.error(f"Gemini API bilan ulanishda xatolik: {e}")

        # Zaxira (Smart Fallback)
        return AISecretaryService._generate_smart_fallback(
            sender_name=sender_name,
            message_text=message_text,
            ai_instructions=ai_instructions,
            owner_name=owner_name,
            has_history=bool(chat_history)
        )

    @staticmethod
    async def generate_ai_voice_reply(
        sender_name: str,
        audio_bytes: bytes,
        mime_type: str = "audio/ogg",
        ai_instructions: str = "",
        owner_name: str = "Akkaunt egasi",
        chat_history: Optional[List[Dict[str, str]]] = None
    ) -> str:
        """Kelgan ovozli xabarni eshitib, suhbatdosh toifasiga mos aqlli javob qaytaradi"""
        api_key = GEMINI_API_KEY.strip() if GEMINI_API_KEY else ""

        if api_key and audio_bytes:
            try:
                system_prompt = build_adaptive_system_prompt(owner_name, sender_name, ai_instructions)
                b64_audio = base64.b64encode(audio_bytes).decode("utf-8")

                contents: List[Dict[str, Any]] = []
                if chat_history:
                    last_role = None
                    for turn in chat_history[-4:]:
                        r = "user" if turn.get("role") == "user" else "model"
                        t = (turn.get("text") or "").strip()
                        if not t:
                            continue
                        if r == last_role:
                            contents[-1]["parts"][0]["text"] += f"\n{t}"
                        else:
                            contents.append({"role": r, "parts": [{"text": t}]})
                            last_role = r

                    while contents and contents[0]["role"] != "user":
                        contents.pop(0)

                audio_part = {
                    "inlineData": {
                        "mimeType": mime_type,
                        "data": b64_audio
                    }
                }
                text_part = {
                    "text": f"Suhbatdosh ({sender_name}) ovozli xabar yubordi. Iltimos, audioni tinglab, uning gapiga toifasiga mos ohangda javob bering."
                }

                contents.append({
                    "role": "user",
                    "parts": [audio_part, text_part]
                })

                payload = {
                    "contents": contents,
                    "systemInstruction": {
                        "parts": [{"text": system_prompt}]
                    },
                    "generationConfig": {
                        "temperature": 0.5,
                        "maxOutputTokens": 300,
                        "topP": 0.95
                    }
                }

                url = f"{GEMINI_API_URL}?key={api_key}"
                timeout = aiohttp.ClientTimeout(total=12)

                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(url, json=payload) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            candidates = data.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                if parts:
                                    reply_text = parts[0].get("text", "").strip()
                                    if reply_text:
                                        return reply_text
                        else:
                            err_txt = await resp.text()
                            logger.warning(f"Gemini Voice API xatosi ({resp.status}): {err_txt[:200]}")
            except Exception as e:
                logger.error(f"Gemini Voice API bilan ulanishda xatolik: {e}")

        # Zaxira (Fallback)
        lower_msg = "ovozli xabar"
        info_part = ""
        if ai_instructions.strip():
            first_line = ai_instructions.strip().split("\n")[0][:120]
            info_part = f"\n\nℹ️ <i>Ma'lumot uchun: {first_line}</i>"

        return (
            f"🎙 <b>Ovozli xabaringiz qabul qilindi.</b>\n"
            f"Hozirda band bo'lganliklari sababli, bo'shashlari bilanoq ovozli xabaringizni eshitib, sizga aloqaga chiqadilar.{info_part}"
        )

    @staticmethod
    def _generate_smart_fallback(
        sender_name: str,
        message_text: str,
        ai_instructions: str = "",
        owner_name: str = "Akkaunt egasi",
        has_history: bool = False
    ) -> str:
        """Gemini ulanmagan yoki xatolik yuz berganda suhbatdosh toifasiga mos aqlli javob"""
        lower_msg = (message_text or "").lower()
        sender_lower = (sender_name or "").lower()
        combined_text = f"{lower_msg} {sender_lower}"

        words = set(re.findall(r'\b\w+\b', combined_text.lower()))
        for w in combined_text.lower().replace("'", "").replace("‘", "").replace("`", "").split():
            words.add(w)

        # 1. Oila va Ota-ona (ona, ota, dada, oyi, bolam, o'g'lim, uyga...)
        if words.intersection(set(FAMILY_KEYWORDS)):
            return (
                "Assalomu alaykum! Xabaringizni ko'rdilar, hozir biroz band bo'lganliklari sababli "
                "bo'shashlari bilanoq darhol o'zlari sizga telefon qiladilar."
            )

        # 2. Do'stlar va Og'aynilar (brat, jigar, jo'ra, qattasan, choyxona...)
        if words.intersection(set(FRIEND_KEYWORDS)):
            return "Salom! Hozir qo'li band edi, bo'shashi bilan o'zi aloqaga chiqadi."

        # 3. Talabalar va Shogirdlar (domla, ustoz, dars, vazifa, para...)
        if words.intersection(set(STUDENT_KEYWORDS)):
            return (
                "Assalomu alaykum! Xabaringiz yetkazildi, ustoz/domla hozir band edilar, "
                "bo'shashlari bilan dars/vazifa bo'yicha javob yozadilar."
            )

        # 4. Hamkasblar (yig'ilish, hisobot, majlis, xodim...)
        if words.intersection(set(COLLEAGUE_KEYWORDS)):
            return (
                "Assalomu alaykum! Xabaringiz qabul qilindi, hozir ish jarayonida band bo'lganliklari "
                "sababli bo'shashlari bilan aloqaga chiqadilar."
            )

        # 5. Mijozlar va umumiy murojaatlar
        info_part = ""
        if ai_instructions.strip():
            first_line = ai_instructions.strip().split("\n")[0][:120]
            info_part = f"\n\nℹ️ <i>Ma'lumot uchun: {first_line}</i>"

        if has_history:
            if any(w in lower_msg for w in ["narx", "kurs", "necha pul", "qancha", "cena", "skolko", "price"]):
                context_reply = "Narxlar bo'yicha savolingiz yetkazildi. Bo'shashlari bilanoq to'liq ma'lumot beradilar."
            else:
                context_reply = "Xabaringiz qabul qilindi. Hozirda band bo'lganliklari sababli bo'shashlari bilan javob qaytaradilar."

            return f"🤖 {context_reply}{info_part}\n\n<i>Hurmat bilan, {owner_name} yordamchisi 🤖</i>"

        greeting = f"Assalomu alaykum, {sender_name}!" if sender_name and sender_name != "Mijoz" else "Assalomu alaykum!"

        if any(w in lower_msg for w in ["narx", "kurs", "necha pul", "qancha", "cena", "skolko", "price"]):
            context_reply = "Narxlar va xizmatlar bo'yicha so'rovingiz qabul qilindi. Tez orada batafsil javob qaytaradilar."
        elif any(w in lower_msg for w in ["uchrashuv", "vaqt", "qachon", "ko'rishamiz", "vstrecha", "kogda"]):
            context_reply = "Uchrashuv va vaqt masalasidagi xabaringiz yetkazildi. Bo'sh vaqtlarini tekshirib aloqaga chiqadilar."
        else:
            context_reply = f"Hozirda {owner_name} band bo'lganliklari sababli xabaringizni qabul qilib oldim. Bo'shashlari bilanoq javob yozadilar."

        return (
            f"🤖 {greeting}\n\n"
            f"{context_reply}{info_part}\n\n"
            f"<i>Hurmat bilan, {owner_name} yordamchisi 🤖</i>"
        )

ai_secretary_service = AISecretaryService()
generate_ai_reply = AISecretaryService.generate_ai_reply
generate_ai_voice_reply = AISecretaryService.generate_ai_voice_reply
