from __future__ import annotations

import threading
from typing import Callable

from PySide6.QtCore import QObject, Signal


class TaskRunner(QObject):
    """在普通 Python 线程中执行一次性任务。"""

    succeeded = Signal(str, object)
    failed = Signal(str, str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._threads: list[threading.Thread] = []

    def submit(
        self,
        *,
        task_name: str,
        fn: Callable[[], object],
    ) -> None:
        """提交一个后台任务。"""

        thread = threading.Thread(
            target=self._run,
            args=(task_name, fn),
            daemon=True,
        )

        self._threads.append(thread)
        thread.start()

    def _run(
        self,
        task_name: str,
        fn: Callable[[], object],
    ) -> None:
        try:
            result = fn()
            self.succeeded.emit(task_name, result)
        except Exception as exc:
            self.failed.emit(task_name, str(exc))
        finally:
            self._removeFinishedThreads()

    def _removeFinishedThreads(self) -> None:
        self._threads = [
            thread
            for thread in self._threads
            if thread.is_alive()
        ]