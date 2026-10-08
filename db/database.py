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
    schema_path = os.path_join("schema.sql")
    with open(schema_path, "r", encoding="utf-8") as f:
        sql = f.read()
    conn = get_conn()
    conn.executescript(sql)
    conn.commit()
    conn.close()


def os_path_join(*parts):
    import os
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), *parts)


# ============ 用户 ============
def create_user(name: str, email: str) -> int:
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO users (name, email) VALUES (?, ?)", (name, email)
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
def save_briefing(user_id: int, title: str, content: str, news_count: int) -> int:
    today = datetime.now().strftime("%Y-%m-%d")
    conn = get_conn()
    cur = conn.execute(
        "INSERT INTO briefings (user_id, date, title, content, news_count) VALUES (?, ?, ?, ?, ?)",
        (user_id, today, title, content, news_count),
    )
    conn.commit()
    bid = cur.lastrowid
    conn.close()
    return bid


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
    conn.execute(
        "INSERT INTO news_cache (title, url, source, summary, published_at) VALUES (?, ?, ?, ?, ?)",
        (title, url, source, summary, published_at),
    )
    conn.commit()
    conn.close()


def get_cached_news(limit: int = 50) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM news_cache ORDER BY fetched_at DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]
