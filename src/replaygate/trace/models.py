from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

Role = Literal["user", "assistant", "tool", "system"]


class ChannelMeta(BaseModel):
    message_id: str | None = None
    order_index: int | None = None


class Message(BaseModel):
    role: Role
    content: str
    ts: datetime
    channel_meta: ChannelMeta | None = None


class ToolCall(BaseModel):
    name: str
    arguments: dict
    result: dict | None = None
    error: str | None = None
    call_id: str
