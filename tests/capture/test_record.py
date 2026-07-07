from datetime import datetime, timezone

from replaygate.capture.adapters import DirectAdapter, Scenario
from replaygate.capture.llm import LLMResponse
from replaygate.capture.record import record_conversation
from replaygate.examples.booking_agent import BookingAgent, booking_tools

TS = datetime(2026, 6, 28, tzinfo=timezone.utc)


class ScriptedLLM:
    def __init__(self, responses):
        self._responses = list(responses)

    def create(self, model, system, messages, tools):
        return self._responses.pop(0)


def test_record_builds_fixture_with_turns_and_recordings():
    scenario = Scenario(name="booking", user_turns=[["what slots on 2026-07-01?"], ["yes, 3pm"]])
    inner = ScriptedLLM([
        LLMResponse(text="There are 10am and 3pm.", tool_calls=[
            {"name": "search_slots", "arguments": {"date": "2026-07-01"}}]),
        LLMResponse(text="Booked 3pm.", tool_calls=[
            {"name": "book_appointment", "arguments": {"slot": "3pm"}}]),
    ])
    fixture = record_conversation(
        agent_factory=lambda llm, tools: BookingAgent(llm=llm, tools=tools),
        inner_llm=inner,
        scenario=scenario,
        adapter=DirectAdapter(),
        tools=booking_tools(),
        agent_version="abc123",
        model="claude-haiku-4-5",
        recorded_at=TS,
    )
    assert len(fixture.conversation.turns) == 2
    assert [tc.name for tc in fixture.conversation.all_tool_calls()] == ["search_slots", "book_appointment"]
    assert len(fixture.llm_recording) == 2
    assert len(fixture.tool_recording) == 2
    assert fixture.meta.agent_version == "abc123"


def _counter_clock():
    t = [0]

    def clock() -> int:
        t[0] += 1
        return t[0]

    return clock


def test_record_emits_conversation_and_call_spans():
    scenario = Scenario(name="booking", user_turns=[["what slots on 2026-07-01?"], ["yes, 3pm"]])
    inner = ScriptedLLM([
        LLMResponse(text="There are 10am and 3pm.", tool_calls=[
            {"name": "search_slots", "arguments": {"date": "2026-07-01"}}]),
        LLMResponse(text="Booked 3pm.", tool_calls=[
            {"name": "book_appointment", "arguments": {"slot": "3pm"}}]),
    ])
    fixture = record_conversation(
        agent_factory=lambda llm, tools: BookingAgent(llm=llm, tools=tools),
        inner_llm=inner,
        scenario=scenario,
        adapter=DirectAdapter(),
        tools=booking_tools(),
        agent_version="abc123",
        model="claude-haiku-4-5",
        recorded_at=TS,
        clock=_counter_clock(),
    )
    ops = [s.operation for s in fixture.spans]
    assert ops.count("conversation") == 1
    assert ops.count("llm.create") == 2
    assert ops.count("tool.call") == 2

    root = next(s for s in fixture.spans if s.operation == "conversation")
    assert root.parent_id is None
    assert root.trace_id == fixture.conversation.id  # spans tie back to the conversation

    calls = [s for s in fixture.spans if s.operation in ("llm.create", "tool.call")]
    assert all(s.parent_id == root.span_id for s in calls)  # every call is a child of the root

    llm = next(s for s in fixture.spans if s.operation == "llm.create")
    assert llm.attributes["gen_ai.request.model"] == "claude-haiku-4-5"
    tool_names = {s.attributes["tool.name"] for s in fixture.spans if s.operation == "tool.call"}
    assert tool_names == {"search_slots", "book_appointment"}
