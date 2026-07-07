from datetime import datetime, timezone

from typer.testing import CliRunner

from replaygate.capture.adapters import DirectAdapter
from replaygate.capture.record import record_conversation
from replaygate.cli.main import app
from replaygate.examples.scenarios import EXAMPLES, scripted_llm_for
from replaygate.store.fixtures import write_fixture

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


def test_default_regress_output_is_pinned(tmp_path):
    _write("booking_happy", str(tmp_path))
    result = runner.invoke(app, ["regress", str(tmp_path)])
    assert result.exit_code == 0
    assert result.stdout == (
        "  [PASS] booked_only_after_confirmation: every booking followed a confirmation\n"
        "regress OK (booking_happy): 1 invariant(s) held\n"
    )


def test_default_regress_failure_exit_code_is_pinned(tmp_path):
    _write("booking_books_without_confirm_regression", str(tmp_path))
    result = runner.invoke(app, ["regress", str(tmp_path)])
    assert result.exit_code == 1
    assert "regress FAILED" in result.stdout
