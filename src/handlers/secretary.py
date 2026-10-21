import logging
import asyncio
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
    get_secretary_owner_by_connection_id,
    get_secretary_schedules,
    add_secretary_schedule,
    delete_secretary_schedule,
    toggle_secretary_schedule,
    seed_default_secretary_schedules_if_empty,
    get_recent_chat_history
)
from src.services.secretary_service import secretary_service, SECRETARY_MODES
from src.services.ai_secretary_service import generate_ai_reply
from src.keyboards.secretary import (
    get_secretary_main_keyboard,
    get_secretary_modes_keyboard,
    get_secretary_logs_keyboard,
    get_secretary_back_keyboard,
    get_secretary_schedules_keyboard,
    get_secretary_schedule_item_keyboard,
    get_secretary_cancel_keyboard
)
from src.keyboards.reply import get_main_keyboard

logger = logging.getLogger(__name__)

router = Router(name="secretary")

class SecretaryFSM(StatesGroup):
    waiting_for_custom_text = State()
    waiting_for_ai_instructions = State()
    waiting_for_test_ai_query = State()

class SecretaryScheduleFSM(StatesGroup):
    waiting_for_title_and_time = State()
    waiting_for_reply_text = State()

def format_secretary_menu_text(settings: dict) -> str:
    """Kotib asosiy menyu matnini chiroyli formatlaydi"""
    is_enabled = settings.get("is_enabled", 0) == 1
    status_text = "🟢 <b>FAOLLASHTIRILGAN</b>" if is_enabled else "🔴 <b>O'CHIRILGAN</b>"
    mode_key = settings.get("mode", "busy")
    mode_info = SECRETARY_MODES.get(mode_key, SECRETARY_MODES["busy"])
    urgent_text = "✅ <b>Yoqilgan</b> (Zudlik bilan xabar beriladi)" if settings.get("urgent_alerts", 1) == 1 else "❌ <b>O'chirilgan</b>"

    custom_txt = settings.get("custom_text", "").strip()
    preview_reply = custom_txt if (mode_key == "custom" and custom_txt) else mode_info.get("default_text", "")
    if mode_key == "ai":
        ai_inst = settings.get("ai_instructions", "").strip()
        if ai_inst:
            preview_reply = f"🤖 AI Kotib (Google Gemini 1.5)\n📌 Yo'riqnomangiz: \"{ai_inst[:90]}...\""
        else:
            preview_reply = "🤖 AI Kotib (Google Gemini 1.5)\nKelgan xabarga mos aqlli va xushmuomala javob qaytaradi."
    elif mode_key == "schedule":
        user_id = settings.get("user_id") or 0
        active_sched = secretary_service.get_active_scheduled_reply(user_id) if user_id else None
        if active_sched:
            sched_name = active_sched.get('title') or "Jadval"
            preview_reply = f"[{sched_name}: {active_sched.get('start_time')}-{active_sched.get('end_time')}]\n{active_sched.get('reply_text')}"
        else:
            preview_reply = "Hozirgi vaqt uchun maxsus jadval topilmadi, standart javob beriladi."

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
@router.message(F.text.contains("Kotib"))
@router.message(F.text.contains("kotib"))
@router.message(F.text.contains("Sekretar"))
@router.message(F.text.contains("sekretar"))
async def show_secretary_menu(message: Message, state: FSMContext):
    await state.clear()
    settings = get_secretary_settings(message.from_user.id)
    text = format_secretary_menu_text(settings)
    # Telefon klaviaturasini yangilash
    await message.answer("🤖 <b>Shaxsiy Kotib menyusi:</b>", reply_markup=get_main_keyboard(message.from_user.id), parse_mode="HTML")
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_secretary_main_keyboard(settings)
    )

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

