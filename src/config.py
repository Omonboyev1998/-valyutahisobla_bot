import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi! Iltimos, .env faylida BOT_TOKEN ni ko'rsating.")

ADMIN_IDS = [int(i.strip()) for i in os.getenv("ADMIN_ID", "1045855587").split(",") if i.strip()]
ADMIN_ID = ADMIN_IDS[0] if ADMIN_IDS else 1045855587

CBU_API_URL = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"

# AI Sozlamalari (Google Gemini)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# Web App sozlamalari
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
_base_url = (RENDER_EXTERNAL_URL or os.getenv("WEB_APP_URL") or "https://valyutabot.onrender.com").rstrip("/")
WEB_APP_URL = f"{_base_url}/app" if not _base_url.endswith("/app") else _base_url

# Userbot (Telegram Client) sozlamalari - Guruhlarni kuzatish uchun
TG_API_ID = int(os.getenv("TG_API_ID", "0") or "0")
TG_API_HASH = os.getenv("TG_API_HASH", "")
TG_SESSION_STRING = os.getenv("TG_SESSION_STRING", "")
TARGET_CHATS = [c.strip() for c in os.getenv("TARGET_CHATS", "Xortumliklar,Xortum,Хортум,Хортумликлар").split(",") if c.strip()]
USERBOT_SESSION = os.getenv("USERBOT_SESSION", "data/userbot")

