"""SQLite 历史记录（数据库仅存于项目 data/ 目录，绝不写入用户文件）。"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "framesense.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL,
    filename TEXT NOT NULL,
    intent_keywords TEXT NOT NULL,
    plan_json TEXT NOT NULL,
    report_md TEXT NOT NULL,
    source_json TEXT NOT NULL
)
"""

def _resolve_db_path(db_path: str | Path | None = None) -> Path:
    """解析数据库路径；支持环境变量 FRAMESENSE_DB_PATH 覆盖默认值。"""
    if db_path is not None:
        return Path(db_path)
    env_path = os.getenv("FRAMESENSE_DB_PATH", "").strip()
    if env_path:
        return Path(env_path)
    return DEFAULT_DB_PATH


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """创建连接并确保表结构存在。"""
    db_path = _resolve_db_path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    conn.commit()
    return conn


def save_session(
    filename: str,
    intent_keywords: list[str],
    plan_json: dict,
    report_md: str,
    source_json: dict,
    db_path: str | Path | None = None,
) -> int:
    """保存一次分析会话，返回 session id。"""
    conn = get_connection(db_path)
    try:
        cur = conn.execute(
            "INSERT INTO sessions (created_at, filename, intent_keywords, plan_json, report_md, source_json)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (
                datetime.now().isoformat(timespec="seconds"),
                filename,
                json.dumps(intent_keywords, ensure_ascii=False),
                json.dumps(plan_json, ensure_ascii=False),
                report_md,
                json.dumps(source_json, ensure_ascii=False),
            ),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def list_sessions(limit: int = 20, db_path: str | Path | None = None) -> list[dict]:
    """列出最近会话（不含大字段）。"""
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT id, created_at, filename, intent_keywords FROM sessions ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_session(session_id: int, db_path: str | Path | None = None) -> dict | None:
    """读取单个会话完整内容。"""
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def delete_session(session_id: int, db_path: str | Path | None = None) -> bool:
    """删除会话记录，返回是否删除成功。"""
    conn = get_connection(db_path)
    try:
        cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
