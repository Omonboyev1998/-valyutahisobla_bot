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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS football_streams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                league TEXT DEFAULT 'APL',
                stream_url TEXT NOT NULL,
                channel_name TEXT DEFAULT 'Sport TV',
                match_time TEXT DEFAULT '🔴 Jonli efir',
                is_live INTEGER DEFAULT 1,
                home_team TEXT,
                away_team TEXT,
                home_logo TEXT,
                away_logo TEXT,
                score TEXT DEFAULT 'vs',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS secretary_settings (
                user_id INTEGER PRIMARY KEY,
                is_enabled INTEGER DEFAULT 0,
                mode TEXT DEFAULT 'busy',
                custom_text TEXT DEFAULT '',
                ai_instructions TEXT DEFAULT '',
                urgent_alerts INTEGER DEFAULT 1,
                auto_digest INTEGER DEFAULT 1,
                cooldown_seconds INTEGER DEFAULT 1800,
                business_connection_id TEXT DEFAULT '',
                has_seeded_schedules INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS secretary_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER NOT NULL,
                sender_id INTEGER NOT NULL,
                sender_name TEXT DEFAULT '',
                sender_username TEXT DEFAULT '',
                message_text TEXT DEFAULT '',
                bot_reply TEXT DEFAULT '',
                is_urgent INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS secretary_schedules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                title TEXT DEFAULT 'Oraliq',
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                reply_text TEXT NOT NULL,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        seed_default_football_streams_if_empty(cursor)
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

        sec_new_columns = [
            ("busy_reason", "TEXT DEFAULT ''"),
            ("emergency_phone", "TEXT DEFAULT ''"),
            ("enable_phone_escalation", "INTEGER DEFAULT 1"),
            ("whitelist", "TEXT DEFAULT '[]'"),
            ("filter_spam", "INTEGER DEFAULT 1"),
            ("has_seeded_schedules", "INTEGER DEFAULT 0")
        ]
        for col_name, col_type in sec_new_columns:
            try:
                cursor.execute(f"ALTER TABLE secretary_settings ADD COLUMN {col_name} {col_type}")
            except Exception:
                pass

        conn.commit()
    logger.info("Ma'lumotlar bazasi (SQLite) muvaffaqiyatli ishga tushirildi.")

def is_new_user(user_id: int) -> bool:
    """Foydalanuvchi bazada mavjud yoki yo'qligini tekshiradi"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone() is None

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
        cursor.execute("SELECT user_id, COALESCE(NULLIF(weather_city, ''), 'Toshkent') FROM users WHERE is_subscribed = 1 AND sub_prayer = 1")
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
        cursor.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            cursor.execute("UPDATE users SET weather_city = ? WHERE user_id = ?", (city, user_id))
        else:
            cursor.execute("""
                INSERT INTO users (user_id, full_name, is_subscribed, sub_currency, sub_weather, sub_football, sub_prayer, notify_time, weather_city)
                VALUES (?, 'Foydalanuvchi', 1, 1, 1, 1, 1, '09:00', ?)
            """, (user_id, city))
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
            return True, f"Bahoingiz qabul qilindi! O'rtacha reyting: ⭐ {avg_r}"
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

# ==================== FOOTBALL STREAMS / TRANSLATSIYA ====================

def seed_default_football_streams_if_empty(cursor):
    """Bazada efirlar bo'lmasa, dastlabki sport telekanallarini qo'shadi"""
    try:
        # Eski soxta o'yinlarni tozalaymiz
        cursor.execute("DELETE FROM football_streams WHERE title LIKE '%Real Madrid vs Barcelona%' OR title LIKE '%Arsenal vs Manchester City%' OR title LIKE '%Liverpool vs Chelsea%'")
        cursor.execute("SELECT COUNT(*) FROM football_streams")
        row = cursor.fetchone()
        count = row[0] if row else 0
        if count == 0:
            default_channels = [
                ("Zo'r TV", "🎭 Ko'ngilochar Telekanal", "https://stream8.cinerama.uz/1016/tracks-v1a1/mono.m3u8", "Zo'r TV", "🔴 24/7 Jonli", 1, "Zo'r", "TV", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("Sport TV HD (O'zbekiston)", "⚽️ Sport Telekanal", "https://stream.mtrk.uz/sport/index.m3u8", "Sport TV", "🔴 24/7 Jonli efir", 1, "Sport TV", "O'zbekiston", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("Futbol TV", "⚽️ Futbol Telekanali", "https://stream.mtrk.uz/sport/index.m3u8", "Futbol TV", "🔴 24/7 Jonli", 1, "Futbol TV", "O'zbekiston", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("Milliy TV", "🎬 Milliy Serial & Shou", "https://stream8.cinerama.uz/1018/tracks-v1a1/mono.m3u8", "Milliy TV", "🔴 24/7 Jonli", 1, "Milliy", "TV", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("MY5 TV (Mening Yurtim)", "⭐️ Yoshlar & Ko'ngilochar", "https://stream8.cinerama.uz/1019/tracks-v1a1/mono.m3u8", "MY5 TV", "🔴 24/7 Jonli", 1, "MY5", "TV", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("Sevimli TV", "❤️ Sevimli Telekanal", "https://stream8.cinerama.uz/1017/tracks-v1a1/mono.m3u8", "Sevimli TV", "🔴 24/7 Jonli", 1, "Sevimli", "TV", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("Yoshlar TV", "⭐️ Yoshlar & Madaniyat", "https://stream.mtrk.uz/yoshlar/index.m3u8", "Yoshlar TV", "🔴 24/7 Jonli", 1, "Yoshlar", "TV", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("Kinoteatr TV", "🍿 Filmlar & Kinolar", "https://stream.mtrk.uz/kinoteatr/index.m3u8", "Kinoteatr TV", "🔴 24/7 Jonli", 1, "Kinoteatr", "TV", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("Bolajon TV", "👶 Bolalar Multfilmlari", "https://stream.mtrk.uz/bolajon/index.m3u8", "Bolajon TV", "🔴 24/7 Jonli", 1, "Bolajon", "TV", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("Aqlvoy TV", "🧠 Ta'limiy & Tarbiyaviy", "https://stream.mtrk.uz/bolajon/index.m3u8", "Aqlvoy TV", "🔴 24/7 Jonli", 1, "Aqlvoy", "TV", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("Dunyo bo'ylab TV", "🌍 Geografik & Hujjatli", "https://stream.mtrk.uz/dunyo/index.m3u8", "Dunyo bo'ylab", "🔴 24/7 Jonli", 1, "Dunyo", "bo'ylab", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("Madaniyat va ma'rifat", "📚 Ilm-fan & Madaniyat", "https://stream.mtrk.uz/madaniyat/index.m3u8", "Madaniyat TV", "🔴 24/7 Jonli", 1, "Madaniyat", "TV", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("Mahalla TV", "🏘 Ijtimoiy & Oilaviy", "https://stream.mtrk.uz/mahalla/index.m3u8", "Mahalla TV", "🔴 24/7 Jonli", 1, "Mahalla", "TV", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("O'zbekiston TV (MTRK)", "🇺🇿 Bosh Milliy Kanal", "https://stream.mtrk.uz/uzbekistan/index.m3u8", "O'zbekiston TV", "🔴 24/7 Jonli", 1, "O'zbekiston", "MTRK", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("FTV Fayz TV", "🎵 Musiqa & Estrada", "https://stream8.cinerama.uz/1018/playlist.m3u8", "FTV", "🔴 24/7 Jonli", 1, "FTV", "Music", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("Navo TV", "🎶 Milliy Qo'shiqlar", "https://stream8.cinerama.uz/1008/tracks-v1a1/playlist.m3u8", "Navo TV", "🔴 24/7 Jonli", 1, "Navo", "TV", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("BIZ TV", "💼 Biznes & Ko'ngilochar", "https://fl.biztv.media/biz_tv_720_uni8jhub4h8fub4idejswh8dh3j94finbu4nidj39inwsj92in3d/index.m3u8", "BIZ TV", "🔴 24/7 Jonli", 1, "BIZ", "TV", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("BIZ Cinema", "🎬 BIZ Kinolar", "https://fl.biztv.media/cinema_720_EMfSyXgoRdiIHgldXTZICucKTIeCKO/index.m3u8", "BIZ Cinema", "🔴 24/7 Jonli", 1, "BIZ", "Cinema", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("BIZ Music", "🎵 BIZ Musiqa", "https://fl.biztv.media/music_720_QAKpGmVUjaPApCNjpsgBxrdqNihAkl/index.m3u8", "BIZ Music", "🔴 24/7 Jonli", 1, "BIZ", "Music", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("Cheksiz TV", "📺 Cheksiz Seriallar", "https://fl.biztv.media/cheksiz_tv_480_unif7hujidth7f4du83jrhuid3k94j8hfj8d93eubych8eju93n4ubt/tracks-v1a1/mono.m3u8", "Cheksiz TV", "🔴 24/7 Jonli", 1, "Cheksiz", "TV", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("Makon TV", "📍 Hududiy Telekanal", "https://stream8.cinerama.uz/1497/tracks-v1a1/mono.m3u8", "Makon TV", "🔴 24/7 Jonli", 1, "Makon", "TV", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("Dasturxon TV", "🍲 Pazandachilik", "https://stream8.cinerama.uz/1206/tracks-v1a1/playlist.m3u8", "Dasturxon TV", "🔴 24/7 Jonli", 1, "Dasturxon", "TV", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("Muz TV Uzbekistan", "🎶 Musiqiy Telekanal", "https://stream8.cinerama.uz/1063/tracks-v1a1/mono.m3u8", "Muz TV", "🔴 24/7 Jonli", 1, "Muz", "TV", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("Farg'ona MTRK", "🏢 Viloyat Telekanali", "https://stream8.cinerama.uz/1458/tracks-v1a1/mono.m3u8", "Farg'ona TV", "🔴 24/7 Jonli", 1, "Farg'ona", "TV", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("Navoiy MTRK", "🏢 Viloyat Telekanali", "https://stream8.cinerama.uz/1460/tracks-v1a1/mono.m3u8", "Navoiy TV", "🔴 24/7 Jonli", 1, "Navoiy", "TV", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("Nurafshon TV", "🏢 Toshkent Viloyati TV", "https://stream8.cinerama.uz/1220/tracks-v1a1/mono.m3u8", "Nurafshon TV", "🔴 24/7 Jonli", 1, "Nurafshon", "TV", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("Real Madrid TV", "🇪🇸 Real Madrid Rasmiy TV", "https://rmtv.akamaized.net/hls/live/2043153/rmtv-es-web/master.m3u8", "Real Madrid TV", "🔴 24/7 Jonli", 1, "Real Madrid", "TV", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("Inter TV", "🇮🇹 Inter Milan Rasmiy TV", "https://d3k8wzt41aflvx.cloudfront.net/INTERTV/Live.m3u8", "Inter TV", "🔴 24/7 Jonli", 1, "Inter", "TV", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("A Spor", "🇹🇷 Turkiya Sport TV", "https://rnttwmjcin.turknet.ercdn.net/lcpmvefbyo/aspor/aspor.m3u8", "A Spor", "🔴 24/7 Jonli", 1, "A Spor", "Turkiya", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("Match! Ultra 4K", "🇷🇺 Rossiya Match TV Ultra", "https://flussonic.linkintel.ru/match/index.m3u8", "Match Ultra", "🔴 24/7 Jonli", 1, "Match TV", "Ultra", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("CBS Sports Golazo", "🇺🇸 AQSH Futbol Oqimi", "https://dai.google.com/linear/hls/event/7f3Wv6f7QEKfQna22jHqLQ/master.m3u8", "CBS Golazo", "🔴 24/7 Jonli", 1, "CBS", "Golazo", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD"),
                ("Red Bull TV", "🇦🇹 Ekstremal Sportlar", "https://rbmn-live.akamaized.net/hls/live/590964/BoRB-AT/master.m3u8", "Red Bull TV", "🔴 24/7 Jonli", 1, "Red Bull", "TV", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "https://upload.wikimedia.org/wikipedia/commons/thumb/d/d3/Soccerball.svg/500px-Soccerball.svg.png", "HD")
            ]
            for s in default_channels:
                cursor.execute("""
                    INSERT INTO football_streams 
                    (title, league, stream_url, channel_name, match_time, is_live, home_team, away_team, home_logo, away_logo, score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, s)
    except Exception as e:
        logger.error(f"Default telekanallarni yaratishda xatolik: {e}")

def get_football_streams(is_live_only: bool = False) -> List[Dict[str, Any]]:
    """Futbol translatsiyalari va kanallar ro'yxatini oladi"""
    with get_db() as conn:
        cursor = conn.cursor()
        if is_live_only:
            cursor.execute("""
                SELECT id, title, league, stream_url, channel_name, match_time, is_live, 
                       home_team, away_team, home_logo, away_logo, score, created_at 
                FROM football_streams 
                WHERE is_live = 1 
                ORDER BY id DESC
            """)
        else:
            cursor.execute("""
                SELECT id, title, league, stream_url, channel_name, match_time, is_live, 
                       home_team, away_team, home_logo, away_logo, score, created_at 
                FROM football_streams 
                ORDER BY is_live DESC, id DESC
            """)
        rows = cursor.fetchall()
        result = []
        for r in rows:
            result.append({
                "id": r[0],
                "title": r[1],
                "league": r[2] or "Futbol",
                "stream_url": r[3],
                "channel_name": r[4] or "Sport TV",
                "match_time": r[5] or "🔴 Jonli efir",
                "is_live": int(r[6]) if r[6] is not None else 1,
                "home_team": r[7] or "",
                "away_team": r[8] or "",
                "home_logo": r[9] or "",
                "away_logo": r[10] or "",
                "score": r[11] or "vs",
                "created_at": str(r[12]) if r[12] else ""
            })
        return result

def add_football_stream(
    title: str,
    stream_url: str,
    league: str = "APL",
    channel_name: str = "Sport TV",
    match_time: str = "🔴 Jonli efir",
    is_live: int = 1,
    home_team: str = "",
    away_team: str = "",
    home_logo: str = "",
    away_logo: str = "",
    score: str = "vs"
) -> int:
    """Yangi translatsiya yoki kanal qo'shish"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO football_streams 
            (title, league, stream_url, channel_name, match_time, is_live, home_team, away_team, home_logo, away_logo, score)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, league, stream_url, channel_name, match_time, is_live, home_team, away_team, home_logo, away_logo, score))
        conn.commit()
        return cursor.lastrowid

def delete_football_stream(stream_id: int) -> bool:
    """Translatsiyani o'chirish"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM football_streams WHERE id = ?", (stream_id,))
        conn.commit()
        return cursor.rowcount > 0


# ==================== SHAXSIY KOTIB / SEKRETAR REJIM ====================

def get_secretary_settings(user_id: int) -> Dict[str, Any]:
    """Foydalanuvchining kotib sozlamalarini oladi yoki yangisini yaratadi"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, is_enabled, mode, custom_text, ai_instructions, 
                   urgent_alerts, auto_digest, cooldown_seconds, business_connection_id, has_seeded_schedules,
                   busy_reason, emergency_phone, enable_phone_escalation, whitelist, filter_spam,
                   created_at, updated_at
            FROM secretary_settings
            WHERE user_id = ?
        """, (user_id,))
        row = cursor.fetchone()
        if not row:
            cursor.execute("""
                INSERT INTO secretary_settings (user_id, is_enabled, mode, custom_text, urgent_alerts, auto_digest, cooldown_seconds, has_seeded_schedules)
                VALUES (?, 0, 'busy', '', 1, 1, 300, 0)
            """, (user_id,))
            conn.commit()
            return {
                "user_id": user_id,
                "is_enabled": 0,
                "mode": "busy",
                "custom_text": "",
                "ai_instructions": "",
                "urgent_alerts": 1,
                "auto_digest": 1,
                "cooldown_seconds": 300,
                "business_connection_id": "",
                "has_seeded_schedules": 0,
                "busy_reason": "",
                "emergency_phone": "",
                "enable_phone_escalation": 1,
                "whitelist": "[]",
                "filter_spam": 1,
                "created_at": "",
                "updated_at": ""
            }
        return {
            "user_id": row[0],
            "is_enabled": int(row[1]) if row[1] is not None else 0,
            "mode": row[2] or "busy",
            "custom_text": row[3] or "",
            "ai_instructions": row[4] or "",
            "urgent_alerts": int(row[5]) if row[5] is not None else 1,
            "auto_digest": int(row[6]) if row[6] is not None else 1,
            "cooldown_seconds": int(row[7]) if row[7] is not None else 300,
            "business_connection_id": row[8] or "",
            "has_seeded_schedules": int(row[9]) if row[9] is not None else 0,
            "busy_reason": row[10] or "",
            "emergency_phone": row[11] or "",
            "enable_phone_escalation": int(row[12]) if row[12] is not None else 1,
            "whitelist": row[13] or "[]",
            "filter_spam": int(row[14]) if row[14] is not None else 1,
            "created_at": str(row[15]) if row[15] else "",
            "updated_at": str(row[16]) if row[16] else ""
        }

