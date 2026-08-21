from datetime import datetime, timezone

from replaygate.capture.replay import turn_diff_flags
from replaygate.dashboard.models import DiffView, TurnDiff, TurnSide
from replaygate.trace.models import Message, ToolCall, Turn

TS = datetime(2026, 6, 29, tzinfo=timezone.utc)


def _turn(index: int, text: str, tools: tuple = ()) -> Turn:
    return Turn(
        index=index,
        user_messages=[Message(role="user", content="u", ts=TS)],
        assistant_messages=[Message(role="assistant", content=text, ts=TS)],
        tool_calls=[
            ToolCall(name=n, arguments=a, result=r, call_id=f"call-{i}")
            for i, (n, a, r) in enumerate(tools)
        ],
    )


def test_turn_diff_flags_identical_turn_is_unchanged():
    t = _turn(0, "same", (("lookup_order", {"order_id": "ORD-1234"}, {"status": "shipped"}),))
    assert turn_diff_flags(t, t) == (False, False)


def test_turn_diff_flags_detects_text_change():
    baseline = _turn(1, "ORD-1234 has shipped — ETA 2026-07-02.")
    current = _turn(1, "Sure — what's your order number?")
    assert turn_diff_flags(baseline, current) == (True, False)


def test_turn_diff_flags_detects_dropped_tool_call():
    baseline = _turn(1, "same", (("lookup_order", {"order_id": "ORD-1234"}, {"ok": True}),))
    current = _turn(1, "same")
    assert turn_diff_flags(baseline, current) == (False, True)


def test_changed_is_a_serialized_computed_field():
    td = TurnDiff(
        index=1,
        user_text="any update on the delivery?",
        baseline=TurnSide(assistant_text="ORD-1234 has shipped — ETA 2026-07-02."),
        current=TurnSide(assistant_text="Sure — what's your order number?"),
        text_changed=True,
    )
    assert td.changed is True
    assert td.model_dump()["changed"] is True


def test_changed_turn_indexes_lists_only_changed_turns():
    unchanged = TurnDiff(
        index=0,
        user_text="my order ORD-1234 — has it shipped?",
        baseline=TurnSide(assistant_text="Let me check ORD-1234 for you."),
        current=TurnSide(assistant_text="Let me check ORD-1234 for you."),
    )
    changed = TurnDiff(
        index=1,
        user_text="any update on the delivery?",
        baseline=TurnSide(assistant_text="ORD-1234 has shipped — ETA 2026-07-02."),
        current=TurnSide(assistant_text="Sure — what's your order number?"),
        text_changed=True,
    )
    view = DiffView(
        run_id="support_happy",
        scenario="support_happy",
        status="failed",
        channel="direct",
        model="claude-haiku-4-5",
        agent_version="dev",
        recorded_at=TS,
        turns=[unchanged, changed],
    )
    assert view.changed_turn_indexes == [1]
    assert view.model_dump()["changed_turn_indexes"] == [1]
