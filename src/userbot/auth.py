import asyncio
import os
import sys
from telethon import TelegramClient
from src.config import TG_API_ID, TG_API_HASH, USERBOT_SESSION, TARGET_CHATS

async def main():
    print("=" * 60)
    print("🤖 TELEGRAM USERBOT BIR MARTALIK AVTORIZATSIYA (LOGIN)")
    print("=" * 60)

    if not TG_API_ID or not TG_API_HASH:
        print("\n❌ XATOLIK: .env faylida TG_API_ID yoki TG_API_HASH topilmadi!")
        print("\nIltimos, avval quyidagilarni bajaring:")
        print("1. https://my.telegram.org saytiga kiring (telefon raqamingiz bilan)")
        print("2. 'API development tools' bo'limiga o'ting")
        print("3. Yangi ilova yarating (masalan 'Loyiha') va u yerdan API ID hamda API HASH ni oling")
        print("4. .env fayliga quyidagilarni yozing:")
        print("   TG_API_ID=12345678")
        print("   TG_API_HASH=abcdef1234567890abcdef")
        print("   TARGET_CHATS=Xortumliklar")
        return

    os.makedirs(os.path.dirname(USERBOT_SESSION) or ".", exist_ok=True)

    print(f"\nUlanish parametrlari:")
    print(f"API_ID: {TG_API_ID}")
    print(f"Session fayli: {USERBOT_SESSION}.session")
    print(f"Kuzatiladigan guruhlar: {TARGET_CHATS}")
    print("\nTelegram hisobingizga ulanmoqda...")

    client = TelegramClient(USERBOT_SESSION, TG_API_ID, TG_API_HASH)
    await client.start()

    me = await client.get_me()
    print(f"\n✅ Muvaffaqiyatli ulandi!")
    print(f"👤 Akkaunt: {me.first_name} {getattr(me, 'last_name', '') or ''} (@{me.username or 'username yoq'})")
    print(f"📞 Telefon: +{me.phone}")

    print("\n🔍 A'zo bo'lgan guruhlaringiz tekshirilmoqda...")
    dialogs = await client.get_dialogs()
    groups = [d for d in dialogs if d.is_group]

    print(f"\nJami guruhlar soni: {len(groups)}")
    found_target = False
    for g in groups:
        title = g.title
        is_target = any(t.lower() in title.lower() for t in TARGET_CHATS)
        mark = "🎯 [KUZATILADI]" if is_target else "   "
        if is_target:
            found_target = True
        print(f"{mark} {title} (ID: {g.id})")

    if found_target:
        print("\n🎉 Tabriklaymiz! Siz ko'rsatgan maqsadli guruh(lar) topildi.")
    else:
        print(f"\n⚠️ DIQQAT: Siz a'zo bo'lgan guruhlar orasida {TARGET_CHATS} nomiga mos guruh topilmadi.")
        print("Guruh nomini aniqlashtirib, .env faylidagi TARGET_CHATS qiymatiga to'g'irlab qo'yishingiz mumkin.")

    print("\nEndi userbotni fonda ishga tushirishingiz mumkin:")
    print("👉 python -m src.userbot.listener")
    print("Yoki mavjud oxirgi xabarlarni darhol skanerlab olish uchun:")
    print("👉 python -m src.userbot.listener --scan")
    print("=" * 60)

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