@router.callback_query(F.data == "sec:set_ai")
async def callback_secretary_set_ai(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SecretaryFSM.waiting_for_ai_instructions)
    settings = get_secretary_settings(callback.from_user.id)
    current_inst = settings.get("ai_instructions", "").strip()
    preview = f"\n\n📌 <b>Hozirgi yo'riqnomangiz:</b>\n<i>\"{current_inst}\"</i>" if current_inst else ""
    text = (
        "🧠 <b>AI-Kotib uchun shaxsiy yo'riqnomani kiriting:</b>\n\n"
        "AI sun'iy intellekti siz haqingizda nimalarni bilishi va xabarlarga qanday mezonlar asosida javob berishi kerakligini yozing.\n\n"
        "<b>Misol:</b>\n"
        "<i>«Men oliygohda domlaman / dasturchiman. Talabalarimga domla sifatida darslar bo'yicha, ota-onamga juda mehrli va samimiy, do'stlarimga jo'ralarcha qisqa, mijozlarga esa xushmuomala javob ber.»</i>\n\n"
        "<i>(Bekor qilish uchun /cancel yozing)</i>"
        + preview
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_secretary_back_keyboard())
    await callback.answer()

@router.message(SecretaryFSM.waiting_for_ai_instructions)
async def process_ai_instructions(message: Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        await state.clear()
        settings = get_secretary_settings(message.from_user.id)
        await message.answer("Jarayon bekor qilindi.", reply_markup=get_secretary_main_keyboard(settings))
        return

    new_instructions = message.text.strip()
    update_secretary_settings(message.from_user.id, ai_instructions=new_instructions, mode="ai")
    await state.clear()
    settings = get_secretary_settings(message.from_user.id)
    text = (
        "🤖 <b>AI-Kotib yo'riqnomasi muvaffaqiyatli saqlandi!</b>\n\n"
        "Endi shaxsiy akkauntingizga kelgan xabarlarga sun'iy intellekt siz kiritgan ma'lumotlar asosida aqlli va muloyim javob beradi.\n\n"
        + format_secretary_menu_text(settings)
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_secretary_main_keyboard(settings))

@router.callback_query(F.data == "sec:test_ai")
async def callback_secretary_test_ai(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SecretaryFSM.waiting_for_test_ai_query)
    settings = get_secretary_settings(callback.from_user.id)
    ai_inst = settings.get("ai_instructions", "").strip()
    preview = f"\n\n📌 <b>Faol yo'riqnoma:</b> <i>\"{ai_inst[:80]}...\"</i>" if ai_inst else "\n\n⚠️ <i>Hozircha yo'riqnoma kiritilmagan. Standart yordamchi tarzida javob beradi.</i>"
    text = (
        "🧪 <b>AI-Kotib javobini sinab ko'rish:</b>\n\n"
        "Xuddi mijozdek xabar yozing yoki <b>ovozli xabar (golosovoy)</b> yuboring!\n\n"
        "AI kotib yo'riqnomangiz asosida yozma yoki ovozli savollaringizga qanday javob qaytarishini shu yerda sinab ko'rishingiz mumkin.\n\n"
        "<i>(Sinovdan chiqish uchun /cancel yozing)</i>"
        + preview
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_secretary_back_keyboard())
    await callback.answer()

@router.message(SecretaryFSM.waiting_for_test_ai_query)
async def process_test_ai_query(message: Message, state: FSMContext, bot: Bot):
    if message.text and message.text.startswith("/"):
        await state.clear()
        settings = get_secretary_settings(message.from_user.id)
        await message.answer("Sinov rejimidan chiqildi.", reply_markup=get_secretary_main_keyboard(settings))
        return

    settings = get_secretary_settings(message.from_user.id)
    ai_inst = settings.get("ai_instructions", "")
    owner_name = message.from_user.full_name or "Akkaunt egasi"

    wait_msg = await message.answer("🤖 <i>AI tahlil qilmoqda...</i>", parse_mode="HTML")

    if message.voice or message.audio:
        from io import BytesIO
        from src.services.ai_secretary_service import generate_ai_voice_reply
        buf = BytesIO()
        target = message.voice or message.audio
        mime_type = "audio/ogg" if message.voice else (message.audio.mime_type or "audio/mp3")
        try:
            await bot.download(target, destination=buf)
            audio_bytes = buf.getvalue()
        except Exception as dl_err:
            audio_bytes = b""
            logger.error(f"Test voice download error: {dl_err}")

        reply = await generate_ai_voice_reply(
            sender_name="Mijoz (Sinov)",
            audio_bytes=audio_bytes,
            mime_type=mime_type,
            ai_instructions=ai_inst,
            owner_name=owner_name
        )
        query_text = "[🎙 Yuborilgan ovozli xabar]"
    else:
        query_text = (message.text or message.caption or "").strip()
        reply = await generate_ai_reply(
            sender_name="Mijoz (Sinov)",
            message_text=query_text,
            ai_instructions=ai_inst,
            owner_name=owner_name
        )

    try:
        await wait_msg.delete()
    except Exception:
        pass

    res_text = (
        f"🧪 <b>Sinov natijasi:</b>\n\n"
        f"👤 <b>Mijoz:</b> <i>\"{query_text}\"</i>\n\n"
        f"<b>🤖 AI javobi:</b>\n{reply}\n\n"
        f"<i>Yana savol yoki ovozli xabar yuborib ko'rishingiz mumkin (chiqish uchun /cancel).</i>"
    )
    await message.answer(res_text, parse_mode="HTML", reply_markup=get_secretary_back_keyboard())

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
        "⚠️ <b>DIQQAT:</b> Agar Telegram Business'da botni tanlash imkoni chiqmasa:\n"
        "Telegramda <b>@BotFather</b> botiga kiring ➡️ <code>/mybots</code> ➡️ botingizni tanlang ➡️ <b>Bot Settings</b> ➡️ <b>Business Mode</b> ➡️ <b>Turn on</b> (Yoqish) tugmasini bosing!\n\n"
        "🎉 Shundan so'ng bot sizning lichkangizga kelgan xabarlarga siz belgilagan rejim bo'yicha mustaqil avto-javob qaytaradi va shoshilinch xabarlarni sizga yetkazadi!"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_secretary_back_keyboard())
    await callback.answer()

