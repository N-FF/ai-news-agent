"""SQLite 数据库操作封装"""
import sqlite3
from datetime import datetime
from typing import Optional
import config


def get_conn():
    conn = sqlite3.connect(config.DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """执行 schema.sql 建表"""
    schema_path = os_path_join("schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()
    conn = get_conn()
    try:
        conn.executescript(sql)
        columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
        if "daily_send_time" not in columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN daily_send_time TEXT NOT NULL DEFAULT '09:00'"
            )
        if "timezone_name" not in columns:
            conn.execute(
                "ALTER TABLE users ADD COLUMN timezone_name TEXT NOT NULL DEFAULT 'Asia/Shanghai'"
            )
        conn.execute(
            """
            DELETE FROM news_cache
            WHERE url IS NOT NULL AND url <> ''
              AND rowid NOT IN (
                  SELECT MAX(rowid) FROM news_cache
                  WHERE url IS NOT NULL AND url <> ''
                  GROUP BY url
              )
            """
        )
        conn.execute(
            """
            DELETE FROM briefings
            WHERE id NOT IN (
                SELECT MAX(id) FROM briefings GROUP BY user_id, date
            )
            """
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_news_cache_url ON news_cache(url) WHERE url IS NOT NULL AND url <> ''"
        )
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_briefings_user_date ON briefings(user_id, date)"
        )
        conn.commit()
    finally:
        conn.close()


def os_path_join(*parts):
    import os
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), *parts)


# ============ 用户 ============
def create_user(name: str, email: str, timezone_name: str = "Asia/Shanghai") -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO users (name, email, timezone_name) VALUES (?, ?, ?)",
        (name, email, timezone_name),
    )
    conn.commit()
    uid = cur.lastrowid
    conn.close()
    return uid


def get_user_by_email(email: str) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_user(user_id: int) -> Optional[dict]:
    conn = get_conn()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def update_user_schedule(email: str, daily_send_time: str, timezone_name: str) -> bool:
    conn = get_conn()
    try:
        cur = conn.execute(
            "UPDATE users SET daily_send_time = ?, timezone_name = ? WHERE email = ?",
            (daily_send_time, timezone_name, email),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_users_with_subscriptions() -> list:
    conn = get_conn()
    try:
        rows = conn.execute(
            """
            SELECT users.* FROM users
                        WHERE EXISTS (
                  SELECT 1 FROM subscriptions
                  WHERE subscriptions.user_id = users.id
              )
            """,
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


# ============ 订阅偏好 ============
def add_subscription(user_id: int, topic: str, keyword: str = ""):
    conn = get_conn()
    conn.execute(
        "INSERT INTO subscriptions (user_id, topic, keyword) VALUES (?, ?, ?)",
        (user_id, topic, keyword),
    )
    conn.commit()
    conn.close()


def get_subscriptions(user_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM subscriptions WHERE user_id = ?", (user_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_subscription(sub_id: int):
    conn = get_conn()
    conn.execute("DELETE FROM subscriptions WHERE id = ?", (sub_id,))
    conn.commit()
    conn.close()


# ============ 简报 ============
def save_briefing(
    user_id: int,
    title: str,
    content: str,
    news_count: int,
    briefing_date: str | None = None,
) -> int:
    today = briefing_date or datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    conn.execute(
        """
        INSERT INTO briefings (user_id, date, title, content, news_count)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(user_id, date) DO UPDATE SET
            title = excluded.title,
            content = excluded.content,
            news_count = excluded.news_count,
            created_at = CURRENT_TIMESTAMP
        """,
        (user_id, today, title, content, news_count),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM briefings WHERE user_id = ? AND date = ?",
        (user_id, today),
    ).fetchone()
    conn.close()
    return row["id"]


def get_briefings(user_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM briefings WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_users() -> list:
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ============ 新闻缓存 ============
def cache_news(title: str, url: str, source: str, summary: str, published_at: str):
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO news_cache (title, url, source, summary, published_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(url) WHERE url IS NOT NULL AND url <> '' DO UPDATE SET
                title = excluded.title,
                source = excluded.source,
                summary = excluded.summary,
                published_at = excluded.published_at,
                fetched_at = CURRENT_TIMESTAMP
            """,
            (title, url, source, summary, published_at),
        )
        conn.commit()
    finally:
        conn.close()


def cleanup_old_news_cache(retention_days: int = 30) -> int:
    retention_days = max(1, int(retention_days))
    conn = get_conn()
    try:
        cur = conn.execute(
            "DELETE FROM news_cache WHERE fetched_at < datetime('now', ?)",
            (f"-{retention_days} days",),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def get_cached_news(limit: int = 50) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM news_cache ORDER BY fetched_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def record_email_delivery(
    recipient: str,
    subject: str,
    status: str,
    attempts: int,
    error_message: str = "",
) -> None:
    conn = get_conn()
    try:
        conn.execute(
            """
            INSERT INTO email_deliveries
                (recipient, subject, status, attempts, error_message)
            VALUES (?, ?, ?, ?, ?)
            """,
            (recipient, subject, status, attempts, error_message[:1000]),
        )
        conn.commit()
    finally:
        conn.close()
