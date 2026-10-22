import asyncio
import logging
import os
import sys
from typing import Optional, List, Dict, Any, Tuple

from telethon import TelegramClient, events
from telethon.sessions import StringSession
from telethon.tl.types import User, Channel, Chat

from src.config import (
    TG_API_ID,
    TG_API_HASH,
    TARGET_CHATS,
    USERBOT_SESSION,
    TG_SESSION_STRING,
    BOT_TOKEN,
    ADMIN_ID,
    GEMINI_API_KEY
)
from src.database import add_service, get_service_by_phone
from src.services.ad_parser_service import parse_ad_with_gemini

# Aiogram bot orqali adminga xabar va rasm yuborish
from aiogram import Bot
from aiogram.types import BufferedInputFile

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("UserbotListener")

_active_client: Optional[TelegramClient] = None

async def get_or_create_client() -> TelegramClient:
    """Telethon mijozini olish yoki ulash"""
    global _active_client
    if _active_client and _active_client.is_connected():
        return _active_client

    if TG_SESSION_STRING:
        session = StringSession(TG_SESSION_STRING)
    else:
        os.makedirs(os.path.dirname(USERBOT_SESSION) or ".", exist_ok=True)
        session = USERBOT_SESSION

    _active_client = TelegramClient(session, TG_API_ID, TG_API_HASH)
    await _active_client.connect()
    return _active_client

def is_target_chat(chat_id: int, chat_title: str, chat_username: Optional[str]) -> bool:
    """Xabar kelgan guruh biz kuzatmoqchi bo'lgan guruhlar ro'yxatida bormi?"""
    # 1. Admin panel orqali bazada faollashtirilganmi?
    from src.database import is_chat_monitored
    try:
        if is_chat_monitored(chat_id, chat_title, chat_username):
            return True
    except Exception:
        pass

    # 2. Config dagi standart TARGET_CHATS ro'yxatida bormi?
    if not TARGET_CHATS or "*" in TARGET_CHATS:
        return True

    title_lower = (chat_title or "").lower()
    user_lower = (chat_username or "").lower()

    for target in TARGET_CHATS:
        t_clean = target.strip().lower().lstrip("@")
        if t_clean in title_lower or (user_lower and t_clean == user_lower):
            return True
    return False

async def notify_admin_about_new_service(
    bot: Bot,
    service_id: int,
    ad_data: Dict[str, Any],
    chat_title: str,
    photo_bytes: Optional[bytes] = None
) -> Optional[str]:
    """Admin botiga yangi usta kartochkasi haqida bildirishnoma yuborish"""
    text = (
        f"🆕 <b>Guruhdan yangi usta kartochkasi qo'shildi!</b>\n\n"
        f"📍 <b>Guruh:</b> {chat_title}\n"
        f"👤 <b>Usta:</b> {ad_data['master_name']}\n"
        f"🏷 <b>Kategoriya:</b> {ad_data['category']}\n"
        f"📌 <b>Sarlavha:</b> {ad_data['title']}\n"
        f"📞 <b>Telefon:</b> <code>{ad_data['phone']}</code>\n"
        f"💰 <b>Narx:</b> {ad_data.get('price', 'Kelishilgan holda')}\n"
        f"📍 <b>Hudud:</b> {ad_data.get('region', 'Andijon')}\n"
        f"🆔 <b>ID:</b> #{service_id}\n\n"
        f"📝 <b>Tavsif:</b>\n<i>{ad_data['description'][:400]}...</i>"
    )

    photo_id = None
    try:
        if photo_bytes:
            photo_file = BufferedInputFile(photo_bytes, filename=f"service_{service_id}.jpg")
            sent_msg = await bot.send_photo(
                chat_id=ADMIN_ID,
                photo=photo_file,
                caption=text,
                parse_mode="HTML"
            )
            if sent_msg.photo:
                photo_id = sent_msg.photo[-1].file_id
        else:
            await bot.send_message(
                chat_id=ADMIN_ID,
                text=text,
                parse_mode="HTML"
            )
    except Exception as e:
        logger.error(f"Adminga xabar yuborishda xatolik: {e}")

    return photo_id

