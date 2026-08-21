"""The offline stand-in for the Node sidecar.

Drives a virtual clock: ``poll`` advances it by whatever the script says the
channel made us wait, so a 30-hour silence costs a test zero seconds. Every
automated test in this sprint runs against this, never against WhatsApp.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from replaygate.channels.transport import InboundMessage


@dataclass(frozen=True)
class ScriptedInbound:
    id: str
    text: str
    after_s: float = 0.0
    """Seconds after the previous message in this burst."""


@dataclass(frozen=True)
class ScriptedBurst:
    messages: list[ScriptedInbound] = field(default_factory=list)
    gap_s: float = 5.0
    """Idle seconds before this burst's first message."""
    reply_after_s: float = 1.0
    """How long the agent takes to answer this burst."""
    deliver_out_of_order: bool = False
    """Hand the burst to the adapter reversed, as a reconnect would."""


class ScriptedTransport:
    def __init__(self, bursts: list[ScriptedBurst], start: datetime):
        self._bursts = list(bursts)
        self._clock = start
        self._burst_open = False
        self._sent = 0
        self._pending_reply_after = 0.0

    def now(self) -> datetime:
        return self._clock

    def poll(self, timeout_s: float) -> list[InboundMessage]:
        # A real sidecar delivers a burst, then goes quiet for the caller's gap.
        # Mirror that exactly: the poll after a burst closes it, it does not pop
        # the next one.
        if self._burst_open or not self._bursts:
            self._burst_open = False
            self._clock += timedelta(seconds=timeout_s)
            return []
        burst = self._bursts.pop(0)
        self._clock += timedelta(seconds=burst.gap_s)
        messages: list[InboundMessage] = []
        for spec in burst.messages:
            self._clock += timedelta(seconds=spec.after_s)
            messages.append(InboundMessage(id=spec.id, text=spec.text, sent_at=self._clock))
        self._pending_reply_after = burst.reply_after_s
        self._burst_open = True
        return list(reversed(messages)) if burst.deliver_out_of_order else messages

    def send(self, text: str) -> str:
        self._clock += timedelta(seconds=self._pending_reply_after)
        self._pending_reply_after = 0.0
        self._sent += 1
        return f"OUT-{self._sent}"
