import json
from framesense.learning.draft import read_draft, write_draft


def test_draft_is_atomic_and_preserves_unicode(tmp_path):
    path = tmp_path / "练习" / "draft.json"
    write_draft(
        path, {"schema": 1, "notes": "阴影更冷，肤色保留", "reference_path": "参考.jpg"}
    )
    assert read_draft(path)["notes"] == "阴影更冷，肤色保留"
    assert not list(path.parent.glob(".draft-*"))
    write_draft(path, {"schema": 1, "notes": "第二次"})
    assert read_draft(path)["notes"] == "第二次"


def test_corrupt_or_future_draft_is_ignored(tmp_path):
    path = tmp_path / "draft.json"
    path.write_text("{broken")
    assert read_draft(path) is None
    path.write_text(json.dumps({"schema": 999}))
    assert read_draft(path) is None
