from datetime import datetime, timezone
from pathlib import Path

import pytest

from replaygate.capture.adapters import DirectAdapter
from replaygate.capture.record import record_conversation
from replaygate.dashboard.service import RunNotFound, UnknownCandidate, list_runs, load_run
from replaygate.examples.scenarios import EXAMPLES, scripted_llm_for
from replaygate.store.fixtures import write_fixture

TS = datetime(2026, 6, 29, tzinfo=timezone.utc)


def _record(scenario_name: str, out_dir: Path) -> None:
    spec = EXAMPLES[scenario_name]
    fixture = record_conversation(
        agent_factory=spec.build_agent,
        inner_llm=scripted_llm_for(scenario_name),
        scenario=spec.scenario,
        adapter=DirectAdapter(),
        tools=spec.tools(),
        agent_version="test",
        model=spec.model,
        recorded_at=TS,
    )
    write_fixture(str(out_dir), fixture)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    _record("support_happy", tmp_path / "support_happy")
    _record("booking_happy", tmp_path / "booking_happy")
    (tmp_path / "not_a_fixture").mkdir()
    return tmp_path


def test_list_runs_returns_fixture_dirs_sorted(root: Path):
    runs = list_runs(root)
    assert [r.run_id for r in runs] == ["booking_happy", "support_happy"]
    assert all(r.turn_count == 2 for r in runs)
    assert all(r.channel == "direct" for r in runs)


def test_list_runs_ignores_directories_without_a_conversation(root: Path):
    assert "not_a_fixture" not in [r.run_id for r in list_runs(root)]


def test_list_runs_on_a_missing_root_is_empty(tmp_path: Path):
    assert list_runs(tmp_path / "nope") == []


def test_self_replay_is_ok_with_no_changed_turns(root: Path):
    view = load_run(root, "support_happy")
    assert view.status == "ok"
    assert view.changed_turn_indexes == []
    assert [c.passed for c in view.invariants] == [True]


def test_regressed_candidate_flags_turn_one_and_fails_its_invariant(root: Path):
    view = load_run(root, "support_happy", candidate="support_regressed")
    assert view.status == "failed"
    assert view.candidate == "support_regressed"
    assert view.changed_turn_indexes == [1]

    turn0, turn1 = view.turns
    assert turn0.changed is False
    assert turn0.baseline.assistant_text == turn0.current.assistant_text
    assert turn1.text_changed is True
    assert turn1.tools_changed is True
    assert turn1.baseline.assistant_text == "ORD-1234 has shipped — ETA 2026-07-02."
    assert turn1.current.assistant_text == "Sure — what's your order number?"
    assert [tc.name for tc in turn1.baseline.tool_calls] == ["lookup_order"]
    assert turn1.current.tool_calls == []

    (invariant,) = view.invariants
    assert invariant.name == "order_id_never_reasked"
    assert invariant.passed is False
    assert invariant.detail == "turn 1: re-asked for an order id already given on turn 0"


def test_diverged_candidate_has_no_current_side(root: Path):
    view = load_run(root, "support_happy", candidate="support_reworded")
    assert view.status == "diverged"
    assert view.invariants == []
    assert all(t.current is None for t in view.turns)
    assert view.changed_turn_indexes == []
    (divergence,) = view.divergences
    assert divergence.turn_index == 0
    assert divergence.kind == "llm"
    assert "no recorded LLM response" in divergence.summary


def test_missing_judge_verdict_is_an_advisory_note_not_a_failure(root: Path):
    view = load_run(root, "support_happy")
    assert view.judge == []
    assert view.judge_note == (
        "no recorded verdict for this fixture; run `replaygate judge-record` first"
    )
    assert view.status == "ok"


def test_scenario_without_registered_dimensions_says_so(root: Path):
    _record("booking_books_without_confirm_regression", root / "booking_bad")
    view = load_run(root, "booking_bad")
    assert view.status == "failed"
    assert view.judge_note == (
        "no judge dimensions registered for scenario "
        "'booking_books_without_confirm_regression'"
    )


def test_unknown_run_raises(root: Path):
    with pytest.raises(RunNotFound):
        load_run(root, "nope")


@pytest.mark.parametrize("run_id", ["..", ".", "", "../support_happy", "a/b"])
def test_path_traversal_is_refused(root: Path, run_id: str):
    with pytest.raises(RunNotFound):
        load_run(root, run_id)


def test_unknown_candidate_raises(root: Path):
    with pytest.raises(UnknownCandidate):
        load_run(root, "support_happy", candidate="nope")
