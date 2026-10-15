"""Compact, palette-aware histogram and colour-sample widgets."""

from __future__ import annotations

import math

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


class HistogramWidget(QWidget):
    """Brightness histogram; optional second series shares the same scale."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._values: list[float] = []
        self._comparison: list[float] = []
        self.setMinimumSize(140, 76)
        self.setAccessibleName("亮度分布：铜色为参考，青色为原片")

    @staticmethod
    def _clean(values) -> list[float]:
        return [max(0.0, float(v)) if math.isfinite(float(v)) else 0.0 for v in values]

    def set_histogram(
        self, values: list[float], comparison: list[float] | None = None
    ) -> None:
        self._values = self._clean(values)
        self._comparison = self._clean(comparison) if comparison is not None else []
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#151b1b"))
        painter.setPen(QColor("#b0ada3"))
        if not self._values and not self._comparison:
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "导入照片后显示亮度分布"
            )
            return
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        chart = QRectF(0, 5, self.width(), max(1, self.height() - 21))
        maximum = max([*self._values, *self._comparison, 1e-12])
        # Floating bin positions keep all 256 bins inside narrow sidebars.
        for values, colour in (
            (self._values, "#c78961"),
            (self._comparison, "#6f9990"),
        ):
            if not values:
                continue
            path = QPainterPath(QPointF(chart.left(), chart.bottom()))
            n = len(values)
            for i, value in enumerate(values):
                x = chart.left() + (i + 0.5) * chart.width() / n
                y = chart.bottom() - value / maximum * chart.height()
                path.lineTo(x, y)
            path.lineTo(chart.right(), chart.bottom())
            path.closeSubpath()
            fill = QColor(colour)
            fill.setAlpha(76 if self._comparison else 110)
            painter.fillPath(path, fill)
            painter.setPen(QPen(QColor(colour), 1))
            painter.drawPath(path)
        painter.setPen(QColor("#8d948e"))
        painter.drawText(
            QRectF(3, self.height() - 16, 50, 15), Qt.AlignmentFlag.AlignLeft, "暗部"
        )
        painter.drawText(
            QRectF(self.width() - 53, self.height() - 16, 50, 15),
            Qt.AlignmentFlag.AlignRight,
            "亮部",
        )


class ColorSwatchWidget(QWidget):
    """Dominant colours with contrast-tested percentage labels."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._colors: list[dict] = []
        self.setMinimumSize(140, 44)
        self.setAccessibleName("照片主要颜色及占比")

    def set_colors(self, colors: list[dict]) -> None:
        self._colors = list(colors)
        self.setToolTip(
            " · ".join(
                f"{c.get('hex', '#808080')}  {c.get('ratio', 0) * 100:.0f}%"
                for c in colors
            )
        )
        self.update()

    @staticmethod
    def _label_color(color: QColor) -> QColor:
        channels = [color.redF(), color.greenF(), color.blueF()]
        linear = [
            v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
            for v in channels
        ]
        luma = sum(
            v * coefficient for v, coefficient in zip(linear, (0.2126, 0.7152, 0.0722))
        )
        return QColor("#151b1b") if luma > 0.179 else QColor("#ffffff")

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor("#151b1b"))
        if not self._colors:
            painter.setPen(QColor("#b0ada3"))
            painter.drawText(
                self.rect(), Qt.AlignmentFlag.AlignCenter, "导入照片后显示主要颜色"
            )
            return
        n = len(self._colors)
        for i, sample in enumerate(self._colors):
            left, right = i * self.width() / n, (i + 1) * self.width() / n
            area = QRectF(
                left, 3, right - left - (2 if i < n - 1 else 0), self.height() - 6
            )
            color = QColor(sample.get("hex", "#808080"))
            if not color.isValid():
                color = QColor("#808080")
            painter.fillRect(area, color)
            painter.setPen(self._label_color(color))
            label = f"{sample.get('ratio', 0) * 100:.0f}%"
            if painter.fontMetrics().horizontalAdvance(label) + 4 <= area.width():
                painter.drawText(area, Qt.AlignmentFlag.AlignCenter, label)
