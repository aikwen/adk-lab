from pydantic import BaseModel, Field

from typing import Any

from pydantic import BaseModel, Field


class RunSSERequest(BaseModel):
    user_id: str = Field(default="kwen", description="用户 ID")
    session_id: str = Field(default="default", description="会话 ID")
    message: str = Field(..., description="用户输入内容")


class CreateSessionRequest(BaseModel):
    user_id: str = Field(default="kwen", description="用户 ID")
    session_id: str = Field(default="default", description="会话 ID")
    state: dict[str, Any] | None = Field(default=None, description="初始会话状态")