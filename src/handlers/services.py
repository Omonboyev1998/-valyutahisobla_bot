import logging
from typing import Optional, List, Dict, Any
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from src.config import ADMIN_ID
from src.database import (
    add_service,
    get_services,
    count_services,
    get_service_by_id,
    get_user_services,
    delete_service,
    toggle_service_status,
    add_service_review,
    has_user_reviewed,
    add_service_order
)
from src.keyboards.services import (
    SERVICE_CATEGORIES,
    SERVICE_REGIONS,
    get_services_menu_keyboard,
    get_categories_keyboard,
    get_regions_keyboard,
    get_services_list_keyboard,
    get_service_detail_keyboard,
    get_rating_keyboard,
    get_my_service_item_keyboard,
    get_phone_request_keyboard,
    get_photo_request_keyboard,
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
    price = State()
    description = State()
    photo = State()
    phone = State()

class SearchServiceFSM(StatesGroup):
    query = State()

class OrderServiceFSM(StatesGroup):
    service_id = State()
    master_user_id = State()
    service_title = State()
    phone = State()
    message = State()

def format_service_list_text(
    services: List[Dict[str, Any]],
    page: int,
    total: int,
    header_title: str
) -> str:
    """Ustalar ro'yxati matnini shakllantirish"""
    text = f"📋 <b>{header_title}</b> (Jami: <b>{total}</b> ta)\n\n"
    for idx, s in enumerate(services, 1):
        num = page * 5 + idx
        master = s.get("master_name", "Usta")
        title = s.get("title", "")
        region = s.get("region", "Barcha hududlar")
        rating = s.get("rating", 5.0)
        r_cnt = s.get("rating_count", 0)
        price = s.get("price") or "Kelishilgan holda"
        desc = s.get("description", "")
        short_desc = desc[:70] + "..." if len(desc) > 70 else desc

        text += (
            f"<b>{num}. 🛠 {title}</b>\n"
            f"   👤 Usta: <b>{master}</b> | 📍 {region}\n"
            f"   ⭐ <b>{rating:.1f}</b> ({r_cnt} ta baho) | 💰 {price}\n"
            f"   <i>{short_desc}</i>\n\n"
        )

    text += "<i>Batafsil ma'lumot va bog'lanish uchun quyidagi tugmalardan birini tanlang:</i>"
    return text

def format_service_detail_text(service: dict) -> str:
    """Yagona usta kartochkasi matni"""
    title = service.get("title", "")
    category = service.get("category", "")
    master = service.get("master_name", "")
    phone = service.get("phone", "")
    username = service.get("username", "")
    region = service.get("region", "Barcha hududlar")
    price = service.get("price") or "Kelishilgan holda"
    desc = service.get("description", "Qo'shimcha ma'lumot kiritilmagan.")
    rating = service.get("rating", 5.0)
    r_cnt = service.get("rating_count", 0)
    views = service.get("views_count", 0)

    user_link = f"@{username}" if username else "Mavjud emas"

    text = (
        f"🛠 <b>{title}</b>\n\n"
        f"📌 <b>Toifa:</b> {category}\n"
        f"📍 <b>Hudud:</b> {region}\n"
        f"💰 <b>Xizmat narxi:</b> <b>{price}</b>\n"
        f"⭐ <b>Reyting:</b> <b>{rating:.1f}</b> ({r_cnt} ta baho)\n"
        f"👤 <b>Usta / Mutaxassis:</b> <b>{master}</b>\n"
        f"📞 <b>Telefon:</b> <code>{phone}</code>\n"
        f"💬 <b>Telegram:</b> {user_link}\n\n"
        f"📝 <b>Batafsil ma'lumot:</b>\n<i>{desc}</i>\n\n"
        f"👁 <i>Ko'rishlar soni: {views} marta</i>"
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

# ==================== 2. RO'YXAT (LIST VIEW) VA KO'RISH ====================

@router.callback_query(F.data == "srv_browse")
async def browse_categories_callback(callback: CallbackQuery):
    text = (
        "🗂 <b>Xizmat toifasini tanlang:</b>\n\n"
        "Qaysi soha bo'yicha usta yoki mutaxassis qidiryapsiz?"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_categories_keyboard(prefix="srv_cat"))
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=get_categories_keyboard(prefix="srv_cat"))
    await callback.answer()

@router.callback_query(F.data.startswith("srv_cat:"))
async def select_category_callback(callback: CallbackQuery):
    cat_code = callback.data.split(":")[1]
    category_name = None if cat_code == "all" else SERVICE_CATEGORIES[int(cat_code)]

    total = count_services(category=category_name)
    if total == 0:
        cat_disp = category_name or "barcha toifalar"
        await callback.answer(f"{cat_disp} bo'yicha hozircha e'lonlar yo'q.", show_alert=True)
        return

    services = get_services(category=category_name, limit=5, offset=0)
    total_pages = (total + 4) // 5
    title = category_name or "Barcha toifalar"
    text = format_service_list_text(services, 0, total, title)
    markup = get_services_list_keyboard(services, 0, total_pages, cat_code=cat_code, reg_code="all")

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=markup)
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

    total_pages = (total + 4) // 5
    if page < 0:
        page = 0
    if page >= total_pages:
        page = total_pages - 1

    services = get_services(category=category_name, region=region_name, limit=5, offset=page * 5)
    title = category_name or (region_name if region_name else "Barcha xizmatlar")
    text = format_service_list_text(services, page, total, title)
    markup = get_services_list_keyboard(services, page, total_pages, cat_code=cat_code, reg_code=reg_code)

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=markup)
    await callback.answer()