# ==================== SCHEDULES MANAGEMENT ====================

@router.callback_query(F.data == "sec:schedules")
async def callback_secretary_schedules(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    seed_default_secretary_schedules_if_empty(callback.from_user.id)
    schedules = get_secretary_schedules(callback.from_user.id)
    text = secretary_service.format_schedules_text(schedules)
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_secretary_schedules_keyboard(schedules)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("sec_sched_view:"))
async def callback_secretary_schedule_view(callback: CallbackQuery):
    sched_id = int(callback.data.split(":")[1])
    schedules = get_secretary_schedules(callback.from_user.id)
    item = next((s for s in schedules if s["id"] == sched_id), None)
    if not item:
        await callback.answer("Jadval topilmadi.", show_alert=True)
        return

    status_str = "🟢 Faol (Ishlayapti)" if item.get("is_active") else "⚪️ O'chirilgan"
    text = (
        f"⏰ <b>Jadval tafsiloti:</b>\n\n"
        f"📌 <b>Nomi:</b> {item.get('title')}\n"
        f"⏳ <b>Vaqt oralig'i:</b> {item.get('start_time')} - {item.get('end_time')}\n"
        f"🔘 <b>Holati:</b> {status_str}\n\n"
        f"💬 <b>Ushbu vaqtda yuboriladigan avto-javob:</b>\n"
        f"<i>\"{item.get('reply_text')}\"</i>"
    )
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_secretary_schedule_item_keyboard(sched_id, bool(item.get("is_active")))
    )
    await callback.answer()

