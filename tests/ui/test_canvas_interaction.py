"""Exercise photo-canvas gestures and rendering through Qt's event system."""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtCore import QMimeData, QPoint, QPointF, QRectF, Qt, QUrl
from PySide6.QtGui import QColor, QDragEnterEvent, QDropEvent, QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from framesense.core.regions import Region
from framesense.ui.image_view import ImageView
from framesense.ui.widgets import ColorSwatchWidget, HistogramWidget


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def canvas(qapp):
    view = ImageView()
    view.resize(400, 300)
    view.show()
    qapp.processEvents()
    view.set_image(np.full((200, 400, 3), 80, np.uint8), original_size=(4000, 2000))
    yield view
    view.close()


def drag(view, start, end, modifier=Qt.KeyboardModifier.NoModifier):
    QTest.mousePress(view, Qt.MouseButton.LeftButton, modifier, QPoint(*start))
    QTest.mouseMove(view, QPoint(*end))
    QTest.mouseRelease(view, Qt.MouseButton.LeftButton, modifier, QPoint(*end))


def test_canvas_starts_centered_and_preserves_normalized_view_on_resize(canvas, qapp):
    assert canvas._image_rect() == QRectF(0, 50, 400, 200)
    assert canvas.viewport() == {"zoom": 1.0, "center": (0.5, 0.5)}
    canvas.set_viewport({"zoom": 2, "center": (0.3, 0.7)})
    canvas.resize(700, 350)
    qapp.processEvents()
    assert canvas.viewport()["center"] == pytest.approx((0.3, 0.7))
    assert canvas.viewport()["zoom"] == 2


def test_image_set_before_first_show_keeps_fit_center(qapp):
    view = ImageView()
    view.resize(400, 300)
    view.set_image(np.zeros((200, 400, 3), np.uint8))
    view.show()
    qapp.processEvents()
    assert view.viewport()["center"] == pytest.approx((0.5, 0.5))
    assert view._image_rect() == QRectF(0, 50, 400, 200)
    view.close()


@pytest.mark.parametrize("kind", ["padded", "negative", "transposed"])
def test_strided_numpy_images_keep_correct_pixels(qapp, kind):
    data = np.arange(12 * 18 * 3, dtype=np.uint8).reshape(12, 18, 3)
    rgb = {
        "padded": data[:, ::2, :],
        "negative": data[::-1, :, ::-1],
        "transposed": data.transpose(1, 0, 2),
    }[kind]
    view = ImageView()
    view.set_image(rgb)
    image = view._pixmap.toImage()
    for x, y in ((0, 0), (rgb.shape[1] - 1, rgb.shape[0] - 1), (3, 5)):
        pixel = image.pixelColor(x, y)
        assert (pixel.red(), pixel.green(), pixel.blue()) == tuple(rgb[y, x])
    view.close()


def test_wheel_zoom_keeps_photo_point_under_mouse(canvas, qapp):
    point = QPointF(120, 130)
    before = (point - canvas._offset) / canvas._scale
    changed = []
    canvas.viewport_changed.connect(changed.append)
    wheel = QWheelEvent(
        point,
        point,
        QPoint(),
        QPoint(0, 120),
        Qt.MouseButton.NoButton,
        Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase,
        False,
    )
    qapp.sendEvent(canvas, wheel)
    after = (point - canvas._offset) / canvas._scale
    assert (after.x(), after.y()) == pytest.approx((before.x(), before.y()))
    assert canvas.viewport()["zoom"] == pytest.approx(1.15)
    assert len(changed) == 1


def test_left_drag_pans_and_does_not_select(canvas):
    regions, viewports = [], []
    canvas.region_selected.connect(regions.append)
    canvas.viewport_changed.connect(viewports.append)
    drag(canvas, (200, 150), (250, 180))
    assert canvas.viewport()["center"] == pytest.approx((0.375, 0.35))
    assert viewports
    assert regions == []
    assert canvas._region is None


def test_fit_shortcut_resets_pan_and_zoom(canvas):
    canvas.zoom_in()
    drag(canvas, (200, 150), (250, 180))
    QTest.keyClick(canvas, Qt.Key.Key_F)
    assert canvas.viewport() == {"zoom": 1.0, "center": (0.5, 0.5)}


def test_shift_drag_selects_original_pixels_and_clips_to_photo(canvas):
    regions = []
    canvas.region_selected.connect(regions.append)
    drag(canvas, (100, 100), (450, 330), Qt.KeyboardModifier.ShiftModifier)
    assert regions == [Region(1000, 500, 3000, 1500)]
    assert canvas._region == regions[0]
    assert canvas._rubber.isHidden()


def test_region_mode_selection_persists_and_reselection_replaces(canvas):
    changes, regions = [], []
    canvas.selection_mode_changed.connect(changes.append)
    canvas.region_selected.connect(regions.append)
    QTest.keyClick(canvas, Qt.Key.Key_R)
    drag(canvas, (100, 100), (200, 150))
    assert regions == [Region(1000, 500, 1000, 500)]
    # A real paint includes the persistent region after the rubber band hides.
    pixels = canvas.grab().toImage()
    assert pixels.pixelColor(100, 120) != pixels.pixelColor(90, 120)
    drag(canvas, (200, 150), (300, 200))
    assert canvas._region == Region(2000, 1000, 1000, 500)
    QTest.keyClick(canvas, Qt.Key.Key_V)
    assert changes == [True, False]


