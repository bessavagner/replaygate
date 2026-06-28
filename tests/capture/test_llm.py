import pytest

from replaygate.capture.llm import LLMResponse, RecordingLLMClient, request_key


class FakeLLM:
    def __init__(self, text):
        self.text = text
        self.calls = 0

    def create(self, model, system, messages, tools):
        self.calls += 1
        return LLMResponse(text=self.text)


def test_record_mode_captures_and_passes_through():
    rec: list[dict] = []
    client = RecordingLLMClient(FakeLLM("hello"), mode="record", recording=rec)
    out = client.create("claude-haiku-4-5", "sys", [{"role": "user", "content": "hi"}], [])
    assert out.text == "hello"
    assert len(rec) == 1 and "request_key" in rec[0]


def test_replay_mode_returns_recorded_without_calling_inner():
    inner = FakeLLM("LIVE")
    key = request_key("claude-haiku-4-5", "sys", [{"role": "user", "content": "hi"}], [])
    rec = [{"request_key": key, "request": {}, "response": {"text": "RECORDED", "tool_calls": [], "raw": {}}}]
    client = RecordingLLMClient(inner, mode="replay", recording=rec)
    out = client.create("claude-haiku-4-5", "sys", [{"role": "user", "content": "hi"}], [])
    assert out.text == "RECORDED"
    assert inner.calls == 0


def test_replay_missing_key_raises():
    client = RecordingLLMClient(FakeLLM("x"), mode="replay", recording=[])
    with pytest.raises(KeyError):
        client.create("m", "s", [{"role": "user", "content": "nope"}], [])
