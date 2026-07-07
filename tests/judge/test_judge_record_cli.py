from datetime import datetime, timezone

from typer.testing import CliRunner

from replaygate.capture.adapters import DirectAdapter
from replaygate.capture.record import record_conversation
from replaygate.capture.replay import replay_conversation
from replaygate.cli.main import app
from replaygate.examples.scenarios import EXAMPLES, scripted_judge_for, scripted_llm_for
from replaygate.judge.record import judge_key, record_judge
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


class _FakeClaudeJudge:
    """Offline stand-in for ClaudeJudge — returns the scenario's scripted verdict.

    Never imports the anthropic SDK; monkeypatched over ClaudeJudge so the
    judge-record command runs fully offline in the test suite.
    """

    def __init__(self, **kwargs):
        pass

    def judge(self, conversation, dimensions):
        return scripted_judge_for(conversation.scenario).judge(conversation, dimensions)


def test_judge_record_then_regress_replays_offline(tmp_path, monkeypatch):
    out = str(tmp_path)
    _write("booking_happy", out)
    assert read_fixture(out).judge_recording == []  # no verdict yet

    monkeypatch.setattr("replaygate.judge.claude.ClaudeJudge", _FakeClaudeJudge)
    rec = runner.invoke(app, ["judge-record", out])
    assert rec.exit_code == 0, rec.stdout
    assert "recorded judge verdict for booking_happy" in rec.stdout
    assert read_fixture(out).judge_recording  # a verdict was persisted

    # regress --judge now finds the recorded verdict, fully offline
    res = runner.invoke(app, ["regress", out, "--judge"])
    assert res.exit_code == 0
    assert "[judge] goal_completion: 1.00" in res.stdout
    assert "no recorded verdict" not in (res.stdout + res.stderr)


def test_judge_record_missing_fixture_is_exit_2(tmp_path):
    result = runner.invoke(app, ["judge-record", str(tmp_path / "nope")])
    assert result.exit_code == 2


def test_judge_record_non_builtin_scenario_is_exit_2(tmp_path, monkeypatch):
    from types import SimpleNamespace

    fake = SimpleNamespace(conversation=SimpleNamespace(scenario="not_a_real_scenario"))
    monkeypatch.setattr("replaygate.cli.main.read_fixture", lambda d: fake)
    result = runner.invoke(app, ["judge-record", str(tmp_path)])
    assert result.exit_code == 2
    assert "not a built-in example" in (result.stdout + result.stderr)


def test_judge_record_no_dimensions_is_exit_2(tmp_path, monkeypatch):
    out = str(tmp_path)
    _write("booking_happy", out)
    monkeypatch.setattr("replaygate.cli.main.dimensions_for", lambda s: [])
    result = runner.invoke(app, ["judge-record", out])
    assert result.exit_code == 2
    assert "no judge dimensions registered" in (result.stdout + result.stderr)


def test_record_judge_overwrites_and_is_idempotent(tmp_path):
    out = str(tmp_path)
    _write("booking_happy", out)
    fixture = read_fixture(out)
    spec = EXAMPLES["booking_happy"]
    judge = scripted_judge_for("booking_happy")

    record_judge(fixture, judge, spec.build_agent, spec.tools())
    record_judge(fixture, judge, spec.build_agent, spec.tools())

    dims = dimensions_for("booking_happy")
    replayed = replay_conversation(fixture, spec.build_agent, spec.tools())
    key = judge_key(replayed, dims)
    matching = [e for e in fixture.judge_recording if e["judge_key"] == key]
    assert len(matching) == 1  # re-recording overwrote rather than duplicated
