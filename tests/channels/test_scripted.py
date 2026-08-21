from datetime import datetime, timezone

from replaygate.channels.scripted import ScriptedBurst, ScriptedInbound, ScriptedTransport

START = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def _transport(**kwargs):
    burst = ScriptedBurst(
        messages=[
            ScriptedInbound(id="WA-1", text="hey there", after_s=0),
            ScriptedInbound(id="WA-2", text="my order ORD-1234", after_s=1),
        ],
        gap_s=10,
        reply_after_s=4,
        **kwargs,
    )
    return ScriptedTransport([burst], start=START)


def test_poll_returns_a_whole_burst_then_an_empty_close():
    t = _transport()
    first = t.poll(2.0)
    assert [m.id for m in first] == ["WA-1", "WA-2"]
    # The next poll closes the burst rather than popping the following one.
    assert t.poll(2.0) == []


def test_the_clock_advances_by_the_scripted_gaps():
    t = _transport()
    t.poll(2.0)
    # 10s idle gap + 0s + 1s between the two messages.
    assert (t.now() - START).total_seconds() == 11
    t.poll(2.0)  # the 2s quiet gap that closes the burst really elapses
    assert (t.now() - START).total_seconds() == 13


def test_send_advances_the_clock_by_the_reply_delay_and_returns_an_id():
    t = _transport()
    t.poll(2.0)
    before = t.now()
    assert t.send("Let me check ORD-1234 for you.") == "OUT-1"
    assert (t.now() - before).total_seconds() == 4


def test_out_of_order_delivery_hands_the_burst_over_reversed():
    t = _transport(deliver_out_of_order=True)
    got = t.poll(2.0)
    assert [m.id for m in got] == ["WA-2", "WA-1"]
    # Send times still reflect the true send order, whatever the arrival order.
    assert got[0].sent_at > got[1].sent_at


def test_an_exhausted_script_polls_empty_and_still_advances_the_clock():
    t = ScriptedTransport([], start=START)
    assert t.poll(300.0) == []
    assert (t.now() - START).total_seconds() == 300