# ==================== 3. HUDUD BO'YICHA FILTR ====================

@router.callback_query(F.data == "srv_filter_region")
async def filter_region_callback(callback: CallbackQuery):
    text = (
        "📍 <b>O'zingizga qulay hududni tanlang:</b>\n\n"
        "Tanlangan viloyatdagi xizmatlar va ustalar ro'yxati ko'rsatiladi:"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_regions_keyboard(prefix="srv_filter_reg"))
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=get_regions_keyboard(prefix="srv_filter_reg"))
    await callback.answer()

@router.callback_query(F.data.startswith("srv_filter_reg:"))
async def apply_region_filter_callback(callback: CallbackQuery):
    reg_idx = callback.data.split(":")[1]
    region_name = SERVICE_REGIONS[int(reg_idx)]

    total = count_services(region=region_name)
    if total == 0:
        await callback.answer(f"{region_name} bo'yicha hozircha e'lonlar yo'q.", show_alert=True)
        return

    total_pages = (total + 4) // 5
    services = get_services(region=region_name, limit=5, offset=0)
    text = format_service_list_text(services, 0, total, f"{region_name} bo'yicha ustalar")
    markup = get_services_list_keyboard(services, 0, total_pages, cat_code="all", reg_code=reg_idx)

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=markup)
    await callback.answer()

# ==================== 4. USTA DETAIL KO'RINIShI ====================

@router.callback_query(F.data.startswith("srv_view:"))
async def view_service_detail_callback(callback: CallbackQuery, bot: Bot):
    parts = callback.data.split(":")
    s_id = int(parts[1])
    cat_code = parts[2] if len(parts) > 2 else "all"
    reg_code = parts[3] if len(parts) > 3 else "all"
    back_page = int(parts[4]) if len(parts) > 4 else 0

    service = get_service_by_id(s_id)
    if not service:
        await callback.answer("Ushbu xizmat topilmadi yoki o'chirilgan.", show_alert=True)
        return

    text = format_service_detail_text(service)
    markup = get_service_detail_keyboard(service, cat_code=cat_code, reg_code=reg_code, back_page=back_page)
    photo_id = service.get("photo_id")

    if photo_id:
        try:
            await callback.message.delete()
            await bot.send_photo(
                chat_id=callback.message.chat.id,
                photo=photo_id,
                caption=text,
                parse_mode="HTML",
                reply_markup=markup
            )
            await callback.answer()
            return
        except Exception:
            pass

    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=markup)
    await callback.answer()

# ==================== 5. O'Z XIZMATINI QO'SHISH (RASM BILAN) ====================

@router.callback_query(F.data == "srv_add")
async def start_add_service_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(AddServiceFSM.category)
    text = (
        "➕ <b>Yangi xizmat yoki e'lon qo'shish</b>\n\n"
        "1-qadam: Ko'rsatadigan xizmatingiz toifasini tanlang:"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_categories_keyboard(prefix="srv_add_cat"))
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=get_categories_keyboard(prefix="srv_add_cat"))
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
        "<i>(Masalan: Tajribali santexnik, kran va nasos o'rnatish yoki Qo'y yungini toza va tez olish xizmati)</i>"
    )
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(text, parse_mode="HTML", reply_markup=get_cancel_reply_keyboard())

