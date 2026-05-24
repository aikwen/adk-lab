from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

try:
    from agent.runtime import AgentRuntime
except ImportError:
    from agent.runtime import AgentRuntime

try:
    from .panel_chat import RequestMessage
    from .runtime_interface import RuntimeProtocol, RuntimeRequestResult
    from .tab.event_item import InspectEvent
except ImportError:
    from panel_chat import RequestMessage
    from runtime_interface import RuntimeProtocol, RuntimeRequestResult
    from tab.event_item import InspectEvent


class AgentRuntimeAdapter(RuntimeProtocol):
    """将 agent.AgentRuntime 适配为 mock_ui RuntimeProtocol。"""

    def __init__(
        self,
        *,
        agent_runtime: AgentRuntime,
        user_id: str,
        initial_session_ids: list[str] | None = None,
        current_session_id: str = "",
    ) -> None:
        self._agent_runtime = agent_runtime
        self._user_id = user_id

        self._session_ids = list(initial_session_ids or [])
        self._current_session_id = current_session_id

        self._next_session_index = 1
        self._next_invocation_index = 1

        self._requests_by_session: dict[str, list[RequestMessage]] = {}
        self._llm_request_by_invocation: dict[str, dict[str, Any]] = {}
        self._response_events_by_invocation: dict[str, list[InspectEvent]] = {}

        for session_id in self._session_ids:
            self._requests_by_session.setdefault(session_id, [])

        if self._current_session_id:
            self._requests_by_session.setdefault(self._current_session_id, [])
            if self._current_session_id not in self._session_ids:
                self._session_ids.append(self._current_session_id)

    def session_ids(self) -> list[str]:
        """返回当前 UI 已知的 session id 列表。"""
        return list(self._session_ids)

    def current_session_id(self) -> str:
        """返回当前激活的 session id。"""
        return self._current_session_id

    def create_session(self) -> str:
        """通过 agent runtime 创建 session。"""
        session_id = self._next_session_id()

        data = self._run_sync(
            self._agent_runtime.create_session(
                user_id=self._user_id,
                session_id=session_id,
            )
        )

        created_session_id = str(data.get("id") or session_id)

        if created_session_id not in self._session_ids:
            self._session_ids.append(created_session_id)

        self._requests_by_session.setdefault(created_session_id, [])
        self._current_session_id = created_session_id

        return created_session_id

    def set_current_session(self, session_id: str) -> None:
        """切换当前激活的 session。"""
        if session_id not in self._session_ids:
            self._session_ids.append(session_id)

        self._requests_by_session.setdefault(session_id, [])
        self._current_session_id = session_id

    def requests(self, session_id: str) -> list[RequestMessage]:
        """返回指定 session 下的用户 request 列表。"""
        return list(self._requests_by_session.get(session_id, []))

    def request(self, session_id: str, text: str) -> RuntimeRequestResult:
        """向指定 session 发起一次 request。"""
        if not session_id:
            raise ValueError("session_id is empty")

        invocation_id = self._next_invocation_id()

        self._requests_by_session.setdefault(session_id, []).append(
            RequestMessage(
                text=text,
                invocation_id=invocation_id,
            )
        )
        self._response_events_by_invocation[invocation_id] = []

        return RuntimeRequestResult(
            invocation_id=invocation_id,
            response_events=self._response_event_stream(
                session_id=session_id,
                invocation_id=invocation_id,
                text=text,
            ),
        )

    def llm_request(self, invocation_id: str) -> dict[str, Any] | None:
        """返回指定 invocation 对应的 LLM request。"""
        return self._llm_request_by_invocation.get(invocation_id)

    def response_events(self, invocation_id: str) -> list[InspectEvent]:
        """返回指定 invocation 已产生的 response events。"""
        return list(self._response_events_by_invocation.get(invocation_id, []))

    def session_events(self, session_id: str) -> list[InspectEvent]:
        """从 agent runtime 读取 session events。"""
        data = self._run_sync(
            self._agent_runtime.session_events(
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

    async def _response_event_stream(
        self,
        *,
        session_id: str,
        invocation_id: str,
        text: str,
    ) -> AsyncIterator[InspectEvent]:
        async for data in self._agent_runtime.run_events(
            user_id=self._user_id,
            session_id=session_id,
            message=text,
        ):
            if data.get("type") == "done":
                break

            if data.get("type") == "error":
                event = InspectEvent(
                    title="error",
                    content=data,
                )
                self._append_response_event(invocation_id, event)
                yield event
                continue

            raw_event = data.get("event", data)

            self._capture_llm_request(invocation_id, raw_event)

            event = InspectEvent(
                title=self._make_response_event_title(raw_event),
                content=raw_event,
            )

            self._append_response_event(invocation_id, event)
            yield event

    def _capture_llm_request(self, invocation_id: str, event: dict[str, Any]) -> None:
        if invocation_id in self._llm_request_by_invocation:
            return

        real_invocation_id = event.get("invocation_id")
        if not real_invocation_id:
            return

        traces = self._agent_runtime.list_traces()

        for trace in reversed(traces):
            if trace.get("type") != "llm_request":
                continue

            if trace.get("invocation_id") != real_invocation_id:
                continue

            request = trace.get("request")
            if isinstance(request, dict):
                self._llm_request_by_invocation[invocation_id] = request

            return

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

    def _make_session_event_title(self, event: dict[str, Any], index: int) -> str:
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
        while True:
            session_id = f"ui_session_{self._next_session_index}"
            self._next_session_index += 1

            if session_id not in self._session_ids:
                return session_id

    def _next_invocation_id(self) -> str:
        invocation_id = f"ui_inv_{self._next_invocation_index:03d}"
        self._next_invocation_index += 1
        return invocation_id

    def _append_response_event(self, invocation_id: str, event: InspectEvent) -> None:
        events = self._response_events_by_invocation.setdefault(invocation_id, [])
        events.append(event)

    def _run_sync(self, value: Any) -> Any:
        if not asyncio.iscoroutine(value):
            return value

        return asyncio.run(value)