def update_secretary_settings(user_id: int, **kwargs) -> bool:
    """Kotib sozlamalarini yangilash"""
    if not kwargs:
        return False
    # Ensure user exists
    get_secretary_settings(user_id)
    fields = []
    values = []
    allowed = [
        "is_enabled", "mode", "custom_text", "ai_instructions", "urgent_alerts",
        "auto_digest", "cooldown_seconds", "business_connection_id", "has_seeded_schedules",
        "busy_reason", "emergency_phone", "enable_phone_escalation", "whitelist", "filter_spam"
    ]
    for k, v in kwargs.items():
        if k in allowed:
            fields.append(f"{k} = ?")
            values.append(v)
    if not fields:
        return False
    fields.append("updated_at = CURRENT_TIMESTAMP")
    values.append(user_id)
    sql = f"UPDATE secretary_settings SET {', '.join(fields)} WHERE user_id = ?"
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(sql, tuple(values))
        conn.commit()
        return cursor.rowcount > 0

def log_secretary_message(
    owner_id: int,
    sender_id: int,
    sender_name: str,
    sender_username: str,
    message_text: str,
    bot_reply: str,
    is_urgent: int = 0
) -> int:
    """Kotib qabul qilgan va javob bergan xabarni logga yozish"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO secretary_logs (owner_id, sender_id, sender_name, sender_username, message_text, bot_reply, is_urgent)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (owner_id, sender_id, sender_name or "", sender_username or "", message_text or "", bot_reply or "", is_urgent))
        conn.commit()
        return cursor.lastrowid

def get_secretary_logs(owner_id: int, limit: int = 15) -> List[Dict[str, Any]]:
    """Kotib qabul qilgan so'nggi xabarlar tarixini oladi"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, owner_id, sender_id, sender_name, sender_username, message_text, bot_reply, is_urgent, created_at
            FROM secretary_logs
            WHERE owner_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (owner_id, limit))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            result.append({
                "id": r[0],
                "owner_id": r[1],
                "sender_id": r[2],
                "sender_name": r[3] or "Noma'lum",
                "sender_username": r[4] or "",
                "message_text": r[5] or "",
                "bot_reply": r[6] or "",
                "is_urgent": int(r[7]) if r[7] is not None else 0,
                "created_at": str(r[8]) if r[8] else ""
            })
        return result

