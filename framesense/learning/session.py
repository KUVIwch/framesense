"""学习会话的 SQLite 持久化。"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path

from framesense.learning.models import LearningSession

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "colorlab_sessions.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    reference_path TEXT NOT NULL,
    source_path TEXT NOT NULL,
    final_path TEXT,
    mode TEXT NOT NULL DEFAULT 'guided',
    notes TEXT NOT NULL DEFAULT '',
    reference_region TEXT,
    source_region TEXT,
    guidance_json TEXT NOT NULL DEFAULT '{}',
    analysis_json TEXT NOT NULL DEFAULT '{}'
)
"""


def _resolve_db_path(db_path: str | Path | None = None) -> Path:
    if db_path is not None:
        return Path(db_path)
    env_path = os.getenv("FRAMESENSE_DB_PATH", "").strip()
    if env_path:
        return Path(env_path)
    return DEFAULT_DB_PATH


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    path = _resolve_db_path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute(_SCHEMA)
    conn.commit()
    return conn


def _to_model(row: sqlite3.Row) -> LearningSession:
    return LearningSession(
        id=int(row["id"]),
        title=row["title"] or "",
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        reference_path=row["reference_path"],
        source_path=row["source_path"],
        final_path=row["final_path"],
        mode=row["mode"],
        notes=row["notes"] or "",
        reference_region=json.loads(row["reference_region"]) if row["reference_region"] else None,
        source_region=json.loads(row["source_region"]) if row["source_region"] else None,
        guidance_json=json.loads(row["guidance_json"] or "{}"),
        analysis_json=json.loads(row["analysis_json"] or "{}"),
    )


def create_session(
    reference_path: str,
    source_path: str,
    mode: str = "guided",
    title: str = "",
    db_path: str | Path | None = None,
) -> int:
    conn = get_connection(db_path)
    try:
        now = _now()
        cur = conn.execute(
            "INSERT INTO sessions (created_at, updated_at, reference_path, source_path, mode, title)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (now, now, reference_path, source_path, mode, title),
        )
        conn.commit()
        return int(cur.lastrowid)
    finally:
        conn.close()


def update_session(session: LearningSession, db_path: str | Path | None = None) -> None:
    if session.id is None:
        raise ValueError("会话缺少 id，无法更新")
    conn = get_connection(db_path)
    try:
        conn.execute(
            "UPDATE sessions SET title=?, updated_at=?, reference_path=?, source_path=?,"
            " final_path=?, mode=?, notes=?, reference_region=?, source_region=?,"
            " guidance_json=?, analysis_json=? WHERE id=?",
            (
                session.title,
                _now(),
                session.reference_path,
                session.source_path,
                session.final_path,
                session.mode,
                session.notes,
                json.dumps(session.reference_region.model_dump()) if session.reference_region else None,
                json.dumps(session.source_region.model_dump()) if session.source_region else None,
                json.dumps(session.guidance_json, ensure_ascii=False),
                json.dumps(session.analysis_json, ensure_ascii=False),
                session.id,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def list_sessions(limit: int = 20, db_path: str | Path | None = None) -> list[LearningSession]:
    conn = get_connection(db_path)
    try:
        rows = conn.execute(
            "SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [_to_model(r) for r in rows]
    finally:
        conn.close()


def get_session(session_id: int, db_path: str | Path | None = None) -> LearningSession | None:
    conn = get_connection(db_path)
    try:
        row = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,)).fetchone()
        return _to_model(row) if row else None
    finally:
        conn.close()


def delete_session(session_id: int, db_path: str | Path | None = None) -> bool:
    conn = get_connection(db_path)
    try:
        cur = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def missing_paths(session: LearningSession) -> list[str]:
    """返回不存在的文件路径（用于提示用户重新定位）。"""
    paths = [session.reference_path, session.source_path]
    if session.final_path:
        paths.append(session.final_path)
    return [p for p in paths if not Path(p).exists()]


def relink_paths(
    session_id: int,
    reference_path: str | None = None,
    source_path: str | None = None,
    final_path: str | None = None,
    db_path: str | Path | None = None,
) -> LearningSession | None:
    """更新文件路径（用于路径失效后重新定位）。"""
    session = get_session(session_id, db_path=db_path)
    if session is None:
        return None
    if reference_path:
        session.reference_path = reference_path
    if source_path:
        session.source_path = source_path
    if final_path is not None:
        session.final_path = final_path
    update_session(session, db_path=db_path)
    return session
