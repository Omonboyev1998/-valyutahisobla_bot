import sqlite3
import os
import csv
import io
import logging
from contextlib import contextmanager
from typing import List, Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

_libsql = None
if TURSO_DATABASE_URL and TURSO_AUTH_TOKEN:
    try:
        import libsql_experimental as _libsql
        logger.info("Turso Cloud SQLite drayveri (libsql_experimental) faollashtirildi.")
    except ImportError:
        logger.warning("libsql_experimental o'rnatilmagan, standart sqlite3 ishlatilmoqda.")

DB_PATH = os.getenv("DB_PATH") or os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "bot.db")

@contextmanager
def get_db():
    """Turso Cloud yoki Mahalliy SQLite uchun universal ulanish boshqaruvchisi"""
    if _libsql and TURSO_DATABASE_URL and TURSO_AUTH_TOKEN:
        try:
            conn = _libsql.connect(TURSO_DATABASE_URL, auth_token=TURSO_AUTH_TOKEN)
        except TypeError:
            conn = _libsql.connect(f"{TURSO_DATABASE_URL}?authToken={TURSO_AUTH_TOKEN}")
    else:
        conn = sqlite3.connect(DB_PATH, timeout=20.0)
    try:
        yield conn
        try:
            conn.commit()
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass

def to_dict(cols_or_cursor, row):
    if not row:
        return None
    if isinstance(row, dict):
        return row
    if hasattr(row, "keys"):
        try:
            return dict(row)
        except Exception:
            pass
    if isinstance(cols_or_cursor, list):
        cols = cols_or_cursor
    elif hasattr(cols_or_cursor, "description") and cols_or_cursor.description:
        cols = [col[0] for col in cols_or_cursor.description]
    else:
        cols = []
    if cols and len(cols) == len(row):
        return dict(zip(cols, row))
    return {}

