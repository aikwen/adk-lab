import time
import uuid
from typing import Any


_traces: list[dict[str, Any]] = []


def save_llm_request_trace(
    *,
    agent_name: str | None,
    invocation_id: str | None,
    user_id: str | None,
    session_id: str | None,
    request: dict[str, Any],
) -> dict[str, Any]:
    trace = {
        "trace_id": str(uuid.uuid4()),
        "type": "llm_request",
        "agent_name": agent_name,
        "invocation_id": invocation_id,
        "user_id": user_id,
        "session_id": session_id,
        "request": request,
        "timestamp": time.time(),
    }

    _traces.append(trace)
    return trace


def list_traces() -> list[dict[str, Any]]:
    return _traces


def list_traces_by_invocation_ids(invocation_ids: set[str]) -> list[dict[str, Any]]:
    return [
        trace
        for trace in _traces
        if trace.get("invocation_id") in invocation_ids
    ]


def clear_traces() -> None:
    _traces.clear()