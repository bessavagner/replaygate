from datetime import datetime, timezone

from typer.testing import CliRunner

from replaygate.capture.adapters import DirectAdapter
from replaygate.capture.record import record_conversation
from replaygate.cli.main import app
from replaygate.examples.scenarios import EXAMPLES, scripted_llm_for
from replaygate.store.fixtures import write_fixture

runner = CliRunner()
TS = datetime(2026, 6, 29, tzinfo=timezone.utc)


def _write_support(out_dir):
    spec = EXAMPLES["support_happy"]
    fixture = record_conversation(
        agent_factory=spec.build_agent,
        inner_llm=scripted_llm_for("support_happy"),
        scenario=spec.scenario,
        adapter=DirectAdapter(),
        tools=spec.tools(),
        agent_version="A",
        model=spec.model,
        recorded_at=TS,
    )
    write_fixture(out_dir, fixture)


def test_control_candidate_exits_0(tmp_path):
    _write_support(str(tmp_path))
    result = runner.invoke(app, ["regress", str(tmp_path), "--candidate", "support_control"])
    assert result.exit_code == 0, result.output
    assert "regress OK" in result.output


def test_reworded_candidate_pinned_exits_3(tmp_path):
    _write_support(str(tmp_path))
    result = runner.invoke(app, ["regress", str(tmp_path), "--candidate", "support_reworded"])
    assert result.exit_code == 3, result.output
    assert "DIVERGED" in result.output


def test_regressed_candidate_exits_1(tmp_path):
    _write_support(str(tmp_path))
    result = runner.invoke(app, ["regress", str(tmp_path), "--candidate", "support_regressed"])
    assert result.exit_code == 1, result.output
    assert "regress FAILED" in result.output


def test_unknown_candidate_exits_2(tmp_path):
    _write_support(str(tmp_path))
    result = runner.invoke(app, ["regress", str(tmp_path), "--candidate", "nope"])
    assert result.exit_code == 2


def test_default_invocation_is_unchanged(tmp_path):
    _write_support(str(tmp_path))
    result = runner.invoke(app, ["regress", str(tmp_path)])
    assert result.exit_code == 0, result.output
    assert "regress OK" in result.output
