import pytest

from replaygate.capture.tools import ToolRecorder


def test_record_invokes_real_tool_and_logs():
    rec: list[dict] = []
    registry = {"search_slots": lambda date: {"slots": [date]}}
    r = ToolRecorder(registry, mode="record", recording=rec)
    out = r.call("search_slots", {"date": "2026-07-01"})
    assert out == {"slots": ["2026-07-01"]}
    assert rec == [{"tool": "search_slots", "args": {"date": "2026-07-01"}, "result": {"slots": ["2026-07-01"]}}]


def test_replay_returns_recorded_and_does_not_invoke():
    called = {"n": 0}

    def boom(**_):
        called["n"] += 1
        return {}

    rec = [{"tool": "search_slots", "args": {"date": "2026-07-01"}, "result": {"slots": ["X"]}}]
    r = ToolRecorder({"search_slots": boom}, mode="replay", recording=rec)
    assert r.call("search_slots", {"date": "2026-07-01"}) == {"slots": ["X"]}
    assert called["n"] == 0


def test_replay_missing_raises():
    r = ToolRecorder({}, mode="replay", recording=[])
    with pytest.raises(KeyError):
        r.call("nope", {})