@router.message(AddServiceFSM.title, F.text)
async def add_service_title_entered(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("E'lon berish bekor qilindi.", reply_markup=get_main_keyboard())
        return

    title = message.text.strip()
    if len(title) < 4:
        await message.answer("Sarlavha juda qisqa. Kamida 4 ta belgi kiriting:")
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
    await state.set_state(AddServiceFSM.price)

    text = (
        f"✅ Hudud: <b>{region_name}</b>\n\n"
        "4-qadam: <b>Xizmat narxini yozing:</b>\n"
        "<i>(Masalan: <code>50 000 so'mdan</code>, <code>100 000 so'm / soat</code> yoki <code>Kelishilgan holda</code>)</i>"
    )
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(text, parse_mode="HTML", reply_markup=get_cancel_reply_keyboard())

@router.message(AddServiceFSM.price, F.text)
async def add_service_price_entered(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("E'lon berish bekor qilindi.", reply_markup=get_main_keyboard())
        return

    price = message.text.strip()
    await state.update_data(price=price)
    await state.set_state(AddServiceFSM.description)

    text = (
        f"✅ Narx: <b>{price}</b>\n\n"
        "5-qadam: <b>Xizmatingiz haqida batafsil ma'lumot yozing:</b>\n"
        "<i>(Ish tajribangiz, ish vaqti va mijozlarga taqdim etiladigan qulayliklar)</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_cancel_reply_keyboard())

@router.message(AddServiceFSM.description, F.text)
async def add_service_description_entered(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("E'lon berish bekor qilindi.", reply_markup=get_main_keyboard())
        return

    desc = message.text.strip()
    await state.update_data(description=desc)
    await state.set_state(AddServiceFSM.photo)

    text = (
        "6-qadam: <b>Xizmatingiz yoki ishlaringizdan bitta rasm yuboring:</b>\n\n"
        "Rasm mijozlarda ko'proq ishonch uyg'otadi. Agar rasm qo'shishni istamasangiz, pastdagi "
        "<b>'⏭ O'tkazib yuborish (Rasmsiz)'</b> tugmasini bosing:"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_photo_request_keyboard())

@router.message(AddServiceFSM.photo)
async def add_service_photo_received(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("E'lon berish bekor qilindi.", reply_markup=get_main_keyboard())
        return

    photo_id = None
    if message.photo:
        photo_id = message.photo[-1].file_id
    elif message.text and "O'tkazib yuborish" in message.text:
        photo_id = None

    await state.update_data(photo_id=photo_id)
    await state.set_state(AddServiceFSM.phone)

    text = (
        "7-qadam: <b>Mijozlar siz bilan bog'lanishi uchun telefon raqamingizni yuboring:</b>\n\n"
        "Quyidagi <b>'📞 Telefon raqamimni yuborish'</b> tugmasini bosing yoki raqamingizni matn shaklida yozing (Masalan: <code>+998901234567</code>):"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_phone_request_keyboard())

@router.message(AddServiceFSM.phone)
async def add_service_phone_entered(message: Message, state: FSMContext, bot: Bot):
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
        region=data["region"],
        price=data.get("price", ""),
        photo_id=data.get("photo_id")
    )

    await state.clear()

    congrat_text = (
        "🎉 <b>Tabriklaymiz! Xizmatingiz muvaffaqiyatli joylashtirildi!</b>\n\n"
        f"🛠 <b>Sarlavha:</b> {data['title']}\n"
        f"📌 <b>Toifa:</b> {data['category']}\n"
        f"📍 <b>Hudud:</b> {data['region']}\n"
        f"💰 <b>Narx:</b> {data.get('price', 'Kelishilgan holda')}\n"
        f"📞 <b>Telefon:</b> <code>{phone}</code>\n\n"
        "Endi boshqa foydalanuvchilar sizning xizmatingizni ko'rib, to'g'ridan-to'g'ri bog'lanishi yoki bot orqali buyurtma qoldirishi mumkin! 🚀"
    )
    await message.answer(congrat_text, parse_mode="HTML", reply_markup=get_main_keyboard())

    # Adminga xabarnoma (moderatsiya uchun)
    if ADMIN_ID and ADMIN_ID != user.id:
        try:
            admin_msg = (
                "🆕 <b>Yangi xizmat e'loni qo'shildi (Bot orqali):</b>\n\n"
                f"👤 <b>Usta:</b> {master_name} (ID: <code>{user.id}</code>)\n"
                f"📌 <b>Sarlavha:</b> {data['title']}\n"
                f"🛠 <b>Toifa:</b> {data['category']}\n"
                f"📍 <b>Hudud:</b> {data['region']}\n"
                f"📞 <b>Tel:</b> <code>{phone}</code>\n"
                f"💰 <b>Narx:</b> {data.get('price', 'Kelishilgan holda')}"
            )
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            markup = InlineKeyboardMarkup(inline_keyboard=[
                [
                    InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"admin_srv_ok:{service_id}"),
                    InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"admin_srv_del:{service_id}")
                ],
                [
                    InlineKeyboardButton(text="👁 Batafsil ko'rish", callback_data=f"srv_view:{service_id}:all:all:0")
                ]
            ])
            await bot.send_message(chat_id=ADMIN_ID, text=admin_msg, parse_mode="HTML", reply_markup=markup)
        except Exception:
            pass

# ==================== 6. MENING E'LONLARIM ====================

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
        rating = s.get("rating", 5.0)
        text += (
            f"• <b>{s['title']}</b> ({s['category']})\n"
            f"   └ Holat: {st_icon} | ⭐ {rating} | Ko'rishlar: {s['views_count']} ta\n\n"
        )

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

# ==================== 7. BAHOLASH (RATING) ====================

@router.callback_query(F.data.startswith("srv_rate:"))
async def rate_service_callback(callback: CallbackQuery):
    s_id = int(callback.data.split(":")[1])
    user_id = callback.from_user.id

    if has_user_reviewed(s_id, user_id):
        await callback.answer("Siz bu ustaga allaqachon baho bergansiz! ⭐", show_alert=True)
        return

    text = "⭐ <b>Usta xizmati sifatini 1 dan 5 gacha baholang:</b>"
    try:
        await callback.message.edit_reply_markup(reply_markup=get_rating_keyboard(s_id))
    except Exception:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=get_rating_keyboard(s_id))
    await callback.answer()

@router.callback_query(F.data.startswith("srv_star:"))
async def give_star_callback(callback: CallbackQuery):
    parts = callback.data.split(":")
    s_id = int(parts[1])
    stars = int(parts[2])
    user_id = callback.from_user.id

    ok, msg = add_service_review(s_id, user_id, stars)
    await callback.answer(msg, show_alert=True)

    # Kartochkani yangilangan reyting bilan qayta ko'rsatamiz
    service = get_service_by_id(s_id)
    if service:
        text = format_service_detail_text(service)
        markup = get_service_detail_keyboard(service)
        try:
            await callback.message.edit_text(text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            pass

@router.callback_query(F.data.startswith("srv_rate_cancel:"))
async def cancel_rate_callback(callback: CallbackQuery):
    s_id = int(callback.data.split(":")[1])
    service = get_service_by_id(s_id)
    if service:
        markup = get_service_detail_keyboard(service)
        try:
            await callback.message.edit_reply_markup(reply_markup=markup)
        except Exception:
            pass
    await callback.answer()

# ==================== 8. BOT ICHIDA BUYURTMA QOLDIRISH ====================

@router.callback_query(F.data.startswith("srv_order:"))
async def start_order_callback(callback: CallbackQuery, state: FSMContext):
    s_id = int(callback.data.split(":")[1])
    service = get_service_by_id(s_id)
    if not service:
        await callback.answer("Xizmat topilmadi.", show_alert=True)
        return

    await state.set_state(OrderServiceFSM.phone)
    await state.update_data(
        service_id=s_id,
        master_user_id=service["user_id"],
        service_title=service["title"]
    )

    text = (
        f"📩 <b>«{service['title']}» xizmati uchun buyurtma berish</b>\n\n"
        "Usta siz bilan bog'lanishi uchun telefon raqamingizni yuboring:\n"
        "<i>(Quyidagi '📞 Telefon raqamimni yuborish' tugmasini bosing yoki matn qilib yozing)</i>"
    )
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(text, parse_mode="HTML", reply_markup=get_phone_request_keyboard())
    await callback.answer()

@router.message(OrderServiceFSM.phone)
async def order_phone_received(message: Message, state: FSMContext):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Buyurtma bekor qilindi.", reply_markup=get_main_keyboard())
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

    await state.update_data(phone=phone)
    await state.set_state(OrderServiceFSM.message)

    text = (
        "📝 <b>Ustaga nima kerakligini qisqacha yozing:</b>\n"
        "<i>(Masalan: Ertaga ertalab soat 10 da kran o'rnatish kerak edi)</i>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_cancel_reply_keyboard())

@router.message(OrderServiceFSM.message, F.text)
async def order_message_received(message: Message, state: FSMContext, bot: Bot):
    if message.text == "❌ Bekor qilish":
        await state.clear()
        await message.answer("Buyurtma bekor qilindi.", reply_markup=get_main_keyboard())
        return

    client_msg = message.text.strip()
    data = await state.get_data()
    await state.clear()

    client_user = message.from_user
    client_name = client_user.full_name or "Mijoz"
    client_phone = data["phone"]
    service_id = data["service_id"]
    master_user_id = data["master_user_id"]
    service_title = data["service_title"]

    add_service_order(
        service_id=service_id,
        client_user_id=client_user.id,
        client_name=client_name,
        client_phone=client_phone,
        message=client_msg
    )

    # 1. Ustaga darhol xabar yuboramiz
    try:
        master_alert = (
            "🔔 <b>Sizga yangi mijozdan buyurtma keldi!</b>\n\n"
            f"🛠 <b>Xizmat:</b> {service_title}\n"
            f"👤 <b>Mijoz:</b> <b>{client_name}</b>\n"
            f"📞 <b>Telefon:</b> <code>{client_phone}</code>\n"
            f"📝 <b>Xabar:</b> <i>{client_msg}</i>\n\n"
            "<i>Iltimos, mijoz bilan imkon qadar tezroq bog'laning!</i>"
        )
        await bot.send_message(chat_id=master_user_id, text=master_alert, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"Ustaga xabar yuborishda xatolik: {e}")

    # 2. Mijozga tasdiq xabari
    confirm_text = (
        "✅ <b>Buyurtmangiz ustaga muvaffaqiyatli yetkazildi!</b>\n\n"
        f"🛠 <b>Xizmat:</b> {service_title}\n"
        f"📞 <b>Sizning raqamingiz:</b> {client_phone}\n\n"
        "Usta tez orada siz bilan telefon orqali bog'lanadi. Rahmat!"
    )
    await message.answer(confirm_text, parse_mode="HTML", reply_markup=get_main_keyboard())

# ==================== 9. QIDIRUV (SEARCH) ====================

@router.callback_query(F.data == "srv_search")
async def start_search_callback(callback: CallbackQuery, state: FSMContext):
    await state.set_state(SearchServiceFSM.query)
    text = (
        "🔍 <b>Xizmat yoki usta qidirish</b>\n\n"
        "Qidirayotgan xizmat turini yozing (Masalan: <i>santexnik</i>, <i>elektr</i>, <i>yung</i>, <i>suv quvuri</i>, <i>klining</i>):"
    )
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(text, parse_mode="HTML", reply_markup=get_cancel_reply_keyboard())
    await callback.answer()

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
        await message.answer("Asosiy menyuga qaytildi:", reply_markup=get_main_keyboard())
        return

    total_pages = (total + 4) // 5
    services = get_services(search_query=query, limit=5, offset=0)
    text = format_service_list_text(services, 0, total, f"'{query}' bo'yicha qidiruv natijalari")
    markup = get_services_list_keyboard(services, 0, total_pages, cat_code="all", reg_code="all", search_q=query)

    await message.answer("Qidiruv natijalari:", reply_markup=get_main_keyboard())
    await message.answer(text, parse_mode="HTML", reply_markup=markup)

# ==================== 10. ALOQA VA GLOBAL BEKOR QILISH ====================

@router.callback_query(F.data.startswith("srv_contact:"))
async def service_contact_callback(callback: CallbackQuery):
    s_id = int(callback.data.split(":")[1])
    service = get_service_by_id(s_id)
    if service:
        name = service.get("master_name", "Usta")
        phone = service.get("phone", "")
        await callback.answer(f"📞 {name}: {phone}", show_alert=True)
    else:
        await callback.answer("Xizmat ma'lumoti topilmadi.", show_alert=True)

@router.message(F.text == "❌ Bekor qilish")
async def global_cancel_reply_message(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Amal bekor qilindi. Asosiy menyudasiz.", reply_markup=get_main_keyboard())

@router.callback_query(F.data == "srv_cancel")
async def cancel_srv_callback(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("Amal bekor qilindi.", reply_markup=get_main_keyboard())
    await callback.answer()

@router.callback_query(F.data == "srv_noop")
async def noop_callback(callback: CallbackQuery):
    await callback.answer()