async def process_raw_message(message, bot: Optional[Bot] = None) -> bool:
    """Xabarni qabul qilish, tahlil qilish va bazaga qo'shish"""
    raw_text = message.text or message.message or ""
    if not raw_text and not message.photo:
        return False

    chat = await message.get_chat()
    chat_title = getattr(chat, 'title', 'Shaxsiy chat / Noma\'lum')
    chat_username = getattr(chat, 'username', None)
    chat_id = getattr(chat, 'id', 0)

    # 1. Guruh biz kuzatayotgan guruh ekanligini tekshirish
    if not is_target_chat(chat_id, chat_title, chat_username):
        return False

    sender = await message.get_sender()
    sender_info = {
        "first_name": getattr(sender, 'first_name', '') or '',
        "last_name": getattr(sender, 'last_name', '') or '',
        "username": getattr(sender, 'username', None),
        "id": getattr(sender, 'id', 0)
    }

    # 2. Rasm mavjud bo'lsa va Gemini kaliti bo'lsa, OCR tahlil uchun yuklab olish
    photo_bytes = None
    if message.photo and GEMINI_API_KEY:
        try:
            photo_bytes = await message.download_media(file=bytes)
        except Exception as e:
            logger.warning(f"Rasmni yuklab olishda xatolik: {e}")

    # 3. AI / Heuristics orqali xabarni tahlil qilish
    ad_data = await parse_ad_with_gemini(raw_text, photo_bytes, sender_info)
    if not ad_data or not ad_data.get("is_service_ad"):
        return False

    phone = ad_data.get("phone", "")
    if not phone:
        return False

    # 4. Dublikatni tekshirish: bu telefon raqam allaqachon bormi?
    existing = get_service_by_phone(phone)
    if existing:
        logger.info(f"O'tkazib yuborildi: {phone} raqamli usta allaqachon mavjud (ID: #{existing['id']})")
        return False

    # Agar xizmat tasdiqlangan bo'lsa va rasm bo'lsa (lekin hali yuklanmagan bo'lsa), yuklab olamiz
    if message.photo and not photo_bytes:
        try:
            photo_bytes = await message.download_media(file=bytes)
        except Exception as e:
            logger.warning(f"Rasmni yuklab olishda xatolik: {e}")

    # 5. Avval bazaga qo'shish
    try:
        new_id = add_service(
            user_id=sender_info["id"] or 1,
            master_name=ad_data["master_name"],
            phone=phone,
            username=ad_data.get("username"),
            category=ad_data["category"],
            title=ad_data["title"],
            description=ad_data["description"],
            region=ad_data.get("region", "Andijon"),
            price=ad_data.get("price", "Kelishilgan holda"),
            photo_id=None
        )
        logger.info(f"Muvaffaqiyatli saqlandi! Yangi Usta ID: #{new_id} ({ad_data['master_name']} - {phone})")
    except Exception as e:
        logger.error(f"Xizmatni saqlashda xatolik: {e}")
        return False

    # 6. Adminga xabar va rasm yuborish
    if bot:
        try:
            photo_id = await notify_admin_about_new_service(
                bot=bot,
                service_id=new_id,
                ad_data=ad_data,
                chat_title=chat_title,
                photo_bytes=photo_bytes
            )
            # Agar rasm yuklangan bo'lsa, bazaga photo_id ni yangilash
            if photo_id:
                from src.database import get_db
                with get_db() as conn:
                    conn.cursor().execute("UPDATE services SET photo_id = ? WHERE id = ?", (photo_id, new_id))
                    conn.commit()
        except Exception as e:
            logger.warning(f"Adminga bildirishnoma yuborishda xatolik: {e}")

    return True

async def scan_recent_history(client: TelegramClient, bot: Bot, limit: int = 50):
    """Guruhdagi oxirgi xabarlarni aylanib chiqish (tarixni skanerlash)"""
    logger.info(f"Kuzatilayotgan guruhlardagi oxirgi {limit} ta xabarlar skaneri boshlanmoqda...")
    dialogs = await client.get_dialogs(limit=100)
    target_dialogs = [d for d in dialogs if d.is_group and is_target_chat(d.title, getattr(d.entity, 'username', None))]

    if not target_dialogs:
        logger.warning(f"Kuzatiladigan guruhlar topilmadi. TARGET_CHATS={TARGET_CHATS}")
        return

    added_count = 0
    for d in target_dialogs:
        logger.info(f"Guruh skanerlanmoqda: {d.title} (ID: {d.id})")
        async for msg in client.iter_messages(d, limit=limit):
            try:
                res = await process_raw_message(msg, bot)
                if res:
                    added_count += 1
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.error(f"Xabarni skanerlashda xatolik: {e}")

    logger.info(f"Skanerlash yakunlandi. Jami qo'shilgan yangi ustalar soni: {added_count}")

