"""主窗口冒烟测试（离屏渲染，不写数据库）。"""

from __future__ import annotations

import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PIL import Image
from PySide6.QtWidgets import QApplication

from framesense.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def _load(qapp, window: MainWindow, color, is_ref: bool) -> None:
    from framesense.core.loader import load_image_bytes

    buf = __import__("io").BytesIO()
    Image.new("RGB", (40, 30), color).save(buf, format="PNG")
    data = buf.getvalue()
    loaded = load_image_bytes(data, "test.png")
    if is_ref:
        window._ref = loaded
    else:
        window._src = loaded


def test_main_window_analyze_smoke(qapp, tmp_path):
    window = MainWindow(
        db_path=tmp_path / "sessions.db", draft_path=tmp_path / "draft.json"
    )
    _load(qapp, window, (220, 220, 220), is_ref=True)
    _load(qapp, window, (40, 40, 40), is_ref=False)
    window._analyze()
    deadline = time.monotonic() + 10
    while not window._analysis_json and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.01)
    assert (
        "操作建议" in window.guidance_text.toPlainText()
        or "差异较小" in window.guidance_text.toPlainText()
    )
    assert window._analysis_json
    window.close()
