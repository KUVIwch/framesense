"""Streamlit 核心 UI 测试（streamlit.testing.v1，不发起真实网络请求）。"""
from __future__ import annotations

import io
from pathlib import Path

from PIL import Image
from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
APP_PATH = PROJECT_ROOT / "framesense" / "web" / "app.py"


def _set_test_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("FRAMESENSE_VISION_MODE", "mock")
    monkeypatch.setenv("FRAMESENSE_DB_PATH", str(tmp_path / "ui.db"))
    monkeypatch.setenv("FRAMESENSE_REQUEST_TIMEOUT", "10")
    monkeypatch.setenv("FRAMESENSE_MAX_RETRIES", "0")
    monkeypatch.setenv("FRAMESENSE_JSON_MODE", "false")
    monkeypatch.setenv("FRAMESENSE_MAX_TOKENS", "4000")


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 24), (120, 80, 200)).save(buf, format="PNG")
    return buf.getvalue()


def test_app_renders_title(monkeypatch, tmp_path):
    _set_test_env(monkeypatch, tmp_path)
    at = AppTest.from_file(str(APP_PATH))
    at.run(timeout=20)
    assert len(at.title) == 1


def test_app_mock_generation_flow(monkeypatch, tmp_path):
    """Mock 模式下完整生成流程：上传 → 关键词 → 生成 → 显示方案，且不发起真实请求。"""
    _set_test_env(monkeypatch, tmp_path)
    at = AppTest.from_file(str(APP_PATH))
    at.run(timeout=20)

    at.get("file_uploader")[0].set_value([("test.png", _png_bytes(), "image/png")])
    at.run(timeout=20)

    at.multiselect[0].set_value(["电影感"])
    at.run(timeout=20)

    generate_button = [b for b in at.button if "生成" in b.label][0]
    generate_button.click().run(timeout=20)

    assert not at.error
    assert any("Mock" in (i.value or "") for i in at.info)
    assert any("不应破坏的艺术特征" in (m.value or "") for m in at.markdown)
    assert not any("调用失败" in (e.value or "") for e in at.error)
