import logging
import re
import json
import base64
from typing import Optional, Dict, Any, List
import aiohttp
from src.config import GEMINI_API_KEY
from src.keyboards.services import SERVICE_CATEGORIES, SERVICE_REGIONS

logger = logging.getLogger(__name__)

GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"

# Kategoriya kalit so'zlari (xizmat turini aniqlash uchun)
CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "🔧 Santexnika va quvurlar": [
        "santexnik", "santexnika", "truba", "quvur", "kran", "smesitel", "vanna", "unitaz",
        "kanalizatsiya", "ariston", "otopleniye", "isitish tizimi", "nasos", "tyopliy pol",
        "tyoply pol", "kotyol", "katyol", "vodoprovod"
    ],
    "⚡️ Elektr montaj va usta": [
        "elektrik", "elektr", "montaj", "provodka", "lyustra", "avtomat", "shit", "rozetka",
        "viklyuchatel", "kabel", "generator", "transformator"
    ],
    "🔨 Uy ta'miri va qurilish": [
        "tamir", "ta'mir", "remont", "qurilish", "suvoq", "shpaklyovka", "oboy", "kafel", "plitka",
        "gipsokarton", "patalok", "shift", "pol", "laminat", "tom yopish", "profmastil",
        "shifer", "beton", "fundament", "g'isht", "gisht", "ustachilik", "pardozlash", "fasad"
    ],
    "🐑 Qo'y yungini olish & Chorva": [
        "qo'y", "qoy", "qo'chqor", "qochqor", "yung", "jun", "yungini olish", "jun olish", "qirqish",
        "kallapocham", "kalla pocha", "chorva", "mol", "qassob", "somon", "beda", "em-xashak"
    ],
    "❄️ Konditsioner & Maishiy texnika": [
        "konditsioner", "konditsoner", "freon", "xolodilnik", "muzlatgich", "kir yuvish",
        "stiralnaya", "gaz plita", "duxovka", "televizor", "tv usta", "pilesos", "changyutgich"
    ],
    "🧹 Tozalash & Klining": [
        "klining", "tozalash", "uborka", "gilam yuvish", "parda yuvish", "xona tozalash",
        "fasad tozalash", "deraza yuvish"
    ],
    "🚗 Avtoulov ta'miri va usta": [
        "avto", "avtoulov", "mashina", "mator", "xodovoy", "kuzov", "kraska", "kolyosa", "balon",
        "shinomontaj", "vulkanizatsiya", "akkumulyator", "moy almashtirish", "zapchast", "detiling"
    ],
    "📦 Yuk tashish & Haydovchilik": [
        "yuk tashish", "damas", "labo", "gazel", "isuzu", "yuk", "dostavka", "taksi", "reys",
        "ko'chirish", "gruzoperevozki", "tashish xizmati"
    ],
    "🌱 Bog'bonlik va payvandlash": [
        "svarka", "payvandlash", "temir", "reshetka", "darvoza", "naves", "panjara",
        "bog'bon", "bogbon", "daraxt kesish", "butash", "ko'chat", "maysa", "gazon"
    ],
    "🗂 Boshqa maishiy xizmatlar": [
        "mebel", "shkaf", "oshxona mebeli", "eshik", "rom", "akfa", "alyumin", "plastik",
        "soatsoz", "etikdo'z", "poyabzal", "tikuvchi", "repetitor", "dars", "foto", "video"
    ]
}

# Xizmat ko'rsatishga xos bo'lgan harakat so'zlari
SERVICE_INTENT_WORDS = [
    "xizmat", "xizmati", "xizmatlari", "usta", "ustasi", "qilamiz", "ornatamiz", "o'rnatamiz",
    "tamirlaymiz", "ta'mirlaymiz", "quramiz", "tashiymiz", "kesamiz", "olamiz", "kelishamiz",
    "zakaz", "buyurtma", "arzon", "sifatli", "kafolat", "bajariladi", "bajarib beramiz"
]

# Reklama EMAS / Istisno so'zlar (masalan kimdir usta qidirayotgan bo'lsa yoki narsa sotayotgan bo'lsa)
NON_SERVICE_WORDS = [
    "kerak", "kerakmi", "bormi", "kim biladi", "qidiryapman", "sotiladi", "arenda", "ijara",
    "narxi qancha", "topib bering"
]

