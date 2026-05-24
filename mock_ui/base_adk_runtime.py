from __future__ import annotations

import asyncio
import inspect
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, Iterator

try:
    from .panel_chat import RequestMessage
    from .runtime_interface import RuntimeProtocol, RuntimeRequestResult
    from .tab.event_item import InspectEvent
except ImportError:
    from panel_chat import RequestMessage
    from runtime_interface import RuntimeProtocol, RuntimeRequestResult
    from tab.event_item import InspectEvent


class BaseAdkRuntime(RuntimeProtocol, ABC):
    """ADK Runtime Inspector 的通用运行时流程。"""

    def __init__(
        self,
        *,
        initial_session_ids: list[str] | None = None,
        current_session_id: str = "",
    ) -> None:
        self._session_ids = list(initial_session_ids or [])
        self._current_session_id = current_session_id

        self._next_invocation_index = 1

        self._requests_by_session: dict[str, list[RequestMessage]] = {}
        self._llm_request_by_invocation: dict[str, dict[str, Any]] = {}
        self._response_events_by_invocation: dict[str, list[InspectEvent]] = {}

        self._running_invocation_id: str | None = None

        for session_id in self._session_ids:
            self._requests_by_session.setdefault(session_id, [])

        if self._current_session_id:
            self._requests_by_session.setdefault(self._current_session_id, [])
            if self._current_session_id not in self._session_ids:
                self._session_ids.append(self._current_session_id)

    def session_ids(self) -> list[str]:
        """返回当前 Inspector 已知的 session id 列表。"""
        return list(self._session_ids)

    def current_session_id(self) -> str:
        """返回当前激活的 session id。"""
        return self._current_session_id

    def create_session(self) -> str:
        """创建一个新 session。"""
        session_id = self._create_session_impl()
        if not session_id:
            raise RuntimeError("created session id is empty")

        session_id = str(session_id)

        if session_id not in self._session_ids:
            self._session_ids.append(session_id)

        self._requests_by_session.setdefault(session_id, [])
        self._current_session_id = session_id

        return session_id

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
        if self._running_invocation_id is not None:
            raise RuntimeError("another request is still running")

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
        self._running_invocation_id = invocation_id

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
        """返回指定 session 当前的 session events。"""
        raw_events = self._session_events_impl(session_id)

        return [
            InspectEvent(
                title=self.make_session_event_title(event, index),
                content=self.dump_event(event),
            )
            for index, event in enumerate(raw_events)
        ]

    def before_model_callback(self, callback_context: Any, llm_request: Any) -> None:
        """记录 ADK 准备发送给模型的 LLM request。"""
        if self._running_invocation_id is None:
            return None

        self._llm_request_by_invocation[self._running_invocation_id] = (
            self.dump_llm_request(llm_request)
        )

        return None

    def _response_event_stream(
        self,
        *,
        session_id: str,
        invocation_id: str,
        text: str,
    ) -> Iterator[InspectEvent]:
        try:
            async_events = self._run_agent_events_impl(
                session_id=session_id,
                text=text,
            )

            yield from self._consume_async_events(
                async_events=async_events,
                invocation_id=invocation_id,
            )
        finally:
            if self._running_invocation_id == invocation_id:
                self._running_invocation_id = None

    def _consume_async_events(
        self,
        *,
        async_events: AsyncIterator[Any],
        invocation_id: str,
    ) -> Iterator[InspectEvent]:
        loop = asyncio.new_event_loop()

        try:
            while True:
                try:
                    raw_event = loop.run_until_complete(async_events.__anext__())
                except StopAsyncIteration:
                    break

                inspect_event = InspectEvent(
                    title=self.make_response_event_title(raw_event),
                    content=self.dump_event(raw_event),
                )

                self._append_response_event(invocation_id, inspect_event)

                yield inspect_event
        finally:
            loop.run_until_complete(self._close_async_iterator(async_events))
            loop.close()

    async def _close_async_iterator(self, async_events: AsyncIterator[Any]) -> None:
        aclose = getattr(async_events, "aclose", None)
        if aclose is not None:
            await aclose()

    def _next_invocation_id(self) -> str:
        invocation_id = f"inv_{self._next_invocation_index:03d}"
        self._next_invocation_index += 1
        return invocation_id

    def _append_response_event(self, invocation_id: str, event: InspectEvent) -> None:
        events = self._response_events_by_invocation.setdefault(invocation_id, [])
        events.append(event)

    def _run_sync(self, value: Any) -> Any:
        if inspect.isawaitable(value):
            return asyncio.run(value)

        return value

    @abstractmethod
    def _create_session_impl(self) -> str:
        """创建真实 session，并返回 session id。"""
        raise NotImplementedError

    @abstractmethod
    def _session_events_impl(self, session_id: str) -> list[Any]:
        """返回真实 session events。"""
        raise NotImplementedError

    @abstractmethod
    async def _run_agent_events_impl(
        self,
        *,
        session_id: str,
        text: str,
    ) -> AsyncIterator[Any]:
        """运行 agent，并返回原始 ADK event 流。"""
        raise NotImplementedError

    @abstractmethod
    def dump_llm_request(self, llm_request: Any) -> dict[str, Any]:
        """将 LLM request 转换为可展示 JSON。"""
        raise NotImplementedError

    @abstractmethod
    def dump_event(self, event: Any) -> dict[str, Any]:
        """将 ADK event 转换为可展示 JSON。"""
        raise NotImplementedError

    @abstractmethod
    def make_response_event_title(self, event: Any) -> str:
        """生成 response event 的左侧列表标题。"""
        raise NotImplementedError

    @abstractmethod
    def make_session_event_title(self, event: Any, index: int) -> str:
        """生成 session event 的左侧列表标题。"""
        raise NotImplementedError