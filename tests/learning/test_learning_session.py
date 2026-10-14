"""学习会话持久化测试。"""
from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from framesense.learning.models import LearningSession, RegionSpec
from framesense.learning.session import (
    create_session,
    delete_session,
    get_session,
    list_sessions,
    missing_paths,
    relink_paths,
    update_session,
)


def test_create_and_get_session(tmp_path):
    db = tmp_path / "sessions.db"
    sid = create_session(
        reference_path="ref.png",
        source_path="src.png",
        mode="guided",
        title="示例练习",
        db_path=db,
    )
    session = get_session(sid, db_path=db)
    assert session is not None
    assert session.title == "示例练习"
    assert session.mode == "guided"
    assert session.reference_path == "ref.png"


def test_update_session_roundtrip(tmp_path):
    db = tmp_path / "sessions.db"
    sid = create_session("ref.png", "src.png", db_path=db)
    session = get_session(sid, db_path=db)
    assert session is not None
    session.mode = "practice"
    session.notes = "阴影对比明显"
    session.reference_region = RegionSpec(x=10, y=20, width=100, height=80)
    session.source_region = RegionSpec(x=5, y=5, width=90, height=70)
    session.guidance_json = {"steps": [1, 2]}
    session.analysis_json = {"histogram_distance": 0.3}
    update_session(session, db_path=db)

    loaded = get_session(sid, db_path=db)
    assert loaded is not None
    assert loaded.mode == "practice"
    assert loaded.notes == "阴影对比明显"
    assert loaded.reference_region == RegionSpec(x=10, y=20, width=100, height=80)
    assert loaded.source_region == RegionSpec(x=5, y=5, width=90, height=70)
    assert loaded.guidance_json == {"steps": [1, 2]}
    assert loaded.analysis_json == {"histogram_distance": 0.3}


def test_list_sessions_ordered(tmp_path):
    db = tmp_path / "sessions.db"
    a = create_session("ref_a.png", "src_a.png", title="A", db_path=db)
    b = create_session("ref_b.png", "src_b.png", title="B", db_path=db)
    sessions = list_sessions(db_path=db)
    assert [s.id for s in sessions] == [b, a]


def test_delete_session(tmp_path):
    db = tmp_path / "sessions.db"
    sid = create_session("ref.png", "src.png", db_path=db)
    assert delete_session(sid, db_path=db) is True
    assert delete_session(sid, db_path=db) is False
    assert get_session(sid, db_path=db) is None


def test_missing_paths(tmp_path):
    ref = tmp_path / "ref.png"
    ref.write_bytes(b"png")
    src = tmp_path / "missing.png"
    session = LearningSession(
        id=1,
        created_at="t",
        updated_at="t",
        reference_path=str(ref),
        source_path=str(src),
        final_path=str(tmp_path / "final.png"),
    )
    missing = missing_paths(session)
    assert str(src) in missing
    assert str(tmp_path / "final.png") in missing
    assert str(ref) not in missing


def test_relink_paths(tmp_path):
    db = tmp_path / "sessions.db"
    sid = create_session("old_ref.png", "old_src.png", db_path=db)
    new_ref = tmp_path / "new_ref.png"
    new_ref.write_bytes(b"png")
    updated = relink_paths(sid, reference_path=str(new_ref), db_path=db)
    assert updated is not None
    assert updated.reference_path == str(new_ref)
    assert updated.source_path == "old_src.png"


def test_invalid_mode_raises():
    with pytest.raises(ValidationError):
        LearningSession(
            created_at="t",
            updated_at="t",
            reference_path="a",
            source_path="b",
            mode="invalid",
        )
