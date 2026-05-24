from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from agent.runtime import agent_runtime


router = APIRouter(tags=["traces"])


@router.get("/traces")
async def list_all_traces_api() -> dict[str, Any]:
    traces = agent_runtime.list_traces()

    return {
        "traces": traces,
        "trace_count": len(traces),
    }


@router.get("/sessions/{session_id}/traces")
async def list_session_traces_api(
    session_id: str,
    user_id: str = Query(default="kwen", description="用户 ID"),
) -> dict[str, Any]:
    session = await agent_runtime.get_session(
        user_id=user_id,
        session_id=session_id,
    )

    if session is None:
        raise HTTPException(
            status_code=404,
            detail=f"session 不存在: user_id={user_id}, session_id={session_id}",
        )

    traces = agent_runtime.list_traces_by_session_events(
        session_data=session,
    )

    invocation_ids = {
        event.get("invocation_id")
        for event in session.get("events", [])
        if event.get("invocation_id")
    }

    return {
        "user_id": user_id,
        "session_id": session_id,
        "invocation_ids": list(invocation_ids),
        "traces": traces,
        "trace_count": len(traces),
    }


@router.delete("/traces")
async def clear_traces_api() -> dict[str, Any]:
    agent_runtime.clear_traces()

    return {
        "status": "ok",
        "message": "traces cleared",
    }