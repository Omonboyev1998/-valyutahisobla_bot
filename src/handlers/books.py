import html
import logging
from typing import Optional

from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.config import BOOK_STORAGE_CHAT_ID
from src.database import (
    search_books_db,
    get_book_by_id,
    increment_book_download,
    get_books_count
)
from src.services.book_service import format_file_size
from src.keyboards.reply import get_main_keyboard

logger = logging.getLogger(__name__)
router = Router()

class BookSearchState(StatesGroup):
    waiting_for_query = State()

@router.message(F.text == "📚 Kitoblar Kutubxonasi")
@router.message(Command("kitob", "kitoblar", "books"))
async def books_main_menu(message: Message, state: FSMContext):
    """Kutubxona asosiy bo'limi yoki /kitob komandasi"""
    args = message.text.split(maxsplit=1)
    if len(args) > 1 and not message.text.startswith("📚"):
        query = args[1].strip()
        await process_search_query(message, query, state)
        return

    total_books = get_books_count()
    await state.set_state(BookSearchState.waiting_for_query)

    text = (
        "📚 <b>Elektron Kutubxonaga xush kelibsiz!</b>\n\n"
        f"Hozirda bazamizda <b>{total_books:,} ta</b> dan ortiq nodir badiiy, "
        "ilmiy, diniy va biznes kitoblar mavjud.\n\n"
        "🔍 <b>Qidirmoqchi bo'lgan kitobingiz yoki muallif nomini yozing:</b>\n"
        "<i>(Masalan: O'tkan kunlar, Alximik, Chingiz Aytmatov, Stiv Jobs)</i>"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="books_back_main")]
    ])
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@router.message(BookSearchState.waiting_for_query, F.text)
async def handle_book_search_input(message: Message, state: FSMContext):
    """Foydalanuvchi qidiruv matnini yuborganda"""
    query = message.text.strip()
    if query in ["🔙 Asosiy menyu", "/start", "/menu"]:
        await state.clear()
        await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=get_main_keyboard(message.from_user.id))
        return

    await process_search_query(message, query, state)

async def process_search_query(message: Message, query: str, state: FSMContext):
    """Kitob qidiruv natijalarini ko'rsatish"""
    books = search_books_db(query, limit=8)

    if not books:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Boshqa so'z bilan qidirish", callback_data="books_search_again")],
            [InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="books_back_main")]
        ])
        await message.answer(
            f"😔 Kechirasiz, <b>\"{html.escape(query)}\"</b> bo'yicha hech qanday kitob topilmadi.\n\n"
            "💡 <i>Maslahat: Kitob nomi yoki muallif familiyasining bir qismini yozib ko'ring (masalan: Qodiriy, Navoiy, Robin Sharma).</i>",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    text = f"🔍 <b>\"{html.escape(query)}\"</b> bo'yicha topilgan kitoblar:\n\n"
    buttons = []

    for idx, b in enumerate(books, start=1):
        title = html.escape(b.get("title") or "Nomsiz kitob")
        author = html.escape(b.get("author") or "")
        ext = (b.get("file_extension") or "pdf").upper()
        size_str = format_file_size(b.get("file_size") or 0)
        downloads = b.get("download_count") or 0

        author_str = f" • ✍️ {author}" if author else ""
        text += f"<b>{idx}.</b> 📖 <b>{title}</b>{author_str}\n"
        text += f"     └ <i>{ext} • {size_str} • 📥 {downloads} marta yuklangan</i>\n\n"

        btn_title = (b.get("title") or "Kitob")[:25]
        buttons.append([
            InlineKeyboardButton(
                text=f"📥 {idx}. {btn_title} ({ext})",
                callback_data=f"dl_book:{b['id']}"
            )
        ])

    buttons.append([
        InlineKeyboardButton(text="🔍 Qayta qidirish", callback_data="books_search_again"),
        InlineKeyboardButton(text="🔙 Asosiy menyu", callback_data="books_back_main")
    ])

    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data.startswith("dl_book:"))
async def handle_download_book(callback: CallbackQuery, bot: Bot):
    """Kitobni foydalanuvchiga jo'natish"""
    book_id_str = callback.data.split(":")[1]
    if not book_id_str.isdigit():
        await callback.answer("Xatolik yuz berdi.", show_alert=True)
        return

    book_id = int(book_id_str)
    book = get_book_by_id(book_id)

    if not book:
        await callback.answer("Kitob topilmadi yoki o'chirilgan.", show_alert=True)
        return

    await callback.answer("⏳ Kitob yuklanmoqda...", show_alert=False)

    storage_chat = book.get("storage_chat_id") or str(BOOK_STORAGE_CHAT_ID)
    msg_id = book.get("storage_message_id")

    title = book.get("title") or "Kitob"
    author = book.get("author")
    caption = f"📖 <b>{html.escape(title)}</b>\n"
    if author:
        caption += f"✍️ <b>Muallif:</b> {html.escape(author)}\n"
    caption += "\n🤖 @valyutahisobla_bot orqali yuklab olindi."

    try:
        # Shaxsiy ombor kanalimizdan to'g'ridan-to'g'ri foydalanuvchiga nusxalash
        await bot.copy_message(
            chat_id=callback.from_user.id,
            from_chat_id=int(storage_chat) if storage_chat.lstrip("-").isdigit() else storage_chat,
            message_id=msg_id,
            caption=caption,
            parse_mode="HTML"
        )
        increment_book_download(book_id)
    except Exception as e:
        logger.error(f"Kitobni jo'natishda xatolik: {e}")
        await callback.message.answer(
            "⚠️ Kitobni yuklashda vaqtinchalik xatolik yuz berdi. Iltimos, birozdan so'ng qayta urinib ko'ring."
        )

@router.callback_query(F.data == "books_search_again")
async def handle_search_again(callback: CallbackQuery, state: FSMContext):
    await state.set_state(BookSearchState.waiting_for_query)
    await callback.message.answer(
        "🔍 Yangi qidirmoqchi bo'lgan kitobingiz yoki muallif nomini yozing:"
    )
    await callback.answer()

@router.callback_query(F.data == "books_back_main")
async def handle_books_back_main(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        "Asosiy menyu:",
        reply_markup=get_main_keyboard(callback.from_user.id)
    )
    await callback.answer()
