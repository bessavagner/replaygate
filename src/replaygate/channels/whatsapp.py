"""Turn a live WhatsApp thread into ReplayGate turns.

Two channel realities are handled here and nowhere else.

*Bursts.* People send "hey there" and "my order is ORD-1234" one second apart.
That is one turn, not two — treat each message as a turn and the agent answers a
greeting with an order lookup. A turn closes when ``burst_quiet_s`` elapse with
no new inbound message.

*Send order is not arrival order.* WhatsApp redelivers after a reconnect, so a
burst can arrive backwards. The burst is sorted by ``(sent_at, id)`` before it
becomes a turn and ``ChannelMeta.order_index`` records the *send* position, so a
replay reads the conversation the way the human wrote it. The
``messages_in_send_order`` invariant asserts the recording on disk kept that.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterator

from replaygate.capture.adapters import Scenario
from replaygate.channels.transport import ChannelTransport, InboundMessage
from replaygate.trace.models import ChannelMeta, Message

SESSION_WINDOW = timedelta(hours=24)


class WhatsAppAdapter:
    name = "whatsapp"
    channel = "whatsapp"

    SESSION_WINDOW = SESSION_WINDOW

    def __init__(
        self,
        transport: ChannelTransport,
        *,
        max_turns: int = 20,
        burst_quiet_s: float = 2.0,
        idle_timeout_s: float = 300.0,
    ):
        self._transport = transport
        self._max_turns = max_turns
        self._burst_quiet_s = burst_quiet_s
        self._idle_timeout_s = idle_timeout_s
        self._last_inbound_at: datetime | None = None
        self._outbound_count = 0

    def now(self) -> datetime:
        return self._transport.now()

    def user_turns(self, scenario: Scenario) -> Iterator[list[Message]]:
        """Yield one burst per turn.

        ``scenario`` names the run and nothing more: its ``user_turns`` are
        ignored, because on a live channel the human writes them.
        """
        for _ in range(self._max_turns):
            burst = self._collect_burst()
            if not burst:
                return  # the channel went idle — the conversation is over
            self._last_inbound_at = max(m.sent_at for m in burst)
            ordered = sorted(burst, key=lambda m: (m.sent_at, m.id))
            yield [
                Message(
                    role="user",
                    content=m.text,
                    ts=m.sent_at,
                    channel_meta=ChannelMeta(message_id=m.id, order_index=i),
                )
                for i, m in enumerate(ordered)
            ]

    def _collect_burst(self) -> list[InboundMessage]:
        burst: list[InboundMessage] = []
        while True:
            timeout = self._burst_quiet_s if burst else self._idle_timeout_s
            batch = self._transport.poll(timeout)
            if batch:
                burst.extend(batch)
                continue
            # An empty poll either closed the burst or proved nobody is talking.
            return burst

    def deliver(self, text: str) -> ChannelMeta:
        message_id = self._transport.send(text)
        meta = ChannelMeta(message_id=message_id, order_index=self._outbound_count)
        self._outbound_count += 1
        return meta

    def session_window_expiry(self) -> datetime | None:
        if self._last_inbound_at is None:
            return None
        return self._last_inbound_at + SESSION_WINDOW