def extract_uzbek_phone(text: str) -> Optional[str]:
    """
    Matndan O'zbekiston telefon raqamini aniqlash va +998XXXXXXXXX formatga keltirish.
    """
    # 1. To'liq yoki qisqa formatdagi raqamlarni qidirish
    # Masalan: +998 90 123 45 67, 998901234567, 90 123 45 67, 90-123-45-67, 901234567
    pattern = r'(?:\+?998[\s\-]?)?(?:\(?\b(33|88|90|91|93|94|95|97|98|99|71|77|78|50|55)\b\)?[\s\-]?)(\d{3})[\s\-]?(\d{2})[\s\-]?(\d{2})'
    match = re.search(pattern, text)
    if match:
        code = match.group(1)
        part1 = match.group(2)
        part2 = match.group(3)
        part3 = match.group(4)
        return f"+998{code}{part1}{part2}{part3}"
    
    # 2. Oddiy 9 ta ketma-ket raqam
    digits_only = re.findall(r'\b(?:998)?(33|88|90|91|93|94|95|97|98|99|71|77|78|50|55\d{7})\b', re.sub(r'[\s\-\(\)]', '', text))
    if digits_only:
        num = digits_only[0]
        if len(num) == 9:
            return f"+998{num}"
        elif len(num) == 12 and num.startswith("998"):
            return f"+{num}"
            
    return None

def detect_category(text_lower: str) -> str:
    """Kalit so'zlar bo'yicha eng mos kategoriyani aniqlash"""
    best_category = "🗂 Boshqa maishiy xizmatlar"
    max_matches = 0

    for category, keywords in CATEGORY_KEYWORDS.items():
        matches = sum(1 for kw in keywords if kw in text_lower)
        if matches > max_matches:
            max_matches = matches
            best_category = category

    return best_category

def extract_price(text: str) -> str:
    """Matndan narxni aniqlash"""
    # Masalan: 50 000 so'm, 100 ming, kelishilgan, tekin
    lower = text.lower()
    if any(k in lower for k in ["kelishamiz", "kelishilgan", "kelishamz", "narxi kelishiladi"]):
        return "Kelishilgan holda"
    
    price_match = re.search(r'(\d+[\s\d]*)\s*(so\'?m|sum|ming|\$)', text, re.IGNORECASE)
    if price_match:
        return price_match.group(0).strip()
        
    return "Kelishilgan holda"

