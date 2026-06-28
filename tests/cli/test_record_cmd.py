from typer.testing import CliRunner

from replaygate.cli.main import app
from replaygate.store.fixtures import read_fixture

runner = CliRunner()


def test_record_command_writes_fixture(tmp_path):
    out = tmp_path / "booking_fx"
    result = runner.invoke(app, ["record", "booking_happy", str(out)])
    assert result.exit_code == 0, result.output
    fixture = read_fixture(str(out))
    assert fixture.conversation.scenario == "booking_happy"
    assert len(fixture.conversation.turns) >= 1
    assert "search_slots" in [tc.name for tc in fixture.conversation.all_tool_calls()]
