from datetime import datetime, timezone

from replaygate.examples.invariants import user_confirmed_before
from replaygate.trace.models import (
    Conversation,
    Message,
    SessionMeta,
    ToolCall,
    Turn,
)

TS = datetime(2026, 6, 28, tzinfo=timezone.utc)


def _conv(turns):
    return Conversation(
        id="c1",
        scenario="booking",
        channel="direct",
        session_meta=SessionMeta(session_id="s1", started_at=TS),
        turns=turns,
    )


def test_user_confirmed_before_detects_affirmation():
    conv = _conv([
        Turn(index=0, assistant_messages=[Message(role="assistant", content="Confirm booking for 3pm?", ts=TS)]),
        Turn(index=1, user_messages=[Message(role="user", content="yes please", ts=TS)]),
        Turn(index=2, tool_calls=[ToolCall(name="book_appointment", arguments={}, call_id="c")]),
    ])
    assert user_confirmed_before(conv, 2) is True
    assert user_confirmed_before(conv, 1) is False


def test_all_tool_calls_flattens():
    conv = _conv([
        Turn(index=0, tool_calls=[ToolCall(name="search_slots", arguments={}, call_id="a")]),
        Turn(index=1, tool_calls=[ToolCall(name="book_appointment", arguments={}, call_id="b")]),
    ])
    assert [t.name for t in conv.all_tool_calls()] == ["search_slots", "book_appointment"]
