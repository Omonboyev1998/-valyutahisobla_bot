from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from src.database import is_user_subscribed, set_subscription, add_user
from src.keyboards.inline import get_subscription_keyboard
from src.handlers.rates import build_popular_rates_message

router = Router(name="notifications")

def get_status_text(is_sub: bool) -> str:
    status_icon = "✅ Faol" if is_sub else "❌ O'chirilgan"
    return (
        f"🔔 <b>Kunlik tonggi eslatmalar sozlamasi</b>\n\n"
        f"📌 Joriy holat: <b>{status_icon}</b>\n\n"
        f"Har kuni ertalab soat <b>09:00 da</b> Markaziy Bankning yangi valyuta kurslari "
        f"avtomatik tarzda sizga xabar sifatida yuboriladi.\n\n"
        f"Quyidagi tugmalar orqali eslatmalarni yoqishingiz, o'chirishingiz yoki hoziroq sinab ko'rishingiz mumkin:"
    )

@router.message(F.text.contains("Eslatmalar"))
async def show_notifications_settings(message: Message):
    user = message.from_user
    add_user(user.id, user.full_name or "Foydalanuvchi", user.username)
    is_sub = is_user_subscribed(user.id)
    text = get_status_text(is_sub)
    await message.answer(text, parse_mode="HTML", reply_markup=get_subscription_keyboard(is_sub))

@router.callback_query(F.data.startswith("sub_toggle:"))
async def toggle_sub_callback(callback: CallbackQuery):
    action = callback.data.split(":")[1]
    new_status = (action == "on")
    user_id = callback.from_user.id
    set_subscription(user_id, new_status)

    alert_text = "Eslatmalar yoqildi! Har kuni 09:00 da kurslar yuboriladi. 🔔" if new_status else "Eslatmalar o'chirildi! 🔕"
    text = get_status_text(new_status)
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_subscription_keyboard(new_status))
    except Exception:
        pass
    await callback.answer(alert_text, show_alert=True)

@router.callback_query(F.data == "sub_test")
async def test_sub_callback(callback: CallbackQuery):
    rates_text = await build_popular_rates_message()
    test_msg = (
        "🌅 <b>[SINTOV] Xayrli tong! Kunlik valyuta kurslari:</b>\n\n"
        f"{rates_text}\n\n"
        "<i>(Ushbu xabar har kuni ertalab 09:00 da avtomatik yuboriladi)</i>"
    )
    await callback.message.answer(test_msg, parse_mode="HTML")
    await callback.answer("Sinov xabari yuborildi! ✅")