@router.callback_query(F.data.startswith("sec_sched_toggle:"))
async def callback_secretary_schedule_toggle(callback: CallbackQuery):
    sched_id = int(callback.data.split(":")[1])
    toggle_secretary_schedule(sched_id, callback.from_user.id)
    schedules = get_secretary_schedules(callback.from_user.id)
    item = next((s for s in schedules if s["id"] == sched_id), None)
    if item:
        status_alert = "🟢 Jadval faollashtirildi!" if item.get("is_active") else "⏸ Jadval o'chirildi."
        status_str = "🟢 Faol (Ishlayapti)" if item.get("is_active") else "⚪️ O'chirilgan"
        text = (
            f"⏰ <b>Jadval tafsiloti:</b>\n\n"
            f"📌 <b>Nomi:</b> {item.get('title')}\n"
            f"⏳ <b>Vaqt oralig'i:</b> {item.get('start_time')} - {item.get('end_time')}\n"
            f"🔘 <b>Holati:</b> {status_str}\n\n"
            f"💬 <b>Ushbu vaqtda yuboriladigan avto-javob:</b>\n"
            f"<i>\"{item.get('reply_text')}\"</i>"
        )
        await callback.message.edit_text(
            text,
            parse_mode="HTML",
            reply_markup=get_secretary_schedule_item_keyboard(sched_id, bool(item.get("is_active")))
        )
        await callback.answer(status_alert)
    else:
        await callback.answer("Yangilandi.")

@router.callback_query(F.data.startswith("sec_sched_del:"))
async def callback_secretary_schedule_del(callback: CallbackQuery):
    sched_id = int(callback.data.split(":")[1])
    delete_secretary_schedule(sched_id, callback.from_user.id)
    schedules = get_secretary_schedules(callback.from_user.id)
    text = secretary_service.format_schedules_text(schedules)
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_secretary_schedules_keyboard(schedules)
    )
    await callback.answer("🗑 Jadval o'chirildi!", show_alert=True)

@router.callback_query(F.data == "sec_sched_reset")
async def callback_secretary_schedule_reset(callback: CallbackQuery):
    seed_default_secretary_schedules_if_empty(callback.from_user.id, force_reset=True)
    schedules = get_secretary_schedules(callback.from_user.id)
    text = secretary_service.format_schedules_text(schedules)
    await callback.message.edit_text(
        text,
        parse_mode="HTML",
        reply_markup=get_secretary_schedules_keyboard(schedules)
    )
    await callback.answer("Standart jadvallar qayta tiklandi.")

