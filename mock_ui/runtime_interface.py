from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Iterator, Protocol, runtime_checkable

try:
    from .panel_chat import RequestMessage
    from .tab.event_item import InspectEvent
except ImportError:
    from panel_chat import RequestMessage
    from tab.event_item import InspectEvent


@dataclass(slots=True)
class RuntimeRequestResult:
    """一次 request 启动后的运行结果。"""

    invocation_id: str
    response_events: Iterator[InspectEvent] | AsyncIterator[InspectEvent]


@runtime_checkable
class RuntimeProtocol(Protocol):
    """Runtime Inspector 依赖的最小运行时接口。"""

    def session_ids(self) -> list[str]:
        """返回当前 runtime 中可选择的 session id 列表。"""
        ...

    def current_session_id(self) -> str:
        """返回当前激活的 session id。"""
        ...

    def create_session(self) -> str:
        """创建一个新 session，并返回新 session id。"""
        ...

    def set_current_session(self, session_id: str) -> None:
        """切换当前激活的 session。"""
        ...

    def requests(self, session_id: str) -> list[RequestMessage]:
        """返回指定 session 下的用户 request 列表。"""
        ...

    def request(self, session_id: str, text: str) -> RuntimeRequestResult:
        """向指定 session 发起一次 request。"""
        ...

    def llm_request(self, invocation_id: str) -> dict[str, Any] | None:
        """返回指定 invocation 对应的 LLM request。"""
        ...

    def response_events(self, invocation_id: str) -> list[InspectEvent]:
        """返回指定 invocation 已产生的 response events。"""
        ...

    def session_events(self, session_id: str) -> list[InspectEvent]:
        """返回指定 session 当前的 session events。"""
        ...