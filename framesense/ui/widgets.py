"""自定义控件：直方图与颜色样本。"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QWidget


class HistogramWidget(QWidget):
    """亮度直方图控件。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._values: list[float] = []
        self.setMinimumSize(220, 90)

    def set_histogram(self, values: list[float]) -> None:
        self._values = list(values)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.white)
        if not self._values:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "无数据")
            return
        w = self.width()
        h = self.height()
        max_v = max(self._values) or 1.0
        n = len(self._values)
        bar_w = max(1, w // n)
        for i, v in enumerate(self._values):
            bar_h = int((v / max_v) * (h - 4))
            painter.fillRect(i * bar_w, h - bar_h, bar_w, bar_h, QColor(70, 70, 70))


class ColorSwatchWidget(QWidget):
    """主色样本控件。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._colors: list[dict] = []
        self.setMinimumSize(220, 48)

    def set_colors(self, colors: list[dict]) -> None:
        self._colors = list(colors)
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), Qt.GlobalColor.white)
        if not self._colors:
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "无数据")
            return
        n = len(self._colors)
        w = self.width() // max(1, n)
        for i, c in enumerate(self._colors):
            color = QColor(c.get("hex", "#808080"))
            painter.fillRect(i * w, 4, w - 2, self.height() - 8, color)
            painter.drawText(
                i * w,
                16,
                w,
                16,
                Qt.AlignmentFlag.AlignCenter,
                f"{c.get('ratio', 0) * 100:.0f}%",
            )
