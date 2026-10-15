"""Opt-in packaged application verification using synthetic local fixtures."""

from __future__ import annotations
import json
import time
from PIL import Image
from PySide6.QtCore import QTimer
from framesense import __version__
from framesense.ui.resources import asset_path


def verify_package(app, window, output):
    for name, size, color in [
        ("ref", (640, 480), (180, 145, 110)),
        ("src", (800, 550), (100, 135, 165)),
    ]:
        path = output.parent / (name + ".jpg")
        Image.new("RGB", size, color).save(path)
        window.load_path(name, str(path))
    started = time.monotonic()
    timer = QTimer(window)
    timer.setInterval(50)

    def poll():
        if window.jobs.busy and time.monotonic() - started < 30:
            return
        timer.stop()
        result = {
            "ok": False,
            "version": __version__,
            "elapsed_seconds": round(time.monotonic() - started, 3),
        }
        try:
            assert window._guidance and window._analysis_json.get(
                "comparison"
            ), window.statusBar().currentMessage()
            assert not window.windowIcon().isNull()
            assert asset_path("framesense.svg").is_file()
            window.notes_edit.setPlainText("离线打包验证：合成素材，不含用户照片。")
            window._save_session()
            assert window._session_id is not None
            window.mode_combo.setCurrentIndex(1)
            window.mode_combo.setCurrentIndex(2)
            window._toggle_theme()
            window.grab().save(str(output.with_suffix(".png")))
            result.update(
                ok=True,
                checks=[
                    "resources",
                    "different-size JPEG",
                    "ICC fallback",
                    "background analysis",
                    "guidance",
                    "SQLite save",
                    "learning modes",
                    "light theme",
                    "window render",
                ],
            )
        except Exception as exc:
            result["error"] = str(exc)
        output.write_text(
            json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        window.close()
        app.exit(0 if result["ok"] else 2)

    timer.timeout.connect(poll)
    timer.start()
