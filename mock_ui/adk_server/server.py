from __future__ import annotations

import asyncio
import threading
from dataclasses import dataclass
from typing import Any

from PySide6.QtWidgets import QApplication

try:
    from agent.runtime import AgentRuntime, agent_runtime
except ImportError:
    from agent.runtime import AgentRuntime, agent_runtime

try:
    from ..client_window import ClientWindow
    from ..server_interface import MockUIServer, ResponseSnapshot
    from ..tab.event_item import InspectEvent
except ImportError:
    from mock_ui.client_window import ClientWindow
    from mock_ui.server_interface import MockUIServer, ResponseSnapshot
    from mock_ui.tab.event_item import InspectEvent


@dataclass(slots=True)
class _RequestRecord:
    invocation_id: str
    session_id: str
    text: str


class AgentMockUIServer(MockUIServer):
    """基于 AgentRuntime 的 MockUIServer 实现。"""

    def __init__(
        self,
        *,
        runtime: AgentRuntime,
        user_id: str,
    ) -> None:
        self._runtime = runtime
        self._user_id = user_id

        self._next_session_index = 1
        self._next_invocation_index = 1

        self._requests_by_invocation: dict[str, _RequestRecord] = {}
        self._response_events_by_invocation: dict[str, list[InspectEvent]] = {}
        self._llm_request_by_invocation: dict[str, dict[str, Any]] = {}
        self._real_invocation_by_invocation: dict[str, str] = {}
        self._done_by_invocation: dict[str, bool] = {}
        self._error_by_invocation: dict[str, str] = {}

        self._lock = threading.RLock()

    def session_list(self) -> list[str]:
        """返回可选择的 session id 列表。"""
        data = self._run_sync(
            self._runtime.list_sessions(
                user_id=self._user_id,
            )
        )

        sessions = data.get("sessions", [])
        return [
            str(session.get("id"))
            for session in sessions
            if session.get("id")
        ]

    def session_create(self) -> str:
        """创建新 session，并返回 session id。"""
        session_id = self._next_session_id()

        data = self._run_sync(
            self._runtime.create_session(
                user_id=self._user_id,
                session_id=session_id,
            )
        )

        return str(data.get("id") or session_id)

    def message_request(self, session_id: str, text: str) -> str:
        """发送用户消息，并返回 invocation id。"""
        if not session_id:
            raise ValueError("session_id is empty")

        invocation_id = self._next_invocation_id()

        with self._lock:
            self._requests_by_invocation[invocation_id] = _RequestRecord(
                invocation_id=invocation_id,
                session_id=session_id,
                text=text,
            )
            self._response_events_by_invocation[invocation_id] = []
            self._done_by_invocation[invocation_id] = False
            self._error_by_invocation.pop(invocation_id, None)

        thread = threading.Thread(
            target=self._run_invocation,
            args=(invocation_id, session_id, text),
            daemon=True,
        )
        thread.start()

        return invocation_id

    def response(self, invocation_id: str) -> ResponseSnapshot:
        """返回指定 invocation 当前的 response events 快照。"""
        with self._lock:
            events = list(self._response_events_by_invocation.get(invocation_id, []))
            done = self._done_by_invocation.get(invocation_id, True)

        return ResponseSnapshot(
            events=events,
            done=done,
        )

    def llm_request_body(self, invocation_id: str) -> dict[str, Any] | None:
        """返回指定 invocation 对应的 LLM request body。"""
        with self._lock:
            llm_request = self._llm_request_by_invocation.get(invocation_id)

        if llm_request is not None:
            return llm_request

        self._capture_llm_request(invocation_id)

        with self._lock:
            return self._llm_request_by_invocation.get(invocation_id)

    def session_events(self, session_id: str) -> list[InspectEvent]:
        """返回指定 session 当前的 session events。"""
        data = self._run_sync(
            self._runtime.session_events(
                user_id=self._user_id,
                session_id=session_id,
            )
        )

        if data is None:
            return []

        events = data.get("events", [])

        return [
            InspectEvent(
                title=self._make_session_event_title(event, index),
                content=event,
            )
            for index, event in enumerate(events)
        ]

    def _run_invocation(
        self,
        invocation_id: str,
        session_id: str,
        text: str,
    ) -> None:
        try:
            asyncio.run(
                self._consume_runtime_events(
                    invocation_id=invocation_id,
                    session_id=session_id,
                    text=text,
                )
            )
        except Exception as exc:
            self._append_response_event(
                invocation_id,
                InspectEvent(
                    title="error",
                    content={
                        "type": "error",
                        "error": str(exc),
                    },
                ),
            )

            with self._lock:
                self._error_by_invocation[invocation_id] = str(exc)
                self._done_by_invocation[invocation_id] = True

    async def _consume_runtime_events(
        self,
        *,
        invocation_id: str,
        session_id: str,
        text: str,
    ) -> None:
        async for data in self._runtime.run_events(
            user_id=self._user_id,
            session_id=session_id,
            message=text,
        ):
            event_type = data.get("type")

            if event_type == "done":
                self._capture_llm_request(invocation_id)

                with self._lock:
                    self._done_by_invocation[invocation_id] = True

                return

            if event_type == "error":
                self._append_response_event(
                    invocation_id,
                    InspectEvent(
                        title="error",
                        content=data,
                    ),
                )

                with self._lock:
                    self._error_by_invocation[invocation_id] = str(data.get("error", ""))
                    self._done_by_invocation[invocation_id] = True

                return

            raw_event = data.get("event", data)
            if not isinstance(raw_event, dict):
                raw_event = {
                    "value": raw_event,
                }

            self._capture_real_invocation_id(
                invocation_id=invocation_id,
                event=raw_event,
            )
            self._capture_llm_request(invocation_id)

            self._append_response_event(
                invocation_id,
                InspectEvent(
                    title=self._make_response_event_title(raw_event),
                    content=raw_event,
                ),
            )

        self._capture_llm_request(invocation_id)

        with self._lock:
            self._done_by_invocation[invocation_id] = True

    def _capture_real_invocation_id(
        self,
        *,
        invocation_id: str,
        event: dict[str, Any],
    ) -> None:
        real_invocation_id = event.get("invocation_id")
        if not real_invocation_id:
            return

        with self._lock:
            self._real_invocation_by_invocation[invocation_id] = str(real_invocation_id)

    def _capture_llm_request(self, invocation_id: str) -> None:
        with self._lock:
            if invocation_id in self._llm_request_by_invocation:
                return

            real_invocation_id = self._real_invocation_by_invocation.get(invocation_id)

        if not real_invocation_id:
            return

        traces = self._runtime.list_traces()

        for trace in reversed(traces):
            if trace.get("type") != "llm_request":
                continue

            if trace.get("invocation_id") != real_invocation_id:
                continue

            request = trace.get("request")
            if not isinstance(request, dict):
                return

            with self._lock:
                self._llm_request_by_invocation[invocation_id] = request

            return

    def _append_response_event(
        self,
        invocation_id: str,
        event: InspectEvent,
    ) -> None:
        with self._lock:
            events = self._response_events_by_invocation.setdefault(invocation_id, [])
            events.append(event)

    def _make_response_event_title(self, event: dict[str, Any]) -> str:
        author = event.get("author")
        real_invocation_id = event.get("invocation_id")
        partial = event.get("partial")

        parts: list[str] = []

        if author:
            parts.append(str(author))
        else:
            parts.append("event")

        if real_invocation_id:
            parts.append(str(real_invocation_id))

        if partial is not None:
            parts.append(f"partial={partial}")

        return " / ".join(parts)

    def _make_session_event_title(
        self,
        event: dict[str, Any],
        index: int,
    ) -> str:
        author = event.get("author")
        real_invocation_id = event.get("invocation_id")

        parts: list[str] = []

        if author:
            parts.append(str(author))
        else:
            parts.append(f"session_event_{index}")

        if real_invocation_id:
            parts.append(str(real_invocation_id))

        return " / ".join(parts)

    def _next_session_id(self) -> str:
        existing = set(self.session_list())

        while True:
            session_id = f"ui_session_{self._next_session_index}"
            self._next_session_index += 1

            if session_id not in existing:
                return session_id

    def _next_invocation_id(self) -> str:
        with self._lock:
            invocation_id = f"ui_inv_{self._next_invocation_index:03d}"
            self._next_invocation_index += 1
            return invocation_id

    def _run_sync(self, value: Any) -> Any:
        if asyncio.iscoroutine(value):
            return asyncio.run(value)

        return value


def main() -> int:
    app = QApplication([])

    server = AgentMockUIServer(
        runtime=agent_runtime,
        user_id="kwen",
    )

    window = ClientWindow(server=server)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())