@router.callback_query(F.data == "sec_sched_add")
async def callback_secretary_schedule_add(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SecretaryScheduleFSM.waiting_for_title_and_time)
    text = (
        "⏰ <b>Yangi vaqt oralig'i qo'shish (1-qadam):</b>\n\n"
        "Nomi va vaqt oralig'ini quyidagi formatda yuboring:\n"
        "<code>Nomi | HH:MM - HH:MM</code>\n\n"
        "<b>Misollar:</b>\n"
        "• <code>Ish vaqti | 09:00 - 18:00</code>\n"
        "• <code>Tushlik | 13:00 - 14:00</code>\n"
        "• <code>Kechki dam | 18:00 - 23:00</code>\n"
        "• <code>Tungi uyqu | 23:00 - 08:00</code>\n\n"
        "<i>Bekor qilish uchun /cancel yozing yoki tugmani bosing.</i>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_secretary_cancel_keyboard("sec:schedules"))
    await callback.answer()

@router.message(SecretaryScheduleFSM.waiting_for_title_and_time)
async def process_schedule_title_and_time(message: Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        await state.clear()
        schedules = get_secretary_schedules(message.from_user.id)
        await message.answer("Jarayon bekor qilindi.", reply_markup=get_secretary_schedules_keyboard(schedules))
        return

    raw = message.text.strip()
    import re
    time_match = re.search(r'(\d{1,2}:\d{2})\s*[-—–to]+\s*(\d{1,2}:\d{2})', raw)
    if not time_match:
        await message.answer(
            "⚠️ <b>Vaqt formati noto'g'ri kiritildi!</b>\n\n"
            "Iltimos, quyidagi namunadagidek yuboring:\n"
            "<code>Ish vaqti | 09:00 - 18:00</code>\n\n"
            "Qaytadan kiriting:",
            parse_mode="HTML",
            reply_markup=get_secretary_cancel_keyboard("sec:schedules")
        )
        return

    def normalize_time(t_str: str) -> str:
        parts = t_str.strip().split(":")
        h = int(parts[0])
        m = int(parts[1])
        if h > 23 or m > 59:
            raise ValueError()
        return f"{h:02d}:{m:02d}"

    try:
        start_t = normalize_time(time_match.group(1))
        end_t = normalize_time(time_match.group(2))
    except Exception:
        await message.answer("⚠️ Soat 00:00 dan 23:59 gacha bo'lishi kerak. Qaytadan kiriting:")
        return

    parts = raw.split("|")
    if len(parts) >= 2:
        title = parts[0].strip()
    else:
        title = f"{start_t} - {end_t}"

    await state.update_data(title=title, start_time=start_t, end_time=end_t)
    await state.set_state(SecretaryScheduleFSM.waiting_for_reply_text)

    await message.answer(
        f"✅ <b>Vaqt:</b> {title} (<code>{start_t} - {end_t}</code>)\n\n"
        f"💬 <b>2-qadam:</b> Ushbu vaqt oralig'ida yozganlarga qanday avto-javob yuborilsin?\n\n"
        f"<i>(Masalan: «Assalomu alaykum! Hozir ish vaqtidaman. Xabaringizni ko'rib tezda javob beraman.»)</i>",
        parse_mode="HTML",
        reply_markup=get_secretary_cancel_keyboard("sec:schedules")
    )

@router.message(SecretaryScheduleFSM.waiting_for_reply_text)
async def process_schedule_reply_text(message: Message, state: FSMContext):
    if message.text and message.text.startswith("/"):
        await state.clear()
        schedules = get_secretary_schedules(message.from_user.id)
        await message.answer("Jarayon bekor qilindi.", reply_markup=get_secretary_schedules_keyboard(schedules))
        return

    reply_text = message.text.strip()
    data = await state.get_data()
    title = data.get("title", "Oraliq")
    start_time = data.get("start_time", "09:00")
    end_time = data.get("end_time", "18:00")

    add_secretary_schedule(
        user_id=message.from_user.id,
        title=title,
        start_time=start_time,
        end_time=end_time,
        reply_text=reply_text,
        is_active=1
    )
    # Avtomatik ravishda jadval rejimini faollashtiramiz
    update_secretary_settings(message.from_user.id, mode="schedule")
    await state.clear()

    schedules = get_secretary_schedules(message.from_user.id)
    text = (
        f"🎉 <b>Yangi vaqt jadvali muvaffaqiyatli saqlandi!</b>\n\n"
        f"📌 <b>{title}</b> (<code>{start_time} - {end_time}</code>)\n"
        f"💬 <i>\"{reply_text}\"</i>\n\n"
        f"Rejim avtomatik ravishda <b>⏰ Vaqt jadvallari</b> rejimiga o'tkazildi.\n\n"
        + secretary_service.format_schedules_text(schedules)
    )
    await message.answer(
        text,
        parse_mode="HTML",
        reply_markup=get_secretary_schedules_keyboard(schedules)
    )


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
            # Agar DBda bog'lanish saqlanmagan bo'lsa, Telegram API orqali olamiz
            try:
                b_conn = await bot.get_business_connection(business_connection_id=conn_id)
                if b_conn and b_conn.user:
                    user_id = b_conn.user.id
                    update_secretary_settings(
                        user_id,
                        business_connection_id=conn_id,
                        is_enabled=1 if b_conn.is_enabled else 0
                    )
                    owner_settings = get_secretary_settings(user_id)
            except Exception as conn_err:
                logger.warning(f"Failed to fetch business connection info for {conn_id}: {conn_err}")
                return

        if not owner_settings:
            return

        owner_id = owner_settings["user_id"]
        sender = message.from_user

        # Agar xabarni akkaunt egasining o'zi yozgan bo'lsa, o'ziga avtojavob bermaymiz!
        if sender and sender.id == owner_id:
            # Akkaunt egasining o'zi suhbatlashayotganini qayd etamiz (cooldown yangilanadi va bot xalaqit bermaydi)
            log_secretary_message(
                owner_id=owner_id,
                sender_id=message.chat.id,
                sender_name="Siz (Akkaunt egasi)",
                sender_username="",
                message_text=message.text or message.caption or "[Chiqish xabari]",
                bot_reply="[Ega tomonidan qo'lda javob yozildi]",
                is_urgent=0
            )
            return

        # Agar kotib o'chirilgan bo'lsa
        if owner_settings.get("is_enabled", 0) != 1:
            return

        # Ovozli yoki audio xabar kelganini aniqlaymiz
        is_voice = bool(message.voice or message.audio)
        audio_bytes = b""
        mime_type = "audio/ogg"

        if message.voice:
            mime_type = "audio/ogg"
            try:
                from io import BytesIO
                buf = BytesIO()
                await bot.download(message.voice, destination=buf)
                audio_bytes = buf.getvalue()
            except Exception as dl_err:
                logger.warning(f"Voice download failed: {dl_err}")
        elif message.audio:
            mime_type = message.audio.mime_type or "audio/mp3"
            try:
                from io import BytesIO
                buf = BytesIO()
                await bot.download(message.audio, destination=buf)
                audio_bytes = buf.getvalue()
            except Exception as dl_err:
                logger.warning(f"Audio download failed: {dl_err}")

        msg_text = message.text or message.caption or ("[🎙 Ovozli xabar]" if is_voice else "[Media xabar]")
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

        # 2. Cooldown va aqlli filtrlash (Bir odamga ketma-ket avtojavob yozmaslik, minnatdorchiliklarda jim turish)
        cooldown = owner_settings.get("cooldown_seconds", 300)
        mode = owner_settings.get("mode", "busy")
        should_reply = secretary_service.should_respond_to_sender(
            owner_id=owner_id,
            sender_id=sender.id,
            cooldown_seconds=cooldown,
            message_text=msg_text,
            mode=mode
        )
        if not should_reply:
            return

        # 3. Yozmoqda... (Typing) effektini yoqamiz (insoniy va tabiiy ko'rinishi uchun)
        try:
            await bot.send_chat_action(
                chat_id=message.chat.id,
                action="typing",
                business_connection_id=conn_id
            )
        except Exception:
            pass

        # 4. Dialog tarixini olamiz (AI o'tmishdagi suhbatni eslab qolishi uchun)
        chat_history = get_recent_chat_history(owner_id, sender.id, limit=4)

        # Qisqa tabiiy kutish (0.8 - 1.5 soniya)
        await asyncio.sleep(1.2)

        # 5. Avto-javob matnini shakllantiramiz
        custom_txt = owner_settings.get("custom_text", "")
        ai_inst = owner_settings.get("ai_instructions", "")

        if is_voice and audio_bytes:
            reply_content = await secretary_service.generate_auto_voice_reply(
                mode=mode,
                custom_text=custom_txt,
                sender_name=sender_name,
                audio_bytes=audio_bytes,
                mime_type=mime_type,
                ai_instructions=ai_inst,
                user_id=owner_id,
                chat_history=chat_history
            )
        else:
            reply_content = await secretary_service.generate_auto_reply(
                mode=mode,
                custom_text=custom_txt,
                message_text=msg_text,
                sender_name=sender_name,
                ai_instructions=ai_inst,
                user_id=owner_id,
                chat_history=chat_history
            )

        # 4. Javobni Business chatga yuboramiz
        try:
            await bot.send_message(
                chat_id=message.chat.id,
                text=reply_content,
                business_connection_id=conn_id
            )
        except Exception as send_err:
            logger.error(f"Failed to send business reply for {owner_id}: {send_err}")
            return

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
