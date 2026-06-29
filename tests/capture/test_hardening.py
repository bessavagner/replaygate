from types import SimpleNamespace

import pytest

from replaygate.capture.llm import RecordingLLMClient
from replaygate.capture.providers import OpenAICompatibleClient
from replaygate.capture.tools import ToolRecorder
from replaygate.examples.scenarios import scripted_llm_for


def test_record_without_inner_llm_raises_clearly():
    rec = RecordingLLMClient(inner=None, mode="record", recording=[])
    with pytest.raises(RuntimeError, match="inner LLMClient"):
        rec.create("m", "s", [], [])


def test_toolrecorder_unknown_tool_name_raises_clearly():
    rec = ToolRecorder({"search_slots": lambda **kw: {}}, mode="record", recording=[])
    with pytest.raises(KeyError, match="unknown tool"):
        rec.call("ghost_tool", {})


def test_scripted_llm_reports_exhaustion():
    llm = scripted_llm_for("booking_happy")  # ships exactly 2 responses
    llm.create("m", "s", [], [])
    llm.create("m", "s", [], [])
    with pytest.raises(RuntimeError, match="exhausted"):
        llm.create("m", "s", [], [])


def test_openai_empty_choices_raises():
    empty = SimpleNamespace(id="x", model="y", choices=[])
    fake = SimpleNamespace(chat=SimpleNamespace(
        completions=SimpleNamespace(create=lambda **kw: empty)))
    with pytest.raises(ValueError, match="no choices"):
        OpenAICompatibleClient(client=fake).create("m", "s", [], [])
