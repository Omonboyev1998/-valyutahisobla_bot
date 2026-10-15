import sqlite3
import os
import csv
import io
import logging
from typing import List, Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "bot.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                full_name TEXT,
                username TEXT,
                is_subscribed INTEGER DEFAULT 1,
                referrer_id INTEGER,
                sub_currency INTEGER DEFAULT 1,
                sub_weather INTEGER DEFAULT 1,
                sub_football INTEGER DEFAULT 1,
                notify_time TEXT DEFAULT '09:00',
                weather_city TEXT DEFAULT 'Toshkent',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                from_ccy TEXT,
                to_ccy TEXT,
                amount REAL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Yangi ustunlarni tekshirib qo'shish (migratsiya)
        new_columns = [
            ("referrer_id", "INTEGER"),
            ("sub_currency", "INTEGER DEFAULT 1"),
            ("sub_weather", "INTEGER DEFAULT 1"),
            ("sub_football", "INTEGER DEFAULT 1"),
            ("sub_prayer", "INTEGER DEFAULT 1"),
            ("notify_time", "TEXT DEFAULT '09:00'"),
            ("weather_city", "TEXT DEFAULT 'Toshkent'")
        ]
        for col_name, col_type in new_columns:
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            except sqlite3.OperationalError:
                pass

        conn.commit()
    logger.info("Ma'lumotlar bazasi (SQLite) muvaffaqiyatli ishga tushirildi.")

def add_user(user_id: int, full_name: str, username: Optional[str] = None, referrer_id: Optional[int] = None) -> bool:
    is_new_referral = False
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        existing = cursor.fetchone()

        if not existing:
            valid_referrer = referrer_id if (referrer_id and referrer_id != user_id) else None
            cursor.execute("""
                INSERT INTO users (user_id, full_name, username, is_subscribed, referrer_id, sub_currency, sub_weather, sub_football, notify_time, weather_city)
                VALUES (?, ?, ?, 1, ?, 1, 1, 1, '09:00', 'Toshkent')
            """, (user_id, full_name, username, valid_referrer))
            conn.commit()
            if valid_referrer:
                is_new_referral = True
        else:
            cursor.execute("""
                UPDATE users SET full_name = ?, username = ?
                WHERE user_id = ?
            """, (full_name, username, user_id))
            conn.commit()

    return is_new_referral

def get_user_settings(user_id: int) -> Dict[str, Any]:
    """Foydalanuvchining eslatmalar bo'yicha barcha sozlamalarini oladi"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT is_subscribed, sub_currency, sub_weather, sub_football, notify_time, weather_city, sub_prayer
            FROM users WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        if row:
            return {
                "is_subscribed": bool(row[0]),
                "sub_currency": bool(row[1]) if row[1] is not None else True,
                "sub_weather": bool(row[2]) if row[2] is not None else True,
                "sub_football": bool(row[3]) if row[3] is not None else True,
                "notify_time": row[4] or "09:00",
                "weather_city": row[5] or "Toshkent",
                "sub_prayer": bool(row[6]) if row[6] is not None else True
            }
        else:
            return {
                "is_subscribed": True,
                "sub_currency": True,
                "sub_weather": True,
                "sub_football": True,
                "notify_time": "09:00",
                "weather_city": "Toshkent",
                "sub_prayer": True
            }

def toggle_user_topic(user_id: int, topic: str) -> bool:
    """Valyuta, Ob-havo, Futbol yoki Namoz obunasini yoqish/o'chirish"""
    column_map = {
        "currency": "sub_currency",
        "weather": "sub_weather",
        "football": "sub_football",
        "prayer": "sub_prayer"
    }
    col = column_map.get(topic)
    if not col:
        return False

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute(f"SELECT {col} FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        current_val = bool(row[0]) if row and row[0] is not None else True
        new_val = 0 if current_val else 1
        cursor.execute(f"UPDATE users SET {col} = ? WHERE user_id = ?", (new_val, user_id))
        conn.commit()
        return bool(new_val)

def get_users_for_prayer_alert() -> List[Tuple[int, str]]:
    """Namoz eslatmasini yoqqan barcha foydalanuvchilar (user_id, city)"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, weather_city FROM users WHERE is_subscribed = 1 AND sub_prayer = 1")
        return cursor.fetchall()

def set_user_notify_time(user_id: int, time_str: str):
    """Xabar kelish vaqtini o'rnatish (masalan: '08:00', '09:00')"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET notify_time = ? WHERE user_id = ?", (time_str, user_id))
        conn.commit()

def set_user_weather_city(user_id: int, city: str):
    """Ob-havo eslatmasi va doimiy hudud uchun shahar nomini o'rnatish"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET weather_city = ? WHERE user_id = ?", (city, user_id))
        conn.commit()

def get_user_weather_city(user_id: int) -> str:
    """Foydalanuvchining doimiy saqlangan shahrini qaytaradi"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT weather_city FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row[0] if (row and row[0]) else "Toshkent"

def set_subscription(user_id: int, status: bool):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_subscribed = ? WHERE user_id = ?", (1 if status else 0, user_id))
        conn.commit()

def is_user_subscribed(user_id: int) -> bool:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_subscribed FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return bool(row[0]) if row else True

def get_users_for_time(time_str: str) -> List[Dict[str, Any]]:
    """Aynan belgilangan vaqtda xabar oluvchi faol foydalanuvchilar"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, full_name, sub_currency, sub_weather, sub_football, weather_city
            FROM users
            WHERE is_subscribed = 1 AND notify_time = ?
            AND (sub_currency = 1 OR sub_weather = 1 OR sub_football = 1)
        """, (time_str,))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            result.append({
                "user_id": r[0],
                "full_name": r[1],
                "sub_currency": bool(r[2]),
                "sub_weather": bool(r[3]),
                "sub_football": bool(r[4]),
                "weather_city": r[5] or "Toshkent"
            })
        return result

