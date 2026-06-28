from datetime import datetime, timezone

from replaygate.trace.models import ChannelMeta, Message, ToolCall, Turn


def test_message_roundtrips_json():
    m = Message(
        role="user",
        content="hi",
        ts=datetime(2026, 6, 28, tzinfo=timezone.utc),
        channel_meta=ChannelMeta(message_id="wamid.1", order_index=0),
    )
    dumped = m.model_dump_json()
    loaded = Message.model_validate_json(dumped)
    assert loaded == m


def test_toolcall_defaults():
    tc = ToolCall(name="search_slots", arguments={"date": "2026-07-01"}, call_id="c1")
    assert tc.result is None and tc.error is None


def test_turn_collects_multi_message_user_turn():
    t = Turn(
        index=0,
        user_messages=[
            Message(role="user", content="I want", ts=datetime(2026, 6, 28, tzinfo=timezone.utc)),
            Message(role="user", content="to book", ts=datetime(2026, 6, 28, tzinfo=timezone.utc)),
        ],
    )
    assert t.index == 0
    assert len(t.user_messages) == 2
    assert t.tool_calls == []
