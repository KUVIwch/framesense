"""PySide6 控件冒烟测试（离屏渲染）。"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication

from framesense.core.regions import Region
from framesense.ui.image_view import ImageView
from framesense.ui.widgets import ColorSwatchWidget, HistogramWidget


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    return app


def test_image_view_set_image(qapp):
    view = ImageView()
    rgb = np.zeros((30, 40, 3), dtype=np.uint8)
    rgb[:, :, 0] = 200
    view.set_image(rgb)
    assert view._pixmap is not None
    assert view._pixmap.width() == 40


def test_image_view_to_image_region(qapp):
    view = ImageView()
    region = view._to_image_region(QRect(0, 0, 100, 50))
    assert isinstance(region, Region)
    assert region.width == 100
    assert region.height == 50


def test_histogram_widget_set(qapp):
    widget = HistogramWidget()
    widget.set_histogram([0.1, 0.5, 0.4])
    assert widget._values == [0.1, 0.5, 0.4]


def test_color_swatch_set(qapp):
    widget = ColorSwatchWidget()
    widget.set_colors([{"hex": "#ff0000", "ratio": 0.6}, {"hex": "#00ff00", "ratio": 0.4}])
    assert len(widget._colors) == 2
