from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QObject

try:
    from .async_utils.poller import PollRunner
    from .async_utils.worker import TaskRunner
    from .panel_chat import RequestMessage
    from .server_interface import MockUIServer, ResponseSnapshot
    from .tab.event_item import InspectEvent
    from .tab.inspect_tabs import SESSION_EVENTS_TAB
    from .windows import MainWindow
except ImportError:
    from async_utils.poller import PollRunner
    from async_utils.worker import TaskRunner
    from panel_chat import RequestMessage
    from server_interface import MockUIServer, ResponseSnapshot
    from tab.event_item import InspectEvent
    from tab.inspect_tabs import SESSION_EVENTS_TAB
    from windows import MainWindow


class ClientWindow(MainWindow):
    """基于 MockUIServer 的客户端窗口。"""

    def __init__(
        self,
        *,
        server: MockUIServer,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)

        self._server = server

        self._task_runner = TaskRunner(self)
        self._poll_runner = PollRunner(self)

        self._task_index = 1
        self._task_success_handlers: dict[str, Callable[[object], None]] = {}
        self._task_failed_handlers: dict[str, Callable[[str], None]] = {}

        self._requests_by_session: dict[str, list[RequestMessage]] = {}
        self._request_session_by_invocation: dict[str, str] = {}

        self._connectClientSignals()
        self._loadInitialSessions()

    def closeEvent(self, event) -> None:
        self._poll_runner.stopAll()
        super().closeEvent(event)

    def _connectClientSignals(self) -> None:
        self.sessionSelected.connect(self._onSessionSelected)
        self.newSessionRequested.connect(self._onNewSessionRequested)

        self.sendRequested.connect(self._onSendRequested)
        self.requestSelected.connect(self._onRequestSelected)

        self.inspectTabSelected.connect(self._onInspectTabSelected)

        self._task_runner.succeeded.connect(self._onTaskSucceeded)
        self._task_runner.failed.connect(self._onTaskFailed)

        self._poll_runner.snapshotReady.connect(self._onPollSnapshotReady)
        self._poll_runner.finished.connect(self._onPollFinished)
        self._poll_runner.failed.connect(self._onPollFailed)

    def _loadInitialSessions(self) -> None:
        self.setSending(True)

        self._submitTask(
            name="session_list",
            fn=self._server.session_list,
            on_success=self._onSessionListLoaded,
            on_failed=self._onSessionListFailed,
        )

    def _onSessionListLoaded(self, result: object) -> None:
        session_ids = self._normalizeSessionIds(result)

        if not session_ids:
            self._createInitialSession()
            return

        for session_id in session_ids:
            self._requests_by_session.setdefault(session_id, [])

        current_session_id = session_ids[0]

        self.setSessionIds(
            session_ids,
            current_session_id=current_session_id,
        )
        self.setRequests(self._requests_by_session.get(current_session_id, []))
        self.clearInspectTabs()
        self.setSending(False)

    def _onSessionListFailed(self, message: str) -> None:
        self.setSending(False)
        print(f"session list failed: {message}")

    def _createInitialSession(self) -> None:
        self._submitTask(
            name="session_create_initial",
            fn=self._server.session_create,
            on_success=self._onInitialSessionCreated,
            on_failed=self._onCreateSessionFailed,
        )

    def _onInitialSessionCreated(self, result: object) -> None:
        session_id = str(result)
        self._requests_by_session.setdefault(session_id, [])

        self.setSessionIds(
            [session_id],
            current_session_id=session_id,
        )
        self.setRequests([])
        self.clearInspectTabs()
        self.setSending(False)

    def _onSessionSelected(self, session_id: str) -> None:
        self._requests_by_session.setdefault(session_id, [])

        self.setRequests(self._requests_by_session.get(session_id, []))
        self.clearRequestSelection()
        self.clearInspectTabs()

        if self.currentInspectTab() == SESSION_EVENTS_TAB:
            self._loadSessionEvents(session_id)

    def _onNewSessionRequested(self) -> None:
        self._submitTask(
            name="session_create",
            fn=self._server.session_create,
            on_success=self._onSessionCreated,
            on_failed=self._onCreateSessionFailed,
        )

    def _onSessionCreated(self, result: object) -> None:
        session_id = str(result)
        self._requests_by_session.setdefault(session_id, [])

        self.addSessionId(
            session_id,
            activate=True,
            emit_signal=True,
        )

    def _onCreateSessionFailed(self, message: str) -> None:
        print(f"create session failed: {message}")

    def _onSendRequested(self, text: str) -> None:
        session_id = self.currentSessionId()
        if not session_id:
            return

        self.setSending(True)

        self._submitTask(
            name="message_request",
            fn=lambda: self._server.message_request(session_id, text),
            on_success=lambda result: self._onMessageRequestCreated(
                session_id=session_id,
                text=text,
                result=result,
            ),
            on_failed=self._onMessageRequestFailed,
        )

    def _onMessageRequestCreated(
        self,
        *,
        session_id: str,
        text: str,
        result: object,
    ) -> None:
        invocation_id = str(result)

        request = RequestMessage(
            text=text,
            invocation_id=invocation_id,
        )

        self._requests_by_session.setdefault(session_id, []).append(request)
        self._request_session_by_invocation[invocation_id] = session_id

        if self.currentSessionId() == session_id:
            index = self.appendRequest(request)
            self.clearInput()
            self.selectRequest(index)
            self.selectResponseTab()

        self._startResponsePolling(invocation_id)

    def _onMessageRequestFailed(self, message: str) -> None:
        self.setSending(False)
        print(f"message request failed: {message}")

    def _onRequestSelected(self, index: int, invocation_id: str) -> None:
        self._loadInvocationSnapshot(invocation_id)

    def _onInspectTabSelected(self, tab_name: str) -> None:
        if tab_name != SESSION_EVENTS_TAB:
            return

        session_id = self.currentSessionId()
        if not session_id:
            return

        self._loadSessionEvents(session_id)

    def _loadInvocationSnapshot(self, invocation_id: str) -> None:
        self._submitTask(
            name=f"invocation_snapshot:{invocation_id}",
            fn=lambda: (
                self._server.response(invocation_id),
                self._server.llm_request_body(invocation_id),
            ),
            on_success=lambda result: self._onInvocationSnapshotLoaded(
                invocation_id=invocation_id,
                result=result,
            ),
            on_failed=lambda message: self._onInvocationSnapshotFailed(
                invocation_id=invocation_id,
                message=message,
            ),
        )

    def _onInvocationSnapshotLoaded(
        self,
        *,
        invocation_id: str,
        result: object,
    ) -> None:
        selected_request = self.selectedRequest()
        if selected_request is None:
            return

        if selected_request.invocation_id != invocation_id:
            return

        snapshot, llm_request = result

        if isinstance(snapshot, ResponseSnapshot):
            self.setResponseEvents(snapshot.events)
        else:
            self.setResponseEvents([])

        self.setRequestJsonContent(llm_request)
        self.clearResponseSelection()

    def _onInvocationSnapshotFailed(self, *, invocation_id: str, message: str) -> None:
        print(f"load invocation failed: invocation_id={invocation_id}, error={message}")

    def _loadSessionEvents(self, session_id: str) -> None:
        self._submitTask(
            name=f"session_events:{session_id}",
            fn=lambda: self._server.session_events(session_id),
            on_success=lambda result: self._onSessionEventsLoaded(
                session_id=session_id,
                result=result,
            ),
            on_failed=lambda message: self._onSessionEventsFailed(
                session_id=session_id,
                message=message,
            ),
        )

    def _onSessionEventsLoaded(
        self,
        *,
        session_id: str,
        result: object,
    ) -> None:
        if self.currentSessionId() != session_id:
            return

        if self.currentInspectTab() != SESSION_EVENTS_TAB:
            return

        if isinstance(result, list):
            self.setSessionEvents(result)
        else:
            self.setSessionEvents([])

        self.clearSessionSelection()

    def _onSessionEventsFailed(self, *, session_id: str, message: str) -> None:
        print(f"load session events failed: session_id={session_id}, error={message}")

    def _startResponsePolling(self, invocation_id: str) -> None:
        self._poll_runner.start(
            key=invocation_id,
            fn=lambda: (
                self._server.response(invocation_id),
                self._server.llm_request_body(invocation_id),
            ),
            is_done=self._isResponsePollingDone,
            interval_seconds=0.5,
        )

    def _isResponsePollingDone(self, result: object) -> bool:
        if not isinstance(result, tuple):
            return True

        if not result:
            return True

        snapshot = result[0]
        if not isinstance(snapshot, ResponseSnapshot):
            return True

        return snapshot.done

    def _onPollSnapshotReady(self, invocation_id: str, result: object) -> None:
        selected_request = self.selectedRequest()
        if selected_request is None:
            return

        if selected_request.invocation_id != invocation_id:
            return

        if not isinstance(result, tuple) or len(result) != 2:
            return

        snapshot, llm_request = result

        if isinstance(snapshot, ResponseSnapshot):
            self.setResponseEvents(snapshot.events)

        self.setRequestJsonContent(llm_request)

    def _onPollFinished(self, invocation_id: str) -> None:
        self.setSending(False)

        if self.currentInspectTab() != SESSION_EVENTS_TAB:
            return

        session_id = self.currentSessionId()
        if session_id:
            self._loadSessionEvents(session_id)

    def _onPollFailed(self, invocation_id: str, message: str) -> None:
        self.setSending(False)
        print(f"response polling failed: invocation_id={invocation_id}, error={message}")

    def _submitTask(
        self,
        *,
        name: str,
        fn: Callable[[], object],
        on_success: Callable[[object], None],
        on_failed: Callable[[str], None],
    ) -> None:
        task_name = self._nextTaskName(name)

        self._task_success_handlers[task_name] = on_success
        self._task_failed_handlers[task_name] = on_failed

        self._task_runner.submit(
            task_name=task_name,
            fn=fn,
        )

    def _onTaskSucceeded(self, task_name: str, result: object) -> None:
        handler = self._task_success_handlers.pop(task_name, None)
        self._task_failed_handlers.pop(task_name, None)

        if handler is not None:
            handler(result)

    def _onTaskFailed(self, task_name: str, message: str) -> None:
        handler = self._task_failed_handlers.pop(task_name, None)
        self._task_success_handlers.pop(task_name, None)

        if handler is not None:
            handler(message)

    def _nextTaskName(self, prefix: str) -> str:
        task_name = f"{prefix}:{self._task_index}"
        self._task_index += 1
        return task_name

    def _normalizeSessionIds(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []

        return [str(item) for item in value]