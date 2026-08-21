"""Cross-turn invariants that only exist because there is a channel.

Scenario-agnostic, like ``replaygate.invariants``: these are properties of a
*channel recording*, not of any one agent. Concrete scenarios register them in
``replaygate.examples.invariants``.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from replaygate.invariants import InvariantResult
from replaygate.trace.models import Conversation

SESSION_WINDOW = timedelta(hours=24)


def _hours(delta: timedelta) -> str:
    return f"{delta.total_seconds() / 3600:.1f}h"


def messages_in_send_order(conv: Conversation) -> InvariantResult:
    """Within every turn, ``order_index`` must be 0..n-1 and agree with ``ts``.

    A WhatsApp burst can arrive backwards after a reconnect. The adapter sorts by
    send time before building the turn; this asserts the recording on disk kept
    that order, so a replay reads the conversation the way the human wrote it —
    and a future adapter that stops sorting fails here instead of silently
    feeding the agent a scrambled turn.
    """
    name = "messages_in_send_order"
    for turn in conv.turns:
        msgs = [m for m in turn.user_messages if m.channel_meta is not None]
        if not msgs:
            continue
        indexes = [m.channel_meta.order_index for m in msgs]
        if indexes != list(range(len(msgs))):
            return InvariantResult(
                name=name, passed=False,
                detail=f"turn {turn.index}: order_index {indexes} is not 0..{len(msgs) - 1}",
            )
        stamps = [m.ts for m in msgs]
        if stamps != sorted(stamps):
            return InvariantResult(
                name=name, passed=False,
                detail=(f"turn {turn.index}: messages are indexed {indexes} but their "
                        "send times run the other way"),
            )
    return InvariantResult(name=name, passed=True, detail="every burst is in send order")


def no_reply_after_session_window(conv: Conversation) -> InvariantResult:
    """No assistant message may go out more than 24h after the last inbound one.

    WhatsApp closes the customer-service window 24 hours after the customer's last
    message; a free-form reply after that is rejected by the platform. An agent
    that takes a day to answer has regressed even if every word is right — the
    message never arrives. No per-turn assertion can see this: it is a property of
    two turns and the wall clock between them.
    """
    name = "no_reply_after_session_window"
    window_opened_at: datetime | None = None
    for turn in conv.turns:
        if turn.user_messages:
            window_opened_at = max(m.ts for m in turn.user_messages)
        if window_opened_at is None:
            continue
        deadline = window_opened_at + SESSION_WINDOW
        for m in turn.assistant_messages:
            if m.ts > deadline:
                return InvariantResult(
                    name=name, passed=False,
                    detail=(f"turn {turn.index}: replied {_hours(m.ts - window_opened_at)} "
                            "after the last inbound message — outside the 24h session window"),
                )
    return InvariantResult(
        name=name, passed=True, detail="every reply landed inside the 24h session window"
    )