def test_keyboard_nudges_resizes_and_clears_region(canvas):
    canvas.set_region(Region(3980, 1980, 20, 20))
    regions = []
    canvas.region_selected.connect(regions.append)
    QTest.keyClick(canvas, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
    assert canvas._region == Region(3980, 1980, 20, 20)
    QTest.keyClick(canvas, Qt.Key.Key_Left, Qt.KeyboardModifier.ShiftModifier)
    assert canvas._region == Region(3970, 1980, 20, 20)
    QTest.keyClick(canvas, Qt.Key.Key_Right, Qt.KeyboardModifier.ControlModifier)
    assert canvas._region == Region(3970, 1980, 21, 20)
    QTest.keyClick(canvas, Qt.Key.Key_Escape)
    assert canvas._region is None
    assert regions[-1] is None


def test_programmatic_regions_and_viewports_are_silent(canvas):
    regions, viewports = [], []
    canvas.region_selected.connect(regions.append)
    canvas.viewport_changed.connect(viewports.append)
    canvas.set_region(Region(-5, -8, 50, 60))
    assert canvas._region == Region(0, 0, 45, 52)
    canvas.set_region(Region(5000, 3000, 5, 5))
    assert canvas._region is None
    canvas.set_viewport({"zoom": 3, "center": (0.2, 0.8)})
    assert canvas.viewport()["center"] == pytest.approx((0.2, 0.8))
    assert regions == viewports == []
    canvas.clear_region()
    assert regions == [None]


def test_bidirectional_sync_across_aspect_ratios_has_no_feedback(canvas, qapp):
    other = ImageView()
    other.resize(250, 400)
    other.show()
    qapp.processEvents()
    other.set_image(np.zeros((400, 200, 3), np.uint8), original_size=(2000, 4000))
    canvas.viewport_changed.connect(other.set_viewport)
    other.viewport_changed.connect(canvas.set_viewport)
    emitted = []
    other.viewport_changed.connect(emitted.append)
    canvas.zoom_in()
    drag(canvas, (200, 150), (250, 180))
    assert other.viewport()["zoom"] == canvas.viewport()["zoom"]
    assert other.viewport()["center"] == pytest.approx(canvas.viewport()["center"])
    assert emitted == []
    other.close()


def test_result_toggle_can_preserve_viewport_and_region(canvas):
    canvas.set_viewport({"zoom": 2, "center": (0.3, 0.7)})
    canvas.set_region(Region(50, 60, 500, 400))
    canvas.set_image(
        np.zeros((100, 200, 3), np.uint8),
        original_size=(4000, 2000),
        preserve_viewport=True,
    )
    assert canvas.viewport()["zoom"] == 2
    assert canvas.viewport()["center"] == pytest.approx((0.3, 0.7))
    assert canvas._region == Region(50, 60, 500, 400)
    canvas.set_image(np.zeros((100, 200, 3), np.uint8))
    assert canvas._region is None
    assert canvas.viewport() == {"zoom": 1.0, "center": (0.5, 0.5)}


def test_drop_imports_local_photo_on_chinese_path_and_rejects_remote(
    canvas, qapp, tmp_path
):
    photo = tmp_path / "参考照片.JPG"
    photo.write_bytes(b"decoder checks contents after import")
    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(photo))])
    received = []
    canvas.file_dropped.connect(received.append)
    enter = QDragEnterEvent(
        QPoint(30, 30),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    qapp.sendEvent(canvas, enter)
    assert enter.isAccepted()
    drop = QDropEvent(
        QPointF(30, 30),
        Qt.DropAction.CopyAction,
        mime,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    qapp.sendEvent(canvas, drop)
    assert drop.isAccepted()
    assert received == [str(photo)]
    remote = QMimeData()
    remote.setUrls([QUrl("https://example.test/photo.jpg")])
    denied = QDragEnterEvent(
        QPoint(30, 30),
        Qt.DropAction.CopyAction,
        remote,
        Qt.MouseButton.LeftButton,
        Qt.KeyboardModifier.NoModifier,
    )
    qapp.sendEvent(canvas, denied)
    assert not denied.isAccepted()


def test_overlay_swipe_and_blend_render_actual_pixels(canvas):
    reference = np.full((80, 160, 3), (220, 40, 20), np.uint8)
    canvas.set_overlay(reference, swipe=0.5)
    rendered = canvas.grab().toImage()
    assert rendered.pixelColor(40, 100).red() == 220
    assert rendered.pixelColor(360, 100).red() == 80
    canvas.set_overlay(reference, opacity=0.5)
    rendered = canvas.grab().toImage()
    assert rendered.pixelColor(40, 100).red() == pytest.approx(150, abs=1)
    canvas.set_overlay(None)
    assert canvas.grab().toImage().pixelColor(40, 100).red() == 80


def test_histogram_256th_bin_is_visible_in_narrow_widget(qapp):
    widget = HistogramWidget()
    widget.resize(140, 90)
    values = [0.0] * 256
    values[-1] = 1.0
    widget.set_histogram(values)
    image = widget.grab().toImage()
    background = QColor("#151b1b")
    # Previously bin 255 started at x=255 and disappeared from a 140px widget.
    assert any(image.pixelColor(139, y) != background for y in range(5, 55))
    comparison = [0.0] * 256
    comparison[0] = 1.0
    widget.set_histogram(values, comparison)
    image = widget.grab().toImage()
    assert any(image.pixelColor(0, y) != background for y in range(5, 55))


def test_swatch_chooses_legible_text(qapp):
    assert ColorSwatchWidget._label_color(QColor("#ffffff")).name() == "#151b1b"
    assert ColorSwatchWidget._label_color(QColor("#101010")).name() == "#ffffff"
