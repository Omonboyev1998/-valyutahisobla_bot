import re
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from src.services.cbu_service import cbu_service
from src.keyboards.inline import get_converter_quick_keyboard, get_cancel_keyboard
from src.database import log_conversion

router = Router(name="convert")

class ConvertState(StatesGroup):
    from_ccy = State()
    to_ccy = State()
    amount = State()

CURRENCY_ALIASES = {
    "$": "USD",
    "dollar": "USD",
    "dollor": "USD",
    "usd": "USD",
    "евро": "EUR",
    "yevro": "EUR",
    "eur": "EUR",
    "€": "EUR",
    "рубль": "RUB",
    "rubl": "RUB",
    "rub": "RUB",
    "₽": "RUB",
    "tenge": "KZT",
    "kzt": "KZT",
    "yuan": "CNY",
    "cny": "CNY",
    "lira": "TRY",
    "try": "TRY",
    "funt": "GBP",
    "gbp": "GBP",
    "dirham": "AED",
    "aed": "AED",
    "som": "UZS",
    "so'm": "UZS",
    "sum": "UZS",
    "сум": "UZS",
    "uzs": "UZS",
}

@router.message(F.text == "🔄 Valyuta hisoblash")
@router.callback_query(F.data == "open_calc")
async def open_calc_menu(event: Message | CallbackQuery, state: FSMContext):
    await state.clear()
    text = (
        "🧮 <b>Valyuta hisoblash kalkulyatori</b>\n\n"
        "Kerakli yo'nalishni tanlang yoki shunchaki summani yozib yuboring:\n"
        "<i>(Masalan: <code>100 USD</code> yoki <code>500 000 UZS</code>)</i>"
    )
    if isinstance(event, CallbackQuery):
        await event.message.answer(text, parse_mode="HTML", reply_markup=get_converter_quick_keyboard())
        await event.answer()
    else:
        await event.answer(text, parse_mode="HTML", reply_markup=get_converter_quick_keyboard())

