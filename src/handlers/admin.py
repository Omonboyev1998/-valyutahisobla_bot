import asyncio
import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.exceptions import TelegramForbiddenError, TelegramBadRequest

from src.config import ADMIN_ID, ADMIN_IDS, WEB_APP_URL, TARGET_CHATS
from src.database import (
    get_statistics, export_users_csv, get_all_users, set_subscription,
    get_monitored_chats, toggle_monitored_chat, add_monitored_chat,
    get_userbot_setting, set_userbot_setting, count_auto_dms_sent,
    DEFAULT_AUTO_DM_TEMPLATE
)
from src.keyboards.admin import (
    get_admin_main_keyboard,
    get_broadcast_confirm_keyboard,
    get_admin_back_keyboard,
    get_userbot_chats_menu_keyboard,
    get_userbot_groups_toggle_keyboard,
    get_userbot_scan_selection_keyboard,
    get_scan_confirm_keyboard
)
from src.keyboards.reply import get_main_keyboard
from src.services.cbu_service import cbu_service
from src.userbot.listener import (
    get_userbot_dialog_groups,
    join_telegram_group,
    scan_single_chat
)

logger = logging.getLogger(__name__)

router = Router(name="admin")

class BroadcastState(StatesGroup):
    waiting_for_message = State()
    confirm = State()

class JoinGroupState(StatesGroup):
    waiting_for_link = State()

class AutoDmState(StatesGroup):
    waiting_for_template = State()

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

ADMIN_DASHBOARD_TEXT = (
    "👨‍💼 <b>Assalomu alaykum, Admin!</b>\n\n"
    "Valyuta boti boshqaruv paneliga xush kelibsiz.\n"
    "Quyidagi bo'limlardan birini tanlang:"
)

@router.message(Command("admin"))
@router.message(F.text == "👨‍💼 Admin Panel")
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

