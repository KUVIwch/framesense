"""A photo canvas with fit-relative zoom and original-pixel region selection."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PySide6.QtCore import QPointF, QRect, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QRubberBand, QWidget

from framesense.core.regions import Region
from framesense.core.loader import SUPPORTED_EXTENSIONS


class ImageView(QWidget):
    """Display a bounded preview while keeping selections in original pixels.

    ``viewport`` uses a zoom relative to fit and a normalized image coordinate at
    the canvas centre. Applying a viewport is silent, so views can be connected
    in both directions without a signal loop. Left drag pans; R or Shift selects.
    """

    region_selected = Signal(object)
    viewport_changed = Signal(object)
    selection_mode_changed = Signal(bool)
    file_dropped = Signal(str)

    _IMAGE_SUFFIXES = frozenset(SUPPORTED_EXTENSIONS)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._overlay: QPixmap | None = None
        self._overlay_opacity = 0.5
        self._swipe: float | None = None
        self._original_size = (0, 0)
        self._scale = 1.0
        self._zoom = 1.0
        self._offset = QPointF()
        self._canvas_size = (self.width(), self.height())
        self._region: Region | None = None
        self._selection_mode = False
        self._drag_mode: str | None = None
        self._origin = QPointF()
        self._drag_offset = QPointF()
        self._rubber = QRubberBand(QRubberBand.Shape.Rectangle, self)
        self.setMinimumSize(140, 120)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.setAccessibleName("照片画布")
        self.setToolTip(
            "拖动平移 · 滚轮缩放 · Shift 拖动框选 · F 适合窗口 · Esc 清除区域"
        )
        self._update_cursor()

    @staticmethod
    def _to_pixmap(rgb: np.ndarray) -> QPixmap:
        if rgb.ndim != 3 or rgb.shape[2] != 3:
            raise ValueError("预览图必须是 RGB 三通道图像。")
        # Negative, transposed and padded NumPy strides are not a QImage layout.
        data = np.ascontiguousarray(rgb, dtype=np.uint8)
        h, w = data.shape[:2]
        return QPixmap.fromImage(
            QImage(data.data, w, h, data.strides[0], QImage.Format.Format_RGB888).copy()
        )

    def set_image(
        self,
        rgb: np.ndarray | None,
        original_size: tuple[int, int] | None = None,
        preserve_viewport: bool = False,
    ) -> None:
        """Set an sRGB preview; ``original_size`` is the original (width, height)."""
        if rgb is None or rgb.size == 0:
            self.clear()
            return
        previous = (
            self.viewport() if preserve_viewport and self._pixmap is not None else None
        )
        pixmap = self._to_pixmap(rgb)
        w, h = (
            original_size
            if original_size is not None
            else (pixmap.width(), pixmap.height())
        )
        if w <= 0 or h <= 0:
            raise ValueError("原图尺寸必须大于零。")
        self._pixmap = pixmap
        self._original_size = (int(w), int(h))
        self._overlay = None
        self._rubber.hide()
        self._drag_mode = None
        if not preserve_viewport:
            self._region = None
        else:
            self.set_region(self._region)
        self.set_viewport(previous or {"zoom": 1.0, "center": (0.5, 0.5)})
        self._update_cursor()

    def clear(self) -> None:
        self._pixmap = None
        self._overlay = None
        self._region = None
        self._original_size = (0, 0)
        self._zoom = 1.0
        self._scale = 1.0
        self._offset = QPointF()
        self._drag_mode = None
        self._rubber.hide()
        self._update_cursor()
        self.update()

    def _fit_scale(self) -> float:
        w, h = self._original_size
        return min(self.width() / w, self.height() / h) if w and h else 1.0

    def viewport(self) -> dict:
        if self._pixmap is None:
            return {"zoom": 1.0, "center": (0.5, 0.5)}
        w, h = self._original_size
        canvas_w, canvas_h = self._canvas_size
        return {
            "zoom": self._zoom,
            "center": (
                (canvas_w / 2 - self._offset.x()) / (w * self._scale),
                (canvas_h / 2 - self._offset.y()) / (h * self._scale),
            ),
        }

    def set_viewport(self, state: dict) -> None:
        """Restore/synchronize a normalized viewport without emitting a signal."""
        if self._pixmap is None:
            return
        try:
            zoom = float(state.get("zoom", 1.0))
            cx, cy = (float(v) for v in state.get("center", (0.5, 0.5)))
        except (TypeError, ValueError):
            return
        if not all(math.isfinite(v) for v in (zoom, cx, cy)):
            return
        self._zoom = max(0.1, min(32.0, zoom))
        self._scale = self._fit_scale() * self._zoom
        self._canvas_size = (self.width(), self.height())
        w, h = self._original_size
        self._offset = QPointF(
            self.width() / 2 - max(0.0, min(1.0, cx)) * w * self._scale,
            self.height() / 2 - max(0.0, min(1.0, cy)) * h * self._scale,
        )
        self.update()

    def zoom_fit(self) -> None:
        self.set_viewport({"zoom": 1.0, "center": (0.5, 0.5)})
        self._emit_viewport()

    def zoom_in(self) -> None:
        self._zoom_at(1.25, QPointF(self.width() / 2, self.height() / 2))

    def zoom_out(self) -> None:
        self._zoom_at(1 / 1.25, QPointF(self.width() / 2, self.height() / 2))

    def _zoom_at(self, factor: float, anchor: QPointF) -> None:
        if self._pixmap is None:
            return
        image_point = (anchor - self._offset) / self._scale
        self._zoom = max(0.1, min(32.0, self._zoom * factor))
        self._scale = self._fit_scale() * self._zoom
        self._offset = anchor - image_point * self._scale
        self._keep_image_reachable()
        self.update()
        self._emit_viewport()

    def _keep_image_reachable(self) -> None:
        # The centre stays on the photo, even after an oversized drag.
        self.set_viewport(self.viewport())

    def _emit_viewport(self) -> None:
        if self._pixmap is not None:
            self.viewport_changed.emit(self.viewport())

    def set_selection_mode(self, enabled: bool) -> None:
        enabled = bool(enabled)
        if self._selection_mode != enabled:
            self._selection_mode = enabled
            self.selection_mode_changed.emit(enabled)
        self._update_cursor()

    def set_region(self, region: Region | None) -> None:
        """Show a stored original-pixel region; do not trigger analysis."""
        if region is not None and self._pixmap is not None:
            w, h = self._original_size
            x1 = max(0, min(w, int(region.x)))
            y1 = max(0, min(h, int(region.y)))
            x2 = max(x1, min(w, int(region.x + region.width)))
            y2 = max(y1, min(h, int(region.y + region.height)))
            region = Region(x1, y1, x2 - x1, y2 - y1) if x2 > x1 and y2 > y1 else None
        self._region = region if self._pixmap is not None else None
        self.update()

    def clear_region(self) -> None:
        self.set_region(None)
        self.region_selected.emit(None)

    def set_overlay(
        self,
        rgb: np.ndarray | None,
        opacity: float = 0.5,
        swipe: float | None = None,
    ) -> None:
        """Overlay an aligned preview, or show it left of a normalized swipe."""
        self._overlay = self._to_pixmap(rgb) if rgb is not None and rgb.size else None
        self._overlay_opacity = max(0.0, min(1.0, float(opacity)))
        self._swipe = None if swipe is None else max(0.0, min(1.0, float(swipe)))
        self.update()

    def _image_rect(self) -> QRectF:
        w, h = self._original_size
        return QRectF(
            self._offset.x(), self._offset.y(), w * self._scale, h * self._scale
        )

    def _region_rect(self) -> QRectF:
        if self._region is None:
            return QRectF()
        r = self._region
        return QRectF(
            self._offset.x() + r.x * self._scale,
            self._offset.y() + r.y * self._scale,
            r.width * self._scale,
            r.height * self._scale,
        )

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#151b1b"))
        if self._pixmap is None:
            painter.setPen(QColor("#aca99f"))
            painter.drawText(
                self.rect().adjusted(16, 16, -16, -16),
                Qt.AlignmentFlag.AlignCenter,
                "将照片拖到这里\n或点击上方导入",
            )
            return
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        target = self._image_rect()
        painter.drawPixmap(target, self._pixmap, QRectF(self._pixmap.rect()))
        if self._overlay is not None:
            painter.save()
            if self._swipe is None:
                painter.setOpacity(self._overlay_opacity)
            else:
                painter.setClipRect(
                    QRectF(
                        target.x(),
                        target.y(),
                        target.width() * self._swipe,
                        target.height(),
                    )
                )
            painter.drawPixmap(target, self._overlay, QRectF(self._overlay.rect()))
            painter.restore()
            if self._swipe is not None:
                x = target.x() + target.width() * self._swipe
                painter.setPen(QPen(QColor("#e6e0d5"), 1))
                painter.drawLine(QPointF(x, target.top()), QPointF(x, target.bottom()))
        if self._region is not None:
            r = self._region_rect()
            painter.fillRect(r, QColor(199, 137, 97, 25))
            painter.setPen(QPen(QColor("#151b1b"), 3))
            painter.drawRect(r)
            painter.setPen(QPen(QColor("#e4b491"), 1))
            painter.drawRect(r)

    def resizeEvent(self, event) -> None:  # noqa: N802
        if self._pixmap is not None:
            self.set_viewport(self.viewport())
        super().resizeEvent(event)

    def wheelEvent(self, event) -> None:  # noqa: N802
        delta = event.angleDelta().y() or event.pixelDelta().y()
        if self._pixmap is not None and delta:
            self._zoom_at(1.15 ** (delta / 120), event.position())
            event.accept()
        else:
            event.ignore()

    def _update_cursor(self) -> None:
        if self._pixmap is None:
            cursor = Qt.CursorShape.ArrowCursor
        elif self._drag_mode == "pan":
            cursor = Qt.CursorShape.ClosedHandCursor
        elif self._selection_mode:
            cursor = Qt.CursorShape.CrossCursor
        else:
            cursor = Qt.CursorShape.OpenHandCursor
        self.setCursor(cursor)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or self._pixmap is None:
            super().mousePressEvent(event)
            return
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        self._origin = event.position()
        self._drag_offset = QPointF(self._offset)
        selecting = self._selection_mode or bool(
            event.modifiers() & Qt.KeyboardModifier.ShiftModifier
        )
        if selecting:
            if not self._image_rect().contains(self._origin):
                return
            self._drag_mode = "select"
            self._rubber.setGeometry(QRectF(self._origin, self._origin).toAlignedRect())
            self._rubber.show()
        else:
            self._drag_mode = "pan"
        self._update_cursor()
        event.accept()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._drag_mode == "select":
            image = self._image_rect()
            p = event.position()
            endpoint = QPointF(
                max(image.left(), min(image.right(), p.x())),
                max(image.top(), min(image.bottom(), p.y())),
            )
            self._rubber.setGeometry(
                QRectF(self._origin, endpoint).normalized().toAlignedRect()
            )
        elif self._drag_mode == "pan":
            self._offset = self._drag_offset + event.position() - self._origin
            self._keep_image_reachable()
            self.update()
            self._emit_viewport()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() != Qt.MouseButton.LeftButton or self._drag_mode is None:
            super().mouseReleaseEvent(event)
            return
        mode = self._drag_mode
        self._drag_mode = None
        self._update_cursor()
        if mode == "select":
            rect = self._rubber.geometry()
            self._rubber.hide()
            if rect.width() < 3 or rect.height() < 3:
                self.clear_region()
            else:
                self.set_region(self._to_image_region(rect))
                self.region_selected.emit(self._region)
        event.accept()

    def _to_image_region(self, rect: QRect) -> Region:
        """Map canvas bounds through preview scale into clipped original pixels."""
        x1 = math.floor((rect.x() - self._offset.x()) / self._scale)
        y1 = math.floor((rect.y() - self._offset.y()) / self._scale)
        x2 = math.ceil((rect.x() + rect.width() - self._offset.x()) / self._scale)
        y2 = math.ceil((rect.y() + rect.height() - self._offset.y()) / self._scale)
        w, h = self._original_size
        if w and h:
            x1, x2 = max(0, min(w, x1)), max(0, min(w, x2))
            y1, y2 = max(0, min(h, y1)), max(0, min(h, y2))
        return Region(x1, y1, max(0, x2 - x1), max(0, y2 - y1))

    def keyPressEvent(self, event) -> None:  # noqa: N802
        key = event.key()
        if key == Qt.Key.Key_R:
            self.set_selection_mode(True)
        elif key == Qt.Key.Key_V:
            self.set_selection_mode(False)
        elif key == Qt.Key.Key_F:
            self.zoom_fit()
        elif key in (Qt.Key.Key_Plus, Qt.Key.Key_Equal):
            self.zoom_in()
        elif key in (Qt.Key.Key_Minus, Qt.Key.Key_Underscore):
            self.zoom_out()
        elif key == Qt.Key.Key_Escape:
            self._drag_mode = None
            self._rubber.hide()
            self._update_cursor()
            self.clear_region()
        elif self._region is not None and key in (
            Qt.Key.Key_Left,
            Qt.Key.Key_Right,
            Qt.Key.Key_Up,
            Qt.Key.Key_Down,
        ):
            step = 10 if event.modifiers() & Qt.KeyboardModifier.ShiftModifier else 1
            dx = step * ((key == Qt.Key.Key_Right) - (key == Qt.Key.Key_Left))
            dy = step * ((key == Qt.Key.Key_Down) - (key == Qt.Key.Key_Up))
            r = self._region
            w, h = self._original_size
            if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
                region = Region(
                    r.x,
                    r.y,
                    max(1, min(w - r.x, r.width + dx)),
                    max(1, min(h - r.y, r.height + dy)),
                )
            else:
                region = Region(
                    max(0, min(w - r.width, r.x + dx)),
                    max(0, min(h - r.height, r.y + dy)),
                    r.width,
                    r.height,
                )
            self.set_region(region)
            self.region_selected.emit(self._region)
        else:
            super().keyPressEvent(event)
            return
        event.accept()

    def _dropped_file(self, mime) -> str | None:
        if mime.hasUrls():
            for url in mime.urls():
                if url.isLocalFile():
                    path = Path(url.toLocalFile())
                    if path.suffix.lower() in self._IMAGE_SUFFIXES and path.is_file():
                        return str(path)
        return None

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if self._dropped_file(event.mimeData()):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:  # noqa: N802
        path = self._dropped_file(event.mimeData())
        if path:
            event.acceptProposedAction()
            self.file_dropped.emit(path)
        else:
            event.ignore()