@router.callback_query(F.data.startswith("conv:"))
async def process_conv_choice(callback: CallbackQuery, state: FSMContext):
    parts = callback.data.split(":")
    from_ccy = parts[1]
    to_ccy = parts[2]

    await state.update_data(from_ccy=from_ccy, to_ccy=to_ccy)
    await state.set_state(ConvertState.amount)

    await callback.message.answer(
        f"<b>{from_ccy} ➡️ {to_ccy}</b> hisoblash uchun summani kiriting:\n"
        f"<i>(Masalan: 100 yoki 150.50)</i>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()

@router.callback_query(F.data == "cancel_action")
async def cancel_handler(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.answer("Amal bekor qilindi. Bosh menyudasiz.")
    await callback.answer()

@router.message(ConvertState.amount)
async def process_amount(message: Message, state: FSMContext):
    text = message.text.replace(" ", "").replace(",", ".")
    try:
        amount = float(text)
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer(
            "⚠️ Iltimos, faqat musbat son kiriting (masalan: <code>100</code> yoki <code>50000.5</code>):",
            parse_mode="HTML",
            reply_markup=get_cancel_keyboard()
        )
        return

    data = await state.get_data()
    from_ccy = data.get("from_ccy")
    to_ccy = data.get("to_ccy")
    await state.clear()

    res = await cbu_service.convert(amount, from_ccy, to_ccy)
    if not res:
        await message.answer("⚠️ Valyuta kursini hisoblashda xatolik yuz berdi.")
        return

    log_conversion(message.from_user.id, from_ccy, to_ccy, amount)

    result_val = res["result"]
    if to_ccy == "UZS":
        unit_rate = res["unit_rate"]
        msg = (
            f"✅ <b>Hisob-kitob natijasi:</b>\n\n"
            f"💵 <b>{amount:,.2f} {from_ccy}</b> =\n"
            f"👉 <b>{result_val:,.2f} UZS</b>\n\n"
            f"📌 Kurs: 1 {from_ccy} = {unit_rate:,.2f} UZS"
        )
    elif from_ccy == "UZS":
        unit_rate = res["unit_rate"]
        msg = (
            f"✅ <b>Hisob-kitob natijasi:</b>\n\n"
            f"💵 <b>{amount:,.2f} UZS</b> =\n"
            f"👉 <b>{result_val:,.2f} {to_ccy}</b>\n\n"
            f"📌 Kurs: 1 {to_ccy} = {unit_rate:,.2f} UZS"
        )
    else:
        msg = (
            f"✅ <b>Hisob-kitob natijasi:</b>\n\n"
            f"💵 <b>{amount:,.2f} {from_ccy}</b> =\n"
            f"👉 <b>{result_val:,.2f} {to_ccy}</b>\n\n"
            f"📌 Kross-kurs: 1 {from_ccy} ≈ {res.get('cross_rate', 0):,.4f} {to_ccy}"
        )

    await message.answer(msg, parse_mode="HTML")

# --- Smart Text Parser ---
# Foydalanuvchi "100 usd", "500000 som", "200 $", "50 eur uzs" kabi yozganda
@router.message(F.text)
async def smart_text_converter(message: Message, state: FSMContext):
    # Agar foydalanuvchi menyudagi asosiy tugmalarni bosgan bo'lsa, boshqa handlerlar ishlaydi
    if message.text.startswith("/") or any(k in message.text for k in ["kurslar", "Valyuta", "Ob-havo", "Futbol", "Eslatmalar", "Yordam", "Menyu"]):
        return

    text = message.text.strip().lower()

    # Pattern: [son] [valyuta1] (ixtiyoriy: to/dagi [valyuta2])
    # Masalan: "100 usd", "100 $", "500000 uzs", "100 usd to eur", "500 000 som"
    # Tozalash
    pattern = r"^([0-9\s,\.]+)\s*([a-zA-Z\$\€\₽\'\`\а-яА-ЯёЁ]+)(?:\s+(?:to|dagi|ga|in)?\s*([a-zA-Z\$\€\₽\'\`\а-яА-ЯёЁ]+))?$"
    match = re.match(pattern, text)

    if not match:
        return

    amount_str = match.group(1).replace(" ", "").replace(",", ".")
    cur1_str = match.group(2).lower()
    cur2_str = match.group(3).lower() if match.group(3) else None

    try:
        amount = float(amount_str)
        if amount <= 0:
            return
    except ValueError:
        return

    from_ccy = CURRENCY_ALIASES.get(cur1_str, cur1_str.upper())
    to_ccy = CURRENCY_ALIASES.get(cur2_str, cur2_str.upper()) if cur2_str else None

    # Agar valyuta UZS bo'lsa va 2-valyuta berilmagan bo'lsa:
    # UZS summani bir vaqtning o'zida USD, EUR va RUB ga o'girib ko'rsatamiz!
    if from_ccy == "UZS" and not to_ccy:
        usd_res = await cbu_service.convert(amount, "UZS", "USD")
        eur_res = await cbu_service.convert(amount, "UZS", "EUR")
        rub_res = await cbu_service.convert(amount, "UZS", "RUB")

        if not usd_res:
            return

        log_conversion(message.from_user.id, "UZS", "USD", amount)

        msg = (
            f"🇺🇿 <b>{amount:,.2f} UZS</b> ning qiymati:\n\n"
            f"🇺🇸 <b>{usd_res['result']:,.2f} USD</b> (Kurs: {usd_res['unit_rate']:,.2f})\n"
            f"🇪🇺 <b>{eur_res['result']:,.2f} EUR</b> (Kurs: {eur_res['unit_rate']:,.2f})\n"
            f"🇷🇺 <b>{rub_res['result']:,.2f} RUB</b> (Kurs: {rub_res['unit_rate']:,.2f})\n"
        )
        await message.answer(msg, parse_mode="HTML")
        return

    # Agar 2-valyuta berilmagan bo'lsa, xorijiy valyutani UZS ga o'giramiz
    if not to_ccy:
        to_ccy = "UZS"

    res = await cbu_service.convert(amount, from_ccy, to_ccy)
    if not res:
        # Tanimagan valyuta bo'lsa, hech narsa qilmaymiz
        return

    log_conversion(message.from_user.id, from_ccy, to_ccy, amount)

    result_val = res["result"]
    if to_ccy == "UZS":
        unit_rate = res["unit_rate"]
        msg = (
            f"💵 <b>{amount:,.2f} {from_ccy}</b> =\n"
            f"👉 <b>{result_val:,.2f} UZS</b>\n\n"
            f"📌 Kurs: 1 {from_ccy} = {unit_rate:,.2f} UZS"
        )
    elif from_ccy == "UZS":
        unit_rate = res["unit_rate"]
        msg = (
            f"💵 <b>{amount:,.2f} UZS</b> =\n"
            f"👉 <b>{result_val:,.2f} {to_ccy}</b>\n\n"
            f"📌 Kurs: 1 {to_ccy} = {unit_rate:,.2f} UZS"
        )
    else:
        msg = (
            f"💵 <b>{amount:,.2f} {from_ccy}</b> =\n"
            f"👉 <b>{result_val:,.2f} {to_ccy}</b>\n\n"
            f"📌 Kross-kurs: 1 {from_ccy} ≈ {res.get('cross_rate', 0):,.4f} {to_ccy}"
        )

    await message.answer(msg, parse_mode="HTML")
