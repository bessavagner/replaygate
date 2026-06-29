from datetime import datetime, timezone

from replaygate.capture.adapters import DirectAdapter
from replaygate.capture.record import record_conversation
from replaygate.capture.replay import diff_conversations, replay_conversation
from replaygate.examples.scenarios import EXAMPLES, scripted_llm_for

TS = datetime(2026, 6, 29, tzinfo=timezone.utc)


def _record(scenario_name):
    spec = EXAMPLES[scenario_name]
    return record_conversation(
        agent_factory=spec.build_agent,
        inner_llm=scripted_llm_for(scenario_name),
        scenario=spec.scenario,
        adapter=DirectAdapter(),
        tools=spec.tools(),
        agent_version="test",
        model=spec.model,
        recorded_at=TS,
    )


def test_replay_reproduces_recording_with_no_diffs():
    fixture = _record("booking_happy")
    spec = EXAMPLES["booking_happy"]
    replayed = replay_conversation(fixture, spec.build_agent, spec.tools())
    assert diff_conversations(fixture.conversation, replayed) == []
    assert [tc.name for tc in replayed.turns[0].tool_calls] == ["search_slots"]


def test_replay_works_for_memory_invariant_scenario():
    fixture = _record("support_happy")
    spec = EXAMPLES["support_happy"]
    replayed = replay_conversation(fixture, spec.build_agent, spec.tools())
    assert diff_conversations(fixture.conversation, replayed) == []


def test_diff_detects_a_tampered_recording():
    fixture = _record("booking_happy")
    # Simulate a regressed agent: corrupt the recorded LLM reply so replay diverges.
    fixture.llm_recording[1]["response"]["tool_calls"] = []
    spec = EXAMPLES["booking_happy"]
    replayed = replay_conversation(fixture, spec.build_agent, spec.tools())
    diffs = diff_conversations(fixture.conversation, replayed)
    assert diffs
    assert any("tool calls" in d for d in diffs)
