"""Render actual Qt workbench states with synthetic fixtures, never private photos."""

import os, sys, time, json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase
from framesense.ui.theme import apply_theme
from framesense.ui.main_window import MainWindow

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs" / "product-preview"
OUT.mkdir(parents=True, exist_ok=True)
FIX = ROOT / "work" / "visual-fixtures"
FIX.mkdir(parents=True, exist_ok=True)


def specimen(path, w, h, warm):
    yy, xx = np.mgrid[:h, :w]
    light = np.clip(0.86 - 0.30 * xx / w + 0.12 * yy / h, 0, 1)
    base = np.array([190, 181, 157] if warm else [153, 174, 184])
    rgb = (light[..., None] * base).astype(np.uint8)
    im = Image.fromarray(rgb)
    d = ImageDraw.Draw(im)

    def box(v):
        return tuple(round(c * (w if i % 2 == 0 else h)) for i, c in enumerate(v))

    d.rectangle(box((0.07, 0, 0.32, 0.68)), fill=("#a5c4bc" if warm else "#9fb4cb"))
    d.rectangle(box((0.08, 0.05, 0.30, 0.65)), fill=("#c7d6c3" if warm else "#b5cbd5"))
    d.line(box((0.195, 0.05, 0.195, 0.65)), fill="#718b81", width=max(2, w // 250))
    d.rectangle(box((0, 0.7, 1, 1)), fill=("#6a6550" if warm else "#727c80"))
    d.ellipse(box((0.36, 0.79, 0.79, 0.87)), fill="#414a41")
    d.polygon(
        [box((0.48, 0.51)), box((0.65, 0.51)), box((0.70, 0.82)), box((0.43, 0.82))],
        fill=("#c7926a" if warm else "#d7b690"),
    )
    d.ellipse(box((0.48, 0.48, 0.65, 0.56)), fill="#785c43")
    for k in range(6):
        x = 0.56 + (0.025 if k % 2 else -0.025) * k
        y = 0.5 - 0.055 * k
        d.line(box((0.56, 0.53, x, y)), fill="#506c55", width=max(3, w // 160))
        d.ellipse(
            box((x - 0.055, y - 0.025, x + 0.045, y + 0.01)),
            fill=("#6b8269" if warm else "#687d75"),
        )
    d.rectangle(box((0.76, 0.75, 0.88, 0.82)), fill="#b6ada0")
    im = im.filter(ImageFilter.GaussianBlur(0.35))
    im.save(path, quality=93)


def wait(app, window):
    deadline = time.monotonic() + 30
    while (window.jobs.busy or window.jobs._jobs) and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    for _ in range(3):
        app.processEvents()
    if window.jobs.busy:
        raise RuntimeError("Background render timeout")


app = QApplication([])
for font in ("msyh.ttc", "segoeui.ttf"):
    p = Path("C:/Windows/Fonts") / font
    if p.exists():
        QFontDatabase.addApplicationFont(str(p))
apply_theme(app)
w = MainWindow(db_path=FIX / "sessions.db", draft_path=FIX / "draft.json")
w.show()
app.processEvents()
w.grab().save(str(OUT / "workbench-empty.png"))
specimen(FIX / "参考-合成测试.jpg", 1800, 1200, True)
specimen(FIX / "原片-合成测试.jpg", 1600, 1100, False)
specimen(FIX / "调后-合成测试.jpg", 1600, 1100, True)
w.title_edit.setText("窗边静物 / 一次色彩练习")
w.goal_edit.setText("观察冷暖关系，保留花器的颜色")
w.load_path("ref", str(FIX / "参考-合成测试.jpg"))
w.load_path("src", str(FIX / "原片-合成测试.jpg"))
wait(app, w)
w.tabs.setCurrentIndex(0)
app.processEvents()
w.grab().save(str(OUT / "workbench-dark.png"))
w.tabs.setCurrentIndex(1)
app.processEvents()
w.grab().save(str(OUT / "workbench-guidance.png"))
w.mode_combo.setCurrentIndex(1)
app.processEvents()
w.grab().save(str(OUT / "workbench-practice.png"))
w._toggle_theme()
w.tabs.setCurrentIndex(0)
app.processEvents()
w.grab().save(str(OUT / "workbench-light.png"))
w.resize(1024, 720)
app.processEvents()
w.grab().save(str(OUT / "workbench-1024.png"))
w.resize(1440, 900)
w._toggle_theme()
w.load_path("final", str(FIX / "调后-合成测试.jpg"))
wait(app, w)
w.tabs.setCurrentIndex(0)
app.processEvents()
w.grab().save(str(OUT / "workbench-review.png"))
w.close()
app.processEvents()
print(
    "Rendered empty/dark/light/guidance/practice/1024/review states with synthetic images."
)
