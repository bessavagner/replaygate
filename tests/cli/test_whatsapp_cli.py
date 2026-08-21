from typer.testing import CliRunner

from replaygate.cli.main import app
from replaygate.store.fixtures import read_fixture

runner = CliRunner()


def _text(result):
    # Click 8.2+ splits stdout/stderr; typer.BadParameter writes to stderr.
    return result.output + (getattr(result, "stderr", "") or "")


def test_record_whatsapp_writes_a_whatsapp_fixture(tmp_path):
    out = tmp_path / "fx"
    result = runner.invoke(app, ["record", "whatsapp_support", str(out), "--channel", "whatsapp"])
    assert result.exit_code == 0, result.stdout
    conv = read_fixture(str(out)).conversation
    assert conv.channel == "whatsapp"
    assert len(conv.turns) == 2
    assert conv.turns[0].user_messages[0].channel_meta.message_id == "WA-1"
    assert conv.session_meta.window_expired_at is not None


def test_a_whatsapp_fixture_replays_offline(tmp_path):
    out = tmp_path / "fx"
    runner.invoke(app, ["record", "whatsapp_support", str(out), "--channel", "whatsapp"])
    result = runner.invoke(app, ["replay", str(out)])
    assert result.exit_code == 0, result.stdout
    assert "2 turns reproduced offline, zero network" in result.stdout


def test_regress_passes_all_three_invariants_on_the_happy_whatsapp_run(tmp_path):
    out = tmp_path / "fx"
    runner.invoke(app, ["record", "whatsapp_support", str(out), "--channel", "whatsapp"])
    result = runner.invoke(app, ["regress", str(out)])
    assert result.exit_code == 0, result.stdout
    assert "[PASS] order_id_never_reasked" in result.stdout
    assert "[PASS] messages_in_send_order" in result.stdout
    assert "[PASS] no_reply_after_session_window" in result.stdout
    assert "3 invariant(s) held" in result.stdout


def test_a_reply_outside_the_session_window_fails_the_gate(tmp_path):
    out = tmp_path / "fx"
    runner.invoke(
        app,
        ["record", "whatsapp_support_late_reply_regression", str(out), "--channel", "whatsapp"],
    )
    result = runner.invoke(app, ["regress", str(out)])
    assert result.exit_code == 1, result.stdout
    assert "[FAIL] no_reply_after_session_window" in result.stdout
    assert "outside the 24h session window" in result.stdout
    # The agent's words are unchanged — only the channel rule was broken.
    assert "[PASS] order_id_never_reasked" in result.stdout


def test_an_unknown_channel_is_rejected(tmp_path):
    result = runner.invoke(app, ["record", "support_happy", str(tmp_path), "--channel", "sms"])
    assert result.exit_code == 2
    assert "channel must be 'direct' or 'whatsapp'" in _text(result)


def test_a_scenario_without_a_channel_script_is_rejected(tmp_path):
    result = runner.invoke(
        app, ["record", "support_happy", str(tmp_path), "--channel", "whatsapp"]
    )
    assert result.exit_code == 2
    assert "has no whatsapp script" in _text(result)
