"""离线 CLI 测试。"""
from __future__ import annotations

import io
import json

import pytest
from PIL import Image

from framesense.cli import main


def _write_png(path, color=(120, 80, 200)):
    buf = io.BytesIO()
    Image.new("RGB", (32, 24), color).save(buf, format="PNG")
    path.write_bytes(buf.getvalue())


def test_analyze_command(tmp_path, capsys):
    ref = tmp_path / "ref.png"
    src = tmp_path / "src.png"
    _write_png(ref, (220, 220, 220))
    _write_png(src, (30, 30, 30))
    out = tmp_path / "result.json"
    rc = main(["analyze", str(ref), str(src), "--output", str(out)])
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert "guidance" in data
    assert "comparison" in data
    assert data["guidance"]["steps"]


def test_analyze_with_regions(tmp_path):
    ref = tmp_path / "ref.png"
    src = tmp_path / "src.png"
    _write_png(ref, (220, 80, 80))
    _write_png(src, (80, 220, 80))
    out = tmp_path / "result.json"
    rc = main(
        [
            "analyze",
            str(ref),
            str(src),
            "--region-ref",
            "0,0,32,24",
            "--region-src",
            "0,0,32,24",
            "--output",
            str(out),
        ]
    )
    assert rc == 0
    data = json.loads(out.read_text(encoding="utf-8"))
    assert data["regions"]
    assert data["regions"][0]["delta_e_cie76"] > 10


def test_session_commands(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("FRAMESENSE_DB_PATH", str(tmp_path / "sessions.db"))
    ref = tmp_path / "ref.png"
    src = tmp_path / "src.png"
    _write_png(ref)
    _write_png(src)
    rc = main(["session", "create", "--reference", str(ref), "--source", str(src), "--title", "t"])
    assert rc == 0
    sid = int(capsys.readouterr().out.strip())
    rc = main(["session", "list"])
    assert rc == 0
    out = capsys.readouterr().out
    assert str(sid) in out
    rc = main(["session", "get", "--id", str(sid)])
    assert rc == 0
    data = json.loads(capsys.readouterr().out)
    assert data["title"] == "t"
