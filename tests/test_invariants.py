from datetime import datetime, timezone

from replaygate.invariants import booked_only_after_confirmation
from replaygate.trace.models import Conversation, Message, SessionMeta, ToolCall, Turn

TS = datetime(2026, 6, 30, tzinfo=timezone.utc)


def _conv(scenario, turns):
    return Conversation(
        id="c", scenario=scenario, channel="direct",
        session_meta=SessionMeta(session_id="s", started_at=TS), turns=turns,
    )


def _user(text):
    return Message(role="user", content=text, ts=TS)


def _book_call():
    return ToolCall(name="book_appointment", arguments={"slot": "3pm"},
                    result={"booked": True, "slot": "3pm"}, call_id="c1")


def test_booking_after_confirmation_passes():
    conv = _conv("booking_happy", [
        Turn(index=0, user_messages=[_user("what slots on 2026-07-01?")]),
        Turn(index=1, user_messages=[_user("yes, book 3pm")], tool_calls=[_book_call()]),
    ])
    result = booked_only_after_confirmation(conv)
    assert result.passed is True
    assert result.name == "booked_only_after_confirmation"


def test_booking_without_confirmation_fails():
    conv = _conv("booking_books_without_confirm_regression", [
        Turn(index=0, user_messages=[_user("what slots on 2026-07-01?")]),
        Turn(index=1, user_messages=[_user("hmm, let me think about it")], tool_calls=[_book_call()]),
    ])
    result = booked_only_after_confirmation(conv)
    assert result.passed is False
    assert "turn 1" in result.detail
