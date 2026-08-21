"""The seam between ReplayGate and a channel process.

Deliberately tiny: three synchronous methods over plain data. The Node sidecar is
an HTTP *server* and Python is only ever a *client*, so nothing in the recording
process listens on a socket — and a fake transport is ten lines, which is what
keeps the WhatsApp path inside the offline test suite.
"""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from pydantic import BaseModel


class InboundMessage(BaseModel):
    """One message the channel delivered to us.

    ``sent_at`` is the *sender's* timestamp, which is not necessarily arrival
    order — WhatsApp redelivers after a reconnect. ``WhatsAppAdapter`` sorts on it.

    There is deliberately no sender field. The sidecar strips the JID before it
    ever reaches Python: ReplayGate learns what was said and when, never who by.
    """

    id: str
    text: str
    sent_at: datetime


class ChannelTransport(Protocol):
    def poll(self, timeout_s: float) -> list[InboundMessage]:
        """Block up to ``timeout_s`` for inbound messages; ``[]`` means the wait elapsed."""
        ...

    def send(self, text: str) -> str:
        """Send an outbound message; return the channel's id for it."""
        ...

    def now(self) -> datetime:
        """The channel's clock — wall clock for a real transport, virtual for a fake."""
        ...