def get_secretary_last_sender_time(owner_id: int, sender_id: int) -> Optional[float]:
    """Bir xil foydalanuvchiga eng oxirgi avtojavob berilgan vaqtini (timestamp) oladi"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT strftime('%s', created_at)
            FROM secretary_logs
            WHERE owner_id = ? AND sender_id = ?
            ORDER BY id DESC
            LIMIT 1
        """, (owner_id, sender_id))
        row = cursor.fetchone()
        if row and row[0]:
            try:
                return float(row[0])
            except ValueError:
                return None
        return None

def get_recent_chat_history(owner_id: int, sender_id: int, limit: int = 4) -> List[Dict[str, str]]:
    """O'sha suhbatdosh bilan bo'lgan so'nggi dialog tarixini oladi (AI xotirasi uchun)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT message_text, bot_reply
            FROM secretary_logs
            WHERE owner_id = ? AND sender_id = ?
            ORDER BY id DESC
            LIMIT ?
        """, (owner_id, sender_id, limit))
        rows = cursor.fetchall()
        history = []
        for r in reversed(rows):
            msg = (r[0] or "").strip()
            reply = (r[1] or "").strip()
            if msg and not msg.startswith("["):
                history.append({"role": "user", "text": msg})
            if reply and not reply.startswith("["):
                history.append({"role": "model", "text": reply})
        return history

def clear_secretary_logs(owner_id: int) -> bool:
    """Foydalanuvchi kotib loglarini tozalash"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM secretary_logs WHERE owner_id = ?", (owner_id,))
        conn.commit()
        return True

def get_secretary_owner_by_connection_id(connection_id: str) -> Optional[Dict[str, Any]]:
    """business_connection_id bo'yicha kotib egasini topadi"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT user_id, is_enabled, mode, custom_text, ai_instructions, 
                   urgent_alerts, auto_digest, cooldown_seconds, business_connection_id
            FROM secretary_settings
            WHERE business_connection_id = ?
        """, (connection_id,))
        row = cursor.fetchone()
        if not row:
            return None
        return {
            "user_id": row[0],
            "is_enabled": int(row[1]) if row[1] is not None else 0,
            "mode": row[2] or "busy",
            "custom_text": row[3] or "",
            "ai_instructions": row[4] or "",
            "urgent_alerts": int(row[5]) if row[5] is not None else 1,
            "auto_digest": int(row[6]) if row[6] is not None else 1,
            "cooldown_seconds": int(row[7]) if row[7] is not None else 1800,
            "business_connection_id": row[8] or ""
        }

def get_secretary_schedules(user_id: int) -> List[Dict[str, Any]]:
    """Foydalanuvchining barcha vaqt jadvallarini oladi"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, user_id, title, start_time, end_time, reply_text, is_active, created_at
            FROM secretary_schedules
            WHERE user_id = ?
            ORDER BY start_time ASC
        """, (user_id,))
        rows = cursor.fetchall()
        result = []
        for r in rows:
            result.append({
                "id": r[0],
                "user_id": r[1],
                "title": r[2] or "Vaqt oralig'i",
                "start_time": r[3],
                "end_time": r[4],
                "reply_text": r[5],
                "is_active": int(r[6]) if r[6] is not None else 1,
                "created_at": str(r[7]) if r[7] else ""
            })
        return result

def add_secretary_schedule(
    user_id: int,
    title: str = "Oraliq",
    start_time: str = "09:00",
    end_time: str = "18:00",
    reply_text: str = "",
    is_active: int = 1
) -> int:
    """Yangi vaqt oralig'i va javob matnini qo'shish"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO secretary_schedules (user_id, title, start_time, end_time, reply_text, is_active)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (user_id, title, start_time, end_time, reply_text, is_active))
        conn.commit()
        return cursor.lastrowid