def get_all_users() -> List[int]:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        rows = cursor.fetchall()
        return [row[0] for row in rows]

def get_referral_count(user_id: int) -> int:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
        return cursor.fetchone()[0]

def get_top_referrers(limit: int = 10) -> List[Tuple[str, int]]:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.full_name, COUNT(r.user_id) as ref_count
            FROM users u
            JOIN users r ON u.user_id = r.referrer_id
            GROUP BY u.user_id
            ORDER BY ref_count DESC
            LIMIT ?
        """, (limit,))
        return cursor.fetchall()

def log_conversion(user_id: int, from_ccy: str, to_ccy: str, amount: float):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conversions (user_id, from_ccy, to_ccy, amount)
                VALUES (?, ?, ?, ?)
            """, (user_id, from_ccy.upper(), to_ccy.upper(), amount))
            conn.commit()
    except Exception as e:
        logger.error(f"Statistikani yozishda xatolik: {e}")

def get_statistics() -> Dict[str, Any]:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM users")
        total_users = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE date(created_at, '+5 hours') = date('now', '+5 hours')")
        today_users = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM users WHERE is_subscribed = 1")
        subscribed_users = cursor.fetchone()[0]

        unsubscribed_users = total_users - subscribed_users

        cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id IS NOT NULL")
        referral_joined = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM conversions")
        total_conversions = cursor.fetchone()[0]

        cursor.execute("""
            SELECT from_ccy, COUNT(*) as count 
            FROM conversions 
            WHERE from_ccy != 'UZS'
            GROUP BY from_ccy 
            ORDER BY count DESC 
            LIMIT 5
        """)
        top_currencies = cursor.fetchall()

    return {
        "total_users": total_users,
        "today_users": today_users,
        "subscribed_users": subscribed_users,
        "unsubscribed_users": unsubscribed_users,
        "referral_joined": referral_joined,
        "total_conversions": total_conversions,
        "top_currencies": top_currencies
    }

def export_users_csv() -> str:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, full_name, username, is_subscribed, referrer_id, notify_time, weather_city, created_at FROM users ORDER BY created_at DESC")
        rows = cursor.fetchall()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=',', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["User ID", "To'liq ismi", "Username", "Obuna holati", "Taklif qiluvchi ID", "Eslatma vaqti", "Ob-havo shahri", "Ro'yxatdan o'tgan sana"])
    for row in rows:
        writer.writerow(row)

    return output.getvalue()
