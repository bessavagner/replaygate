import pytest

from replaygate.capture.errors import DivergenceError
from replaygate.capture.llm import LLMResponse, RecordingLLMClient
from replaygate.capture.tools import ToolRecorder


class _FakeLLM:
    def __init__(self, text: str):
        self._text = text

    def create(self, model, system, messages, tools) -> LLMResponse:
        return LLMResponse(text=self._text)


def test_llm_replay_miss_raises_divergence_error():
    rec = RecordingLLMClient(inner=None, mode="replay", recording=[])
    with pytest.raises(DivergenceError) as ei:
        rec.create("m", "s", [], [])
    assert ei.value.kind == "llm"
    assert isinstance(ei.value, KeyError)  # back-compat


def test_llm_replay_miss_live_falls_back_and_records():
    recording: list[dict] = []
    rec = RecordingLLMClient(inner=_FakeLLM("hi"), mode="replay",
                             recording=recording, on_miss="live")
    resp = rec.create("m", "s", [{"role": "user", "content": "x"}], [])
    assert resp.text == "hi"
    assert len(recording) == 1  # the live exchange was appended


def test_tool_replay_miss_raises_divergence_error():
    r = ToolRecorder({}, mode="replay", recording=[], on_miss="raise")
    with pytest.raises(DivergenceError) as ei:
        r.call("lookup_order", {"order_id": "ORD-1"})
    assert ei.value.kind == "tool"


def test_tool_replay_miss_live_falls_back_and_records():
    recording: list[dict] = []
    r = ToolRecorder({"lookup_order": lambda order_id: {"status": "ok"}},
                     mode="replay", recording=recording, on_miss="live")
    result = r.call("lookup_order", {"order_id": "ORD-1"})
    assert result == {"status": "ok"}
    assert len(recording) == 1
