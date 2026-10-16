import logging
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.database import (
    add_service,
    get_services,
    count_services,
    get_service_by_id,
    get_user_services,
    delete_service,
    toggle_service_status
)
from src.keyboards.services import (
    SERVICE_CATEGORIES,
    SERVICE_REGIONS,
    get_services_menu_keyboard,
    get_categories_keyboard,
    get_regions_keyboard,
    get_service_card_keyboard,
    get_my_service_item_keyboard,
    get_phone_request_keyboard,
    get_cancel_reply_keyboard
)
from src.keyboards.reply import get_main_keyboard

logger = logging.getLogger(__name__)

router = Router(name="services")

# FSM Holatlari
class AddServiceFSM(StatesGroup):
    category = State()
    title = State()
    region = State()
    description = State()
    phone = State()

class SearchServiceFSM(StatesGroup):
    query = State()

def format_service_card(service: dict, page: int, total_pages: int) -> str:
    """Xizmat kartochkasini chiroyli matn shaklida chiqarish"""
    title = service.get("title", "")
    category = service.get("category", "")
    master = service.get("master_name", "")
    phone = service.get("phone", "")
    username = service.get("username", "")
    region = service.get("region", "Barcha hududlar")
    desc = service.get("description", "Qo'shimcha ma'lumot kiritilmagan.")
    views = service.get("views_count", 0)

    user_link = f"@{username}" if username else "Mavjud emas"

    text = (
        f"🛠 <b>{title}</b>\n\n"
        f"📌 <b>Toifa:</b> {category}\n"
        f"📍 <b>Hudud:</b> {region}\n"
        f"👤 <b>Usta / Mutaxassis:</b> <b>{master}</b>\n"
        f"📞 <b>Telefon:</b> <code>{phone}</code>\n"
        f"💬 <b>Telegram:</b> {user_link}\n\n"
        f"📝 <b>Batafsil ma'lumot:</b>\n<i>{desc}</i>\n\n"
        f"👁 <i>Ko'rishlar soni: {views} | Sahifa: {page + 1}/{total_pages}</i>"
    )
    return text

# ==================== 1. ASOSIY MENYU ====================

@router.message(Command("xizmatlar"))
@router.message(Command("usta"))
@router.message(F.text.contains("Maishiy xizmat"))
async def show_services_menu(message: Message, state: FSMContext):
    await state.clear()
    text = (
        "🛠 <b>Maishiy Xizmatlar va Ustalar Bozori</b>\n\n"
        "Bu bo'lim orqali siz:\n"
        "• Turli soha ustalarini (santexnik, elektrchi, ta'mirlovchi, qo'y yungini oluvchi va b.) topishingiz;\n"
        "• O'z xizmatingizni e'lon qilib, mijozlar orttirishingiz mumkin!\n\n"
        "Kerakli bo'limni tanlang:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_services_menu_keyboard())

@router.callback_query(F.data == "srv_main")
async def back_to_srv_main_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text = (
        "🛠 <b>Maishiy Xizmatlar va Ustalar Bozori</b>\n\n"
        "Kerakli bo'limni tanlang:"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_services_menu_keyboard())
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=get_services_menu_keyboard())
    await callback.answer()

# ==================== 2. XIZMATLARNI KO'RISH (BROWSE) ====================

@router.callback_query(F.data == "srv_browse")
async def browse_categories_callback(callback: CallbackQuery):
    text = (
        "🗂 <b>Xizmat toifasini tanlang:</b>\n\n"
        "Qaysi soha bo'yicha usta yoki mutaxassis qidiryapsiz?"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_categories_keyboard(prefix="srv_cat"))
    await callback.answer()

@router.callback_query(F.data.startswith("srv_cat:"))
async def select_category_callback(callback: CallbackQuery):
    cat_code = callback.data.split(":")[1]
    category_name = None if cat_code == "all" else SERVICE_CATEGORIES[int(cat_code)]

    # 1-sahifadagi xizmatlarni olamiz
    total = count_services(category=category_name)
    if total == 0:
        cat_disp = category_name or "barcha toifalar"
        await callback.answer(f"{cat_disp} bo'yicha hozircha e'lonlar yo'q.", show_alert=True)
        return

    services = get_services(category=category_name, limit=1, offset=0)
    if not services:
        await callback.answer("E'lonlar topilmadi.", show_alert=True)
        return

    service = services[0]
    get_service_by_id(service["id"]) # Ko'rishlar sonini oshirish

    text = format_service_card(service, 0, total)
    markup = get_service_card_keyboard(service, cat_idx=cat_code, reg_idx="all", page=0, total_pages=total)

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    await callback.answer()