def init_db():
    if not (TURSO_DATABASE_URL and TURSO_AUTH_TOKEN):
        os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    with get_db() as conn:
        if not (TURSO_DATABASE_URL and TURSO_AUTH_TOKEN):
            try:
                conn.execute("PRAGMA journal_mode=WAL;")
                conn.execute("PRAGMA busy_timeout = 20000;")
            except Exception:
                pass
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
                sub_prayer INTEGER DEFAULT 1,
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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                master_name TEXT NOT NULL,
                phone TEXT NOT NULL,
                username TEXT,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                region TEXT DEFAULT 'Barcha hududlar',
                is_active INTEGER DEFAULT 1,
                views_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_reviews (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_id INTEGER NOT NULL,
                user_id INTEGER NOT NULL,
                rating INTEGER NOT NULL,
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(service_id, user_id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                service_id INTEGER NOT NULL,
                client_user_id INTEGER NOT NULL,
                client_name TEXT NOT NULL,
                client_phone TEXT NOT NULL,
                message TEXT,
                status TEXT DEFAULT 'new',
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
            except Exception:
                pass

        # services jadvali uchun yangi ustunlar
        service_new_columns = [
            ("photo_id", "TEXT"),
            ("price", "TEXT DEFAULT ''"),
            ("rating", "REAL DEFAULT 5.0"),
            ("rating_count", "INTEGER DEFAULT 0")
        ]
        for col_name, col_type in service_new_columns:
            try:
                cursor.execute(f"ALTER TABLE services ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

        conn.commit()
    logger.info("Ma'lumotlar bazasi (SQLite) muvaffaqiyatli ishga tushirildi.")

def add_user(user_id: int, full_name: str, username: Optional[str] = None, referrer_id: Optional[int] = None) -> bool:
    is_new_referral = False
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        existing = cursor.fetchone()

        if not existing:
            valid_referrer = referrer_id if (referrer_id and referrer_id != user_id) else None
            cursor.execute("""
                INSERT INTO users (user_id, full_name, username, is_subscribed, referrer_id, sub_currency, sub_weather, sub_football, sub_prayer, notify_time, weather_city)
                VALUES (?, ?, ?, 1, ?, 1, 1, 1, 1, '09:00', 'Toshkent')
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
    with get_db() as conn:
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

    with get_db() as conn:
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
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, weather_city FROM users WHERE is_subscribed = 1 AND sub_prayer = 1")
        return cursor.fetchall()

def set_user_notify_time(user_id: int, time_str: str):
    """Xabar kelish vaqtini o'rnatish (masalan: '08:00', '09:00')"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET notify_time = ? WHERE user_id = ?", (time_str, user_id))
        conn.commit()

def set_user_weather_city(user_id: int, city: str):
    """Ob-havo eslatmasi va doimiy hudud uchun shahar nomini o'rnatish"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET weather_city = ? WHERE user_id = ?", (city, user_id))
        conn.commit()

def get_user_weather_city(user_id: int) -> str:
    """Foydalanuvchining doimiy saqlangan shahrini qaytaradi"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT weather_city FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return row[0] if (row and row[0]) else "Toshkent"

def set_subscription(user_id: int, status: bool):
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_subscribed = ? WHERE user_id = ?", (1 if status else 0, user_id))
        conn.commit()

def is_user_subscribed(user_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_subscribed FROM users WHERE user_id = ?", (user_id,))
        row = cursor.fetchone()
        return bool(row[0]) if row else True

def get_users_for_time(time_str: str) -> List[Dict[str, Any]]:
    """Aynan belgilangan vaqtda xabar oluvchi faol foydalanuvchilar"""
    with get_db() as conn:
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
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM users")
        rows = cursor.fetchall()
        return [row[0] for row in rows]

def get_referral_count(user_id: int) -> int:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (user_id,))
        return cursor.fetchone()[0]

def get_top_referrers(limit: int = 10) -> List[Tuple[str, int]]:
    with get_db() as conn:
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
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO conversions (user_id, from_ccy, to_ccy, amount)
                VALUES (?, ?, ?, ?)
            """, (user_id, from_ccy.upper(), to_ccy.upper(), amount))
            conn.commit()
    except Exception as e:
        logger.error(f"Statistikani yozishda xatolik: {e}")

def get_statistics() -> Dict[str, Any]:
    with get_db() as conn:
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
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, full_name, username, is_subscribed, referrer_id, notify_time, weather_city, created_at FROM users ORDER BY created_at DESC")
        rows = cursor.fetchall()

    output = io.StringIO()
    writer = csv.writer(output, delimiter=',', quoting=csv.QUOTE_MINIMAL)
    writer.writerow(["User ID", "To'liq ismi", "Username", "Obuna holati", "Taklif qiluvchi ID", "Eslatma vaqti", "Ob-havo shahri", "Ro'yxatdan o'tgan sana"])
    for row in rows:
        writer.writerow(row)

    return output.getvalue()

# ==================== MAISHIY XIZMATLAR (USTALAR BOZORI) ====================

def add_service(
    user_id: int,
    master_name: str,
    phone: str,
    username: Optional[str],
    category: str,
    title: str,
    description: str,
    region: str = "Barcha hududlar",
    price: str = "",
    photo_id: Optional[str] = None
) -> int:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO services (user_id, master_name, phone, username, category, title, description, region, price, photo_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (user_id, master_name, phone, username, category, title, description, region, price, photo_id))
        conn.commit()
        return cursor.lastrowid

def get_services(
    category: Optional[str] = None,
    region: Optional[str] = None,
    search_query: Optional[str] = None,
    limit: int = 5,
    offset: int = 0
) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()

        query = "SELECT * FROM services WHERE is_active = 1"
        params: List[Any] = []

        if category and category != "Barchasi":
            query += " AND category = ?"
            params.append(category)

        if region and region != "Barcha hududlar":
            query += " AND (region = ? OR region = 'Barcha hududlar')"
            params.append(region)

        if search_query:
            query += " AND (title LIKE ? OR description LIKE ? OR master_name LIKE ?)"
            like_term = f"%{search_query}%"
            params.extend([like_term, like_term, like_term])

        query += " ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor.execute(query, tuple(params))
        rows = cursor.fetchall()
        return [to_dict(cursor, row) for row in rows]

def count_services(
    category: Optional[str] = None,
    region: Optional[str] = None,
    search_query: Optional[str] = None
) -> int:
    with get_db() as conn:
        cursor = conn.cursor()
        query = "SELECT COUNT(*) FROM services WHERE is_active = 1"
        params: List[Any] = []

        if category and category != "Barchasi":
            query += " AND category = ?"
            params.append(category)

        if region and region != "Barcha hududlar":
            query += " AND (region = ? OR region = 'Barcha hududlar')"
            params.append(region)

        if search_query:
            query += " AND (title LIKE ? OR description LIKE ? OR master_name LIKE ?)"
            like_term = f"%{search_query}%"
            params.extend([like_term, like_term, like_term])

        cursor.execute(query, tuple(params))
        return cursor.fetchone()[0]

def get_service_by_id(service_id: int) -> Optional[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM services WHERE id = ?", (service_id,))
        cols = [col[0] for col in cursor.description] if cursor.description else []
        row = cursor.fetchone()
        if row:
            cursor.execute("UPDATE services SET views_count = views_count + 1 WHERE id = ?", (service_id,))
            conn.commit()
            return to_dict(cols, row)
        return None

def get_user_services(user_id: int) -> List[Dict[str, Any]]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM services WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
        rows = cursor.fetchall()
        return [to_dict(cursor, row) for row in rows]

def delete_service(service_id: int, user_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM services WHERE id = ? AND user_id = ?", (service_id, user_id))
        conn.commit()
        return cursor.rowcount > 0

def admin_delete_service(service_id: int) -> bool:
    """Admin tomonidan xizmatni bazadan o'chirish"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM services WHERE id = ?", (service_id,))
        conn.commit()
        return cursor.rowcount > 0

def admin_approve_service(service_id: int) -> bool:
    """Admin tomonidan xizmatni tasdiqlash (faol qilish)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE services SET is_active = 1 WHERE id = ?", (service_id,))
        conn.commit()
        return cursor.rowcount > 0

def toggle_service_status(service_id: int, user_id: int) -> Optional[int]:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT is_active FROM services WHERE id = ? AND user_id = ?", (service_id, user_id))
        row = cursor.fetchone()
        if not row:
            return None
        new_status = 0 if row[0] == 1 else 1
        cursor.execute("UPDATE services SET is_active = ? WHERE id = ? AND user_id = ?", (new_status, service_id, user_id))
        conn.commit()
        return new_status

def add_service_review(service_id: int, user_id: int, rating: int, comment: str = "") -> Tuple[bool, str]:
    with get_db() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO service_reviews (service_id, user_id, rating, comment)
                VALUES (?, ?, ?, ?)
            """, (service_id, user_id, rating, comment))

            # Yangi o'rtacha reytingni hisoblash
            cursor.execute("SELECT AVG(rating), COUNT(rating) FROM service_reviews WHERE service_id = ?", (service_id,))
            avg_r, cnt_r = cursor.fetchone()
            avg_r = round(avg_r, 1) if avg_r else 5.0

            cursor.execute("""
                UPDATE services 
                SET rating = ?, rating_count = ? 
                WHERE id = ?
            """, (avg_r, cnt_r, service_id))

            conn.commit()
        except Exception as e:
            if "UNIQUE" in str(e) or "integrity" in str(e).lower() or isinstance(e, sqlite3.IntegrityError):
                return False, "Siz ushbu ustaga allaqachon baho bergansiz!"
            logger.error(f"Baho qo'shishda xatolik: {e}")
            return False, "Baho qo'shishda xatolik yuz berdi."

def has_user_reviewed(service_id: int, user_id: int) -> bool:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM service_reviews WHERE service_id = ? AND user_id = ?", (service_id, user_id))
        return cursor.fetchone() is not None

def add_service_order(
    service_id: int,
    client_user_id: int,
    client_name: str,
    client_phone: str,
    message: str = ""
) -> int:
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO service_orders (service_id, client_user_id, client_name, client_phone, message)
            VALUES (?, ?, ?, ?, ?)
        """, (service_id, client_user_id, client_name, client_phone, message))
        conn.commit()
        return cursor.lastrowid
