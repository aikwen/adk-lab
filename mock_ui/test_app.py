from __future__ import annotations

import asyncio
import sys
from typing import AsyncIterator, Iterator

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtWidgets import QApplication

try:
    from .panel_chat import RequestMessage
    from .runtime_interface import RuntimeProtocol, RuntimeRequestResult
    from .tab.event_item import InspectEvent
    from .tab.inspect_tabs import SESSION_EVENTS_TAB
    from .windows import MainWindow
except ImportError:
    from panel_chat import RequestMessage
    from runtime_interface import RuntimeProtocol, RuntimeRequestResult
    from tab.event_item import InspectEvent
    from tab.inspect_tabs import SESSION_EVENTS_TAB
    from windows import MainWindow


class ResponseStreamWorker(QObject):
    eventReady = Signal(str, object)
    finished = Signal(str)
    failed = Signal(str, str)

    def __init__(
        self,
        invocation_id: str,
        response_events: Iterator[InspectEvent] | AsyncIterator[InspectEvent],
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._invocation_id = invocation_id
        self._response_events = response_events

    @Slot()
    def run(self) -> None:
        try:
            if hasattr(self._response_events, "__aiter__"):
                asyncio.run(self._run_async_events())
            else:
                self._run_sync_events()

            self.finished.emit(self._invocation_id)
        except Exception as exc:
            self.failed.emit(self._invocation_id, str(exc))

    def _run_sync_events(self) -> None:
        for event in self._response_events:
            self.eventReady.emit(self._invocation_id, event)

    async def _run_async_events(self) -> None:
        async for event in self._response_events:
            self.eventReady.emit(self._invocation_id, event)


class CreateSessionWorker(QObject):
    created = Signal(str)
    failed = Signal(str)

    def __init__(self, runtime: RuntimeProtocol, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._runtime = runtime

    @Slot()
    def run(self) -> None:
        try:
            session_id = self._runtime.create_session()
            self.created.emit(session_id)
        except Exception as exc:
            self.failed.emit(str(exc))


class TestAppController(QObject):
    def __init__(
        self,
        window: MainWindow,
        runtime: RuntimeProtocol,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self._window = window
        self._runtime = runtime

        self._threads: list[QThread] = []
        self._workers: list[QObject] = []

        self._connectSignals()
        self._syncInitialState()

    def _connectSignals(self) -> None:
        self._window.sessionSelected.connect(self._onSessionSelected)
        self._window.newSessionRequested.connect(self._onNewSessionRequested)

        self._window.sendRequested.connect(self._onSendRequested)
        self._window.requestSelected.connect(self._onRequestSelected)

        self._window.inspectTabSelected.connect(self._onInspectTabSelected)

    def _syncInitialState(self) -> None:
        session_id = self._runtime.current_session_id()

        self._window.setSessionIds(
            self._runtime.session_ids(),
            current_session_id=session_id,
        )
        self._window.setRequests(self._runtime.requests(session_id))
        self._window.clearInspectTabs()
        self._window.setSending(False)

    def _onSessionSelected(self, session_id: str) -> None:
        self._runtime.set_current_session(session_id)

        self._window.setRequests(self._runtime.requests(session_id))
        self._window.clearRequestSelection()
        self._window.clearInspectTabs()

    def _onNewSessionRequested(self) -> None:
        worker = CreateSessionWorker(self._runtime)
        thread = QThread(self)

        worker.moveToThread(thread)

        thread.started.connect(worker.run)

        worker.created.connect(self._onSessionCreated)
        worker.failed.connect(self._onCreateSessionFailed)

        worker.created.connect(thread.quit)
        worker.failed.connect(thread.quit)

        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda current=thread: self._removeThread(current))
        thread.finished.connect(lambda current=worker: self._removeWorker(current))

        self._threads.append(thread)
        self._workers.append(worker)

        thread.start()

    def _onSessionCreated(self, session_id: str) -> None:
        self._window.addSessionId(
            session_id,
            activate=True,
            emit_signal=True,
        )

    def _onCreateSessionFailed(self, message: str) -> None:
        print(f"create session failed: {message}")

    def _onSendRequested(self, text: str) -> None:
        self._window.setSending(True)

        try:
            session_id = self._window.currentSessionId()
            result = self._runtime.request(session_id, text)
        except Exception as exc:
            self._window.setSending(False)
            print(f"request failed: {exc}")
            return

        request = RequestMessage(
            text=text,
            invocation_id=result.invocation_id,
        )

        index = self._window.appendRequest(request)
        self._window.clearInput()

        self._window.selectRequest(index)
        self._window.selectResponseTab()

        self._startResponseStream(result)

    def _onRequestSelected(self, index: int, invocation_id: str) -> None:
        llm_request = self._runtime.llm_request(invocation_id)
        response_events = self._runtime.response_events(invocation_id)

        self._window.setRequestJsonContent(llm_request)
        self._window.setResponseEvents(response_events)
        self._window.clearResponseSelection()

    def _onInspectTabSelected(self, tab_name: str) -> None:
        if tab_name != SESSION_EVENTS_TAB:
            return

        session_id = self._window.currentSessionId()
        self._window.setSessionEvents(self._runtime.session_events(session_id))
        self._window.clearSessionSelection()

    def _startResponseStream(self, result: RuntimeRequestResult) -> None:
        worker = ResponseStreamWorker(
            invocation_id=result.invocation_id,
            response_events=result.response_events,
        )
        thread = QThread(self)

        worker.moveToThread(thread)

        thread.started.connect(worker.run)

        worker.eventReady.connect(self._onResponseEventReady)
        worker.finished.connect(self._onResponseStreamFinished)
        worker.failed.connect(self._onResponseStreamFailed)

        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)

        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(lambda current=thread: self._removeThread(current))
        thread.finished.connect(lambda current=worker: self._removeWorker(current))

        self._threads.append(thread)
        self._workers.append(worker)

        thread.start()

    def _onResponseEventReady(self, invocation_id: str, event: object) -> None:
        if not isinstance(event, InspectEvent):
            return

        selected_request = self._window.selectedRequest()
        if selected_request is None:
            return

        if selected_request.invocation_id != invocation_id:
            return

        llm_request = self._runtime.llm_request(invocation_id)
        if llm_request is not None:
            self._window.setRequestJsonContent(llm_request)

        self._window.appendResponseEvent(event)

    def _onResponseStreamFinished(self, invocation_id: str) -> None:
        self._window.setSending(False)

        llm_request = self._runtime.llm_request(invocation_id)
        selected_request = self._window.selectedRequest()
        if (
            llm_request is not None
            and selected_request is not None
            and selected_request.invocation_id == invocation_id
        ):
            self._window.setRequestJsonContent(llm_request)

        if self._window.currentInspectTab() != SESSION_EVENTS_TAB:
            return

        session_id = self._window.currentSessionId()
        self._window.setSessionEvents(self._runtime.session_events(session_id))

    def _onResponseStreamFailed(self, invocation_id: str, message: str) -> None:
        self._window.setSending(False)
        print(f"response stream failed: invocation_id={invocation_id}, error={message}")

    def _removeThread(self, thread: QThread) -> None:
        if thread in self._threads:
            self._threads.remove(thread)

    def _removeWorker(self, worker: QObject) -> None:
        if worker in self._workers:
            self._workers.remove(worker)


if __name__ == "__main__":
    app = QApplication(sys.argv)

    from agent.runtime import agent_runtime
    from mock_ui.agent_runtime_adapter import AgentRuntimeAdapter

    runtime = AgentRuntimeAdapter(
        agent_runtime=agent_runtime,
        user_id="kwen",
    )
    session_id = runtime.create_session()
    runtime.set_current_session(session_id)

    window = MainWindow()
    controller = TestAppController(window, runtime)

    window.show()

    sys.exit(app.exec())