from __future__ import annotations

import os
from typing import Any, AsyncIterator

from dotenv import load_dotenv
from google.adk.agents import Agent
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService, Session
from google.genai import types

from agent.tools import get_current_time, get_weather
from agent.trace import (
    clear_traces,
    list_traces,
    list_traces_by_invocation_ids,
    save_llm_request_trace,
)
from agent.util_event import event_to_dict


APP_NAME = "adk-lab"


class AgentRuntime:
    """ADK agent 的核心运行时。"""

    def __init__(
        self,
        *,
        app_name: str = APP_NAME,
        model: str = "openai/deepseek-v3.2",
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key: str | None = None,
        max_llm_calls: int = 10,
    ) -> None:
        load_dotenv()

        self._app_name = app_name
        self._model = model
        self._base_url = base_url
        self._api_key = api_key or os.getenv("API_KEY")

        self._session_service = InMemorySessionService()
        self._root_agent = self._create_root_agent()

        self._runner = Runner(
            agent=self._root_agent,
            app_name=self._app_name,
            session_service=self._session_service,
        )

        self._run_config = RunConfig(
            streaming_mode=StreamingMode.SSE,
            max_llm_calls=max_llm_calls,
        )

    @property
    def app_name(self) -> str:
        return self._app_name

    @property
    def root_agent(self) -> Agent:
        return self._root_agent

    @property
    def runner(self) -> Runner:
        return self._runner

    @property
    def session_service(self) -> InMemorySessionService:
        return self._session_service

    @property
    def run_config(self) -> RunConfig:
        return self._run_config

    async def create_session(
        self,
        *,
        user_id: str,
        session_id: str | None = None,
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """创建 session，并返回可 JSON 序列化的数据。"""
        kwargs: dict[str, Any] = {
            "app_name": self._app_name,
            "user_id": user_id,
            "state": state,
        }

        if session_id is not None:
            kwargs["session_id"] = session_id

        session = await self._session_service.create_session(**kwargs)
        return self.session_to_dict(session)

    async def get_session(
        self,
        *,
        user_id: str,
        session_id: str,
    ) -> dict[str, Any] | None:
        """获取指定 session。"""
        session = await self._session_service.get_session(
            app_name=self._app_name,
            user_id=user_id,
            session_id=session_id,
        )

        if session is None:
            return None

        return self.session_to_dict(session)

    async def list_sessions(self, *, user_id: str) -> dict[str, Any]:
        """列出指定用户的 sessions。"""
        sessions = await self._session_service.list_sessions(
            app_name=self._app_name,
            user_id=user_id,
        )

        return {
            "user_id": user_id,
            "sessions": [
                self.session_to_dict(session)
                for session in sessions.sessions
            ],
        }

    async def session_events(
        self,
        *,
        user_id: str,
        session_id: str,
    ) -> dict[str, Any] | None:
        """返回指定 session 的 events。"""
        session = await self.get_session(
            user_id=user_id,
            session_id=session_id,
        )

        if session is None:
            return None

        events = session.get("events", [])

        return {
            "user_id": user_id,
            "session_id": session_id,
            "events": events,
            "event_count": len(events),
        }

    async def run_events(
        self,
        *,
        user_id: str,
        session_id: str,
        message: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """运行 agent，并持续产出可 JSON 序列化的事件。"""
        session = await self.get_session(
            user_id=user_id,
            session_id=session_id,
        )

        if session is None:
            yield {
                "type": "error",
                "error": f"session 不存在: user_id={user_id}, session_id={session_id}",
            }
            return

        content = types.Content(
            role="user",
            parts=[
                types.Part(text=message),
            ],
        )

        async for event in self._runner.run_async(
            user_id=user_id,
            session_id=session_id,
            new_message=content,
            run_config=self._run_config,
        ):
            yield {
                "type": "event",
                "event": self.event_to_dict(event),
            }

        yield {
            "type": "done",
        }

    async def run_sse_events(
        self,
        *,
        user_id: str,
        session_id: str,
        message: str,
    ) -> AsyncIterator[dict[str, Any]]:
        """返回适合 SSE 输出的事件数据。"""
        async for event in self.run_events(
            user_id=user_id,
            session_id=session_id,
            message=message,
        ):
            yield event

    def list_traces(self) -> list[dict[str, Any]]:
        """返回全部 LLM request traces。"""
        return list_traces()

    def list_traces_by_session_events(
        self,
        *,
        session_data: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """根据 session events 中的 invocation_id 查询 traces。"""
        invocation_ids = {
            event.get("invocation_id")
            for event in session_data.get("events", [])
            if event.get("invocation_id")
        }

        return list_traces_by_invocation_ids(invocation_ids)

    def clear_traces(self) -> None:
        """清空 LLM request traces。"""
        clear_traces()

    def session_to_dict(self, session: Session) -> dict[str, Any]:
        """转换 session 为可 JSON 序列化的字典。"""
        return session.model_dump(mode="json", exclude_none=True)

    def event_to_dict(self, event: Any) -> dict[str, Any]:
        """转换 ADK event 为可 JSON 序列化的字典。"""
        return event_to_dict(event)

    def _create_root_agent(self) -> Agent:
        return Agent(
            name="agent",
            model=LiteLlm(
                model=self._model,
                api_key=self._api_key,
                base_url=self._base_url,
            ),
            description="一个用于学习 Google ADK Runtime 和 Function Tools 的实验智能体。",
            instruction=(
                "你是一个用于 ADK 实验的中文助手。"
                "请使用简体中文回复。"
            ),
            tools=[
                get_weather,
                get_current_time,
            ],
            before_model_callback=self._save_llm_request_callback,
        )

    def _save_llm_request_callback(self, callback_context: Any, llm_request: Any) -> None:
        request = llm_request.model_dump(mode="json", exclude_none=True)

        save_llm_request_trace(
            agent_name=self._get_context_attr(callback_context, "agent_name"),
            invocation_id=self._get_context_attr(callback_context, "invocation_id"),
            user_id=self._get_context_attr(callback_context, "user_id"),
            session_id=self._get_context_attr(callback_context, "session_id"),
            request=request,
        )

        return None

    def _get_context_attr(self, callback_context: Any, name: str) -> Any:
        value = self._get_attr(callback_context, name)
        if value is not None:
            return value

        invocation_context = self._get_attr(callback_context, "_invocation_context")
        value = self._get_attr(invocation_context, name)
        if value is not None:
            return value

        session = self._get_attr(callback_context, "session")
        value = self._get_attr(session, name)
        if value is not None:
            return value

        return None

    def _get_attr(self, obj: Any, name: str) -> Any:
        if obj is None:
            return None

        return getattr(obj, name, None)


agent_runtime = AgentRuntime()