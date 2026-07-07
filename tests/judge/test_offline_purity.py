import subprocess
import sys
import textwrap


def test_judge_replay_path_never_imports_anthropic():
    script = textwrap.dedent(
        """
        import sys
        from datetime import datetime, timezone
        from replaygate.judge.record import RecordingJudge
        from replaygate.judge.registry import dimensions_for
        from replaygate.trace.models import Conversation, Message, SessionMeta, Turn

        TS = datetime(2026, 7, 7, tzinfo=timezone.utc)
        conv = Conversation(
            id="c1", scenario="booking_happy", channel="direct",
            session_meta=SessionMeta(session_id="s1", started_at=TS),
            turns=[Turn(index=0, user_messages=[Message(role="user", content="hi", ts=TS)])],
        )
        from replaygate.judge.models import DimensionVerdict, JudgeVerdict
        from replaygate.judge.record import judge_key
        dims = dimensions_for("booking_happy")
        verdict = JudgeVerdict(scenario="booking_happy", verdicts=[
            DimensionVerdict(dimension=d, score=1.0, rationale="ok") for d in dims])
        rec = [{"judge_key": judge_key(conv, dims), "verdict": verdict.model_dump(mode="json")}]
        RecordingJudge(None, mode="replay", recording=rec).judge(conv, dims)
        assert "anthropic" not in sys.modules, "anthropic was imported on the offline judge path"
        print("OK")
        """
    )
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "OK" in result.stdout
