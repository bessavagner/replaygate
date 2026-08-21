from datetime import datetime, timedelta, timezone

from replaygate.capture.adapters import Scenario
from replaygate.capture.llm import LLMResponse
from replaygate.capture.record import record_conversation
from replaygate.capture.replay import replay_conversation
from replaygate.channels.scripted import ScriptedBurst, ScriptedInbound, ScriptedTransport
from replaygate.channels.whatsapp import WhatsAppAdapter
from replaygate.examples.support_agent import SupportAgent, support_tools

START = datetime(2026, 8, 21, 12, 0, tzinfo=timezone.utc)

BURSTS = [
    ScriptedBurst(
        messages=[
            ScriptedInbound(id="WA-1", text="hey there"),
            ScriptedInbound(id="WA-2", text="my order ORD-1234 — has it shipped?", after_s=1),
        ],
        gap_s=0,
        reply_after_s=4,
    ),
    ScriptedBurst(
        messages=[ScriptedInbound(id="WA-3", text="any update on the delivery?")],
        gap_s=120,
        reply_after_s=6,
    ),
]


class ScriptedLLM:
    def __init__(self, responses):
        self._responses = list(responses)

    def create(self, model, system, messages, tools):
        return self._responses.pop(0)


def _record(bursts=BURSTS):
    transport = ScriptedTransport(bursts, start=START)
    return record_conversation(
        agent_factory=lambda llm, tools: SupportAgent(llm=llm, tools=tools),
        inner_llm=ScriptedLLM([
            LLMResponse(text="Let me check ORD-1234 for you."),
            LLMResponse(text="ORD-1234 has shipped — ETA 2026-07-02."),
        ]),
        scenario=Scenario(name="whatsapp_support", user_turns=[]),
        adapter=WhatsAppAdapter(transport),
        tools=support_tools(),
        agent_version="test",
        model="claude-haiku-4-5",
        recorded_at=START,
    )


def test_recording_stamps_outbound_messages_from_the_channel():
    conv = _record().conversation
    assert conv.channel == "whatsapp"
    outbound = [m for t in conv.turns for m in t.assistant_messages]
    assert [m.channel_meta.message_id for m in outbound] == ["OUT-1", "OUT-2"]
    assert [m.channel_meta.order_index for m in outbound] == [0, 1]


def test_the_assistant_timestamp_is_the_send_time_not_the_run_start():
    conv = _record().conversation
    first_reply = conv.turns[0].assistant_messages[0]
    last_inbound = conv.turns[0].user_messages[-1].ts
    # 2s of quiet closes the burst, then the scripted 4s reply delay. Both are
    # channel time and both belong in the recording.
    assert (first_reply.ts - last_inbound).total_seconds() == 6
    assert first_reply.ts > conv.session_meta.started_at


def test_session_meta_records_when_the_window_closes():
    conv = _record().conversation
    last_inbound = conv.turns[-1].user_messages[-1].ts
    assert conv.session_meta.window_expired_at == last_inbound + timedelta(hours=24)


def test_replay_carries_the_recorded_send_times_forward():
    fixture = _record()
    replayed = replay_conversation(
        fixture, lambda llm, tools: SupportAgent(llm=llm, tools=tools), support_tools()
    )
    recorded_ts = [m.ts for t in fixture.conversation.turns for m in t.assistant_messages]
    replayed_ts = [m.ts for t in replayed.turns for m in t.assistant_messages]
    assert replayed_ts == recorded_ts
    replayed_ids = [m.channel_meta.message_id for t in replayed.turns for m in t.assistant_messages]
    assert replayed_ids == ["OUT-1", "OUT-2"]
