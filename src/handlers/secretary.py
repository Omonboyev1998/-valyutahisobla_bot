import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, BusinessConnection
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State

from src.database import (
    get_secretary_settings,
    update_secretary_settings,
    log_secretary_message,
    get_secretary_logs,
    clear_secretary_logs,
    get_secretary_owner_by_connection_id
)
from src.services.secretary_service import secretary_service, SECRETARY_MODES
from src.keyboards.secretary import (
    get_secretary_main_keyboard,
    get_secretary_modes_keyboard,
    get_secretary_logs_keyboard,
    get_secretary_back_keyboard
)

logger = logging.getLogger(__name__)

router = Router(name="secretary")

class SecretaryFSM(StatesGroup):
    waiting_for_custom_text = State()
    waiting_for_ai_instructions = State()

def format_secretary_menu_text(settings: dict) -> str:
    """Kotib asosiy menyu matnini chiroyli formatlaydi"""
    is_enabled = settings.get("is_enabled", 0) == 1
    status_text = "🟢 <b>FAOLLASHTIRILGAN</b>" if is_enabled else "🔴 <b>O'CHIRILGAN</b>"
    mode_key = settings.get("mode", "busy")
    mode_info = SECRETARY_MODES.get(mode_key, SECRETARY_MODES["busy"])
    urgent_text = "✅ <b>Yoqilgan</b> (Zudlik bilan xabar beriladi)" if settings.get("urgent_alerts", 1) == 1 else "❌ <b>O'chirilgan</b>"

    custom_txt = settings.get("custom_text", "").strip()
    preview_reply = custom_txt if (mode_key == "custom" and custom_txt) else mode_info["default_text"]
    if mode_key == "ai":
        preview_reply = "AI-kotib kelgan xabarni tahlil qilib, o'zingiz kiritgan ma'lumotlar asosida aqlli javob beradi."

    has_business = bool(settings.get("business_connection_id"))
    conn_badge = "🔗 <i>Telegram Business ulangan</i>" if has_business else "⚠️ <i>Hali Telegram Business bog'lanmagan</i>"

    return (
        f"🤖 <b>Shaxsiy Kotib / Sekretar Rejim</b>\n\n"
        f"Akkauntingiz uchun avto-javob beruvchi, shoshilinch xabarlarni saralovchi va siz band bo'lganingizda xabarlarni qabul qiluvchi shaxsiy yordamchingiz.\n\n"
        f"• <b>Holati:</b> {status_text}\n"
        f"• <b>Faol Rejim:</b> {mode_info['title']} ({mode_info['desc']})\n"
        f"• <b>Shoshilinch xabar filtri:</b> {urgent_text}\n"
        f"• <b>Akkaunt holati:</b> {conn_badge}\n\n"
        f"💬 <b>Hozirgi avtojavob ko'rinishi:</b>\n"
        f"<i>\"{preview_reply}\"</i>\n\n"
        f"<i>💡 Rejimni o'zgartirish yoki sozlash uchun pastdagi tugmalardan foydalaning:</i>"
    )

@router.message(Command("sekretar"))
@router.message(Command("secretary"))
@router.message(Command("kotib"))
@router.message(F.text == "🤖 Shaxsiy Kotib")
@router.message(F.text == "💼 Sekretar Rejim")
async def show_secretary_menu(message: Message, state: FSMContext):
    await state.clear()
    settings = get_secretary_settings(message.from_user.id)
    text = format_secretary_menu_text(settings)
    await message.answer(text, parse_mode="HTML", reply_markup=get_secretary_main_keyboard(settings))

@router.callback_query(F.data == "sec:back")
async def callback_secretary_back(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    settings = get_secretary_settings(callback.from_user.id)
    text = format_secretary_menu_text(settings)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_secretary_main_keyboard(settings))
    await callback.answer()

@router.callback_query(F.data == "sec:toggle")
async def callback_secretary_toggle(callback: CallbackQuery):
    settings = get_secretary_settings(callback.from_user.id)
    new_status = 0 if settings.get("is_enabled", 0) == 1 else 1
    update_secretary_settings(callback.from_user.id, is_enabled=new_status)
    settings["is_enabled"] = new_status
    text = format_secretary_menu_text(settings)
    status_alert = "✅ Kotib faollashtirildi!" if new_status == 1 else "⏸ Kotib o'chirildi."
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_secretary_main_keyboard(settings))
    await callback.answer(status_alert)

@router.callback_query(F.data == "sec:toggle_urgent")
async def callback_secretary_toggle_urgent(callback: CallbackQuery):
    settings = get_secretary_settings(callback.from_user.id)
    new_val = 0 if settings.get("urgent_alerts", 1) == 1 else 1
    update_secretary_settings(callback.from_user.id, urgent_alerts=new_val)
    settings["urgent_alerts"] = new_val
    text = format_secretary_menu_text(settings)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_secretary_main_keyboard(settings))
    await callback.answer("Shoshilinch xabar filtri yangilandi.")

