from datetime import datetime, timezone

import pytest

from replaygate.capture.adapters import DirectAdapter
from replaygate.capture.llm import LLMResponse
from replaygate.capture.record import record_conversation
from replaygate.examples.scenarios import CANDIDATES, EXAMPLES, scripted_llm_for
from replaygate.regress import run_regress

TS = datetime(2026, 6, 29, tzinfo=timezone.utc)


class _FakeLLM:
    """A benign inner client for live fallback — never says 'order number'."""

    def __init__(self, text: str = "ok, checking that for you"):
        self._text = text

    def create(self, model, system, messages, tools) -> LLMResponse:
        return LLMResponse(text=self._text)


def _record_support():
    spec = EXAMPLES["support_happy"]
    return record_conversation(
        agent_factory=spec.build_agent,
        inner_llm=scripted_llm_for("support_happy"),
        scenario=spec.scenario,
        adapter=DirectAdapter(),
        tools=spec.tools(),
        agent_version="A",
        model=spec.model,
        recorded_at=TS,
    )


def test_control_candidate_matches_recording_and_holds():
    fx = _record_support()
    cand = CANDIDATES["support_control"]
    report = run_regress(fx, cand.build_agent, cand.tools())
    assert report.status == "ok"
    assert report.divergences == []
    assert report.passed is True


def test_reworded_candidate_diverges_under_pinned():
    fx = _record_support()
    cand = CANDIDATES["support_reworded"]
    report = run_regress(fx, cand.build_agent, cand.tools())  # pinned default
    assert report.status == "diverged"
    assert report.passed is False
    assert report.divergences[0].kind == "llm"
    assert report.divergences[0].turn_index == 0


def test_reworded_candidate_holds_under_live():
    fx = _record_support()
    cand = CANDIDATES["support_reworded"]
    report = run_regress(
        fx, cand.build_agent, cand.tools(), policy="live", inner_llm=_FakeLLM()
    )
    assert report.status == "ok"


def test_regressed_candidate_fails_its_invariant_offline():
    fx = _record_support()
    cand = CANDIDATES["support_regressed"]
    report = run_regress(fx, cand.build_agent, cand.tools())
    assert report.status == "failed"
    assert any(not r.passed for r in report.results)


def test_live_policy_requires_inner_llm():
    fx = _record_support()
    cand = CANDIDATES["support_control"]
    with pytest.raises(ValueError, match="requires an inner_llm"):
        run_regress(fx, cand.build_agent, cand.tools(), policy="live")
