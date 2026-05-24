from __future__ import annotations

import json
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse

from agent.runtime import agent_runtime
from app.routes_trace import router as trace_router
from app.schemas import CreateSessionRequest, RunSSERequest


app = FastAPI(title="ADK Lab")
app.include_router(trace_router)


def encode_sse(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/sessions")
async def create_session_api(request: CreateSessionRequest) -> dict[str, Any]:
    return await agent_runtime.create_session(
        user_id=request.user_id,
        session_id=request.session_id,
        state=request.state,
    )


@app.get("/sessions")
async def list_sessions_api(
    user_id: str = Query(default="kwen", description="用户 ID"),
) -> dict[str, Any]:
    return await agent_runtime.list_sessions(
        user_id=user_id,
    )


@app.get("/sessions/{session_id}/events")
async def get_session_events_api(
    session_id: str,
    user_id: str = Query(default="kwen", description="用户 ID"),
) -> dict[str, Any]:
    result = await agent_runtime.session_events(
        user_id=user_id,
        session_id=session_id,
    )

    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"session 不存在: user_id={user_id}, session_id={session_id}",
        )

    return result


@app.post("/run_sse")
async def run_sse(request: RunSSERequest) -> StreamingResponse:
    async def event_stream() -> AsyncIterator[str]:
        async for event in agent_runtime.run_sse_events(
            user_id=request.user_id,
            session_id=request.session_id,
            message=request.message,
        ):
            yield encode_sse(event)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )