"""
دیتابیس SQLite برای ذخیره کاربران، لینک‌های دعوت، لینک‌های EarnApp و سوابق
"""

import aiosqlite
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)

DB_PATH = "bot_data.db"


async def init_db():
    """ساخت جداول دیتابیس"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                invite_link TEXT,
                invite_link_name TEXT,
                successful_invites INTEGER DEFAULT 0,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS earn_links (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                link TEXT UNIQUE NOT NULL,
                is_used INTEGER DEFAULT 0,
                used_by INTEGER,
                used_at TEXT,
                added_by INTEGER,
                added_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS invite_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                inviter_id INTEGER,
                invited_user_id INTEGER,
                invited_username TEXT,
                invited_full_name TEXT,
                invite_link TEXT,
                status TEXT DEFAULT 'pending',  -- pending, approved, declined
                approved_by INTEGER,
                approved_at TEXT,
                earn_link_given TEXT,
                created_at TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS join_requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                full_name TEXT,
                invite_link TEXT,
                inviter_id INTEGER,
                chat_id INTEGER,
                status TEXT DEFAULT 'pending',
                created_at TEXT
            )
        """)
        await db.commit()
        logger.info("Database initialized successfully")


async def add_or_update_user(user_id: int, username: str = None, full_name: str = None):
    """افزودن یا آپدیت کاربر"""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            INSERT INTO users (user_id, username, full_name, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username = COALESCE(excluded.username, users.username),
                full_name = COALESCE(excluded.full_name, users.full_name),
                updated_at = excluded.updated_at
        """, (user_id, username, full_name, now, now))
        await db.commit()


async def set_user_invite_link(user_id: int, invite_link: str, link_name: str):
    """ذخیره لینک دعوت کاربر"""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users SET invite_link = ?, invite_link_name = ?, updated_at = ?
            WHERE user_id = ?
        """, (invite_link, link_name, now, user_id))
        await db.commit()


async def get_user(user_id: int) -> Optional[Dict[str, Any]]:
    """گرفتن اطلاعات کاربر"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_user_by_link_name(link_name: str) -> Optional[Dict[str, Any]]:
    """پیدا کردن کاربر از روی نام لینک دعوت"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE invite_link_name = ?", (link_name,)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def increment_successful_invites(user_id: int):
    """افزایش تعداد دعوت موفق"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE users SET successful_invites = successful_invites + 1, updated_at = ?
            WHERE user_id = ?
        """, (datetime.utcnow().isoformat(), user_id))
        await db.commit()


# ---------- Earn Links ----------

async def add_earn_links(links: List[str], added_by: int) -> int:
    """افزودن چندین لینک EarnApp (لینک‌های تکراری نادیده گرفته می‌شوند)"""
    now = datetime.utcnow().isoformat()
    added = 0
    async with aiosqlite.connect(DB_PATH) as db:
        for link in links:
            link = link.strip()
            if not link:
                continue
            try:
                await db.execute("""
                    INSERT INTO earn_links (link, added_by, added_at)
                    VALUES (?, ?, ?)
                """, (link, added_by, now))
                added += 1
            except aiosqlite.IntegrityError:
                pass  # تکراری
        await db.commit()
    return added


async def get_available_earn_link() -> Optional[Dict[str, Any]]:
    """گرفتن یک لینک استفاده نشده"""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM earn_links WHERE is_used = 0 ORDER BY id ASC LIMIT 1
        """) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def mark_earn_link_used(link_id: int, used_by: int):
    """علامت‌گذاری لینک به عنوان استفاده شده"""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            UPDATE earn_links SET is_used = 1, used_by = ?, used_at = ?
            WHERE id = ?
        """, (used_by, now, link_id))
        await db.commit()


async def count_earn_links() -> Dict[str, int]:
    """تعداد لینک‌های موجود و استفاده شده"""
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM earn_links WHERE is_used = 0") as c:
            available = (await c.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM earn_links WHERE is_used = 1") as c:
            used = (await c.fetchone())[0]
        return {"available": available, "used": used, "total": available + used}


# ---------- History & Join Requests ----------

async def add_join_request(user_id: int, username: str, full_name: str,
                           invite_link: str, inviter_id: int, chat_id: int) -> int:
    """ثبت درخواست عضویت"""
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO join_requests (user_id, username, full_name, invite_link, inviter_id, chat_id, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (user_id, username, full_name, invite_link, inviter_id, chat_id, now))
        await db.commit()
        return cursor.lastrowid


async def get_pending_join_request(user_id: int, chat_id: int) -> Optional[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM join_requests
            WHERE user_id = ? AND chat_id = ? AND status = 'pending'
            ORDER BY id DESC LIMIT 1
        """, (user_id, chat_id)) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def update_join_request_status(req_id: int, status: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE join_requests SET status = ? WHERE id = ?", (status, req_id))
        await db.commit()


async def add_invite_history(inviter_id: int, invited_user_id: int, invited_username: str,
                             invited_full_name: str, invite_link: str, status: str = "pending",
                             earn_link: str = None, approved_by: int = None) -> int:
    now = datetime.utcnow().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("""
            INSERT INTO invite_history
            (inviter_id, invited_user_id, invited_username, invited_full_name, invite_link,
             status, earn_link_given, approved_by, approved_at, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (inviter_id, invited_user_id, invited_username, invited_full_name, invite_link,
              status, earn_link, approved_by, now if status == "approved" else None, now))
        await db.commit()
        return cursor.lastrowid


async def get_user_history(user_id: int, limit: int = 20) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM invite_history WHERE inviter_id = ?
            ORDER BY id DESC LIMIT ?
        """, (user_id, limit)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_all_history(limit: int = 50) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT * FROM invite_history ORDER BY id DESC LIMIT ?
        """, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]


async def get_top_inviters(limit: int = 10) -> List[Dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("""
            SELECT user_id, username, full_name, successful_invites
            FROM users WHERE successful_invites > 0
            ORDER BY successful_invites DESC LIMIT ?
        """, (limit,)) as cursor:
            rows = await cursor.fetchall()
            return [dict(r) for r in rows]