@router.callback_query(F.data == "sec:modes")
async def callback_secretary_modes(callback: CallbackQuery):
    settings = get_secretary_settings(callback.from_user.id)
    current_mode = settings.get("mode", "busy")
    text = (
        "🎭 <b>Kotib rejimini tanlang:</b>\n\n"
        "Har bir rejim o'ziga mos maxsus xushmuomala matn bilan javob beradi:\n\n"
        "• ⏳ <b>Bandman</b> — Telefon yonida bo'lmaganingizda\n"
        "• 💼 <b>Yig'ilishda</b> — Uchrashuv yoki yig'ilishda bo'lganingizda\n"
        "• 🚗 <b>Ruldaman</b> — Mashina boshqarayotganingizda\n"
        "• 🌙 <b>Dam olish / Tun</b> — Kechki yoki tungi vaqtlarda\n"
        "• 🏖 <b>Ta'tildaman</b> — Safar va dam olish kunlarida\n"
        "• 🤖 <b>AI Kotib</b> — Aqlli sun'iy intellekt javobi\n"
        "• ✏️ <b>Shaxsiy matn</b> — O'zingiz kiritgan shablon\n"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_secretary_modes_keyboard(current_mode))
    await callback.answer()

@router.callback_query(F.data.startswith("sec_mode:"))
async def callback_secretary_select_mode(callback: CallbackQuery):
    new_mode = callback.data.split(":")[1]
    update_secretary_settings(callback.from_user.id, mode=new_mode)
    settings = get_secretary_settings(callback.from_user.id)
    text = format_secretary_menu_text(settings)
    mode_name = SECRETARY_MODES.get(new_mode, {}).get("title", new_mode)
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_secretary_main_keyboard(settings))
    await callback.answer(f"Rejim o'rnatildi: {mode_name}")

@router.callback_query(F.data == "sec:set_text")
async def callback_secretary_set_text(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SecretaryFSM.waiting_for_custom_text)
    text = (
        "✏️ <b>Shaxsiy avto-javob matnini kiriting:</b>\n\n"
        "Sizga lichkaga yozgan odamlarga yuboriladigan matnni yozing.\n"
        "<i>(Masalan: «Assalomu alaykum! Hozir ta'lim kursidaman. Soat 18:00 dan so'ng javob yozaman.»)</i>\n\n"
        "Bekor qilish uchun /cancel buyrug'ini yuboring."
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_secretary_back_keyboard())
    await callback.answer()

