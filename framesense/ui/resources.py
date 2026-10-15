"""Resolve bundled brand assets without relying on the current directory."""

from __future__ import annotations

from pathlib import Path
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer


def asset_path(name: str) -> Path:
    """Return a package asset path, including PyInstaller's onedir layout.

    Names are relative to assets; path traversal is rejected. The path is still
    returned when absent, allowing callers to show a blank optional decoration.
    """
    relative = Path(name)
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("Asset names must stay inside framesense/assets")
    package_root = Path(__file__).resolve().parents[1]
    frozen_root = getattr(sys, "_MEIPASS", None)
    roots = [Path(frozen_root) / "framesense" / "assets"] if frozen_root else []
    roots.append(package_root / "assets")
    for root in roots:
        candidate = root / relative
        if candidate.is_file():
            return candidate
    return roots[0] / relative


def app_icon() -> QIcon:
    """Use native raster sizes for taskbars; retain a scalable SVG fallback."""
    result = QIcon()
    for size in (16, 32, 64, 256, 512):
        path = asset_path(f"framesense-{size}.png")
        if path.exists():
            result.addFile(str(path))
    if result.isNull():
        result.addFile(str(asset_path("framesense.svg")))
    return result


def brand_pixmap(width: int = 170, light: bool = False) -> QPixmap:
    """Return the horizontal mark for a dark or light application surface.

    Render at twice logical width and tag its device-pixel ratio so the brand
    stays sharp on normal and high-density screens without loading a font file.
    """
    width = max(1, int(width))
    path = asset_path("brand-light.svg" if light else "brand-dark.svg")
    renderer = QSvgRenderer(str(path))
    if not renderer.isValid():
        return QPixmap()
    logical_size = renderer.defaultSize()
    result = QPixmap(
        width * 2,
        max(1, round(width * 2 * logical_size.height() / logical_size.width())),
    )
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    renderer.render(painter)
    painter.end()
    result.setDevicePixelRatio(2.0)
    return result
