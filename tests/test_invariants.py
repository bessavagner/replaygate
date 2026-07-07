from datetime import datetime, timezone

from replaygate.examples.invariants import (
    booked_only_after_confirmation,
    dietary_constraint_honored,
    order_id_never_reasked,
)
from replaygate.invariants import check_conversation, invariants_for
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


def _assistant(text):
    return Message(role="assistant", content=text, ts=TS)


def test_order_id_carried_forward_passes():
    conv = _conv("support_happy", [
        Turn(index=0, user_messages=[_user("my order ORD-1234 — has it shipped?")],
             assistant_messages=[_assistant("Let me check ORD-1234.")]),
        Turn(index=1, user_messages=[_user("any update?")],
             assistant_messages=[_assistant("ORD-1234 has shipped.")]),
    ])
    assert order_id_never_reasked(conv).passed is True


def test_order_id_reasked_fails():
    conv = _conv("support_reask_regression", [
        Turn(index=0, user_messages=[_user("my order ORD-1234 — has it shipped?")],
             assistant_messages=[_assistant("Let me check ORD-1234.")]),
        Turn(index=1, user_messages=[_user("any update?")],
             assistant_messages=[_assistant("Sure — what's your order number?")]),
    ])
    result = order_id_never_reasked(conv)
    assert result.passed is False
    assert "turn 1" in result.detail


def _rec_call(contains_dairy):
    return ToolCall(name="recommend_dish", arguments={"avoid_dairy": not contains_dairy},
                    result={"dish": "x", "contains_dairy": contains_dairy}, call_id="c1")


def test_dietary_constraint_honored_passes():
    conv = _conv("profile_happy", [
        Turn(index=0, user_messages=[_user("hi, I'm vegan — no dairy please")]),
        Turn(index=1, user_messages=[_user("what should I order?")], tool_calls=[_rec_call(False)]),
    ])
    assert dietary_constraint_honored(conv).passed is True


def test_dietary_constraint_violated_fails():
    conv = _conv("profile_forgets_regression", [
        Turn(index=0, user_messages=[_user("hi, I'm vegan — no dairy please")]),
        Turn(index=1, user_messages=[_user("what should I order?")], tool_calls=[_rec_call(True)]),
    ])
    result = dietary_constraint_honored(conv)
    assert result.passed is False
    assert "turn 1" in result.detail


def test_registry_maps_booking_scenarios():
    invs = invariants_for("booking_happy")
    assert [i.__name__ for i in invs] == ["booked_only_after_confirmation"]
    assert invariants_for("unknown_scenario") == []


def test_check_conversation_runs_all_registered():
    conv = _conv("booking_happy", [
        Turn(index=0, user_messages=[_user("what slots?")]),
        Turn(index=1, user_messages=[_user("yes, book 3pm")], tool_calls=[_book_call()]),
    ])
    results = check_conversation(conv, invariants_for("booking_happy"))
    assert len(results) == 1
    assert results[0].passed is True
