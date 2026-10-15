"""Qt 后台任务：按通道取消，过时结果永不送回界面。"""

from __future__ import annotations

import threading
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal, Slot


class Cancelled(Exception):
    pass


class Cancellation:
    def __init__(self):
        self.event = threading.Event()

    def check(self):
        if self.event.is_set():
            raise Cancelled()


class _Signals(QObject):
    result = Signal(str, int, object)
    error = Signal(str, int, str)
    done = Signal(str, int)


class _Job(QRunnable):
    def __init__(self, channel, number, token, function):
        super().__init__()
        self.channel, self.number, self.token, self.function = (
            channel,
            number,
            token,
            function,
        )
        self.signals = _Signals()

    @Slot()
    def run(self):
        try:
            self.token.check()
            value = self.function(self.token)
            self.token.check()
            self.signals.result.emit(self.channel, self.number, value)
        except Cancelled:
            pass
        except Exception as exc:
            self.signals.error.emit(self.channel, self.number, str(exc))
        finally:
            self.signals.done.emit(self.channel, self.number)


class TaskController(QObject):
    result = Signal(str, object)
    error = Signal(str, str)
    busy_changed = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.pool = QThreadPool.globalInstance()
        self.pool.setMaxThreadCount(2)
        self._serial = 0
        self._current = {}
        self._jobs = {}

    @property
    def busy(self):
        return bool(self._current)

    def has_task(self, channel):
        return channel in self._current

    def submit(self, channel, function):
        self.cancel(channel)
        self._serial += 1
        token = Cancellation()
        job = _Job(channel, self._serial, token, function)
        self._current[channel] = (self._serial, token)
        self._jobs[self._serial] = job
        job.signals.result.connect(self._result)
        job.signals.error.connect(self._error)
        job.signals.done.connect(self._done)
        self.busy_changed.emit(True)
        self.pool.start(job)

    def cancel(self, channel=None):
        for key in list(self._current):
            if channel is None or key == channel:
                _, token = self._current.pop(key)
                token.event.set()
        self.busy_changed.emit(self.busy)

    def _is_current(self, channel, number):
        return self._current.get(channel, (None,))[0] == number

    @Slot(str, int, object)
    def _result(self, channel, number, value):
        if self._is_current(channel, number):
            self.result.emit(channel, value)

    @Slot(str, int, str)
    def _error(self, channel, number, error):
        if self._is_current(channel, number):
            self.error.emit(channel, error)

    @Slot(str, int)
    def _done(self, channel, number):
        if self._is_current(channel, number):
            self._current.pop(channel, None)
        self._jobs.pop(number, None)
        self.busy_changed.emit(self.busy)
