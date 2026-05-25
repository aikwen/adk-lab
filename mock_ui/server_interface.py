from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

try:
    from .tab.event_item import InspectEvent
except ImportError:
    from tab.event_item import InspectEvent


@dataclass(slots=True)
class ResponseSnapshot:
    """指定 invocation 当前的 response 快照。"""

    events: list[InspectEvent]
    done: bool = False


@runtime_checkable
class MockUIServer(Protocol):
    """mock_ui 依赖的最小服务接口。"""

    def session_list(self) -> list[str]:
        """返回可选择的 session id 列表。"""
        ...

    def session_create(self) -> str:
        """创建新 session，并返回 session id。"""
        ...

    def message_request(self, session_id: str, text: str) -> str:
        """发送用户消息，并返回 invocation id。"""
        ...

    def response(self, invocation_id: str) -> ResponseSnapshot:
        """返回指定 invocation 当前的 response events 快照。"""
        ...

    def llm_request_body(self, invocation_id: str) -> dict[str, Any] | None:
        """返回指定 invocation 对应的 LLM request body。"""
        ...

    def session_events(self, session_id: str) -> list[InspectEvent]:
        """返回指定 session 当前的 session events。"""
        ...