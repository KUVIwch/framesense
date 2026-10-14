"""可缩放、可平移、支持矩形区域选择的图像视图。"""
from __future__ import annotations

import numpy as np
from PySide6.QtCore import QPoint, QRect, QSize, Qt, Signal
from PySide6.QtGui import QImage, QPainter, QPixmap
from PySide6.QtWidgets import QRubberBand, QWidget

from framesense.core.regions import Region


class ImageView(QWidget):
    """显示图像，支持滚轮缩放、拖拽平移、橡皮筋矩形区域选择。"""

    region_selected = Signal(object)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: QPixmap | None = None
        self._scale = 1.0
        self._offset = QPoint(0, 0)
        self._rubber = QRubberBand(QRubberBand.Rectangle, self)
        self._origin = QPoint()
        self.setMinimumSize(240, 180)

    def set_image(self, rgb: np.ndarray | None) -> None:
        """设置显示的 sRGB 图像。"""
        if rgb is None or rgb.size == 0:
            self.clear()
            return
        h, w = rgb.shape[:2]
        qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format.Format_RGB888).copy()
        self._pixmap = QPixmap.fromImage(qimg)
        self._scale = 1.0
        self._offset = QPoint(0, 0)
        self.update()

    def clear(self) -> None:
        self._pixmap = None
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        if self._pixmap is None:
            painter.fillRect(self.rect(), Qt.GlobalColor.lightGray)
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "尚未导入图片")
            return
        painter.fillRect(self.rect(), Qt.GlobalColor.darkGray)
        painter.translate(self._offset)
        painter.scale(self._scale, self._scale)
        painter.drawPixmap(0, 0, self._pixmap)

    def wheelEvent(self, event) -> None:  # noqa: N802
        if self._pixmap is None:
            return
        factor = 1.15 if event.angleDelta().y() > 0 else 1.0 / 1.15
        new_scale = max(0.05, min(20.0, self._scale * factor))
        cursor = event.position()
        img_x = (cursor.x() - self._offset.x()) / self._scale
        img_y = (cursor.y() - self._offset.y()) / self._scale
        self._scale = new_scale
        self._offset = QPoint(
            round(cursor.x() - img_x * self._scale),
            round(cursor.y() - img_y * self._scale),
        )
        self.update()

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self._pixmap is not None:
            self._origin = event.position().toPoint()
            self._rubber.setGeometry(QRect(self._origin, QSize()))
            self._rubber.show()

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._rubber.isVisible():
            self._rubber.setGeometry(QRect(self._origin, event.position().toPoint()).normalized())

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if not self._rubber.isVisible():
            return
        rect = self._rubber.geometry()
        self._rubber.hide()
        if rect.width() < 2 or rect.height() < 2:
            self.region_selected.emit(None)
            return
        self.region_selected.emit(self._to_image_region(rect))

    def _to_image_region(self, rect: QRect) -> Region:
        x = (rect.left() - self._offset.x()) / self._scale
        y = (rect.top() - self._offset.y()) / self._scale
        w = rect.width() / self._scale
        h = rect.height() / self._scale
        return Region(int(x), int(y), int(w), int(h))
