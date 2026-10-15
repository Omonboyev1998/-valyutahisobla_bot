import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi! Iltimos, .env faylida BOT_TOKEN ni ko'rsating.")

ADMIN_ID = int(os.getenv("ADMIN_ID", "1045855587"))

CBU_API_URL = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"
