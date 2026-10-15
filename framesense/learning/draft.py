"""项目内的原子草稿。只记录路径和文字，不复制照片。"""

from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile


def write_draft(path: Path, payload: dict) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".draft-", suffix=".json", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(payload, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def read_draft(path: Path) -> dict | None:
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if isinstance(value, dict) and value.get("schema") == 1:
            return value
    except (OSError, ValueError):
        pass
    return None
