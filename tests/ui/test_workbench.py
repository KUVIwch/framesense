"""Offline end-to-end workbench regression using generated photos and private paths."""

from __future__ import annotations

import os
import socket
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PIL import Image, ImageDraw
from PySide6.QtCore import QPoint, Qt, QUrl
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

from framesense.core.regions import Region
from framesense.core.service import AnalysisService
from framesense.learning.session import get_session
from framesense.ui.main_window import MainWindow
from framesense.ui.theme import apply_theme


def spin(app, predicate, timeout=10):
    """Pump queued deliveries and yield the GIL briefly to Python workers."""
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        app.processEvents()
        # PySide's qWait can retain the GIL; give QRunnable Python code time too.
        time.sleep(0.005)
    assert predicate(), "Workbench did not reach the expected state before the deadline"


@pytest.fixture(scope="module")
def qapp():
    return QApplication.instance() or QApplication([])


@pytest.fixture
def photos(tmp_path):
    result = {}
    for role, size, color in (
        ("ref", (96, 64), (205, 175, 120)),
        ("src", (640, 480), (45, 80, 110)),
        ("final", (2400, 1600), (160, 145, 115)),
    ):
        path = tmp_path / f"{role}-中文练习照片.jpg"
        image = Image.new("RGB", size, color)
        draw = ImageDraw.Draw(image)
        draw.rectangle(
            (0, 0, size[0] // 3, size[1] - 1), fill=tuple(max(0, c - 30) for c in color)
        )
        image.save(path, quality=90)
        result[role] = path
    return result


class GatedService(AnalysisService):
    """Delay selected real operations so cancellation/replacement races repeat."""

    def __init__(self):
        super().__init__(analysis_max_side=128, preview_max_side=240)
        self.load_gates = {}
        self.load_started = {}
        self.compare_gate = None
        self.compare_started = threading.Event()

    def gate_load(self, path):
        self.load_gates[str(path)] = threading.Event()
        self.load_started[str(path)] = threading.Event()
        return self.load_gates[str(path)], self.load_started[str(path)]

    def load(self, path):
        key = str(path)
        if key in self.load_gates:
            self.load_started[key].set()
            self.load_gates[key].wait(6)
        return super().load(path)

    def compare(self, reference, source):
        if self.compare_gate is not None:
            self.compare_started.set()
            self.compare_gate.wait(6)
        return super().compare(reference, source)

    def release_all(self):
        for gate in self.load_gates.values():
            gate.set()
        if self.compare_gate is not None:
            self.compare_gate.set()


@pytest.fixture
def workbench(qapp, tmp_path):
    windows = []

    def factory(service=None, db_path=None, draft_path=None):
        index = len(windows)
        apply_theme(qapp, "dark")
        window = MainWindow(
            service=service
            or AnalysisService(analysis_max_side=128, preview_max_side=240),
            db_path=db_path or tmp_path / f"sessions-{index}.db",
            draft_path=draft_path or tmp_path / f"draft-{index}.json",
        )
        window.show()
        qapp.processEvents()
        windows.append(window)
        return window

    yield factory
    for window in windows:
        if hasattr(window.service, "release_all"):
            window.service.release_all()
        window.jobs.cancel()
    for window in windows:
        spin(qapp, lambda w=window: not w.jobs._jobs)
        window.close()
    qapp.processEvents()
    apply_theme(qapp, "dark")


def load_pair(app, window, photos):
    window.load_path("ref", str(photos["ref"]))
    window.load_path("src", str(photos["src"]))
    spin(
        app,
        lambda: window._ref is not None
        and window._src is not None
        and window._guidance is not None
        and not window.jobs.busy,
    )


def select_regions(window):
    reference, source = Region(10, 8, 55, 40), Region(60, 55, 350, 270)
    window.ref_view.set_region(reference)
    window.ref_view.region_selected.emit(reference)
    window.src_view.set_region(source)
    window.src_view.region_selected.emit(source)
    return reference, source


def fill_complete_practice(app, window, photos):
    load_pair(app, window, photos)
    window.title_edit.setText("阴影与暖色练习")
    window.goal_edit.setText("降低冷感，保留明暗层次")
    window.notes_edit.setPlainText("先观察影调，再处理颜色。\n第二次尝试保留原有暗部。")
    regions = select_regions(window)
    window.load_path("final", str(photos["final"]))
    spin(
        app,
        lambda: window._final is not None
        and not window.jobs.busy
        and bool(window._analysis_json.get("final_comparison"))
        and bool(window._analysis_json.get("region_diffs")),
    )
    window.mode_combo.setCurrentIndex(1)
    window._hint_clicked(QUrl("hint:0"))
    return regions


def test_async_import_chinese_photos_keeps_original_dimensions_and_bounded_previews(
    qapp, workbench, photos
):
    window = workbench()
    load_pair(qapp, window, photos)
    assert (window._ref.width, window._ref.height) == (96, 64)
    assert (window._src.width, window._src.height) == (640, 480)
    assert max(window._src.preview_rgb.shape[:2]) <= 240
    assert window.src_view._original_size == (640, 480)
    window.load_path("final", str(photos["final"]))
    spin(qapp, lambda: window._final is not None and not window.jobs.busy)
    assert (window._final.width, window._final.height) == (2400, 1600)
    assert max(window._final.preview_rgb.shape[:2]) <= 240
    assert window.display_combo.currentIndex() == 1
    assert window.src_view._original_size == (2400, 1600)


def test_modes_preserve_notes_regions_and_practice_hints_can_expand(
    qapp, workbench, photos
):
    window = workbench()
    load_pair(qapp, window, photos)
    window.notes_edit.setPlainText("我判断原片的阴影更冷。")
    regions = select_regions(window)
    spin(qapp, lambda: not window.jobs.busy)
    assert window._guidance.steps
    window.mode_combo.setCurrentIndex(1)
    assert "hint:0" in window.guidance_text.toHtml()
    window._hint_clicked(QUrl("hint:0"))
    assert 0 in window._hint_steps
    assert "hint:0" not in window.guidance_text.toHtml()
    assert window._guidance.steps[0].action in window.guidance_text.toPlainText()
    for mode in (2, 0, 1):
        window.mode_combo.setCurrentIndex(mode)
        window.tabs.setCurrentIndex(2)
        window.tabs.setCurrentIndex(1)
        assert window.notes_edit.toPlainText() == "我判断原片的阴影更冷。"
        assert (window._ref_region, window._src_region) == regions
        assert (window.ref_view._region, window.src_view._region) == regions
    assert 0 in window._hint_steps


def test_save_full_practice_and_restore_from_history(qapp, workbench, photos, tmp_path):
    database = tmp_path / "完整练习.db"
    window = workbench(db_path=database)
    regions = fill_complete_practice(qapp, window, photos)
    window._save_session()
    assert window._session_id is not None
    saved = get_session(window._session_id, database)
    assert saved.final_path == str(photos["final"])
    assert saved.guidance_json["steps"]
    assert saved.analysis_json["final_comparison"]
    assert saved.analysis_json["practice"]["goal"] == window.goal_edit.text()
    restored = workbench(db_path=database)
    restored.tabs.setCurrentIndex(3)
    spin(qapp, lambda: restored.history_list.count() == 1 and not restored.jobs.busy)
    restored.history_list.setCurrentRow(0)
    restored._open_history()
    spin(qapp, lambda: restored._final is not None and not restored.jobs.busy)
    assert restored._session_id == saved.id
    assert restored.title_edit.text() == window.title_edit.text()
    assert restored.notes_edit.toPlainText() == window.notes_edit.toPlainText()
    assert restored.goal_edit.text() == window.goal_edit.text()
    assert (restored._ref_region, restored._src_region) == regions
    assert (
        restored.display_combo.currentIndex()
        == window.display_combo.currentIndex()
        == 1
    )
    assert (
        restored.src_view._region is None
    )  # Source ROI does not belong to the final photo.
    restored.display_combo.setCurrentIndex(0)
    assert (restored.ref_view._region, restored.src_view._region) == regions
    # Restore remeasures the bytes; the report timestamp is intentionally new.
    assert restored._guidance.model_dump(
        exclude={"generated_at"}
    ) == window._guidance.model_dump(exclude={"generated_at"})
    assert (
        restored._analysis_json["final_comparison"]
        == saved.analysis_json["final_comparison"]
    )
    assert restored.mode_combo.currentIndex() == 1
    assert restored._hint_steps == {0}


def test_cancel_import_keeps_current_photo_and_does_not_block_ui(
    qapp, workbench, photos
):
    service = GatedService()
    window = workbench(service=service)
    window.load_path("ref", str(photos["ref"]))
    spin(qapp, lambda: window._ref is not None and not window.jobs.busy)
    gate, started = service.gate_load(photos["final"])
    window.load_path("ref", str(photos["final"]))
    spin(qapp, started.is_set)
    window._cancel()
    window.title_edit.setText("取消过程中仍能输入")
    assert window.title_edit.text() == "取消过程中仍能输入"
    assert window._ref.source_path == str(photos["ref"])
    gate.set()
    spin(qapp, lambda: not window.jobs._jobs)
    assert window._ref.source_path == str(photos["ref"])


def test_quick_replace_does_not_publish_stale_import(qapp, workbench, photos):
    service = GatedService()
    gate, started = service.gate_load(photos["ref"])
    window = workbench(service=service)
    window.load_path("ref", str(photos["ref"]))
    spin(qapp, started.is_set)
    window.load_path("ref", str(photos["final"]))
    spin(
        qapp,
        lambda: window._ref is not None
        and window._ref.source_path == str(photos["final"]),
    )
    gate.set()
    spin(qapp, lambda: not window.jobs._jobs)
    assert window._ref.source_path == str(photos["final"])


def test_cancelled_analysis_does_not_replace_guidance(qapp, workbench, photos):
    service = GatedService()
    window = workbench(service=service)
    load_pair(qapp, window, photos)
    old_guidance = window._guidance
    service.compare_gate = threading.Event()
    window._analyze()
    spin(qapp, service.compare_started.is_set)
    window._cancel()
    service.compare_gate.set()
    spin(qapp, lambda: not window.jobs._jobs)
    assert window._guidance is old_guidance
    assert not window.cancel_btn.isEnabled()


@pytest.mark.parametrize("size", [(1024, 700), (1280, 800), (1600, 1000)])
def test_window_size_keeps_photo_panes_and_controls_inside_work_area(
    qapp, workbench, size
):
    window = workbench()
    window.resize(*size)
    qapp.processEvents()
    assert window.size().width() == size[0]
    assert window.size().height() == size[1]
    splitter = window.splitter
    panes = [splitter.widget(i) for i in range(3)]
    for i, pane in enumerate(panes):
        assert pane.geometry().width() > 0
        assert splitter.rect().contains(pane.geometry())
        if i:
            assert panes[i - 1].geometry().right() < pane.geometry().left()
    for view in (window.ref_view, window.src_view):
        assert view.width() >= 140 and view.height() >= 120
        assert view.parentWidget().rect().contains(view.geometry())
    assert (
        window.centralWidget()
        .rect()
        .contains(window.select_check.mapTo(window.centralWidget(), QPoint(0, 0)))
    )
    assert (
        window.select_check.geometry().right()
        < window.sync_check.parentWidget().width()
    )


def test_offline_analysis_and_both_themes_use_same_measurements(
    qapp, workbench, photos, monkeypatch
):
    def denied(*args, **kwargs):
        raise AssertionError("Core practice attempted a network request")

    monkeypatch.setattr(socket, "create_connection", denied)
    monkeypatch.setattr(socket.socket, "connect", denied)
    window = workbench()
    load_pair(qapp, window, photos)
    baseline = dict(window._analysis_json["comparison"])
    for expected in ("light", "dark"):
        window._toggle_theme()
        assert qapp.property("frameSenseTheme") == expected
        window._analyze()
        spin(qapp, lambda: not window.jobs.busy)
        assert window._analysis_json["comparison"] == baseline
        assert window._guidance is not None


def test_draft_survives_close_and_restores_complete_practice(
    qapp, workbench, photos, tmp_path
):
    draft = tmp_path / "重启草稿.json"
    window = workbench(draft_path=draft)
    regions = fill_complete_practice(qapp, window, photos)
    window.close()
    assert draft.is_file()
    restarted = workbench(draft_path=draft)
    assert restarted.restore_btn.isVisible()
    QTest.mouseClick(restarted.restore_btn, Qt.MouseButton.LeftButton)
    spin(qapp, lambda: restarted._final is not None and not restarted.jobs.busy)
    assert restarted.title_edit.text() == "阴影与暖色练习"
    assert restarted.goal_edit.text() == "降低冷感，保留明暗层次"
    assert "第二次尝试" in restarted.notes_edit.toPlainText()
    assert (restarted._ref_region, restarted._src_region) == regions
    assert restarted._hint_steps == {0}
    assert restarted._analysis_json["final_comparison"]
    assert not restarted.restore_btn.isVisible()


def test_keyboard_selection_mode_updates_workbench_checkbox(qapp, workbench, photos):
    window = workbench()
    load_pair(qapp, window, photos)
    QTest.keyClick(window.ref_view, Qt.Key.Key_R)
    assert window.select_check.isChecked()
    assert window.src_view._selection_mode
    QTest.keyClick(window.src_view, Qt.Key.Key_V)
    assert not window.select_check.isChecked()
    assert not window.ref_view._selection_mode


def test_region_clear_recomputes_and_undo_restores_previous_samples(
    qapp, workbench, photos
):
    window = workbench()
    load_pair(qapp, window, photos)
    regions = select_regions(window)
    spin(qapp, lambda: not window.jobs.busy)
    assert window._analysis_json["region_diffs"]
    window.ref_view.clear_region()
    spin(qapp, lambda: not window.jobs.busy)
    assert window._ref_region is None
    assert window._analysis_json["region_diffs"] == []
    window.activateWindow()
    window.ref_view.setFocus()
    qapp.processEvents()
    QTest.keyClick(
        window.ref_view, Qt.Key.Key_Backspace, Qt.KeyboardModifier.AltModifier
    )
    spin(qapp, lambda: not window.jobs.busy)
    assert (window._ref_region, window._src_region) == regions
    assert window._analysis_json["region_diffs"]


def test_corrupt_image_reports_error_and_keeps_current_photo(
    qapp, workbench, photos, tmp_path
):
    window = workbench()
    load_pair(qapp, window, photos)
    damaged = tmp_path / "损坏图片.png"
    damaged.write_bytes(b"not a PNG")
    previous = window._ref
    window.load_path("ref", str(damaged))
    spin(qapp, lambda: not window.jobs.busy)
    assert window._ref is previous
    assert "未完成" in window.statusBar().currentMessage()
    assert window._src is not None


def test_restore_cannot_overwrite_a_new_import(qapp, workbench, photos):
    service = GatedService()
    window = workbench(service=service)
    load_pair(qapp, window, photos)
    previous = window._snapshot()
    previous["title"] = "旧练习应被取消"
    gate, started = service.gate_load(photos["ref"])
    window.restore_payload(previous)
    spin(qapp, started.is_set)
    window.load_path("ref", str(photos["final"]))
    spin(qapp, lambda: window._ref.source_path == str(photos["final"]))
    gate.set()
    spin(qapp, lambda: not window.jobs._jobs)
    assert window._ref.source_path == str(photos["final"])
    assert window.title_edit.text() != "旧练习应被取消"


def test_old_final_import_cannot_attach_to_a_replaced_source(qapp, workbench, photos):
    service = GatedService()
    window = workbench(service=service)
    load_pair(qapp, window, photos)
    gate, started = service.gate_load(photos["final"])
    window.load_path("final", str(photos["final"]))
    spin(qapp, started.is_set)
    window.load_path("src", str(photos["ref"]))
    spin(qapp, lambda: window._src.source_path == str(photos["ref"]))
    gate.set()
    spin(qapp, lambda: not window.jobs._jobs)
    assert window._src.source_path == str(photos["ref"])
    assert window._final is None
    assert window.display_combo.currentIndex() == 0


def test_draft_restores_theme_viewports_overlay_and_observation_filter(
    qapp, workbench, photos, tmp_path
):
    draft = tmp_path / "视图草稿.json"
    window = workbench(draft_path=draft)
    fill_complete_practice(qapp, window, photos)
    window.display_combo.setCurrentIndex(2)
    window.sync_check.setChecked(False)
    window.ref_view.set_viewport({"zoom": 2.5, "center": (0.3, 0.6)})
    window.src_view.set_viewport({"zoom": 1.8, "center": (0.65, 0.4)})
    window.focus_combo.setCurrentIndex(2)
    window._toggle_theme()
    window.close()
    restarted = workbench(draft_path=draft)
    restarted._restore_draft()
    spin(qapp, lambda: restarted._guidance is not None and not restarted.jobs.busy)
    assert restarted._theme == "light"
    assert qapp.property("frameSenseTheme") == "light"
    assert restarted.display_combo.currentIndex() == 2
    assert restarted.src_view._overlay is not None
    assert not restarted.sync_check.isChecked()
    assert restarted.focus_combo.currentIndex() == 2
    for view, expected in (
        (restarted.ref_view, (2.5, (0.3, 0.6))),
        (restarted.src_view, (1.8, (0.65, 0.4))),
    ):
        assert view.viewport()["zoom"] == pytest.approx(expected[0])
        assert view.viewport()["center"] == pytest.approx(expected[1])


def test_only_goal_is_enough_to_keep_a_draft(qapp, workbench, tmp_path):
    draft = tmp_path / "只有目标.json"
    window = workbench(draft_path=draft)
    window.goal_edit.setText("下一次想观察阴影中的颜色")
    window.close()
    assert draft.is_file()
    restarted = workbench(draft_path=draft)
    restarted._restore_draft()
    spin(qapp, lambda: not restarted.jobs.busy)
    assert restarted.goal_edit.text() == "下一次想观察阴影中的颜色"


def test_restoring_edited_file_recomputes_saved_measurements(qapp, workbench, photos):
    window = workbench()
    load_pair(qapp, window, photos)
    payload = window._snapshot()
    previous_brightness = window._src_stats.mean_brightness
    Image.new("RGB", (640, 480), (235, 235, 235)).save(photos["src"], quality=90)
    restored = workbench()
    restored.restore_payload(payload)
    spin(qapp, lambda: restored._guidance is not None and not restored.jobs.busy)
    assert restored._src_stats.mean_brightness > previous_brightness + 80
    assert (
        restored._analysis_json["src_stats"]["mean_brightness"]
        == restored._src_stats.mean_brightness
    )
    assert (
        restored._analysis_json["comparison"] != payload["analysis_json"]["comparison"]
    )


def test_autosaved_notes_can_restore_before_original_window_closes(
    qapp, workbench, tmp_path
):
    draft = tmp_path / "自动恢复.json"
    window = workbench(draft_path=draft)
    window.goal_edit.setText("观察高光里的暖色")
    window.notes_edit.setPlainText("这段文字应在关闭之前自动保留。")
    spin(qapp, draft.is_file)
    # Start another instance from the already-written draft. No close/save is
    # called on the first window, matching the recoverable part of a crash.
    restarted = workbench(draft_path=draft)
    restarted._restore_draft()
    spin(qapp, lambda: not restarted.jobs.busy)
    assert restarted.notes_edit.toPlainText() == "这段文字应在关闭之前自动保留。"
    assert restarted.goal_edit.text() == "观察高光里的暖色"


def test_failed_restore_keeps_previous_recovery_snapshot(
    qapp, workbench, photos, tmp_path
):
    from framesense.learning.draft import read_draft, write_draft

    window = workbench()
    load_pair(qapp, window, photos)
    backup = window.draft_path.with_name("previous-practice.json")
    write_draft(backup, {"schema": 1, "notes": "必须保留的上一份草稿"})
    corrupt = tmp_path / "坏照片.jpg"
    corrupt.write_bytes(b"broken jpeg")
    payload = window._snapshot()
    payload["reference_path"] = str(corrupt)
    window.restore_payload(payload)
    spin(qapp, lambda: not window.jobs.busy)
    assert read_draft(backup)["notes"] == "必须保留的上一份草稿"
    assert window._ref.source_path == str(photos["ref"])