@router.message(SecretaryFSM.waiting_for_custom_text)
async def process_custom_text(message: Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        await state.clear()
        settings = get_secretary_settings(message.from_user.id)
        await message.answer("Jarayon bekor qilindi.", reply_markup=get_secretary_main_keyboard(settings))
        return

    new_text = message.text.strip()
    update_secretary_settings(message.from_user.id, custom_text=new_text, mode="custom")
    await state.clear()
    settings = get_secretary_settings(message.from_user.id)
    text = (
        "✅ <b>Shaxsiy avto-javob matni saqlandi va rejim 'Shaxsiy matn'ga o'tkazildi!</b>\n\n"
        + format_secretary_menu_text(settings)
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_secretary_main_keyboard(settings))

@router.callback_query(F.data == "sec:logs")
async def callback_secretary_logs(callback: CallbackQuery):
    logs = get_secretary_logs(callback.from_user.id, limit=12)
    digest_text = secretary_service.format_logs_digest(logs)
    await callback.message.edit_text(digest_text, parse_mode="HTML", reply_markup=get_secretary_logs_keyboard())
    await callback.answer()

@router.callback_query(F.data == "sec:clear_logs")
async def callback_secretary_clear_logs(callback: CallbackQuery):
    clear_secretary_logs(callback.from_user.id)
    await callback.message.edit_text(
        "🗑 <b>Kotib qabul qilgan barcha xabarlar tarixi tozalandi.</b>",
        parse_mode="HTML",
        reply_markup=get_secretary_back_keyboard()
    )
    await callback.answer("Tarix tozalandi.")

@router.callback_query(F.data == "sec:guide")
async def callback_secretary_guide(callback: CallbackQuery):
    text = (
        "ℹ️ <b>Botni Telegram akkauntingizga Kotib sifatida ulash qo'llanmasi:</b>\n\n"
        "Telegram Business (yoki Premium) foydalanuvchilari botni o'z akkauntlariga rasmiy kotib qilib ulashlari mumkin:\n\n"
        "1️⃣ Telegram ilovangizda <b>Sozlamalar (Настройки / Settings)</b> bo'limiga kiring.\n"
        "2️⃣ <b>Telegram Business</b> bo'limini oching.\n"
        "3️⃣ <b>Chatbots (Чат-боты / Chatbotlar)</b> qatorini tanlang.\n"
        "4️⃣ Botimizning username'ini qidiring va tanlang.\n"
        "5️⃣ Barcha ruxsatnomalarni (xabarlarga javob berish) tasdiqlang.\n\n"
        "🎉 Shundan so'ng bot sizning lichkangizga kelgan xabarlarga siz belgilagan rejim bo'yicha mustaqil avto-javob qaytaradi va shoshilinch xabarlarni sizga yetkazadi!"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_secretary_back_keyboard())
    await callback.answer()


# ==================== TELEGRAM BUSINESS EVENT HANDLERS ====================

@router.business_connection()
async def on_business_connection_update(connection: BusinessConnection, bot: Bot):
    """Foydalanuvchi botni Telegram Business orqali bog'laganda yoki uzganda chaqiriladi"""
    try:
        user_id = connection.user.id
        conn_id = connection.id
        is_enabled = 1 if connection.is_enabled else 0

        update_secretary_settings(
            user_id,
            is_enabled=is_enabled,
            business_connection_id=conn_id if is_enabled else ""
        )

        if is_enabled:
            congrats_text = (
                f"🎉 <b>Tabriklaymiz, {connection.user.first_name}!</b>\n\n"
                f"Siz botimizni shaxsiy Telegram akkauntingizga <b>Shaxsiy Kotib</b> sifatida muvaffaqiyatli bog'ladingiz.\n\n"
                f"Endi lichkangizga kelgan xabarlarga bot siz belgilagan rejim bo'yicha muloyim javob qaytaradi "
                f"va shoshilinch holatlarni darhol sizga bildiradi.\n\n"
                f"Sozlamalarni o'zgartirish uchun: /sekretar"
            )
            try:
                await bot.send_message(chat_id=user_id, text=congrats_text, parse_mode="HTML")
            except Exception as e:
                logger.warning(f"Business connection xabar yuborishda xatolik: {e}")
        else:
            try:
                await bot.send_message(
                    chat_id=user_id,
                    text="ℹ️ Siz botni shaxsiy akkauntingizdan uzdingiz. Kotib rejimi to'xtatildi.",
                    parse_mode="HTML"
                )
            except Exception:
                pass
    except Exception as e:
        logger.error(f"Error handling business connection: {e}")

@router.business_message()
async def on_incoming_business_message(message: Message, bot: Bot):
    """Foydalanuvchining shaxsiy lichkasiga xabar kelganda avto-kotib mantiqi"""
    try:
        conn_id = message.business_connection_id
        if not conn_id:
            return

        # Akkaunt egasini aniqlaymiz
        owner_settings = get_secretary_owner_by_connection_id(conn_id)
        if not owner_settings:
            return

        owner_id = owner_settings["user_id"]
        sender = message.from_user

        # Agar xabarni akkaunt egasining o'zi yozgan bo'lsa, o'ziga avtojavob bermaymiz!
        if sender and sender.id == owner_id:
            return

        # Agar kotib o'chirilgan bo'lsa
        if owner_settings.get("is_enabled", 0) != 1:
            return

        msg_text = message.text or message.caption or "[Media xabar]"
        sender_name = sender.full_name if sender else "Mijoz"
        sender_username = sender.username or ""

        # 1. Shoshilinch xabarni tekshirish
        is_urgent = secretary_service.is_urgent_message(msg_text)
        if is_urgent and owner_settings.get("urgent_alerts", 1) == 1:
            # Akkaunt egasiga darhol bot orqali tezkor signal yuboramiz!
            username_tag = f"(@{sender_username})" if sender_username else ""
            urgent_notification = (
                f"🚨 <b>DIQQAT! SHOSHILINCH XABAR KELDI!</b>\n\n"
                f"👤 <b>Kimdan:</b> {sender_name} {username_tag}\n"
                f"💬 <b>Xabar:</b> <i>\"{msg_text[:300]}\"</i>\n\n"
                f"⏰ <i>Iltimos, imkon qadar tezroq akkauntingizga kirib javob qaytaring!</i>"
            )
            try:
                await bot.send_message(chat_id=owner_id, text=urgent_notification, parse_mode="HTML")
            except Exception as err:
                logger.warning(f"Could not notify owner about urgent message: {err}")

        # 2. Cooldown tekshirish (Bir odamga ketma-ket har soniyada avtojavob yozmaslik)
        cooldown = owner_settings.get("cooldown_seconds", 1800)
        should_reply = secretary_service.should_respond_to_sender(owner_id, sender.id, cooldown)
        if not should_reply:
            return

        # 3. Avto-javob matnini shakllantiramiz
        mode = owner_settings.get("mode", "busy")
        custom_txt = owner_settings.get("custom_text", "")
        ai_inst = owner_settings.get("ai_instructions", "")

        reply_content = secretary_service.generate_auto_reply(
            mode=mode,
            custom_text=custom_txt,
            message_text=msg_text,
            sender_name=sender_name,
            ai_instructions=ai_inst
        )

        # 4. Javobni Business chatga yuboramiz
        await message.answer(reply_content, business_connection_id=conn_id)

        # 5. Logga qayd etamiz
        log_secretary_message(
            owner_id=owner_id,
            sender_id=sender.id,
            sender_name=sender_name,
            sender_username=sender_username,
            message_text=msg_text,
            bot_reply=reply_content,
            is_urgent=1 if is_urgent else 0
        )

    except Exception as e:
        logger.error(f"Error in on_incoming_business_message: {e}")
