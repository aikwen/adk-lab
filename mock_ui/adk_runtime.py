from __future__ import annotations

import sys
from typing import Any, AsyncIterator

try:
    from google.genai import types
except ImportError:
    types = None

try:
    from .base_adk_runtime import BaseAdkRuntime
except ImportError:
    from base_adk_runtime import BaseAdkRuntime


class AdkRuntime(BaseAdkRuntime):
    """Google ADK Runtime 适配层。"""

    def __init__(
        self,
        *,
        runner: Any,
        session_service: Any,
        app_name: str,
        user_id: str,
        initial_session_ids: list[str] | None = None,
        current_session_id: str = "",
    ) -> None:
        super().__init__(
            initial_session_ids=initial_session_ids,
            current_session_id=current_session_id,
        )

        self._runner = runner
        self._session_service = session_service
        self._app_name = app_name
        self._user_id = user_id

    def _create_session_impl(self) -> str:
        """通过 ADK SessionService 创建 session。"""
        session = self._run_sync(
            self._session_service.create_session(
                app_name=self._app_name,
                user_id=self._user_id,
            )
        )

        session_id = self._read_attr(session, "id")
        if not session_id:
            raise RuntimeError("session_service.create_session() did not return a session id")

        return str(session_id)

    def _session_events_impl(self, session_id: str) -> list[Any]:
        """从 ADK SessionService 读取 session events。"""
        session = self._run_sync(
            self._session_service.get_session(
                app_name=self._app_name,
                user_id=self._user_id,
                session_id=session_id,
            )
        )

        events = self._read_attr(session, "events")
        if events is None:
            return []

        return list(events)

    async def _run_agent_events_impl(
        self,
        *,
        session_id: str,
        text: str,
    ) -> AsyncIterator[Any]:
        """运行 ADK Runner 并返回原始 event 流。"""
        new_message = self.build_user_message(text)

        async for event in self._runner.run_async(
            user_id=self._user_id,
            session_id=session_id,
            new_message=new_message,
        ):
            yield event

    def build_user_message(self, text: str) -> Any:
        """构造发送给 ADK Runner 的用户消息。"""
        if types is None:
            raise RuntimeError("google-genai is not installed")

        return types.Content(
            role="user",
            parts=[
                types.Part(text=text),
            ],
        )

    def dump_llm_request(self, llm_request: Any) -> dict[str, Any]:
        """将 LLM request 转换为可展示 JSON。"""
        return self._dump_object(llm_request)

    def dump_event(self, event: Any) -> dict[str, Any]:
        """将 ADK event 转换为可展示 JSON。"""
        return self._dump_object(event)

    def make_response_event_title(self, event: Any) -> str:
        """生成 response event 的左侧标题。"""
        author = self._read_attr(event, "author")
        invocation_id = self._read_attr(event, "invocation_id")
        partial = self._read_attr(event, "partial")

        parts: list[str] = []

        if author:
            parts.append(str(author))
        else:
            parts.append(type(event).__name__)

        if invocation_id:
            parts.append(str(invocation_id))

        if partial is not None:
            parts.append(f"partial={partial}")

        return " / ".join(parts)

    def make_session_event_title(self, event: Any, index: int) -> str:
        """生成 session event 的左侧标题。"""
        author = self._read_attr(event, "author")
        invocation_id = self._read_attr(event, "invocation_id")

        parts: list[str] = []

        if author:
            parts.append(str(author))
        else:
            parts.append(f"session_event_{index}")

        if invocation_id:
            parts.append(str(invocation_id))

        return " / ".join(parts)

    def _dump_object(self, obj: Any) -> dict[str, Any]:
        if obj is None:
            return {}

        if isinstance(obj, dict):
            return obj

        model_dump = getattr(obj, "model_dump", None)
        if callable(model_dump):
            return model_dump(mode="json", exclude_none=True)

        to_dict = getattr(obj, "to_dict", None)
        if callable(to_dict):
            value = to_dict()
            if isinstance(value, dict):
                return value

            return {"value": value}

        if hasattr(obj, "__dict__"):
            return {
                key: self._dump_value(value)
                for key, value in vars(obj).items()
                if not key.startswith("_")
            }

        return {
            "value": str(obj),
        }

    def _dump_value(self, value: Any) -> Any:
        if value is None:
            return None

        if isinstance(value, str | int | float | bool):
            return value

        if isinstance(value, list | tuple):
            return [self._dump_value(item) for item in value]

        if isinstance(value, dict):
            return {
                str(key): self._dump_value(item)
                for key, item in value.items()
            }

        model_dump = getattr(value, "model_dump", None)
        if callable(model_dump):
            return model_dump(mode="json", exclude_none=True)

        to_dict = getattr(value, "to_dict", None)
        if callable(to_dict):
            return self._dump_value(to_dict())

        if hasattr(value, "__dict__"):
            return {
                key: self._dump_value(item)
                for key, item in vars(value).items()
                if not key.startswith("_")
            }

        return str(value)

    def _read_attr(self, obj: Any, name: str) -> Any:
        if obj is None:
            return None

        if isinstance(obj, dict):
            return obj.get(name)

        return getattr(obj, name, None)


if __name__ == "__main__":
    print("AdkRuntime is an adapter implementation.")
    print("Create it with runner, session_service, app_name, and user_id.")
    sys.exit(0)