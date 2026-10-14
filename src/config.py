import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN topilmadi! Iltimos, .env faylida BOT_TOKEN ni ko'rsating.")

CBU_API_URL = "https://cbu.uz/uz/arkhiv-kursov-valyut/json/"
