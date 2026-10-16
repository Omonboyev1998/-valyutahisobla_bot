import asyncio
import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from src.config import ADMIN_ID
from src.database import get_statistics, export_users_csv, get_all_users, set_subscription
from src.keyboards.admin import (
    get_admin_main_keyboard,
    get_broadcast_confirm_keyboard,
    get_admin_back_keyboard
)
from src.services.cbu_service import cbu_service

logger = logging.getLogger(__name__)

router = Router(name="admin")

class BroadcastState(StatesGroup):
    waiting_for_message = State()
    confirm = State()

def is_admin(user_id: int) -> bool:
    return user_id == ADMIN_ID

ADMIN_DASHBOARD_TEXT = (
    "👨‍💼 <b>Assalomu alaykum, Admin!</b>\n\n"
    "Valyuta boti boshqaruv paneliga xush kelibsiz.\n"
    "Quyidagi bo'limlardan birini tanlang:"
)

@router.message(Command("admin"))
async def cmd_admin(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        # Oddiy foydalanuvchilarga bildirmaslik
        return

    await state.clear()
    await message.answer(
        ADMIN_DASHBOARD_TEXT,
        parse_mode="HTML",
        reply_markup=get_admin_main_keyboard()
    )

@router.callback_query(F.data == "admin:back")
async def callback_admin_back(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    await callback.message.edit_text(
        ADMIN_DASHBOARD_TEXT,
        parse_mode="HTML",
        reply_markup=get_admin_main_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "admin:close")
async def callback_admin_close(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        await callback.message.edit_text("Admin panel yopildi.")
    await callback.answer()

# --- STATISTIKA ---
@router.callback_query(F.data == "admin:stats")
async def callback_admin_stats(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    stats = get_statistics()
    total = stats["total_users"]
    today = stats["today_users"]
    sub = stats["subscribed_users"]
    unsub = stats["unsubscribed_users"]
    total_conv = stats["total_conversions"]
    top_curr = stats["top_currencies"]

    sub_percent = f"{(sub / total * 100):.1f}%" if total > 0 else "0%"

    top_text = ""
    if top_curr:
        for idx, (ccy, cnt) in enumerate(top_curr, 1):
            top_text += f"   {idx}. <b>{ccy}</b> — {cnt} marta\n"
    else:
        top_text = "   <i>Hozircha hisob-kitoblar mavjud emas</i>\n"

    text = (
        "📊 <b>Botning jonli statistikasi:</b>\n\n"
        f"👥 <b>Jami foydalanuvchilar:</b> {total:,} ta\n"
        f"🆕 <b>Bugun qo'shilganlar:</b> +{today:,} ta\n"
        f"🎁 <b>Referal orqali qo'shilganlar:</b> {stats.get('referral_joined', 0):,} ta\n\n"
        f"🔔 <b>Eslatmalarga obuna bo'lganlar:</b> {sub:,} ta ({sub_percent})\n"
        f"🔕 <b>Obunani o'chirganlar:</b> {unsub:,} ta\n\n"
        f"🔄 <b>Jami hisob-kitoblar (konvertatsiya):</b> {total_conv:,} marta\n\n"
        f"🔝 <b>Eng ko'p hisoblangan valyutalar:</b>\n"
        f"{top_text}"
    )

    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_admin_back_keyboard()
    )
    await callback.answer()

# --- CBU KURSLARINI MAJBURAN YANGILASH ---
@router.callback_query(F.data == "admin:refresh_cbu")
async def callback_refresh_cbu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    await cbu_service.get_all_rates(force_refresh=True)
    await callback.answer("CBU kurslari majburan yangilandi! ✅", show_alert=True)

# --- CSV EKSPORT ---
@router.callback_query(F.data == "admin:export")
async def callback_admin_export(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return

    await callback.answer("Foydalanuvchilar bazasi tayyorlanmoqda...")
    csv_data = export_users_csv()
    csv_bytes = csv_data.encode("utf-8-sig")  # Excelda o'zbek harflari buzilmasligi uchun utf-8-sig

    document = BufferedInputFile(csv_bytes, filename="valyutabot_foydalanuvchilar.csv")
    await callback.message.answer_document(
        document=document,
        caption="📁 <b>Barcha foydalanuvchilar ro'yxati (CSV/Excel formatida)</b>",
        parse_mode="HTML"
    )

# --- XABAR TARQATISH (RASSILKA) ---
@router.callback_query(F.data == "admin:broadcast")
async def callback_admin_broadcast(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return

    await state.set_state(BroadcastState.waiting_for_message)
    await callback.message.edit_text(
        "📢 <b>Xabar tarqatish (Rassilka) bo'limi</b>\n\n"
        "Barcha foydalanuvchilarga yubormoqchi bo'lgan xabaringizni yuboring.\n"
        "<i>(Matn, Rasm, Video yoki Forward qilingan xabar bo'lishi mumkin)</i>\n\n"
        "❌ Bekor qilish uchun: /cancel",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(Command("cancel"))
async def cmd_cancel_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await message.answer("Amal bekor qilindi. Boshqaruv paneliga qaytdingiz.", reply_markup=get_admin_main_keyboard())

@router.message(BroadcastState.waiting_for_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    # Xabar parametrlarini saqlab olamiz
    await state.update_data(
        from_chat_id=message.chat.id,
        message_id=message.message_id
    )
    await state.set_state(BroadcastState.confirm)

    # Foydalanuvchiga preview (ko'rinish) yuboramiz
    await message.reply(
        "👆 <b>Xabaringiz yuqoridagidek ko'rinishda yuboriladi.</b>\n\n"
        "Uni barcha foydalanuvchilarga tarqatishni tasdiqlaysizmi?",
        parse_mode="HTML",
        reply_markup=get_broadcast_confirm_keyboard()
    )

@router.callback_query(BroadcastState.confirm, F.data == "broadcast:cancel")
async def callback_cancel_confirm(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("Xabar tarqatish bekor qilindi.")
    await callback.message.answer(ADMIN_DASHBOARD_TEXT, parse_mode="HTML", reply_markup=get_admin_main_keyboard())
    await callback.answer()

@router.callback_query(BroadcastState.confirm, F.data == "broadcast:confirm")
async def callback_execute_broadcast(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id):
        return

    data = await state.get_data()
    from_chat_id = data.get("from_chat_id")
    msg_id = data.get("message_id")
    await state.clear()

    user_ids = get_all_users()
    total = len(user_ids)

    if total == 0:
        await callback.message.edit_text("Bazada foydalanuvchilar topilmadi.")
        await callback.answer()
        return

    status_msg = await callback.message.edit_text(
        f"⏳ <b>Xabar tarqatilmoqda...</b>\n\nJami: <b>{total}</b> ta foydalanuvchi.",
        parse_mode="HTML"
    )

    sent = 0
    blocked = 0

    for idx, uid in enumerate(user_ids, 1):
        try:
            await bot.copy_message(
                chat_id=uid,
                from_chat_id=from_chat_id,
                message_id=msg_id
            )
            sent += 1
            await asyncio.sleep(0.04)  # Telegram sekundiga ~30 ta xabar limitiga rioya qilish
        except TelegramForbiddenError:
            blocked += 1
            set_subscription(uid, False)
        except TelegramBadRequest:
            blocked += 1
        except Exception as e:
            logger.error(f"Xabar yuborishda xatolik ({uid}): {e}")
            blocked += 1

    result_text = (
        "✅ <b>Xabar tarqatish yakunlandi!</b>\n\n"
        f"👥 <b>Jami foydalanuvchilar:</b> {total} ta\n"
        f"📬 <b>Yetkazildi:</b> {sent} ta\n"
        f"🚫 <b>Yetib bormadi (bloklaganlar):</b> {blocked} ta"
    )

    await status_msg.edit_text(result_text, parse_mode="HTML", reply_markup=get_admin_back_keyboard())
    await callback.answer("Rassilka yakunlandi! ✅")

# ==================== XIZMATLARNI MODERATSIYA QILISH ====================

@router.callback_query(F.data.startswith("admin_srv_ok:"))
async def callback_admin_approve_service(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return
    try:
        s_id = int(callback.data.split(":")[1])
        from src.database import admin_approve_service, get_service_by_id
        admin_approve_service(s_id)
        srv = get_service_by_id(s_id)
        title = srv.get("title", f"#{s_id}") if srv else f"#{s_id}"
        await callback.message.edit_text(
            f"✅ <b>E'lon muvaffaqiyatli tasdiqlandi!</b>\n\n"
            f"📌 <b>Xizmat:</b> {title}\n"
            f"🟢 <b>Holati:</b> Faol (katalogda ko'rinadi)",
            parse_mode="HTML"
        )
        await callback.answer("E'lon tasdiqlandi va faol holatga keltirildi! ✅")
    except Exception as e:
        logger.error(f"E'lonni tasdiqlashda xatolik: {e}")
        await callback.answer("Xatolik yuz berdi!", show_alert=True)

@router.callback_query(F.data.startswith("admin_srv_del:"))
async def callback_admin_delete_service(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return
    try:
        s_id = int(callback.data.split(":")[1])
        from src.database import admin_delete_service, get_service_by_id
        srv = get_service_by_id(s_id)
        title = srv.get("title", f"#{s_id}") if srv else f"#{s_id}"
        admin_delete_service(s_id)
        await callback.message.edit_text(
            f"🗑 <b>E'lon o'chirildi!</b>\n\n"
            f"📌 <b>Xizmat:</b> {title}\n"
            f"❌ <b>Holati:</b> Butunlay bazadan o'chirildi",
            parse_mode="HTML"
        )
        await callback.answer("E'lon muvaffaqiyatli o'chirildi! 🗑", show_alert=True)
    except Exception as e:
        logger.error(f"E'lonni o'chirishda xatolik: {e}")
        await callback.answer("Xatolik yuz berdi!", show_alert=True)
