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
        agent_version="abc123",
        model="claude-haiku-4-5",
        recorded_at=TS,
    )
    assert len(fixture.conversation.turns) == 2
    assert [tc.name for tc in fixture.conversation.all_tool_calls()] == ["search_slots", "book_appointment"]
    assert len(fixture.llm_recording) == 2
    assert len(fixture.tool_recording) == 2
    assert fixture.meta.agent_version == "abc123"
