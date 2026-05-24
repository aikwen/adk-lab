from __future__ import annotations

import random
import sys
import time
from typing import Any, Iterator

try:
    from .panel_chat import RequestMessage
    from .runtime_interface import RuntimeProtocol, RuntimeRequestResult
    from .tab.event_item import InspectEvent
except ImportError:
    from panel_chat import RequestMessage
    from runtime_interface import RuntimeProtocol, RuntimeRequestResult
    from tab.event_item import InspectEvent


class MockRuntime(RuntimeProtocol):
    """用于 Runtime Inspector demo 的模拟运行时。"""

    def __init__(self) -> None:
        self._session_ids: list[str] = []
        self._current_session_id = ""

        self._next_session_index = 1

        self._next_invocation_index = 1
        self._requests_by_session: dict[str, list[RequestMessage]] = {}
        self._llm_request_by_invocation: dict[str, dict[str, Any]] = {}
        self._response_events_by_invocation: dict[str, list[InspectEvent]] = {}
        self._session_events_by_session: dict[str, list[InspectEvent]] = {}
        self._session_by_invocation: dict[str, str] = {}

        self.create_session()

    def session_ids(self) -> list[str]:
        """返回当前可选择的 session id 列表。"""
        return list(self._session_ids)

    def current_session_id(self) -> str:
        """返回当前激活的 session id。"""
        return self._current_session_id

    def create_session(self) -> str:
        """创建一个模拟 session。"""
        time.sleep(1)

        session_id = f"session_{self._next_session_index:03d}"
        self._next_session_index += 1

        self._session_ids.append(session_id)
        self._requests_by_session[session_id] = []
        self._session_events_by_session[session_id] = []
        self._current_session_id = session_id

        return session_id

    def set_current_session(self, session_id: str) -> None:
        """切换当前激活的 session。"""
        if session_id not in self._session_ids:
            return

        self._current_session_id = session_id

    def requests(self, session_id: str) -> list[RequestMessage]:
        """返回指定 session 下的用户 request 列表。"""
        return list(self._requests_by_session.get(session_id, []))

    def request(self, session_id: str, text: str) -> RuntimeRequestResult:
        """向指定 session 发起一次模拟 request。"""
        if session_id not in self._session_ids:
            raise ValueError(f"unknown session_id: {session_id}")

        invocation_id = self._next_invocation_id()

        request = RequestMessage(
            text=text,
            invocation_id=invocation_id,
        )

        self._requests_by_session[session_id].append(request)
        self._response_events_by_invocation[invocation_id] = []
        self._session_by_invocation[invocation_id] = session_id

        self._append_session_event(
            session_id,
            InspectEvent(
                title=f"user_message: {invocation_id}",
                content={
                    "session_id": session_id,
                    "invocation_id": invocation_id,
                    "author": "user",
                    "content": {
                        "role": "user",
                        "parts": [
                            {
                                "text": text,
                            }
                        ],
                    },
                },
            ),
        )

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
        return list(self._session_events_by_session.get(session_id, []))

    def _next_invocation_id(self) -> str:
        invocation_id = f"inv_{self._next_invocation_index:03d}"
        self._next_invocation_index += 1
        return invocation_id

    def _response_event_stream(
        self,
        *,
        session_id: str,
        invocation_id: str,
        text: str,
    ) -> Iterator[InspectEvent]:
        events = self._build_response_events(
            session_id=session_id,
            invocation_id=invocation_id,
            text=text,
        )

        for event in events:
            time.sleep(random.uniform(1, 3))

            if event.title == "llm_request":
                self._llm_request_by_invocation[invocation_id] = event.content

            self._append_response_event(invocation_id, event)
            yield event

        self._append_session_event(
            session_id,
            InspectEvent(
                title=f"model_message: {invocation_id}",
                content={
                    "session_id": session_id,
                    "invocation_id": invocation_id,
                    "author": "model",
                    "content": {
                        "role": "model",
                        "parts": [
                            {
                                "text": f"Mock response for: {text}",
                            }
                        ],
                    },
                },
            ),
        )

    def _build_response_events(
        self,
        *,
        session_id: str,
        invocation_id: str,
        text: str,
    ) -> list[InspectEvent]:
        return [
            InspectEvent(
                title="llm_request",
                content={
                    "model": "mock_model",
                    "contents": [
                        {
                            "role": "system",
                            "parts": [
                                {
                                    "text": "You are a mock ADK agent used by Runtime Inspector.",
                                }
                            ],
                        },
                        {
                            "role": "user",
                            "parts": [
                                {
                                    "text": text,
                                }
                            ],
                        },
                    ],
                    "tools": [
                        {
                            "name": "mock_search",
                            "description": "Search mock documents.",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {
                                        "type": "string",
                                    }
                                },
                                "required": [
                                    "query",
                                ],
                            },
                        }
                    ],
                    "generation_config": {
                        "temperature": 0.7,
                        "max_output_tokens": 1024,
                    },
                    "metadata": {
                        "session_id": session_id,
                        "invocation_id": invocation_id,
                    },
                },
            ),
            InspectEvent(
                title="tool_call: mock_search",
                content={
                    "session_id": session_id,
                    "invocation_id": invocation_id,
                    "tool_name": "mock_search",
                    "args": {
                        "query": text,
                    },
                },
            ),
            InspectEvent(
                title="tool_response: mock_search",
                content={
                    "session_id": session_id,
                    "invocation_id": invocation_id,
                    "tool_name": "mock_search",
                    "response": {
                        "ok": True,
                        "items": [
                            {
                                "title": "Mock runtime event",
                                "score": 0.91,
                            },
                            {
                                "title": "Mock session event",
                                "score": 0.86,
                            },
                        ],
                    },
                },
            ),
            InspectEvent(
                title="final_response",
                content={
                    "session_id": session_id,
                    "invocation_id": invocation_id,
                    "author": "model",
                    "content": {
                        "role": "model",
                        "parts": [
                            {
                                "text": f"Mock response for: {text}",
                            }
                        ],
                    },
                },
            ),
        ]

    def _append_response_event(self, invocation_id: str, event: InspectEvent) -> None:
        events = self._response_events_by_invocation.setdefault(invocation_id, [])
        events.append(event)

    def _append_session_event(self, session_id: str, event: InspectEvent) -> None:
        events = self._session_events_by_session.setdefault(session_id, [])
        events.append(event)


if __name__ == "__main__":
    runtime = MockRuntime()

    session_id = runtime.current_session_id()

    print("session_ids:")
    print(runtime.session_ids())
    print()

    print("request start")
    result = runtime.request(session_id, "Explain ADK runtime events.")
    print(f"invocation_id: {result.invocation_id}")
    print()

    print("llm_request before stream:")
    print(runtime.llm_request(result.invocation_id))
    print()

    print("response_events:")
    for event in result.response_events:
        print(f"yield: {event.title}")
        print(event.content)
        print()

        if event.title == "llm_request":
            print("llm_request captured:")
            print(runtime.llm_request(result.invocation_id))
            print()

    print("cached response_events:")
    for event in runtime.response_events(result.invocation_id):
        print(event.title)
    print()

    print("session_events:")
    for event in runtime.session_events(session_id):
        print(event.title)
    print()

    sys.exit(0)