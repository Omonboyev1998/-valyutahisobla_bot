import asyncio
import logging
import os
import re
from typing import Optional, Tuple, Dict, Any, List

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from aiogram import Bot

from src.config import (
    BOOK_SOURCE_CHAT,
    BOOK_STORAGE_CHAT,
    BOOK_STORAGE_CHAT_ID
)
from src.database import (
    add_book,
    is_book_indexed,
    get_book_by_id,
    increment_book_download,
    get_books_count,
    search_books_db,
    get_userbot_setting,
    set_userbot_setting
)

logger = logging.getLogger("BookService")

_indexing_running = False
_indexing_task: Optional[asyncio.Task] = None

BOOK_EXTENSIONS = {"pdf", "epub", "fb2", "djvu", "mobi", "doc", "docx", "txt", "mp3", "m4b"}

def format_file_size(size_bytes: int) -> str:
    """Fayl hajmini odam tushunadigan ko'rinishga keltirish"""
    if not size_bytes:
        return "Noma'lum"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

def clean_book_metadata(raw_file_name: str, raw_caption: Optional[str] = None) -> Tuple[str, str, str]:
    """
    Fayl nomi va izohidan sarlavha, muallif hamda toza matnni ajratib olish.
    Reklama kanallari (@..., t.me/...) va ortiqcha belgilarni tozalaydi.
    """
    caption = raw_caption or ""
    # Reklama havolalari va belgilarni tozalash
    caption_clean = re.sub(r"https?://\S+|t\.me/\S+", "", caption)
    caption_clean = re.sub(r"@[a-zA-Z0-9_]+", "", caption_clean).strip()

    title = ""
    author = ""

    # Agar captionda Muallif va Kitob nomi yozilgan bo'lsa
    author_match = re.search(r"(?:Muallif|Avtor|Author|Муаллиф|Автор)\s*[:\-–—]\s*([^\n\r,]+)", caption, re.IGNORECASE)
    if author_match:
        author = author_match.group(1).strip()

    title_match = re.search(r"(?:Nomi|Kitob|Title|Номи|Китоб|Asar)\s*[:\-–—]\s*([^\n\r,]+)", caption, re.IGNORECASE)
    if title_match:
        title = title_match.group(1).strip()

    # Agar title topilmagan bo'lsa, fayl nomidan olamiz
    if not title:
        fn = raw_file_name or ""
        # Kengaytmani olib tashlash (.pdf, .epub ...)
        fn = re.sub(r"\.(pdf|epub|fb2|djvu|mobi|docx?|txt|mp3|m4b)$", "", fn, flags=re.IGNORECASE)
        # Reklamalarni olib tashlash
        fn = re.sub(r"@[a-zA-Z0-9_]+", "", fn)
        fn = re.sub(r"https?://\S+|t\.me/\S+", "", fn)
        # _ va . ni probelga almashtirish
        fn = fn.replace("_", " ").replace(".", " ").strip()
        fn = re.sub(r"\s+", " ", fn)

        # Agar "Muallif - Kitob" ko'rinishida bo'lsa
        if " - " in fn or " — " in fn:
            parts = re.split(r"\s+[-—–]\s+", fn, maxsplit=1)
            if len(parts) == 2:
                if not author:
                    author = parts[0].strip()
                title = parts[1].strip()
            else:
                title = fn
        else:
            title = fn

    title = title.strip(" -—.,:;")
    author = author.strip(" -—.,:;")
    if not title:
        title = raw_file_name or "Noma'lum kitob"

    return title, author, caption_clean

def is_indexing_active() -> bool:
    global _indexing_running
    return _indexing_running

def stop_indexing():
    global _indexing_running, _indexing_task
    _indexing_running = False
    try:
        set_userbot_setting("is_book_indexing_enabled", "0")
    except Exception:
        pass
    if _indexing_task and not _indexing_task.done():
        _indexing_task.cancel()

