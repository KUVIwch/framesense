"""Rebuild FrameSense's original vector marks and raster exports.

Run from the project virtual environment. Only the existing QtSvg and Pillow
dependencies are used; no network, font download, or graphics editor is needed.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image
from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "framesense" / "assets"
PREVIEW = ROOT / "outputs" / "product-preview"
SIZES = (16, 32, 64, 256, 512)


def svg(
    content: str, *, width: int = 128, height: int = 128, viewbox: str = "0 0 128 128"
) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
        f'height="{height}" viewBox="{viewbox}" role="img" '
        f'aria-label="FrameSense">{content}</svg>\n'
    )


def mark(concept: int = 1, *, light: bool = False) -> str:
    paper, ink = ("#e6e0d5", "#26342f") if light else ("#151b1b", "#e6e0d5")
    tile = f'<rect width="128" height="128" rx="23" fill="{paper}"/>'
    if concept == 1:
        # Four open corners keep the frame legible at 16 px. Three solid colour
        # cuts form the observation subject; no tiny lens detail is required.
        corners = (
            f'<path d="M28 47V28h19 M81 28h19v19 '
            f'M100 81v19H81 M47 100H28V81" fill="none" '
            f'stroke="{ink}" stroke-width="7" stroke-linecap="square"/>'
        )
        slices = (
            '<path d="M40 49l13-8v42l-13 8z" fill="#6f9990"/>'
            '<path d="M57 44l14-8v47l-14 8z" fill="#c78961"/>'
            f'<path d="M75 44l13-8v39l-13 8z" fill="{ink}"/>'
        )
        return svg(tile + corners + slices)
    if concept == 2:
        # Two contact-print windows: colour is observed by juxtaposition.
        windows = (
            f'<rect x="25" y="29" width="78" height="70" rx="3" '
            f'fill="none" stroke="{ink}" stroke-width="6"/>'
            '<path d="M35 39h23v50H35z" fill="#6f9990"/>'
            '<path d="M70 39h23v50H70z" fill="#c78961"/>'
            f'<path d="M61 38h6v52h-6z" fill="{ink}"/>'
        )
        return svg(tile + windows)
    # Offset focus: a quiet aperture-like study, without a camera silhouette.
    focus = (
        f'<circle cx="64" cy="64" r="35" fill="none" stroke="{ink}" '
        'stroke-width="7"/>'
        '<path d="M64 29a35 35 0 0 1 35 35H64z" fill="#6f9990"/>'
        '<path d="M64 64h35a35 35 0 0 1-35 35z" fill="#c78961"/>'
        f'<path d="M29 64h35v35a35 35 0 0 1-35-35z" fill="{ink}"/>'
        f'<circle cx="64" cy="64" r="9" fill="{paper}"/>'
    )
    return svg(tile + focus)


def wordmark(*, light: bool = False) -> str:
    ink = "#26342f" if light else "#e6e0d5"
    # Text remains live vector text, using system fonts, with no font embedded.
    inner = (
        mark(light=light).split('aria-label="FrameSense">', 1)[1].rsplit("</svg>", 1)[0]
    )
    return svg(
        f'<g transform="scale(.5)">{inner}</g>'
        f'<text x="79" y="31" fill="{ink}" font-family="Segoe UI,Arial,sans-serif" '
        'font-size="27" font-weight="600" letter-spacing="-.6">FrameSense</text>'
        f'<text x="80" y="51" fill="{ink}" font-family="Segoe UI,Arial,sans-serif" '
        'font-size="10" letter-spacing="2.2">COLOR LAB</text>',
        width=290,
        height=64,
        viewbox="0 0 290 64",
    )


def render(source: str, width: int, height: int | None = None) -> QImage:
    renderer = QSvgRenderer(QByteArray(source.encode("utf-8")))
    if not renderer.isValid():
        raise ValueError("Invalid brand SVG")
    result = QImage(width, height or width, QImage.Format.Format_ARGB32_Premultiplied)
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter, QRectF(0, 0, result.width(), result.height()))
    painter.end()
    return result


def contact_sheet() -> None:
    # Native-size marks are deliberately kept unscaled so this is a real
    # 16/32/64/256-pixel legibility study, not a zoomed-up approximation.
    sheet = QImage(1160, 1160, QImage.Format.Format_RGB32)
    painter = QPainter(sheet)
    families = QFontDatabase.families()
    family = "Microsoft YaHei UI" if "Microsoft YaHei UI" in families else "Segoe UI"
    for row, light in enumerate((False, True)):
        background, text = ("#e6e0d5", "#26342f") if light else ("#151b1b", "#e6e0d5")
        top = row * 580
        painter.fillRect(0, top, 1160, 580, QColor(background))
        painter.setPen(QColor(text))
        painter.setFont(QFont(family, 17, QFont.Weight.DemiBold))
        painter.drawText(
            32, top + 38, "FrameSense  /  01 色彩取景 · 02 接触印样 · 03 观察焦点"
        )
        painter.setFont(QFont(family, 10))
        painter.drawText(
            32,
            top + 63,
            "最终选择 01。每列以 16 / 32 / 64 / 256 实际像素呈现；下方为应用内标识。",
        )
        for col in range(3):
            left = 32 + col * 380
            source = mark(col + 1, light=light)
            painter.drawText(
                left,
                top + 92,
                f"0{col + 1}" + ("  SELECTED" if col == 0 else "  STUDY"),
            )
            x = left
            for size in (16, 32, 64):
                painter.drawImage(x, top + 112 + (64 - size) // 2, render(source, size))
                painter.drawText(x, top + 198, str(size))
                x += size + 30
            painter.drawImage(left, top + 216, render(source, 256))
            painter.drawText(left + 271, top + 349, "256")
        painter.drawImage(32, top + 500, render(wordmark(light=light), 290, 64))
    painter.end()
    if not sheet.save(str(PREVIEW / "icon-study.png")):
        raise OSError("Could not save icon contact sheet")


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    # Windows' headless Qt platform does not enumerate installed fonts. Use
    # existing local OS fonts for this renderer only, never copy/package them.
    if not QFontDatabase.families() and sys.platform == "win32":
        system_fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for filename in ("segoeui.ttf", "seguisb.ttf", "msyh.ttc"):
            if (system_fonts / filename).is_file():
                QFontDatabase.addApplicationFont(str(system_fonts / filename))
    ASSETS.mkdir(parents=True, exist_ok=True)
    (ASSETS / "concepts").mkdir(exist_ok=True)
    PREVIEW.mkdir(parents=True, exist_ok=True)
    for concept in (1, 2, 3):
        (ASSETS / "concepts" / f"concept-{concept:02d}.svg").write_text(
            mark(concept), encoding="utf-8"
        )
    for name, source in (
        ("framesense.svg", mark()),
        ("framesense-light.svg", mark(light=True)),
        ("brand-dark.svg", wordmark()),
        ("brand-light.svg", wordmark(light=True)),
        ("readme-wordmark-dark.svg", wordmark()),
        ("readme-wordmark-light.svg", wordmark(light=True)),
    ):
        (ASSETS / name).write_text(source, encoding="utf-8")
    for size in SIZES:
        if not render(mark(), size).save(str(ASSETS / f"framesense-{size}.png")):
            raise OSError(f"Failed to export {size}px brand mark")
    with Image.open(ASSETS / "framesense-512.png") as master:
        master.save(
            ASSETS / "framesense.ico",
            format="ICO",
            sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)],
        )
    contact_sheet()
    print(f"Original vectors, five PNG sizes, seven-frame ICO: {ASSETS}")
    print(f"Native-size dark/light contact sheet: {PREVIEW / 'icon-study.png'}")
    del app


if __name__ == "__main__":
    main()
