from datetime import datetime, timezone

import pytest

from replaygate.capture.adapters import DirectAdapter
from replaygate.capture.errors import DivergenceError
from replaygate.capture.record import record_conversation
from replaygate.capture.replay import replay_conversation
from replaygate.examples.scenarios import EXAMPLES, scripted_llm_for
from replaygate.judge.models import DimensionVerdict, JudgeVerdict
from replaygate.judge.record import RecordingJudge, judge_key
from replaygate.judge.registry import dimensions_for
from replaygate.trace.models import Conversation, Message, SessionMeta, Turn

TS = datetime(2026, 7, 7, tzinfo=timezone.utc)


def _conversation():
    return Conversation(
        id="c1", scenario="booking_happy", channel="direct",
        session_meta=SessionMeta(session_id="s1", started_at=TS),
        turns=[Turn(index=0, user_messages=[Message(role="user", content="hi", ts=TS)])],
    )


class FakeJudge:
    def __init__(self, verdict):
        self._verdict = verdict
        self.calls = 0

    def judge(self, conversation, dimensions):
        self.calls += 1
        return self._verdict


def _verdict():
    return JudgeVerdict(scenario="booking_happy", verdicts=[
        DimensionVerdict(dimension="tone", score=0.9, rationale="warm"),
    ])


def test_record_mode_captures_and_passes_through():
    rec: list[dict] = []
    inner = FakeJudge(_verdict())
    out = RecordingJudge(inner, mode="record", recording=rec).judge(_conversation(), ["tone"])
    assert out == _verdict()
    assert len(rec) == 1 and "judge_key" in rec[0] and "verdict" in rec[0]


def test_replay_returns_recorded_without_calling_inner():
    conv, dims = _conversation(), ["tone"]
    rec = [{"judge_key": judge_key(conv, dims), "verdict": _verdict().model_dump(mode="json")}]
    inner = FakeJudge(JudgeVerdict(scenario="x", verdicts=[]))
    out = RecordingJudge(inner, mode="replay", recording=rec).judge(conv, dims)
    assert out == _verdict()
    assert inner.calls == 0


def test_replay_miss_raises_divergence():
    with pytest.raises(DivergenceError) as exc:
        RecordingJudge(None, mode="replay", recording=[]).judge(_conversation(), ["tone"])
    assert exc.value.kind == "judge"


def test_key_is_stable_and_order_independent_on_dimensions():
    conv = _conversation()
    assert judge_key(conv, ["tone", "relevance"]) == judge_key(conv, ["relevance", "tone"])


def test_judge_key_is_stable_across_replay():
    """Guards the record<->regress seam: recording keys the verdict over
    ``fixture.conversation``, but ``regress --judge`` looks it up over
    ``replay_conversation(fixture)``. If replay ever produces a conversation that
    hashes differently (e.g. per-message timestamps), a recorded verdict would
    never be found on replay: --judge would go advisory-only and --judge-gate
    would refuse to run.
    """
    spec = EXAMPLES["booking_happy"]
    fixture = record_conversation(
        agent_factory=spec.build_agent,
        inner_llm=scripted_llm_for("booking_happy"),
        scenario=spec.scenario,
        adapter=DirectAdapter(),
        tools=spec.tools(),
        agent_version="test",
        model=spec.model,
        recorded_at=TS,
    )
    replayed = replay_conversation(fixture, spec.build_agent, spec.tools())
    dims = dimensions_for("booking_happy")
    assert dims
    assert judge_key(fixture.conversation, dims) == judge_key(replayed, dims)
