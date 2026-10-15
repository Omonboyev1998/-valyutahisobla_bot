# 🌟 Universal Yordamchi Telegram Bot (@valyutahisobla_bot)

Zamonaviy, ko'p funksiyali va qulay Telegram bot. Foydalanuvchilarning kundalik ehtiyojlari uchun barcha muhim xizmatlar yagona botda mujassamlashgan: **Valyuta kurslari**, **Namoz vaqtlari**, **Ob-havo ma'lumotlari**, **Futbol olami**, **Shaxsiy eslatmalar** va **Viral referal tizimi**.

---

## 🚀 Asosiy Imkoniyatlar va Bo'limlar

### 📱 Telegram Mini App (Web App) Interfeysi
Bot shunchaki matnli xabarlar bilan cheklanmaydi — unda to'laqonli zamonaviy **Telegram Mini App** mavjud:
- **Telegram ekotizimiga to'liq moslashgan UI:** Foydalanuvchining tungi/kunduzgi mavzusiga avtomatik moslashadi.
- **Valyuta grafiklari:** USD, EUR, RUB, KZT, CNY, GBP kabi asosiy valyutalarning **7 va 30 kunlik dinamik Chart.js chiziqli grafiklari** (eng baland, eng past ko'rsatkichlar va trendlar).
- **Namoz vaqtlari va interaktiv soat:** Jonli raqamli soat, keyingi namozgacha orqaga hisoblash taymeri, joriy namoz vaqtining yonib-o'chuvchi animatsiyasi va viloyatlar tanlovi.
- **Futbol jadvallari va klub logotiplari:** APL, La Liga, Serie A, Bundesliga va UCL turnir jadvallari rasmiy jamoalar logotiplari bilan.
- **O'rnatilgan kalkulyator va ob-havo kartasi.**
- **Tezkor kirish:** Telegram chatida pastki chap burchakdagi doimiy `📱 Mini App` tugmasi orqali istalgan paytda bir bosishda ochiladi!

### 1. 💵 Valyuta kurslari va Aqlli Hisoblagich
- **O'zbekiston Markaziy Banki (CBU)** rasmiy kurslari bilan integratsiya (USD, EUR, RUB, KZT, CNY, TRY, GBP va boshqalar).
- O'sish/pasayish trendlari (📈 / 📉) va kurslar farqi ko'rsatiladi.
- Barcha mavjud xorijiy valyutalarni ko'rish imkoniyati.
- **Tezkor matnli kalkulyator:** Botga shunchaki `100 USD`, `500000 som`, `50 EUR` deb yozsangiz, u avtomatik ravishda konvertatsiya qilib beradi.
- Interaktiv inline-valyuta konvertori.

### 2. 🕌 Namoz vaqtlari va Ro'za taqvimi
- **O'zbekiston Musulmonlari Idorasi va Hanafiy mazhabiga** muvofiq 5 mahal namoz vaqtlari (Tong/Saharlik, Quyosh, Peshin, Asr, Shom/Iftorlik, Xufton).
- **Keyingi namozga qolgan vaqt** orqaga hisoblash taymeri bilan ko'rsatiladi.
- **Saharlik va Iftorlik duolari:** O'zbekcha va arabcha matnlari bilan qulay inline-tugmalar orqali taqdim etiladi.
- **15 daqiqa oldin eslatma:** Har bir namoz kirishidan 15 daqiqa oldin foydalanuvchiga ovozli eslatma yuborish funksiyasi (yoqish/o'chirish imkoniyati bilan).
- O'zbekistonning barcha viloyat va shaharlari bo'yicha doimiy saqlanadigan hudud tanlash.

### 3. 🌤 Ob-havo Ma'lumotlari (Multi-Platform Engine)
- **Ko'p platformali zaxira tizimi:** MET Norway (`yr.no`) asosiy provayder, Open-Meteo va `wttr.in` zaxira provayderlar sifatida ulanadi.
- **Hozirgi ob-havo:** Harorat, hiss qilinishi, namlik, shamol tezligi va holat emojilari.
- **3 kunlik batafsil prognoz:** Kunduzgi va kechki haroratlar.
- **Doimiy hudud xotirasi:** Foydalanuvchi viloyatni bir marta tanlasa yoki GPS lokatsiya yuborsa, bot uni eslab qoladi va keyingi safar avtomatik ko'rsatadi.

### 4. ⚽️ Futbol Olami
- **ESPN Soccer API** orqali jonli ma'lumotlar.
- Top chempionatlar:
  - 🏴󠁧󠁢󠁥󠁮󠁧󠁿 Angliya Premyer-ligasi (APL)
  - 🇪🇸 Ispaniya La Ligasi
  - 🇮🇹 Italiya Serie A
  - 🇩🇪 Germaniya Bundesligasi
  - 🏆 UEFA Chempionlar Ligasi
- Turnir jadvallari (O'rin, Klub, O'yinlar soni, To'plar nisbati, Ochko).
- Yaqin o'yinlar taqvimi va so'nggi o'yin natijalari.

### 5. 🔔 Moslashuvchan Shaxsiy Eslatmalar (Smart Digest)
- Har bir foydalanuvchi qaysi sohalar bo'yicha eslatma olishni o'zi tanlaydi:
  - 💵 Valyuta kurslari (yoqish/o'chirish)
  - 🕌 Namoz vaqtlari (yoqish/o'chirish)
  - 🌤 Ob-havo ma'lumoti (yoqish/o'chirish)
  - ⚽️ Futbol xabarlari (yoqish/o'chirish)
- **Xabar kelish vaqtini belgilash:** Foydalanuvchi eslatma soatini (06:00 dan 22:00 gacha) o'ziga qulay vaqtga sozlashi mumkin.
- Barcha tanlangan ma'lumotlar belgilangan vaqtda yagona chiroyli xabar (digest) shaklida yetkaziladi.

### 6. 🎁 Do'stlarni taklif qilish (Viral Referal)
- Har bir foydalanuvchi uchun unikal taklif havolasi (`t.me/valyutahisobla_bot?start=ref_USERID`).
- **Bir bosishda ulashish:** `t.me/share/url` orqali foydalanuvchi o'z kontaktlari va guruhlariga bitta tugma bilan xabarni ulashishi mumkin.
- Yangi do'st qo'shilganda taklif etuvchiga avtomatik tabrik xabarnomasi yuboriladi.
- Eng ko'p do'st taklif qilgan faol a'zolar **Peshqadamlar jadvali (Leaderboard)**.

### 7. 🛡 Admin Paneli (`/admin`)
- Faqat belgilangan admin (`ADMIN_ID`) uchun kirish ruxsati.
- **Jonli statistika:** Jami foydalanuvchilar, bugungi yangi obunachilar, konvertatsiyalar soni va referal ko'rsatkichlari.
- **Eksport (CSV):** Foydalanuvchilar bazasini bir bosishda Excel/CSV fayl sifatida yuklab olish.
- **Ommaviy xabar yuborish (Rassilka):** Matn, rasm yoki tugmali xabarlarni barcha foydalanuvchilarga xavfsiz va uzluksiz tarqatish.

---

## 🛠 Texnologiyalar

- **Dasturlash tili:** Python 3.11+
- **Freymvork:** Aiogram 3.x (Asinxron Telegram Bot API)
- **Ma'lumotlar bazasi:** SQLite3 (WAL rejimi bilan tezkor ishlash)
- **Tarmoq va API kutubxonalari:** `aiohttp` (IPv4 majburiy ulanish va timeouts bilan)
- **Veb-server:** Aiohttp keep-alive serveri (Render.com bepul hostingida 24/7 faol turish uchun)
- **Tashqi bepul API xizmatlari:**
  - Markaziy Bank CBU API
  - Aladhan Prayer Times API
  - MET Norway Weather API / Open-Meteo
  - ESPN Sports Core API

---

## 📋 Bot Buyruqlari

| Buyruq | Tavsif |
|---|---|
| `/start` | Botni ishga tushirish va asosiy menyu |
| `/app` | Telegram Mini App (Grafiklar, Soat va Jadvallar) |
| `/kurslar` | Markaziy Bank valyuta kurslari va hisoblagich |
| `/namoz` | 5 mahal namoz vaqtlari va saharlik/iftorlik duolari |
| `/obhavo` | Viloyatlar yoki GPS bo'yicha ob-havo ma'lumoti |
| `/futbol` | Top futbol ligalari jadvallari va natijalari |
| `/ref` | Shaxsiy taklif havolasi va do'stlarga ulashish |
| `/help` | Botdan foydalanish bo'yicha to'liq qo'llanma |
| `/admin` | Bot boshqaruv paneli (faqat admin uchun) |

---

## ⚙️ O'rnatish va Mahalliy Ishga Tushirish

1. **Repozitoriyni klonlash:**
```bash
git clone https://github.com/Omonboyev1998/-valyutahisobla_bot.git
cd -valyutahisobla_bot
```

2. **Virtual muhitni yaratish va faollashtirish:**
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux / macOS:
source .venv/bin/activate
```

3. **Kutubxonalarni o'rnatish:**
```bash
pip install -r requirements.txt
```

4. **Muhit o'zgaruvchilari (`.env` fayli):**
```env
BOT_TOKEN=8804264020:AAE6dL9DjGKkOCno_1Bj1qMdA-s_LOEIjLM
ADMIN_ID=1045855587
PORT=8000
```

5. **Botni ishga tushirish:**
```bash
python -m src.main
```

---

## ☁️ Render.com Bulutli Xizmatida Ishga Tushirish

Loyiha Render platformasiga to'liq moslashtirilgan (`render.yaml` mavjud):
1. GitHub repozitoriyangizni Render.com bilan ulang.
2. Web Service sifatida sozlang (Build Command: `pip install -r requirements.txt`, Start Command: `python -m src.main`).
3. Environment Variables bo'limida `BOT_TOKEN` va `ADMIN_ID` ni kiriting.
4. Ichki keep-alive web serveri `http://0.0.0.0:$PORT` da avtomatik ishlaydi va botni to'xtovsiz rejimda ushlab turadi.

---

Muallif: **Omonboyev**
Bot havolasi: [@valyutahisobla_bot](https://t.me/valyutahisobla_bot)
