import logging
import json
import aiohttp
from typing import Optional
from src.config import GEMINI_API_KEY

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

class AISecretaryService:
    """Google Gemini 1.5 Flash asosidagi Shaxsiy AI Kotib xizmati"""

    @staticmethod
    async def generate_ai_reply(
        sender_name: str,
        message_text: str,
        ai_instructions: str = "",
        owner_name: str = "Akkaunt egasi"
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
                    f"Sizga {owner_name}ning shaxsiy Telegram akkauntiga yozgan odamning xabari keldi.\n\n"
                    f"VAZIFANGIZ:\n"
                    f"1. Suhbatdoshga (ismi: {sender_name}) juda xushmuomala, iliq va professional ohangda qisqa javob yozing.\n"
                    f"2. Kelgan xabar mazmunini tushungan holda, uning murojaatini qabul qilganingizni va {owner_name} hozirda band bo'lganligi sababli, bo'shashi bilanoq o'zi javob yozishini bildiring.\n"
                    f"3. Quyida {owner_name} tomonidan kiritilgan shaxsiy yo'riqnomalar berilgan. Agar suhbatdoshning savoliga shu yo'riqnomada javob bo'lsa, muloyimlik bilan qisqacha ma'lumot bering:\n"
                    f"--- EGASINING YO'RIQNOMASI ---\n"
                    f"{inst_text}\n"
                    f"------------------------------\n"
                    f"4. QOIDALAR:\n"
                    f"- Hech qachon o'zingizdan moliyaviy va'da bermang, qarz bermang, pul masalasini egasining o'zi bilan gaplashishni ayting.\n"
                    f"- Xabar qaysi tilda kelgan bo'lsa (o'zbek, rus yoki ingliz), xuddi o'sha tilda javob bering.\n"
                    f"- Javob juda cho'zilib ketmasin (ko'pi bilan 2-3 ta ixcham va chiroyli gap).\n"
                    f"- Xabar oxirida yangi qatordan «Hurmat bilan, {owner_name}ning shaxsiy AI-kotibi 🤖» deb yakunlang.\n"
                )

                payload = {
                    "contents": [
                        {
                            "role": "user",
                            "parts": [
                                {"text": f"Suhbatdosh ({sender_name}) yozgan xabar: \"{message_text}\""}
                            ]
                        }
                    ],
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
        return AISecretaryService._generate_smart_fallback(sender_name, message_text, ai_instructions, owner_name)

    @staticmethod
    def _generate_smart_fallback(
        sender_name: str,
        message_text: str,
        ai_instructions: str = "",
        owner_name: str = "Akkaunt egasi"
    ) -> str:
        """Gemini ulanmagan yoki xatolik yuz berganda xushmuomala aqlli javob"""
        greeting = f"Assalomu alaykum, {sender_name}!" if sender_name and sender_name != "Mijoz" else "Assalomu alaykum!"
        
        lower_msg = (message_text or "").lower()

        # Agar maxsus yo'riqnoma kiritilgan bo'lsa, qisqacha qo'shamiz
        info_part = ""
        if ai_instructions.strip():
            first_line = ai_instructions.strip().split("\n")[0][:120]
            info_part = f"\n\nℹ️ <i>Ma'lumot uchun: {first_line}</i>"

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

