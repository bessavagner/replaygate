from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

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


class Turn(BaseModel):
    index: int
    user_messages: list[Message] = Field(default_factory=list)
    assistant_messages: list[Message] = Field(default_factory=list)
    tool_calls: list[ToolCall] = Field(default_factory=list)


_AFFIRMATIONS = {"yes", "yep", "yeah", "sure", "ok", "okay", "confirm", "please do", "go ahead"}


class SessionMeta(BaseModel):
    session_id: str
    started_at: datetime
    window_expired_at: datetime | None = None


class Conversation(BaseModel):
    id: str
    scenario: str
    channel: Literal["direct", "whatsapp"]
    session_meta: SessionMeta
    turns: list[Turn] = Field(default_factory=list)
    agent_version: str = ""
    model: str = ""

    def all_tool_calls(self) -> list[ToolCall]:
        return [tc for turn in self.turns for tc in turn.tool_calls]

    def tool_results(self) -> list[ToolCall]:
        return [tc for tc in self.all_tool_calls() if tc.result is not None]

    def user_confirmed_before(self, turn_index: int) -> bool:
        for turn in self.turns:
            if turn.index >= turn_index:
                break
            for msg in turn.user_messages:
                text = msg.content.strip().lower()
                if any(text == a or text.startswith(a + " ") or a in text.split() for a in _AFFIRMATIONS):
                    return True
        return False
