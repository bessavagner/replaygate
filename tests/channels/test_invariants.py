from datetime import datetime, timedelta, timezone

from replaygate.channels.invariants import (
    messages_in_send_order,
    no_reply_after_session_window,
)
from replaygate.trace.models import ChannelMeta, Conversation, Message, SessionMeta, Turn

START = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)


def _user(text, offset_s, index, mid):
    return Message(
        role="user",
        content=text,
        ts=START + timedelta(seconds=offset_s),
        channel_meta=ChannelMeta(message_id=mid, order_index=index),
    )


def _assistant(text, offset_s):
    return Message(role="assistant", content=text, ts=START + timedelta(seconds=offset_s))


def _conv(turns):
    return Conversation(
        id="c1",
        scenario="whatsapp_support",
        channel="whatsapp",
        session_meta=SessionMeta(session_id="s1", started_at=START),
        turns=turns,
    )


def test_send_order_holds_for_a_well_ordered_burst():
    conv = _conv([Turn(
        index=0,
        user_messages=[_user("hey", 0, 0, "WA-1"), _user("ORD-1234", 1, 1, "WA-2")],
        assistant_messages=[_assistant("checking", 5)],
    )])
    result = messages_in_send_order(conv)
    assert result.passed
    assert result.name == "messages_in_send_order"


def test_send_order_fails_when_order_index_contradicts_the_send_times():
    conv = _conv([Turn(
        index=0,
        # order_index says WA-2 came first; its timestamp says otherwise.
        user_messages=[_user("ORD-1234", 1, 0, "WA-2"), _user("hey", 0, 1, "WA-1")],
    )])
    result = messages_in_send_order(conv)
    assert not result.passed
    assert "turn 0" in result.detail


def test_send_order_ignores_turns_without_channel_metadata():
    conv = _conv([Turn(
        index=0,
        user_messages=[Message(role="user", content="hi", ts=START)],
    )])
    assert messages_in_send_order(conv).passed


def test_a_prompt_reply_is_inside_the_session_window():
    conv = _conv([Turn(
        index=0,
        user_messages=[_user("hey", 0, 0, "WA-1")],
        assistant_messages=[_assistant("hi", 60)],
    )])
    result = no_reply_after_session_window(conv)
    assert result.passed
    assert result.name == "no_reply_after_session_window"


def test_a_reply_after_24h_violates_the_session_window():
    conv = _conv([
        Turn(index=0, user_messages=[_user("hey", 0, 0, "WA-1")],
             assistant_messages=[_assistant("hi", 60)]),
        Turn(index=1, user_messages=[_user("any update?", 120, 0, "WA-2")],
             assistant_messages=[_assistant("sorry for the delay", 120 + 30 * 3600)]),
    ])
    result = no_reply_after_session_window(conv)
    assert not result.passed
    assert "turn 1" in result.detail
    assert "30.0h" in result.detail


def test_the_window_reopens_on_every_inbound_burst():
    # 20h, then a new inbound, then another 20h reply: each is inside its own window.
    conv = _conv([
        Turn(index=0, user_messages=[_user("hey", 0, 0, "WA-1")],
             assistant_messages=[_assistant("hi", 20 * 3600)]),
        Turn(index=1, user_messages=[_user("still there?", 21 * 3600, 0, "WA-2")],
             assistant_messages=[_assistant("yes", 41 * 3600)]),
    ])
    assert no_reply_after_session_window(conv).passed