@router.callback_query(F.data.startswith("srv_page:"))
async def paginate_services_callback(callback: CallbackQuery):
    _, cat_code, reg_code, page_str = callback.data.split(":")
    page = int(page_str)

    category_name = None if cat_code == "all" else SERVICE_CATEGORIES[int(cat_code)]
    region_name = None if reg_code == "all" else SERVICE_REGIONS[int(reg_code)]

    total = count_services(category=category_name, region=region_name)
    if total == 0:
        await callback.answer("Ushbu filtr bo'yicha e'lonlar mavjud emas.", show_alert=True)
        return

    if page < 0:
        page = 0
    if page >= total:
        page = total - 1

    services = get_services(category=category_name, region=region_name, limit=1, offset=page)
    if not services:
        await callback.answer("Boshqa e'lon yo'q.", show_alert=True)
        return

    service = services[0]
    get_service_by_id(service["id"])

    text = format_service_card(service, page, total)
    markup = get_service_card_keyboard(service, cat_idx=cat_code, reg_idx=reg_code, page=page, total_pages=total)

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        pass
    await callback.answer()

# ==================== 3. HUDUD BO'YICHA FILTR ====================

@router.callback_query(F.data == "srv_filter_region")
async def filter_region_callback(callback: CallbackQuery):
    text = (
        "📍 <b>O'zingizga qulay hududni tanlang:</b>\n\n"
        "Tanlangan viloyatdagi xizmatlar va ustalar ro'yxati ko'rsatiladi:"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_regions_keyboard(prefix="srv_filter_reg"))
    await callback.answer()

@router.callback_query(F.data.startswith("srv_filter_reg:"))
async def apply_region_filter_callback(callback: CallbackQuery):
    reg_idx = callback.data.split(":")[1]
    region_name = SERVICE_REGIONS[int(reg_idx)]

    total = count_services(region=region_name)
    if total == 0:
        await callback.answer(f"{region_name} bo'yicha hozircha e'lonlar yo'q.", show_alert=True)
        return

    services = get_services(region=region_name, limit=1, offset=0)
    service = services[0]
    get_service_by_id(service["id"])

    text = format_service_card(service, 0, total)
    markup = get_service_card_keyboard(service, cat_idx="all", reg_idx=reg_idx, page=0, total_pages=total)

    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    await callback.answer()

# ==================== 4. O'Z XIZMATINI QO'SHISH (FSM) ====================

@router.callback_query(F.data == "srv_add")
async def start_add_service_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddServiceFSM.category)
    text = (
        "➕ <b>Yangi xizmat yoki e'lon qo'shish</b>\n\n"
        "1-qadam: Ko'rsatadigan xizmatingiz toifasini tanlang:"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_categories_keyboard(prefix="srv_add_cat"))
    await callback.answer()

@router.callback_query(AddServiceFSM.category, F.data.startswith("srv_add_cat:"))
async def add_service_category_chosen(callback: CallbackQuery, state: FSMContext):
    cat_idx = int(callback.data.split(":")[1])
    category_name = SERVICE_CATEGORIES[cat_idx]
    await state.update_data(category=category_name)
    await state.set_state(AddServiceFSM.title)

    text = (
        f"✅ Toifa: <b>{category_name}</b>\n\n"
        "2-qadam: <b>Xizmatingiz sarlavhasini yozing.</b>\n"
        "<i>(Masalan: Tajribali santexnik, kran va nasos o'rnatish yoki Qo'y yungini tez va toza olish xizmati)</i>"
    )
    await callback.message.delete()
    await callback.message.answer(text, parse_mode="HTML", reply_markup=get_cancel_reply_keyboard())