def delete_secretary_schedule(schedule_id: int, user_id: int = 0) -> bool:
    """Vaqt oralig'ini o'chirish"""
    with get_db() as conn:
        cursor = conn.cursor()
        if user_id:
            cursor.execute("DELETE FROM secretary_schedules WHERE id = ? AND (user_id = ? OR user_id = 0)", (schedule_id, user_id))
            cursor.execute("UPDATE secretary_settings SET has_seeded_schedules = 1 WHERE user_id = ?", (user_id,))
        else:
            cursor.execute("DELETE FROM secretary_schedules WHERE id = ?", (schedule_id,))
        conn.commit()
        return cursor.rowcount > 0

def clear_all_secretary_schedules(user_id: int) -> bool:
    """Foydalanuvchining barcha vaqt jadvallarini tozalash (o'chirish)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM secretary_schedules WHERE user_id = ?", (user_id,))
        cursor.execute("UPDATE secretary_settings SET has_seeded_schedules = 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        return True

def toggle_secretary_schedule(schedule_id: int, user_id: int) -> bool:
    """Vaqt oralig'ini faollashtirish yoki vaqtincha to'xtatish"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE secretary_schedules 
            SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END
            WHERE id = ? AND user_id = ?
        """, (schedule_id, user_id))
        conn.commit()
        return cursor.rowcount > 0

def seed_default_secretary_schedules_if_empty(user_id: int, force_reset: bool = False):
    """Foydalanuvchida birinchi marta kirganda yoki majburiy tiklanganda standart jadvallarni qo'shadi"""
    try:
        # Foydalanuvchi sozlamalari mavjudligini ta'minlaymiz
        settings = get_secretary_settings(user_id)
        if not force_reset:
            # Agar allaqachon seed qilingan bo'lsa, foydalanuvchi o'chirgan bo'lsa ham qayta qo'shmaymiz!
            if settings.get("has_seeded_schedules") == 1:
                return

        with get_db() as conn:
            cursor = conn.cursor()
            if force_reset:
                cursor.execute("DELETE FROM secretary_schedules WHERE user_id = ?", (user_id,))
            else:
                cursor.execute("SELECT COUNT(*) FROM secretary_schedules WHERE user_id = ?", (user_id,))
                row = cursor.fetchone()
                if row and row[0] > 0:
                    cursor.execute("UPDATE secretary_settings SET has_seeded_schedules = 1 WHERE user_id = ?", (user_id,))
                    conn.commit()
                    return

            defaults = [
                (user_id, "☀️ Ish vaqti (Kunduzi)", "09:00", "18:00", "Assalomu alaykum! Hozir ish vaqtidaman. Xabaringizni ko'rib tez orada aloqaga chiqaman.", 1),
                (user_id, "☕️ Tushlik vaqti", "13:00", "14:00", "Assalomu alaykum! Hozir tushlik tanaffusidaman. Soat 14:00 dan so'ng javob yozaman.", 1),
                (user_id, "🌇 Kechki vaqt", "18:00", "23:00", "Xayrli kech! Hozir ishdan tashqari vaqtdaman. Xabaringizni ko'rib albatta javob qaytaraman.", 1),
                (user_id, "🌙 Tungi uyqu", "23:00", "09:00", "Assalomu alaykum! Hozir tungi dam olish vaqti bo'lganligi sababli javob bera olmayapman. Ertalab birinchilardan bo'lib javob qaytaraman.", 1)
            ]
            for d in defaults:
                cursor.execute("""
                    INSERT INTO secretary_schedules (user_id, title, start_time, end_time, reply_text, is_active)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, d)

            # Belgilaymiz: standart jadvallar berildi
            cursor.execute("""
                UPDATE secretary_settings SET has_seeded_schedules = 1 WHERE user_id = ?
            """, (user_id,))
            conn.commit()
    except Exception as e:
        logger.error(f"Default jadvallarni yaratishda xatolik: {e}")

