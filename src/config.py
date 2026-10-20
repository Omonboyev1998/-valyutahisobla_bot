import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi! Iltimos, .env faylida BOT_TOKEN ni ko'rsating.")

ADMIN_IDS = [int(i.strip()) for i in os.getenv("ADMIN_ID", "1045855587").split(",") if i.strip()]
ADMIN_ID = ADMIN_IDS[0] if ADMIN_IDS else 1045855587

CBU_API_URL = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"

# Web App sozlamalari
RENDER_EXTERNAL_URL = os.getenv("RENDER_EXTERNAL_URL")
_base_url = os.getenv("WEB_APP_URL", RENDER_EXTERNAL_URL or "https://valyutabot.onrender.com").rstrip("/")
WEB_APP_URL = f"{_base_url}/app" if not _base_url.endswith("/app") else _base_url