async def start_userbot(scan_history: bool = False, history_limit: int = 50):
    """Userbotni ishga tushirish"""
    if not TG_API_ID or not TG_API_HASH:
        logger.error(
            "TG_API_ID yoki TG_API_HASH .env faylida ko'rsatilmagan! "
            "Iltimos, my.telegram.org saytidan API ID va HASH olib .env fayliga kiriting."
        )
        return

    # Sessiyani aniqlash (StringSession bulutli muhitlar/Render uchun, fayl esa lokal uchun)
    if TG_SESSION_STRING:
        session = StringSession(TG_SESSION_STRING)
        logger.info("Userbot StringSession orqali yuklanmoqda (Bulutli muhit/Render).")
    else:
        os.makedirs(os.path.dirname(USERBOT_SESSION) or ".", exist_ok=True)
        session = USERBOT_SESSION
        logger.info(f"Userbot fayl sessiyasi orqali yuklanmoqda: {USERBOT_SESSION}")

    global _active_client
    client = TelegramClient(session, TG_API_ID, TG_API_HASH)
    _active_client = client
    bot = Bot(token=BOT_TOKEN)

    logger.info("Telegram Client-ga ulanish...")
    await client.start()
    logger.info("Userbot muvaffaqiyatli ulandi va guruhlarni kuzatishni boshladi!")
    logger.info(f"Kuzatilayotgan guruhlar: {TARGET_CHATS}")

    # Agar tarixni ham skanerlash so'ralgan bo'lsa:
    if scan_history:
        await scan_recent_history(client, bot, limit=history_limit)

    # Yangi xabarlarni jonli rejimda tinglash
    @client.on(events.NewMessage)
    async def handler(event):
        try:
            # Faqat guruh yoki superguruh xabarlari
            if event.is_group:
                await process_raw_message(event.message, bot)
        except Exception as e:
            logger.error(f"Xabarni qabul qilishda xatolik: {e}")

    await client.run_until_disconnected()

async def get_userbot_dialog_groups(limit: int = 100) -> List[Dict[str, Any]]:
    """Akkaunt a'zo bo'lgan guruhlar ro'yxatini olish"""
    client = await get_or_create_client()
    dialogs = await client.get_dialogs(limit=limit)
    res = []
    for d in dialogs:
        if d.is_group:
            res.append({
                "id": d.id,
                "title": d.title,
                "username": getattr(d.entity, "username", None)
            })
    return res

async def join_telegram_group(invite: str) -> Tuple[bool, str]:
    """Guruhga havola orqali a'zo bo'lish"""
    client = await get_or_create_client()
    clean_invite = invite.strip()
    try:
        from telethon.tl.functions.channels import JoinChannelRequest
        from telethon.tl.functions.messages import ImportChatInviteRequest
        from src.database import add_monitored_chat

        if "+" in clean_invite or "joinchat/" in clean_invite:
            hash_str = clean_invite.split("+")[-1].split("joinchat/")[-1].strip("/")
            res = await client(ImportChatInviteRequest(hash_str))
            title = getattr(res.chats[0], "title", "Guruh") if res.chats else "Guruh"
            chat_id = res.chats[0].id if res.chats else 0
            if chat_id:
                add_monitored_chat(chat_id, title)
            return True, f"Muvaffaqiyatli a'zo bo'lindi: {title}"
        else:
            clean_username = clean_invite.replace("https://t.me/", "").replace("t.me/", "").lstrip("@")
            entity = await client.get_entity(clean_username)
            await client(JoinChannelRequest(entity))
            title = getattr(entity, "title", clean_username)
            chat_id = getattr(entity, "id", 0)
            if chat_id:
                add_monitored_chat(chat_id, title, getattr(entity, "username", None))
            return True, f"Muvaffaqiyatli a'zo bo'lindi: {title}"
    except Exception as e:
        logger.error(f"Guruhga a'zo bo'lishda xatolik: {e}")
        return False, str(e)

async def scan_single_chat(chat_id: int, bot: Bot, limit: int = 50) -> int:
    """Aynan bitta guruh tarixini skanerlash"""
    client = await get_or_create_client()
    entity = await client.get_entity(chat_id)
    added_count = 0
    async for msg in client.iter_messages(entity, limit=limit):
        try:
            res = await process_raw_message(msg, bot)
            if res:
                added_count += 1
            await asyncio.sleep(0.2)
        except Exception as e:
            logger.error(f"Xabarni skanerlashda xatolik: {e}")
    return added_count

if __name__ == "__main__":
    scan = "--scan" in sys.argv
    asyncio.run(start_userbot(scan_history=scan))
