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
        # Agar avval yaratilgan bazada referrer_id bo'lmasa, qo'shib qo'yamiz
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN referrer_id INTEGER")
        except sqlite3.OperationalError:
            pass  # Ustun allaqachon mavjud

        conn.commit()
    logger.info("Ma'lumotlar bazasi (SQLite) muvaffaqiyatli ishga tushirildi.")

def add_user(user_id: int, full_name: str, username: Optional[str] = None, referrer_id: Optional[int] = None) -> bool:
    """
    Foydalanuvchini bazaga qo'shadi yoki yangilaydi.
    Agar yangi referal bo'lib qo'shilgan bo'lsa True qaytaradi.
    """
    is_new_referral = False
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        existing = cursor.fetchone()

        if not existing:
            # Yangi foydalanuvchi
            valid_referrer = referrer_id if (referrer_id and referrer_id != user_id) else None
            cursor.execute("""
                INSERT INTO users (user_id, full_name, username, is_subscribed, referrer_id)
                VALUES (?, ?, ?, 1, ?)
            """, (user_id, full_name, username, valid_referrer))
            conn.commit()
            if valid_referrer:
                is_new_referral = True
        else:
            # Mavjud foydalanuvchi ma'lumotlarini yangilash
            cursor.execute("""
                UPDATE users SET full_name = ?, username = ?
                WHERE user_id = ?
            """, (full_name, username, user_id))
            conn.commit()

    return is_new_referral

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

def get_all_subscribed_users() -> List[int]:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE is_subscribed = 1")
        rows = cursor.fetchall()
        return [row[0] for row in rows]

def get_all_users() -> List[int]:
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        rows = cursor.fetchall()
        return [row[0] for row in rows]

def get_referral_count(user_id: int) -> int:
    """Foydalanuvchi nechta do'stini taklif qilganini hisoblaydi"""
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
        return cursor.fetchone()[0]

def get_top_referrers(limit: int = 10) -> List[Tuple[str, int]]:
    """Eng ko'p do'st taklif qilgan faol foydalanuvchilar"""
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
        cursor.execute("SELECT user_id, full_name, username, is_subscribed, referrer_id, created_at FROM users ORDER BY created_at DESC")
        rows = cursor.fetchall()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=',', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["User ID", "To'liq ismi", "Username", "Obuna holati", "Taklif qiluvchi ID", "Ro'yxatdan o'tgan sana"])
    for row in rows:
        writer.writerow(row)

    return output.getvalue()
