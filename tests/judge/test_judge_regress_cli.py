from datetime import datetime, timezone

from typer.testing import CliRunner

from replaygate.capture.adapters import DirectAdapter
from replaygate.capture.record import record_conversation
from replaygate.cli.main import app
from replaygate.examples.scenarios import EXAMPLES, scripted_judge_for, scripted_llm_for
from replaygate.judge.record import RecordingJudge
from replaygate.judge.registry import dimensions_for
from replaygate.store.fixtures import read_fixture, write_fixture

runner = CliRunner()
TS = datetime(2026, 6, 29, tzinfo=timezone.utc)


def _write_with_judge(scenario_name, out_dir):
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
    fixture = read_fixture(out_dir)
    RecordingJudge(scripted_judge_for(scenario_name), mode="record",
                   recording=fixture.judge_recording).judge(
        fixture.conversation, dimensions_for(scenario_name))
    write_fixture(out_dir, fixture)


def test_judge_path_runs_fully_offline_for_builtin_scenarios(tmp_path):
    _write_with_judge("support_happy", str(tmp_path))
    result = runner.invoke(app, ["regress", str(tmp_path), "--judge"])
    assert result.exit_code == 0
    assert "[judge] goal_completion: 1.00" in result.stdout
    assert "[judge] tone: 1.00" in result.stdout
