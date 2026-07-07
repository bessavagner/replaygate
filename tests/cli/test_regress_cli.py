from datetime import datetime, timezone

from typer.testing import CliRunner

from replaygate.capture.adapters import DirectAdapter
from replaygate.capture.record import record_conversation
from replaygate.cli.main import app
from replaygate.examples.scenarios import EXAMPLES, scripted_judge_for, scripted_llm_for
from replaygate.judge.models import DimensionVerdict, JudgeVerdict
from replaygate.judge.record import RecordingJudge
from replaygate.judge.registry import dimensions_for
from replaygate.store.fixtures import read_fixture, write_fixture

runner = CliRunner()
TS = datetime(2026, 6, 29, tzinfo=timezone.utc)


def _write(scenario_name, out_dir):
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
    write_fixture(out_dir, fixture)


def test_regress_passes_on_happy_fixture(tmp_path):
    _write("booking_happy", str(tmp_path))
    result = runner.invoke(app, ["regress", str(tmp_path)])
    assert result.exit_code == 0
    assert "regress OK" in result.stdout


def test_regress_fails_on_regression_fixture(tmp_path):
    _write("booking_books_without_confirm_regression", str(tmp_path))
    result = runner.invoke(app, ["regress", str(tmp_path)])
    assert result.exit_code == 1
    assert "regress FAILED" in result.stdout


def test_regress_missing_fixture_is_exit_2(tmp_path):
    result = runner.invoke(app, ["regress", str(tmp_path / "nope")])
    assert result.exit_code == 2


def _write_with_judge(scenario_name, out_dir, verdict=None):
    _write(scenario_name, out_dir)
    fixture = read_fixture(out_dir)
    inner = _ScriptedOne(verdict) if verdict is not None else scripted_judge_for(scenario_name)
    RecordingJudge(inner, mode="record", recording=fixture.judge_recording).judge(
        fixture.conversation, dimensions_for(scenario_name)
    )
    write_fixture(out_dir, fixture)


class _ScriptedOne:
    def __init__(self, verdict):
        self._verdict = verdict

    def judge(self, conversation, dimensions):
        return self._verdict


def test_judge_flag_prints_verdicts_and_preserves_exit_code(tmp_path):
    _write_with_judge("booking_happy", str(tmp_path))
    result = runner.invoke(app, ["regress", str(tmp_path), "--judge"])
    assert result.exit_code == 0
    assert "regress OK" in result.stdout
    assert "[judge] goal_completion" in result.stdout


def test_judge_flag_does_not_change_default_behavior(tmp_path):
    # Same fixture, without --judge, must match the pinned default output.
    _write_with_judge("booking_happy", str(tmp_path))
    result = runner.invoke(app, ["regress", str(tmp_path)])
    assert result.exit_code == 0
    assert "[judge]" not in result.stdout


def test_judge_gate_can_fail_the_run(tmp_path):
    failing = JudgeVerdict(scenario="booking_happy", verdicts=[
        DimensionVerdict(dimension="goal_completion", score=0.1, rationale="never booked"),
    ])
    _write_with_judge("booking_happy", str(tmp_path), verdict=failing)
    result = runner.invoke(app, ["regress", str(tmp_path), "--judge-gate"])
    assert result.exit_code == 4
    assert "JUDGE-GATE" in result.stdout


def test_judge_gate_passes_when_scores_hold(tmp_path):
    _write_with_judge("booking_happy", str(tmp_path))  # scripted verdict scores 1.0
    result = runner.invoke(app, ["regress", str(tmp_path), "--judge-gate"])
    assert result.exit_code == 0


def test_judge_flag_without_recording_is_advisory(tmp_path):
    _write("booking_happy", str(tmp_path))  # no judge_recording written
    result = runner.invoke(app, ["regress", str(tmp_path), "--judge"])
    assert result.exit_code == 0  # advisory: missing verdict never changes the exit code
    assert "no recorded" in (result.stdout + result.stderr)