@router.message(AddServiceFSM.title, F.text)
async def add_service_title_entered(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("E'lon berish bekor qilindi.", reply_markup=get_main_keyboard())
        return

    title = message.text.strip()
    if len(title) < 5:
        await message.answer("Sarlavha juda qisqa. Kamida 5 ta belgi kiriting:")
        return

    await state.update_data(title=title)
    await state.set_state(AddServiceFSM.region)

    text = (
        f"✅ Sarlavha: <b>{title}</b>\n\n"
        "3-qadam: <b>Xizmat ko'rsatadigan hududingizni tanlang:</b>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_regions_keyboard(prefix="srv_add_reg"))

@router.callback_query(AddServiceFSM.region, F.data.startswith("srv_add_reg:"))
async def add_service_region_chosen(callback: CallbackQuery, state: FSMContext):
    reg_idx = int(callback.data.split(":")[1])
    region_name = SERVICE_REGIONS[reg_idx]
    await state.update_data(region=region_name)
    await state.set_state(AddServiceFSM.description)

    text = (
        f"✅ Hudud: <b>{region_name}</b>\n\n"
        "4-qadam: <b>Xizmatingiz haqida batafsil ma'lumot va narxlarni yozing:</b>\n"
        "<i>(Tajribangiz, ish vaqti, narxlar va qulayliklar haqida ma'lumot qoldiring)</i>"
    )
    await callback.message.delete()
    await callback.message.answer(text, parse_mode="HTML", reply_markup=get_cancel_reply_keyboard())

@router.message(AddServiceFSM.description, F.text)
async def add_service_description_entered(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("E'lon berish bekor qilindi.", reply_markup=get_main_keyboard())
        return

    desc = message.text.strip()
    await state.update_data(description=desc)
    await state.set_state(AddServiceFSM.phone)

    text = (
        "5-qadam: <b>Mijozlar siz bilan bog'lanishi uchun telefon raqamingizni yuboring:</b>\n\n"
        "Quyidagi <b>'📞 Telefon raqamimni yuborish'</b> tugmasini bosing yoki raqamingizni matn shaklida yozing (Masalan: +998901234567):"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_phone_request_keyboard())

@router.message(AddServiceFSM.phone)
async def add_service_phone_entered(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("E'lon berish bekor qilindi.", reply_markup=get_main_keyboard())
        return

    phone = ""
    if message.contact:
        phone = message.contact.phone_number
        if not phone.startswith("+"):
            phone = "+" + phone
    elif message.text:
        phone = message.text.strip()

    if not phone or len(phone) < 7:
        await message.answer("Iltimos, to'g'ri telefon raqamini kiriting:")
        return

    data = await state.get_data()
    user = message.from_user
    master_name = user.full_name or "Usta"
    username = user.username or ""

    service_id = add_service(
        user_id=user.id,
        master_name=master_name,
        phone=phone,
        username=username,
        category=data["category"],
        title=data["title"],
        description=data["description"],
        region=data["region"]
    )

    await state.clear()

    congrat_text = (
        "🎉 <b>Tabriklaymiz! Xizmatingiz muvaffaqiyatli joylashtirildi!</b>\n\n"
        f"🛠 <b>Sarlavha:</b> {data['title']}\n"
        f"📌 <b>Toifa:</b> {data['category']}\n"
        f"📍 <b>Hudud:</b> {data['region']}\n"
        f"📞 <b>Telefon:</b> {phone}\n\n"
        "Endi boshqa foydalanuvchilar sizning xizmatingizni ko'rib, to'g'ridan-to'g'ri qo'ng'iroq qilishi yoki Telegramingizga yozishi mumkin! 🚀"
    )
    await message.answer(congrat_text, parse_mode="HTML", reply_markup=get_main_keyboard())

# ==================== 5. MENING E'LONLARIM ====================

@router.callback_query(F.data == "srv_my")
async def show_my_services_callback(callback: CallbackQuery):
    user_id = callback.from_user.id
    my_services = get_user_services(user_id)

    if not my_services:
        text = (
            "👤 <b>Sizda hali joylashtirilgan xizmatlar yo'q.</b>\n\n"
            "O'z xizmatingizni e'lon qilish uchun <b>'➕ O'z xizmatingizni qo'shish'</b> tugmasini bosing:"
        )
        buttons = [
            [InlineKeyboardButton(text="➕ Xizmat qo'shish", callback_data="srv_add")],
            [InlineKeyboardButton(text="🔙 Orqaga", callback_data="srv_main")]
        ]
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        await callback.answer()
        return

    text = f"👤 <b>Siz joylashtirgan xizmatlar ({len(my_services)} ta):</b>\n\n"
    for s in my_services:
        st_icon = "🟢 Faol" if s["is_active"] == 1 else "⏸ To'xtatilgan"
        text += (
            f"• <b>{s['title']}</b> ({s['category']})\n"
            f"   └ Holat: {st_icon} | Ko'rishlar: {s['views_count']} ta\n\n"
        )

    # Har bir xizmat uchun alohida boshqaruv tugmasi yuboramiz
    await callback.message.delete()
    for s in my_services:
        active_label = "🟢 Faol" if s["is_active"] == 1 else "⏸ To'xtatilgan"
        s_text = (
            f"🛠 <b>{s['title']}</b>\n"
            f"📌 Toifa: {s['category']} | 📍 Hudud: {s['region']}\n"
            f"Holati: {active_label}"
        )
        await callback.message.answer(
            s_text,
            parse_mode="HTML",
            reply_markup=get_my_service_item_keyboard(s["id"], s["is_active"])
        )

    await callback.message.answer(
        "Xizmatlar menyusiga qaytish uchun:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🔙 Xizmatlar menyusi", callback_data="srv_main")]])
    )

