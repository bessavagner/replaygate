from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterator, Protocol

from pydantic import BaseModel

from replaygate.trace.models import ChannelMeta, Message


class Scenario(BaseModel):
    name: str
    user_turns: list[list[str]]


class ChannelAdapter(Protocol):
    """How a channel feeds turns in and pushes replies out.

    ``user_turns`` is the inbound half and was the whole protocol until WhatsApp:
    a scripted channel has nothing to push back. A live one does, so the protocol
    also owns the outbound side (``deliver``), the channel's clock (``now``), and
    whatever session rule the channel enforces (``session_window_expiry``).
    """

    name: str
    channel: str

    def user_turns(self, scenario: Scenario) -> Iterator[list[Message]]: ...

    def now(self) -> datetime:
        """The channel's clock, used to stamp outbound messages."""
        ...

    def deliver(self, text: str) -> ChannelMeta | None:
        """Push one assistant message out; ``None`` when the channel has no outbound side."""
        ...

    def session_window_expiry(self) -> datetime | None:
        """When the channel stops accepting free-form replies, if it ever does."""
        ...


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

    def now(self) -> datetime:
        return datetime.now(timezone.utc)

    def deliver(self, text: str) -> ChannelMeta | None:
        return None  # there is no wire to push a direct-mode reply onto

    def session_window_expiry(self) -> datetime | None:
        return None  # a direct conversation never expires
