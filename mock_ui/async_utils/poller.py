from __future__ import annotations

import threading
import time
from typing import Callable

from PySide6.QtCore import QObject, Signal


class PollRunner(QObject):
    """在普通 Python 线程中执行轮询任务。"""

    snapshotReady = Signal(str, object)
    finished = Signal(str)
    failed = Signal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._tasks: dict[str, _PollTask] = {}

    def start(
        self,
        *,
        key: str,
        fn: Callable[[], object],
        is_done: Callable[[object], bool],
        interval_seconds: float = 0.5,
    ) -> None:
        """启动一个轮询任务。"""
        self.stop(key)

        task = _PollTask(
            key=key,
            fn=fn,
            is_done=is_done,
            interval_seconds=interval_seconds,
            snapshot_callback=self._emitSnapshot,
            finished_callback=self._emitFinished,
            failed_callback=self._emitFailed,
            cleanup_callback=self._removeTask,
        )

        self._tasks[key] = task
        task.start()

    def stop(self, key: str) -> None:
        """停止指定轮询任务。"""
        task = self._tasks.pop(key, None)
        if task is not None:
            task.stop()

    def stopAll(self) -> None:
        """停止全部轮询任务。"""
        for key in list(self._tasks):
            self.stop(key)

    def _emitSnapshot(self, key: str, snapshot: object) -> None:
        self.snapshotReady.emit(key, snapshot)

    def _emitFinished(self, key: str) -> None:
        self.finished.emit(key)

    def _emitFailed(self, key: str, message: str) -> None:
        self.failed.emit(key, message)

    def _removeTask(self, key: str) -> None:
        self._tasks.pop(key, None)


class _PollTask:
    """单个轮询任务。"""

    def __init__(
        self,
        *,
        key: str,
        fn: Callable[[], object],
        is_done: Callable[[object], bool],
        interval_seconds: float,
        snapshot_callback: Callable[[str, object], None],
        finished_callback: Callable[[str], None],
        failed_callback: Callable[[str, str], None],
        cleanup_callback: Callable[[str], None],
    ) -> None:
        self._key = key
        self._fn = fn
        self._is_done = is_done
        self._interval_seconds = interval_seconds
        self._snapshot_callback = snapshot_callback
        self._finished_callback = finished_callback
        self._failed_callback = failed_callback
        self._cleanup_callback = cleanup_callback

        self._stop_event = threading.Event()
        self._thread = threading.Thread(
            target=self._run,
            daemon=True,
        )

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()

    def _run(self) -> None:
        try:
            while not self._stop_event.is_set():
                snapshot = self._fn()
                self._snapshot_callback(self._key, snapshot)

                if self._is_done(snapshot):
                    self._finished_callback(self._key)
                    break

                self._stop_event.wait(self._interval_seconds)
        except Exception as exc:
            self._failed_callback(self._key, str(exc))
        finally:
            self._cleanup_callback(self._key)