@router.callback_query(F.data.startswith("srv_toggle:"))
async def toggle_service_callback(callback: CallbackQuery):
    service_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    new_status = toggle_service_status(service_id, user_id)
    if new_status is not None:
        status_word = "faollashtirildi 🟢" if new_status == 1 else "to'xtatildi ⏸"
        await callback.answer(f"Xizmat {status_word}!", show_alert=True)
        # Tugmani yangilaymiz
        try:
            await callback.message.edit_reply_markup(reply_markup=get_my_service_item_keyboard(service_id, new_status))
        except Exception:
            pass
    else:
        await callback.answer("Xatolik yuz berdi.", show_alert=True)

@router.callback_query(F.data.startswith("srv_del:"))
async def delete_service_callback(callback: CallbackQuery):
    service_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    ok = delete_service(service_id, user_id)
    if ok:
        await callback.answer("E'lon muvaffaqiyatli o'chirildi! 🗑", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
    else:
        await callback.answer("O'chirishda xatolik.", show_alert=True)

# ==================== 6. QIDIRUV (SEARCH) ====================

@router.callback_query(F.data == "srv_search")
async def start_search_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SearchServiceFSM.query)
    text = (
        "🔍 <b>Xizmat yoki usta qidirish</b>\n\n"
        "Qidirayotgan xizmat turini yozing (Masalan: <i>santexnik</i>, <i>elektr</i>, <i>yung</i>, <i>suv quvuri</i>, <i>klining</i>):"
    )
    await callback.message.delete()
    await callback.message.answer(text, parse_mode="HTML", reply_markup=get_cancel_reply_keyboard())

@router.message(SearchServiceFSM.query, F.text)
async def process_search_query(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Qidiruv bekor qilindi.", reply_markup=get_main_keyboard())
        return

    query = message.text.strip()
    await state.clear()

    total = count_services(search_query=query)
    if total == 0:
        await message.answer(
            f"🔍 <b>'{query}'</b> bo'yicha hech qanday xizmat topilmadi.\n\n"
            "Boshqa so'z bilan qidirib ko'ring yoki barcha toifalarni ko'rib chiqing:",
            parse_mode="HTML",
            reply_markup=get_services_menu_keyboard()
        )
        return

    services = get_services(search_query=query, limit=1, offset=0)
    service = services[0]
    get_service_by_id(service["id"])

    text = f"🔍 <b>'{query}' bo'yicha qidiruv natijalari ({total} ta topildi):</b>\n\n"
    text += format_service_card(service, 0, total)
    markup = get_service_card_keyboard(service, cat_idx="all", reg_idx="all", page=0, total_pages=total)

    await message.answer(text, parse_mode="HTML", reply_markup=markup)

@router.callback_query(F.data == "srv_cancel")
async def cancel_srv_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.delete()
    await callback.message.answer("Amal bekor qilindi.", reply_markup=get_main_keyboard())
    await callback.answer()

@router.callback_query(F.data == "srv_noop")
async def noop_callback(callback: CallbackQuery):
    await callback.answer()
