from datetime import datetime, timezone

from replaygate.capture.adapters import DirectAdapter
from replaygate.capture.record import record_conversation
from replaygate.examples.scenarios import EXAMPLES, scripted_llm_for
from replaygate.regress import run_regress

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


def _regress(scenario_name):
    fixture = _record(scenario_name)
    spec = EXAMPLES[scenario_name]
    return run_regress(fixture, spec.build_agent, spec.tools())


def test_happy_scenarios_pass_their_invariants():
    for name in ["booking_happy", "support_happy", "profile_happy"]:
        report = _regress(name)
        assert report.passed is True, f"{name}: {report.results}"


def test_regression_scenarios_fail_their_invariants():
    for name in [
        "booking_books_without_confirm_regression",
        "support_reask_regression",
        "profile_forgets_regression",
    ]:
        report = _regress(name)
        assert report.passed is False, f"{name} should have violated an invariant"
        assert any(not r.passed for r in report.results)