@router.message(F.text == "📢 E'lon yuborish")
@router.message(Command("elon"))
@router.message(Command("broadcast"))
async def cmd_direct_broadcast(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.set_state(BroadcastState.waiting_for_message)
    await message.answer(
        "📢 <b>Bot foydalanuvchilariga e'lon yuborish bo'limi</b>\n\n"
        "Barcha foydalanuvchilarga yubormoqchi bo'lgan e'loningizni yuboring.\n"
        "<i>(Matn, Rasm, Video yoki Forward qilingan xabar bo'lishi mumkin)</i>\n\n"
        "❌ Bekor qilish uchun: /cancel",
        parse_mode="HTML"
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

# ==================== USERBOT GURUHLAR BOSHQARUVI ====================

@router.callback_query(F.data == "admin:userbot_chats")
async def callback_admin_userbot_chats(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.clear()
    monitored = get_monitored_chats()
    active_count = sum(1 for m in monitored if m.get("is_active"))
    auto_dm_enabled = get_userbot_setting("auto_dm_enabled", "1") == "1"
    auto_dm_status = "✅ Yoqilgan" if auto_dm_enabled else "❌ O'chirilgan"
    dms_sent_count = count_auto_dms_sent()

    text = (
        "📡 <b>Userbot Guruh Kuzatuvchisi Boshqaruv Paneli</b>\n\n"
        f"🟢 <b>Faol kuzatilayotgan guruhlar:</b> {active_count} ta\n"
        f"📊 <b>Ro'yxatdagi jami guruhlar:</b> {len(monitored)} ta\n"
        f"💬 <b>Ustaga avto-xabar (Auto-DM):</b> {auto_dm_status}\n"
        f"📩 <b>Jami yuborilgan avto-xabarlar:</b> {dms_sent_count} ta\n\n"
        "Guruhlardan ustalar reklamalarini avtomatik ajratib olib, bot va Mini App'ga joylash hamda ustalar bilan shaxsiyda bog'lanish uchun quyidagi bo'limlardan foydalaning:"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_userbot_chats_menu_keyboard(auto_dm_enabled=auto_dm_enabled))
    await callback.answer()

@router.callback_query(F.data == "ub:toggle_autodm")
async def callback_userbot_toggle_autodm(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    current = get_userbot_setting("auto_dm_enabled", "1")
    new_val = "0" if current == "1" else "1"
    set_userbot_setting("auto_dm_enabled", new_val)
    status_str = "faollashtirildi ✅" if new_val == "1" else "to'xtatildi ❌"
    await callback.answer(f"Avto-xabar yuborish {status_str}!")

    monitored = get_monitored_chats()
    active_count = sum(1 for m in monitored if m.get("is_active"))
    auto_dm_enabled = new_val == "1"
    auto_dm_status = "✅ Yoqilgan" if auto_dm_enabled else "❌ O'chirilgan"
    dms_sent_count = count_auto_dms_sent()

    text = (
        "📡 <b>Userbot Guruh Kuzatuvchisi Boshqaruv Paneli</b>\n\n"
        f"🟢 <b>Faol kuzatilayotgan guruhlar:</b> {active_count} ta\n"
        f"📊 <b>Ro'yxatdagi jami guruhlar:</b> {len(monitored)} ta\n"
        f"💬 <b>Ustaga avto-xabar (Auto-DM):</b> {auto_dm_status}\n"
        f"📩 <b>Jami yuborilgan avto-xabarlar:</b> {dms_sent_count} ta\n\n"
        "Guruhlardan ustalar reklamalarini avtomatik ajratib olib, bot va Mini App'ga joylash hamda ustalar bilan shaxsiyda bog'lanish uchun quyidagi bo'limlardan foydalaning:"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_userbot_chats_menu_keyboard(auto_dm_enabled=auto_dm_enabled))

@router.callback_query(F.data == "ub:edit_dm_template")
async def callback_userbot_edit_dm_template(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(AutoDmState.waiting_for_template)
    current_tmpl = get_userbot_setting("auto_dm_template", DEFAULT_AUTO_DM_TEMPLATE)
    text = (
        "✏️ <b>Ustaga yuboriladigan avto-xabar matnini tahrirlash</b>\n\n"
        "Guruhda yangi usta topilganda uning shaxsiyiga yuboriladigan yangi matnni yozing.\n\n"
        "<b>Mavjud o'zgaruvchilar:</b>\n"
        "• <code>{master_name}</code> — Usta ismi\n"
        "• <code>{chat_title}</code> — Guruh nomi\n"
        "• <code>{service_id}</code> — E'lon ID raqami\n\n"
        f"<b>Hozirgi matn:</b>\n<i>{current_tmpl}</i>\n\n"
        "Standart holatga qaytarish uchun: <code>/default</code>\n"
        "Bekor qilish uchun: /cancel"
    )
    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()

@router.message(AutoDmState.waiting_for_template)
async def process_new_auto_dm_template(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    text = (message.text or "").strip()
    if text == "/cancel":
        await state.clear()
        await message.answer("Tahrirlash bekor qilindi.", reply_markup=get_admin_main_keyboard())
        return

    if text == "/default":
        set_userbot_setting("auto_dm_template", DEFAULT_AUTO_DM_TEMPLATE)
        await state.clear()
        await message.answer("✅ Avto-xabar matni standart holatga qaytarildi!", reply_markup=get_admin_back_keyboard())
        return

    set_userbot_setting("auto_dm_template", text)
    await state.clear()
    await message.answer(
        "🎉 <b>Yangi avto-xabar matni muvaffaqiyatli saqlandi!</b>\n\n"
        f"Endi har bir yangi usta topilganda unga ushbu matn yuboriladi:\n\n<i>{text}</i>",
        parse_mode="HTML",
        reply_markup=get_admin_back_keyboard()
    )

@router.callback_query(F.data.startswith("ub:dialogs:"))
async def callback_userbot_dialogs(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    page = int(callback.data.split(":")[2])
    await callback.answer("Guruhlar ro'yxati olinmoqda...")
    try:
        groups = await get_userbot_dialog_groups(limit=100)
        monitored = get_monitored_chats()
        active_ids = {m["chat_id"] for m in monitored if m.get("is_active")}
        
        # Standart TARGET_CHATS dagi guruhlarni ham avtomatik belgilash
        for g in groups:
            if any(t.lower() in g["title"].lower() for t in TARGET_CHATS):
                active_ids.add(g["id"])

        kb = get_userbot_groups_toggle_keyboard(groups, active_ids, page=page)
        text = (
            "📋 <b>Akkauntingiz a'zo bo'lgan guruhlar</b>\n\n"
            "Kuzatmoqchi bo'lgan guruhingiz ustiga bosing:\n"
            "✅ — Hozir kuzatuvda (reklamalar botga tushadi)\n"
            "➕ — Kuzatilmayapti (yoqish uchun bosing)\n"
        )
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception as e:
        logger.error(f"Error fetching userbot dialogs: {e}")
        await callback.message.edit_text(
            f"❌ Guruhlarni olishda xatolik yuz berdi:\n<code>{e}</code>",
            parse_mode="HTML",
            reply_markup=get_admin_back_keyboard()
        )

@router.callback_query(F.data.startswith("ub:toggle:"))
async def callback_userbot_toggle(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")
    chat_id = int(parts[2])
    page = int(parts[3])

    groups = await get_userbot_dialog_groups(limit=100)
    title = next((g["title"] for g in groups if g["id"] == chat_id), "Guruh")
    username = next((g["username"] for g in groups if g["id"] == chat_id), None)

    new_status = toggle_monitored_chat(chat_id, title, username)
    status_str = "faollashtirildi ✅" if new_status else "to'xtatildi ❌"
    await callback.answer(f"{title[:20]} {status_str}!")

    monitored = get_monitored_chats()
    active_ids = {m["chat_id"] for m in monitored if m.get("is_active")}
    kb = get_userbot_groups_toggle_keyboard(groups, active_ids, page=page)
    await callback.message.edit_reply_markup(reply_markup=kb)

@router.callback_query(F.data == "ub:join_prompt")
async def callback_userbot_join_prompt(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    await state.set_state(JoinGroupState.waiting_for_link)
    await callback.message.edit_text(
        "➕ <b>Havola orqali guruhga qo'shilish</b>\n\n"
        "Guruhning havolasini yuboring (masalan: <code>https://t.me/+AbCdEf...</code> yoki <code>@guruh_nomi</code>):\n\n"
        "Akkauntingiz ushbu guruhga o'zi avtomatik a'zo bo'ladi va uni kuzatuv ro'yxatiga kiritadi.\n\n"
        "❌ Bekor qilish uchun: /cancel",
        parse_mode="HTML"
    )
    await callback.answer()

@router.message(JoinGroupState.waiting_for_link)
async def process_join_group_link(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    link = (message.text or "").strip()
    if link == "/cancel":
        await state.clear()
        await message.answer("Bekor qilindi.", reply_markup=get_admin_main_keyboard())
        return

    wait_msg = await message.answer("⏳ Guruhga a'zo bo'linmoqda, kuting...")
    success, res_msg = await join_telegram_group(link)
    await state.clear()
    if success:
        await wait_msg.edit_text(
            f"🎉 <b>Muvaffaqiyatli!</b>\n\n{res_msg}\nGuruh avtomatik kuzatuv ro'yxatiga qo'shildi va undan reklamalar ushlanadi.",
            parse_mode="HTML",
            reply_markup=get_admin_back_keyboard()
        )
    else:
        await wait_msg.edit_text(
            f"❌ <b>A'zo bo'lishda xatolik yuz berdi:</b>\n<code>{res_msg}</code>",
            parse_mode="HTML",
            reply_markup=get_admin_back_keyboard()
        )

@router.callback_query(F.data.startswith("ub:scan_menu:"))
async def callback_scan_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    page = int(callback.data.split(":")[2])
    await callback.answer("Guruhlar ro'yxati olinmoqda...")
    try:
        groups = await get_userbot_dialog_groups(limit=100)
        kb = get_userbot_scan_selection_keyboard(groups, page=page)
        await callback.message.edit_text(
            "🔍 <b>Tarixini skanerlamoqchi bo'lgan guruhni tanlang:</b>\n\n"
            "Guruhdagi avvalgi e'lonlar aylanib chiqiladi va yangi ustalar bazaga qo'shiladi.",
            parse_mode="HTML",
            reply_markup=kb
        )
    except Exception as e:
        await callback.message.edit_text(f"Xatolik: {e}", reply_markup=get_admin_back_keyboard())

@router.callback_query(F.data.startswith("ub:scan_pick:"))
async def callback_scan_pick(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        return
    chat_id = int(callback.data.split(":")[2])
    kb = get_scan_confirm_keyboard(chat_id)
    await callback.message.edit_text(
        "⚡️ <b>Ushbu guruhdagi oxirgi nechta xabarni tahlil qilamiz?</b>\n\n"
        "Tanlang:",
        parse_mode="HTML",
        reply_markup=kb
    )
    await callback.answer()

@router.callback_query(F.data.startswith("ub:do_scan:"))
async def callback_do_scan(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id):
        return
    parts = callback.data.split(":")
    chat_id = int(parts[2])
    limit = int(parts[3])
    await callback.message.edit_text(f"⏳ Oxirgi {limit} ta xabar tahlil qilinmoqda, iltimos kuting...")
    try:
        added = await scan_single_chat(chat_id, bot, limit=limit)
        await callback.message.edit_text(
            f"🎉 <b>Skanerlash muvaffaqiyatli yakunlandi!</b>\n\n"
            f"✅ <b>Jami qo'shilgan yangi ustalar soni:</b> {added} ta\n\n"
            f"Barcha yangi ustalar bot va Mini App'dagi ro'yxatga muvaffaqiyatli kiritildi.",
            parse_mode="HTML",
            reply_markup=get_admin_back_keyboard()
        )
    except Exception as e:
        logger.error(f"Error in scan: {e}")
        await callback.message.edit_text(f"❌ Skanerlashda xatolik yuz berdi:\n<code>{e}</code>", parse_mode="HTML", reply_markup=get_admin_back_keyboard())

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
    await message.answer("Amal bekor qilindi. Asosiy menyudasiz.", reply_markup=get_main_keyboard(message.from_user.id))

@router.message(BroadcastState.waiting_for_message)
async def process_broadcast_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    # Xabar parametrlarini saqlab olamiz
    await state.update_data(
        from_chat_id=message.chat.id,
        message_id=message.message_id,
        with_app_btn=False
    )
    await state.set_state(BroadcastState.confirm)

    # Foydalanuvchiga preview (ko'rinish) yuboramiz
    await message.reply(
        "👆 <b>Xabaringiz yuqoridagidek ko'rinishda yuboriladi.</b>\n\n"
        "Xabar ostiga '📱 Mini App' tugmasini qo'shishingiz yoki darhol yuborishingiz mumkin:",
        parse_mode="HTML",
        reply_markup=get_broadcast_confirm_keyboard(with_app_btn=False)
    )

@router.callback_query(BroadcastState.confirm, F.data == "broadcast:toggle_btn")
async def callback_toggle_broadcast_btn(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        return
    data = await state.get_data()
    current_val = data.get("with_app_btn", False)
    new_val = not current_val
    await state.update_data(with_app_btn=new_val)
    await callback.message.edit_reply_markup(reply_markup=get_broadcast_confirm_keyboard(new_val))
    status_text = "Mini App tugmasi qo'shildi! ✅" if new_val else "Mini App tugmasi olib tashlandi. ❌"
    await callback.answer(status_text)

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
    with_app_btn = data.get("with_app_btn", False)
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

    from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    app_markup = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📱 Mini Appni ochish", web_app=WebAppInfo(url=WEB_APP_URL))]
    ]) if with_app_btn else None

    sent = 0
    blocked = 0

    for idx, uid in enumerate(user_ids, 1):
        try:
            await bot.copy_message(
                chat_id=uid,
                from_chat_id=from_chat_id,
                message_id=msg_id,
                reply_markup=app_markup
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
