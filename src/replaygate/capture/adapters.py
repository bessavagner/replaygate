from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator, Protocol

from pydantic import BaseModel

from replaygate.trace.models import ChannelMeta, Message


class Scenario(BaseModel):
    name: str
    user_turns: list[list[str]]


class ChannelAdapter(Protocol):
    name: str
    channel: str

    def user_turns(self, scenario: Scenario) -> Iterator[list[Message]]: ...


class DirectAdapter:
    name = "direct"
    channel = "direct"

    def user_turns(self, scenario: Scenario) -> Iterator[list[Message]]:
        for turn in scenario.user_turns:
            yield [
                Message(
                    role="user",
                    content=text,
                    ts=datetime.now(timezone.utc),
                    channel_meta=ChannelMeta(order_index=i),
                )
                for i, text in enumerate(turn)
            ]