def parse_ad_heuristic(text: str, sender_info: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Qoidalar va Heuristics (Regex) asosida xabar reklama ekanligini aniqlash.
    """
    text_clean = text.strip()
    if len(text_clean) < 15:
        return None

    lower = text_clean.lower()
    phone = extract_uzbek_phone(text_clean)

    # Agar telefon raqam bo'lmasa, reklama sifatida qabul qilmaymiz (mijoz bog'lana olishi shart)
    if not phone:
        return None

    # Istisno: agar xabar usta QIDIRISH bo'lsa (masalan: "santexnik kerak", "kimda telefon bor?")
    # Lekin "menga kerak" bilan "arzon narxda kerak bo'lsa murojaat qiling" ni farqlash:
    is_seeking = False
    for non_kw in NON_SERVICE_WORDS:
        if non_kw in lower:
            # Agar "kerak bo'lsa murojaat qiling" kabi ibora bo'lmasa:
            if not ("kerak bo'lsa" in lower or "kerak bolsa" in lower or "murojaat" in lower):
                is_seeking = True
                break

    if is_seeking:
        return None

    # Xizmat ko'rsatish so'zlari borligini tekshirish
    has_service_intent = any(word in lower for word in SERVICE_INTENT_WORDS)
    matched_category = detect_category(lower)
    has_category_kw = matched_category != "🗂 Boshqa maishiy xizmatlar" or any(kw in lower for kw in CATEGORY_KEYWORDS["🗂 Boshqa maishiy xizmatlar"])

    if not (has_service_intent or has_category_kw):
        return None

    # Usta ismi
    sender_name = "Usta"
    sender_username = None
    if sender_info:
        fn = (sender_info.get("first_name") or "").strip()
        ln = (sender_info.get("last_name") or "").strip()
        sender_name = f"{fn} {ln}".strip() or sender_info.get("username") or "Usta"
        sender_username = sender_info.get("username")

    # Matndan usta ismini qidirish (masalan: "Ali usta", "Usta Jasur")
    name_match = re.search(r'([A-ZА-ЯЁ][a-zа-яё\']+)\s+usta|usta\s+([A-ZА-ЯЁ][a-zа-яё\']+)', text_clean, re.IGNORECASE)
    if name_match:
        found_name = name_match.group(1) or name_match.group(2)
        if len(found_name) > 2:
            sender_name = f"{found_name.capitalize()} Usta"

    # Sarlavha (Title) yaratish
    GREETING_PATTERNS = ["assalomu", "salom", "xayrli", "hurmatli", "yurtdoshlar", "aka-uka", "aka uka", "birodarlar"]
    lines = [line.strip() for line in text_clean.split("\n") if line.strip()]
    candidate_title = None
    for line in lines:
        l_lower = line.lower()
        if any(gp in l_lower for gp in GREETING_PATTERNS):
            continue
        if len(line) >= 5 and len(line) <= 60 and not any(ch in line for ch in ["+", "@", "http", ":"]):
            candidate_title = line
            break

    clean_cat_name = matched_category.split(" ", 1)[-1]
    title = candidate_title if candidate_title else f"{clean_cat_name} xizmati"

    # Region aniqlash (Default: Andijon / Xortum)
    region = "Andijon"
    for r in SERVICE_REGIONS:
        if r.lower() in lower:
            region = r
            break

    price = extract_price(text_clean)

    return {
        "is_service_ad": True,
        "title": title[:100],
        "master_name": sender_name[:50],
        "phone": phone,
        "username": sender_username,
        "category": matched_category,
        "description": text_clean[:800],
        "region": region,
        "price": price
    }

async def parse_ad_with_gemini(text: str, photo_bytes: Optional[bytes] = None, sender_info: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
    """
    Google Gemini 1.5 Flash orqali reklamani chuqur tahlil qilish va JSON chiqarish.
    """
    if not GEMINI_API_KEY:
        return parse_ad_heuristic(text, sender_info)

    prompt = f"""
Siz Telegram guruhlaridagi e'lonlarni tahlil qiluvchi aqlli agentsiz.
Vazifangiz: Berilgan xabar MAISHIY XIZMAT yoki USTA (santexnik, elektrik, uy ta'miri, yuk tashish, chorva, tozalash, mebel va h.k.) REKLAMASI ekanligini aniqlash.

Kategoriyalar ro'yxati (faqat shu ro'yxatdan birini tanlang):
- 🔧 Santexnika va quvurlar
- ⚡️ Elektr montaj va usta
- 🔨 Uy ta'miri va qurilish
- 🐑 Qo'y yungini olish & Chorva
- ❄️ Konditsioner & Maishiy texnika
- 🧹 Tozalash & Klining
- 🚗 Avtoulov ta'miri va usta
- 📦 Yuk tashish & Haydovchilik
- 🌱 Bog'bonlik va payvandlash
- 🗂 Boshqa maishiy xizmatlar

QOIDALAR:
1. Agar bu oddiy gaplashish, savol ("santexnik bormi?"), narsa sotish (mashina, telefon, velosiped sotiladi) yoki spam bo'lsa:
   {{"is_service_ad": false}} qaytaring.
2. Agar usta/xizmat o'z xizmatini taklif qilayotgan bo'lsa:
   - "is_service_ad": true
   - "category": Ro'yxatdagi mos kategoriya
   - "title": Qisqa va aniq sarlavha (masalan: "Uy ta'miri va kafel terish")
   - "master_name": Usta ismi (agar bo'lsa, aks holda "Usta")
   - "phone": Telefon raqami (+998XXXXXXXXX formatda). Agar xabarda telefon bo'lmasa, bo'sh satr ""
   - "description": Xizmat haqida tozalangan, chiroyli tavsif
   - "region": Xizmat hududi (agar Andijon yoki Xortum bo'lsa "Andijon", aks holda mos viloyat yoki "Barcha hududlar")
   - "price": Narxi (agar aytilgan bo'lsa, aks holda "Kelishilgan holda")

Faqat toza JSON formatida javob bering, hech qanday markdown (` ```json `) yoki ortiqcha matn qo'shmang.
"""
    parts: List[Dict[str, Any]] = [{"text": prompt}]

    if photo_bytes:
        parts.append({
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": base64.b64encode(photo_bytes).decode("utf-8")
            }
        })

    parts.append({"text": f"Xabar matni:\n{text}"})

    url = f"{GEMINI_API_URL}?key={GEMINI_API_KEY}"
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.1,
            "maxOutputTokens": 600,
            "responseMimeType": "application/json"
        }
    }

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        raw_json = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                        clean_json = raw_json.strip()
                        if clean_json.startswith("```json"):
                            clean_json = clean_json[7:]
                        if clean_json.endswith("```"):
                            clean_json = clean_json[:-3]
                        result = json.loads(clean_json.strip())
                        if result.get("is_service_ad") and result.get("phone"):
                            # Agar username yuborilgan bo'lsa
                            if sender_info and sender_info.get("username"):
                                result["username"] = sender_info.get("username")
                            return result
    except Exception as e:
        logger.warning(f"Gemini orqali e'lonni tahlil qilishda xatolik: {e}. Heuristic tahlilga o'tiladi.")

    # Agar Gemini ishlamasa yoki kalit bo'lmasa, doim heuristic ishlaydi
    return parse_ad_heuristic(text, sender_info)
