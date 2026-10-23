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
_last_copier_status = "Boshlanmagan"
_last_copier_error = "Xatolik yo'q"
_last_scanned_title = ""

def get_copier_debug_status() -> Dict[str, Any]:
    global _indexing_running, _last_copier_status, _last_copier_error, _last_scanned_title
    return {
        "version": "v3-inputfilter-dialogsearch",
        "running": _indexing_running,
        "status": _last_copier_status,
        "error": _last_copier_error,
        "last_title": _last_scanned_title,
        "last_offset_id": get_userbot_setting("last_book_offset_id", "0"),
        "last_scanned_id": get_userbot_setting("last_scanned_book_msg_id", "0"),
        "is_enabled": get_userbot_setting("is_book_indexing_enabled", "0"),
        "books_in_db": get_books_count()
    }

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
    Telegramning rasmiy InputMessagesFilterDocument filtri orqali
    guruhdagi yuz minglab chat xabarlarini tashlab o'tib,
    faqat haqiqiy hujjat va kitoblarni to'g'ridan-to'g'ri filtrlab nusxalash.
    Uzilishlar va tarmoq xatolariga chidamli (Auto-retry).
    """
    global _indexing_running, _last_copier_status, _last_copier_error, _last_scanned_title
    _indexing_running = True
    _last_copier_status = "Boshlandi, ulanmoqda..."

    from telethon.tl.types import InputMessagesFilterDocument
    from src.userbot.listener import get_or_create_client
    logger.info("Kitoblar nusxalash jarayoni (Document Filter) boshlanmoqda...")

    indexed_in_this_run = 0

    while _indexing_running:
        try:
            _last_copier_status = "Telethon mijoziga ulanmoqda..."
            client = await get_or_create_client()

            _last_copier_status = "Dialoglar keshlanmoqda..."
            await client.get_dialogs(limit=50)

            _last_copier_status = "Guruh va kanal obyektlari olinmoqda..."
            source_entity = await client.get_entity(BOOK_SOURCE_CHAT)

            dest_entity = None
            raw_target_id = int(str(BOOK_STORAGE_CHAT_ID).replace("-100", "").lstrip("-"))
            target_ids = [BOOK_STORAGE_CHAT_ID, raw_target_id, BOOK_STORAGE_CHAT, "dunyokitoblari1"]
            for target_id in target_ids:
                try:
                    dest_entity = await client.get_entity(target_id)
                    if dest_entity:
                        break
                except Exception:
                    pass

            if not dest_entity:
                # Agar to'g'ridan-to'g'ri get_entity topolmasa, userbotning dialoglar ro'yxatidan qidiramiz
                async for dialog in client.iter_dialogs(limit=250):
                    clean_d_id = str(dialog.id).replace("-100", "").lstrip("-")
                    target_clean_id = str(BOOK_STORAGE_CHAT_ID).replace("-100", "").lstrip("-")
                    d_username = (getattr(dialog.entity, "username", "") or "").lower()
                    if (
                        clean_d_id == target_clean_id 
                        or dialog.id == BOOK_STORAGE_CHAT_ID 
                        or d_username in ("dunyokitoblari1", str(BOOK_STORAGE_CHAT).lstrip("@").lower())
                    ):
                        dest_entity = dialog.entity
                        logger.info(f"Ombor kanal dialoglar ro'yxatidan topildi: {dialog.name} (id={dialog.id})")
                        break

            if not dest_entity:
                raise ValueError(f"Ombor kanal topilmadi: {BOOK_STORAGE_CHAT} ({BOOK_STORAGE_CHAT_ID})")

            dest_storage_id = f"-100{str(dest_entity.id).lstrip('-')}" if not str(dest_entity.id).startswith("-100") else str(dest_entity.id)

            last_id_str = get_userbot_setting("last_book_offset_id", "0")
            offset_id = int(last_id_str) if last_id_str.isdigit() else 0

            _last_copier_status = f"Hujjatlar filtri orqali skanerlanmoqda (offset_id={offset_id})..."
            logger.info(f"Nusxalash offset_id={offset_id} dan boshlanmoqda...")

            async for msg in client.iter_messages(
                source_entity,
                offset_id=offset_id,
                filter=InputMessagesFilterDocument
            ):
                if not _indexing_running:
                    _last_copier_status = "To'xtatildi"
                    logger.info("Kitoblar nusxalash jarayoni foydalanuvchi tomonidan to'xtatildi.")
                    return

                # Har bir xabarda offset_id ni saqlab boramiz
                set_userbot_setting("last_book_offset_id", str(msg.id))
                set_userbot_setting("last_scanned_book_msg_id", str(msg.id))

                if not msg.media or not getattr(msg, "file", None):
                    continue

                file_obj = msg.file
                file_name = file_obj.name or ""
                file_ext = (file_obj.ext or "").lower().lstrip(".")
                mime_type = file_obj.mime_type or ""

                # Faqat elektron kitob va audio kitob formatlari
                if file_ext not in BOOK_EXTENSIONS and "pdf" not in mime_type and "epub" not in mime_type:
                    continue

                # Avval nusxalanganmi? (Dublikat tekshiruvi)
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
                    _last_scanned_title = title

                    # 3. Bazaga kiritish
                    add_book(
                        title=title,
                        author=author,
                        file_name=file_name,
                        file_size=file_obj.size or 0,
                        file_extension=file_ext,
                        mime_type=mime_type,
                        storage_chat_id=dest_storage_id,
                        storage_message_id=copied_msg.id,
                        source_chat_id=str(source_entity.id),
                        source_message_id=msg.id,
                        caption=clean_cap
                    )

                    indexed_in_this_run += 1
                    _last_copier_status = f"Nusxalanmoqda (#{indexed_in_this_run}): {title[:30]}"
                    logger.info(f"Yangi kitob nusxalandi (#{indexed_in_this_run}): {title} [{file_ext.upper()}] (msg #{msg.id})")

                    # Telegram limitlariga tushmaslik uchun xavfsiz tanaffus
                    await asyncio.sleep(1.2)

                except FloodWaitError as fwe:
                    wait_time = fwe.seconds + 5
                    _last_copier_status = f"FloodWait kutilmoqda ({wait_time}s)"
                    logger.warning(f"Telegram FloodWait: {wait_time} sekund kutilmoqda...")
                    await asyncio.sleep(wait_time)
                except Exception as e:
                    _last_copier_error = f"Forward error (msg #{msg.id}): {e}"
                    logger.error(f"Kitobni nusxalashda xatolik (msg #{msg.id}): {e}")
                    await asyncio.sleep(1.0)

                if indexed_in_this_run >= limit_total:
                    logger.info(f"Limitga yetildi ({limit_total}).")
                    _indexing_running = False
                    _last_copier_status = "Limitga yetildi"
                    return

            _last_copier_status = "Barcha kitoblar tugadi, kutish rejimida"
            logger.info("Guruhdagi barcha kitoblar to'liq skanerlandi va nusxalandi!")
            # Guruhdagi barcha hujjatlar tugasa, yangilari kelishini kutish uchun offset_id ni 0 qilamiz
            set_userbot_setting("last_book_offset_id", "0")
            await asyncio.sleep(60)

        except Exception as e:
            import traceback
            _last_copier_error = f"{type(e).__name__}: {str(e)}"
            _last_copier_status = f"Xatolik: {type(e).__name__}"
            logger.error(f"Kitoblar nusxalashda tarmoq xatoligi: {e}. 15 soniyadan so'ng qayta ulanadi...")
            await asyncio.sleep(15)

    _indexing_running = False
    _last_copier_status = "To'xtatilgan"

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