async def run_book_copier(limit_total: int = 50000):
    """
    Userbot orqali source guruhdagi kitoblarni private kanalga nusxalab,
    bazaga indekslaydigan asosiy asinxron jarayon.
    Uzilishlar va tarmoq xatolariga chidamli (Auto-retry).
    """
    global _indexing_running
    _indexing_running = True

    from src.userbot.listener import get_or_create_client
    logger.info("Kitoblar nusxalash jarayoni boshlanmoqda...")

    indexed_in_this_run = 0

    while _indexing_running:
        try:
            client = await get_or_create_client()
            source_entity = await client.get_entity(BOOK_SOURCE_CHAT)
            dest_entity = await client.get_entity(BOOK_STORAGE_CHAT)

            last_id_str = get_userbot_setting("last_scanned_book_msg_id", "0")
            min_id = int(last_id_str) if last_id_str.isdigit() else 0
            current_highest_id = min_id

            logger.info(f"Nusxalash #{min_id} xabardan davom ettirilmoqda...")

            async for msg in client.iter_messages(source_entity, min_id=min_id, reverse=True):
                if not _indexing_running:
                    logger.info("Kitoblar nusxalash jarayoni foydalanuvchi tomonidan to'xtatildi.")
                    return

                current_highest_id = max(current_highest_id, msg.id)
                # Har 10 ta xabarda bir oxirgi o'qilgan ID ni bazaga yangilash
                if msg.id % 10 == 0 or msg.media:
                    set_userbot_setting("last_scanned_book_msg_id", str(current_highest_id))

                # Xabarda hujjat (fayl) bormi?
                if not msg.media or not getattr(msg, "file", None):
                    continue

                file_obj = msg.file
                file_name = file_obj.name or ""
                file_ext = (file_obj.ext or "").lower().lstrip(".")
                mime_type = file_obj.mime_type or ""

                # Faqat elektron kitob va audio kitob formatlari
                if file_ext not in BOOK_EXTENSIONS and "pdf" not in mime_type and "epub" not in mime_type:
                    continue

                # Avval nusxalanganmi?
                if is_book_indexed(str(source_entity.id), msg.id, file_name, file_obj.size):
                    continue

                # 1. Shaxsiy ombor kanalimizga forward/copy qilamiz
                try:
                    copied_msgs = await client.forward_messages(dest_entity, msg)
                    if not copied_msgs:
                        continue
                    copied_msg = copied_msgs[0] if isinstance(copied_msgs, list) else copied_msgs

                    # 2. Metadatalarni tozalash va ajratish
                    title, author, clean_cap = clean_book_metadata(file_name, msg.message or "")

                    # 3. Bazaga kiritish
                    add_book(
                        title=title,
                        author=author,
                        file_name=file_name,
                        file_size=file_obj.size or 0,
                        file_extension=file_ext,
                        mime_type=mime_type,
                        storage_chat_id=str(dest_entity.id),
                        storage_message_id=copied_msg.id,
                        source_chat_id=str(source_entity.id),
                        source_message_id=msg.id,
                        caption=clean_cap
                    )

                    indexed_in_this_run += 1
                    set_userbot_setting("last_scanned_book_msg_id", str(msg.id))
                    logger.info(f"Yangi kitob nusxalandi (#{indexed_in_this_run}): {title} [{file_ext.upper()}]")

                    # Telegram limitlariga tushmaslik uchun tanaffus
                    await asyncio.sleep(1.2)

                except FloodWaitError as fwe:
                    wait_time = fwe.seconds + 5
                    logger.warning(f"Telegram FloodWait: {wait_time} sekund kutilmoqda...")
                    await asyncio.sleep(wait_time)
                except Exception as e:
                    logger.error(f"Kitobni nusxalashda xatolik (msg #{msg.id}): {e}")
                    await asyncio.sleep(1.0)

                if indexed_in_this_run >= limit_total:
                    logger.info(f"Limitga yetildi ({limit_total}).")
                    _indexing_running = False
                    return

            # Agar iteratsiya oxiriga yetgan bo'lsa (yangi xabarlar qolmagan bo'lsa)
            logger.info("Guruhdagi barcha mavjud xabarlar to'liq ko'chirildi. Yangi xabarlar kutilmoqda...")
            await asyncio.sleep(30)

        except Exception as e:
            logger.error(f"Kitoblar nusxalashda tarmoq yoki kutilmagan xatolik: {e}. 15 soniyadan so'ng qayta ulanadi...")
            await asyncio.sleep(15)

    _indexing_running = False

def start_indexing():
    global _indexing_running, _indexing_task
    if _indexing_running:
        return False
    try:
        set_userbot_setting("is_book_indexing_enabled", "1")
    except Exception:
        pass
    _indexing_task = asyncio.create_task(run_book_copier())
    return True
