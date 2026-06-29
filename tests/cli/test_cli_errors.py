from typer.testing import CliRunner

from replaygate.cli.main import app

runner = CliRunner()


def _text(result):
    # Tolerate Click versions that split stdout/stderr.
    return result.output + (getattr(result, "stderr", "") or "")


def test_record_unknown_scenario_is_a_clean_error(tmp_path):
    result = runner.invoke(app, ["record", "nope", str(tmp_path / "out")])
    assert result.exit_code != 0
    assert "unknown scenario" in _text(result)


def test_record_live_unknown_provider_is_a_clean_error(tmp_path):
    result = runner.invoke(
        app, ["record-live", "booking_happy", str(tmp_path / "out"), "--provider", "cohere"]
    )
    assert result.exit_code != 0
    assert "unknown provider" in _text(result)


def test_replay_missing_fixture_is_a_clean_error(tmp_path):
    result = runner.invoke(app, ["replay", str(tmp_path / "does_not_exist")])
    assert result.exit_code != 0
    assert "cannot read fixture" in _text(result)
