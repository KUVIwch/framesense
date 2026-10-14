"""SQLite 历史记录测试。"""
from __future__ import annotations

from framesense.db import (
    delete_session,
    get_session,
    list_sessions,
    save_session,
)


def test_save_and_get_session(tmp_path):
    db = tmp_path / "test.db"
    sid = save_session(
        filename="photo.jpg",
        intent_keywords=["电影感"],
        plan_json={"summary": "方案", "model_provider": "mock"},
        report_md="# 报告",
        source_json={"exif": {"iso": 100}},
        db_path=db,
    )
    assert sid > 0
    row = get_session(sid, db_path=db)
    assert row is not None
    assert row["filename"] == "photo.jpg"
    assert "电影感" in row["intent_keywords"]
    assert "方案" in row["plan_json"]
    assert row["report_md"] == "# 报告"


def test_list_sessions_ordered(tmp_path):
    db = tmp_path / "test.db"
    save_session("a.jpg", ["明亮"], {"summary": "a"}, "a", {}, db_path=db)
    save_session("b.jpg", ["阴郁"], {"summary": "b"}, "b", {}, db_path=db)
    sessions = list_sessions(limit=10, db_path=db)
    assert len(sessions) == 2
    assert sessions[0]["filename"] == "b.jpg"
    assert sessions[1]["filename"] == "a.jpg"


def test_delete_session(tmp_path):
    db = tmp_path / "test.db"
    sid = save_session("a.jpg", ["明亮"], {"summary": "a"}, "a", {}, db_path=db)
    assert delete_session(sid, db_path=db) is True
    assert delete_session(sid, db_path=db) is False
    assert get_session(sid, db_path=db) is None
