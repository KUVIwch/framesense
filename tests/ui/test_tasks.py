"""任务取消、替换、异常与界面事件响应的真实行为。"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import threading
import time
import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer
from framesense.ui.tasks import TaskController


@pytest.fixture
def qapp():
    return QApplication.instance() or QApplication([])


def spin(app, condition, timeout=5):
    deadline = time.monotonic() + timeout
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.005)
    assert condition()


def test_replaced_task_never_overwrites_new_result(qapp):
    manager = TaskController()
    gate = threading.Event()
    results = []
    manager.result.connect(lambda channel, value: results.append(value))
    manager.submit("load", lambda token: (gate.wait(2), "stale")[1])
    manager.submit("load", lambda token: "current")
    spin(qapp, lambda: results == ["current"])
    gate.set()
    spin(qapp, lambda: not manager._jobs)
    assert results == ["current"]


def test_cancel_suppresses_result_and_ui_keeps_ticking(qapp):
    manager = TaskController()
    gate = threading.Event()
    results = []
    ticks = []
    timer = QTimer()
    timer.setInterval(5)
    timer.timeout.connect(lambda: ticks.append(1))
    timer.start()
    manager.result.connect(lambda channel, value: results.append(value))
    manager.submit("slow", lambda token: gate.wait(2))
    spin(qapp, lambda: len(ticks) >= 5)
    manager.cancel()
    gate.set()
    spin(qapp, lambda: not manager._jobs)
    timer.stop()
    assert results == [] and not manager.busy


def test_worker_failure_does_not_break_next_job(qapp):
    manager = TaskController()
    errors = []
    results = []
    manager.error.connect(lambda channel, error: errors.append(error))
    manager.result.connect(lambda channel, value: results.append(value))

    def fail(token):
        raise ValueError("corrupt image")

    manager.submit("load", fail)
    spin(qapp, lambda: bool(errors))
    manager.submit("load", lambda token: 42)
    spin(qapp, lambda: results == [42])
    spin(qapp, lambda: not manager._jobs)
    assert errors == ["corrupt image"]
