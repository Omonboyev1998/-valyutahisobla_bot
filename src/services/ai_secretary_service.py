import logging
import json
import re
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

def clean_text_for_matching(text: str) -> str:
    """Belgilarni olib tashlab, toza kichik harfli matn qaytaradi"""
    if not text:
        return ""
    # Emojilar va tinish belgilarini olib tashlaymiz
    cleaned = re.sub(r'[^\w\s]', '', text.lower()).strip()
    return cleaned

def is_acknowledgment_only(text: str) -> bool:
    """Xabar faqat qisqa minnatdorchilik yoki oddiy reaktsiya ekanini tekshiradi"""
    if not text:
        return True
    
    clean = clean_text_for_matching(text)
    # Agar faqat emojilardan iborat bo'lsa
    if not clean:
        return True
    
    words = clean.split()
    # Agar 5 ta so'zdan kam bo'lsa va so'zlarning barchasi minnatdorchilik bo'lsa
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
    
    # 1. Savol belgisi bo'lsa
    if "?" in text:
        return True
    
    clean = clean_text_for_matching(text)
    words = set(clean.split())

    # 2. Savol kalit so'zlari bo'lsa
    if words.intersection(QUESTION_KEYWORDS):
        return True
    
    # 3. Yoki kamida 4 ta so'zdan iborat to'liq gap bo'lsa
    if len(words) >= 4 and len(text.strip()) >= 15:
        return True

    return False

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

        # Agar API kalit bo'lsa, Gemini 1.5 Flash ga so'rov yuboramiz
        if api_key:
            try:
                inst_text = ai_instructions.strip() if ai_instructions else ""
                if not inst_text:
                    inst_text = "Hozircha maxsus yo'riqnoma yo'q. Faqat xabarni qabul qilganingizni va ega bo'shashi bilan aloqaga chiqishini ayting."

                system_prompt = (
                    f"Siz {owner_name}ning shaxsiy, muloyim va yordamchi AI-kotibisiz.\n"
                    f"Siz {owner_name}ning Telegram akkauntiga kelgan xabarlarga javob yozasiz.\n\n"
                    f"VAZIFANGIZ:\n"
                    f"1. Suhbatdoshga ({sender_name}) xushmuomala, iliq va professional ohangda qisqa javob yozing.\n"
                    f"2. Agar avvalgi xabarlarda salomlashilgan bo'lsa (tarixda ko'rinsa), qayta salomlashmang! To'g'ridan-to'g'ri savolga yoki mavzuga javob bering.\n"
                    f"3. Kelgan xabar mazmunini tushungan holda, murojaatni qabul qilganingizni va {owner_name} hozirda bandligi sababli, bo'shashi bilanoq o'zi javob yozishini bildiring.\n"
                    f"4. Quyida {owner_name} tomonidan kiritilgan shaxsiy yo'riqnomalar berilgan. Agar suhbatdoshning savoliga shu yo'riqnomada javob bo'lsa, muloyimlik bilan qisqacha ma'lumot bering:\n"
                    f"--- EGASINING YO'RIQNOMASI ---\n"
                    f"{inst_text}\n"
                    f"------------------------------\n"
                    f"5. QOIDALAR:\n"
                    f"- Hech qachon o'zingizdan moliyaviy va'da bermang, qarz bermang, pul masalasini egasining o'zi bilan gaplashishni ayting.\n"
                    f"- Xabar qaysi tilda kelgan bo'lsa (o'zbek, rus yoki ingliz), xuddi o'sha tilda javob bering.\n"
                    f"- Javob ixcham bo'lsin (ko'pi bilan 2-3 ta chiroyli gap).\n"
                    f"- Xabar oxirida yangi qatordan «Hurmat bilan, {owner_name}ning shaxsiy AI-kotibi 🤖» deb yakunlang.\n"
                )

                # Dialog tarixini Gemini formatiga moslaymiz
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

                    # Gemini talabi: birinchi element user bo'lishi kerak
                    while contents and contents[0]["role"] != "user":
                        contents.pop(0)

                # Joriy xabarni qo'shamiz
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
                        "parts": [
                            {"text": system_prompt}
                        ]
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

        # Zaxira (Smart Fallback) avtojavob mantiqi (Agar API kalit bo'lmasa yoki tarmoqda xatolik bo'lsa)
        return AISecretaryService._generate_smart_fallback(
            sender_name=sender_name,
            message_text=message_text,
            ai_instructions=ai_instructions,
            owner_name=owner_name,
            has_history=bool(chat_history)
        )

    @staticmethod
    def _generate_smart_fallback(
        sender_name: str,
        message_text: str,
        ai_instructions: str = "",
        owner_name: str = "Akkaunt egasi",
        has_history: bool = False
    ) -> str:
        """Gemini ulanmagan yoki xatolik yuz berganda xushmuomala aqlli javob"""
        lower_msg = (message_text or "").lower()

        # Agar maxsus yo'riqnoma kiritilgan bo'lsa, qisqacha qo'shamiz
        info_part = ""
        if ai_instructions.strip():
            first_line = ai_instructions.strip().split("\n")[0][:120]
            info_part = f"\n\nℹ️ <i>Ma'lumot uchun: {first_line}</i>"

        # Agar bu davom etayotgan suhbat bo'lsa, qayta salom bermaymiz
        if has_history:
            if any(w in lower_msg for w in ["narx", "kurs", "necha pul", "qancha", "cena", "skolko", "price"]):
                context_reply = "Narxlar bo'yicha savolingiz yetkazildi. Bo'shashlari bilanoq to'liq ma'lumot beradilar."
            else:
                context_reply = "Xabaringiz qabul qilindi. Hozirda band bo'lganliklari sababli bo'shashlari bilan javob qaytaradilar."

            return (
                f"🤖 {context_reply}{info_part}\n\n"
                f"<i>Hurmat bilan, {owner_name}ning shaxsiy AI-kotibi 🤖</i>"
            )

        greeting = f"Assalomu alaykum, {sender_name}!" if sender_name and sender_name != "Mijoz" else "Assalomu alaykum!"

        if any(w in lower_msg for w in ["salom", "qalesiz", "qalaysiz", "yaxshimisiz", "privet", "hello"]):
            context_reply = "Xabaringizni qabul qilib oldim. Hozirda telefon yonida emas edilar, bo'shashlari bilan sizga aloqaga chiqadilar."
        elif any(w in lower_msg for w in ["narx", "kurs", "necha pul", "qancha", "cena", "skolko", "price"]):
            context_reply = "Narxlar va xizmatlar bo'yicha so'rovingiz qabul qilindi. Tez orada batafsil javob qaytaradilar."
        elif any(w in lower_msg for w in ["uchrashuv", "vaqt", "qachon", "ko'rishamiz", "vstrecha", "kogda"]):
            context_reply = "Uchrashuv va vaqt masalasidagi xabaringiz yetkazildi. Bo'sh vaqtlarini tekshirib aloqaga chiqadilar."
        else:
            context_reply = f"Men {owner_name}ning shaxsiy AI-kotibisiz. Hozirda ular band bo'lganligi sababli xabaringizni qabul qilib oldim va ularga yetkazdim. Bo'shashlari bilanoq javob yozadilar."

        return (
            f"🤖 {greeting}\n\n"
            f"{context_reply}{info_part}\n\n"
            f"<i>Hurmat bilan, {owner_name}ning shaxsiy AI-kotibi 🤖</i>"
        )

ai_secretary_service = AISecretaryService()
generate_ai_reply = AISecretaryService.generate_ai_reply
