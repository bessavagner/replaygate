from datetime import datetime, timedelta, timezone

from replaygate.capture.adapters import Scenario
from replaygate.channels.scripted import ScriptedBurst, ScriptedInbound, ScriptedTransport
from replaygate.channels.whatsapp import WhatsAppAdapter

START = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)
SCENARIO = Scenario(name="whatsapp_support", user_turns=[])


def _adapter(bursts, **kwargs):
    return WhatsAppAdapter(ScriptedTransport(bursts, start=START), **kwargs)


def test_a_burst_of_messages_is_one_turn():
    adapter = _adapter([
        ScriptedBurst(messages=[
            ScriptedInbound(id="WA-1", text="hey there"),
            ScriptedInbound(id="WA-2", text="my order ORD-1234", after_s=1),
        ]),
    ])
    turns = list(adapter.user_turns(SCENARIO))
    assert len(turns) == 1
    assert [m.content for m in turns[0]] == ["hey there", "my order ORD-1234"]
    assert all(m.role == "user" for m in turns[0])


def test_channel_meta_carries_the_message_id_and_send_position():
    adapter = _adapter([
        ScriptedBurst(messages=[
            ScriptedInbound(id="WA-1", text="hey there"),
            ScriptedInbound(id="WA-2", text="my order ORD-1234", after_s=1),
        ]),
    ])
    turn = next(iter(adapter.user_turns(SCENARIO)))
    assert [m.channel_meta.message_id for m in turn] == ["WA-1", "WA-2"]
    assert [m.channel_meta.order_index for m in turn] == [0, 1]


def test_an_out_of_order_burst_is_restored_to_send_order():
    adapter = _adapter([
        ScriptedBurst(
            messages=[
                ScriptedInbound(id="WA-1", text="hey there"),
                ScriptedInbound(id="WA-2", text="my order ORD-1234", after_s=1),
            ],
            deliver_out_of_order=True,
        ),
    ])
    turn = next(iter(adapter.user_turns(SCENARIO)))
    assert [m.channel_meta.message_id for m in turn] == ["WA-1", "WA-2"]
    assert [m.channel_meta.order_index for m in turn] == [0, 1]
    assert turn[0].ts < turn[1].ts


def test_separate_bursts_are_separate_turns():
    adapter = _adapter([
        ScriptedBurst(messages=[ScriptedInbound(id="WA-1", text="first")]),
        ScriptedBurst(messages=[ScriptedInbound(id="WA-2", text="second")], gap_s=120),
    ])
    turns = list(adapter.user_turns(SCENARIO))
    assert [[m.content for m in t] for t in turns] == [["first"], ["second"]]


def test_user_turns_stops_at_max_turns():
    bursts = [ScriptedBurst(messages=[ScriptedInbound(id=f"WA-{i}", text=str(i))]) for i in range(5)]
    adapter = _adapter(bursts, max_turns=2)
    assert len(list(adapter.user_turns(SCENARIO))) == 2


def test_user_turns_stops_when_the_channel_goes_idle():
    adapter = _adapter([ScriptedBurst(messages=[ScriptedInbound(id="WA-1", text="only one")])])
    # The script has one burst; the adapter would take up to 20 turns but the
    # second poll times out, which ends the recording.
    assert len(list(adapter.user_turns(SCENARIO))) == 1


def test_deliver_sends_through_the_transport_and_returns_channel_meta():
    adapter = _adapter([ScriptedBurst(messages=[ScriptedInbound(id="WA-1", text="hi")])])
    first = adapter.deliver("hello back")
    second = adapter.deliver("and again")
    assert (first.message_id, first.order_index) == ("OUT-1", 0)
    assert (second.message_id, second.order_index) == ("OUT-2", 1)


def test_session_window_expiry_is_24h_after_the_last_inbound():
    adapter = _adapter([
        ScriptedBurst(messages=[ScriptedInbound(id="WA-1", text="hi")], gap_s=0),
    ])
    assert adapter.session_window_expiry() is None  # nothing inbound yet
    turn = next(iter(adapter.user_turns(SCENARIO)))
    assert adapter.session_window_expiry() == turn[-1].ts + timedelta(hours=24)
