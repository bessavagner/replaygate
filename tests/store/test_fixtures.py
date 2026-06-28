from datetime import datetime, timezone

from replaygate.store.fixtures import Fixture, FixtureMeta, read_fixture, write_fixture
from replaygate.trace.models import Conversation, SessionMeta, SpanRecord

TS = datetime(2026, 6, 28, tzinfo=timezone.utc)


def _fixture():
    conv = Conversation(
        id="c1", scenario="booking", channel="direct",
        session_meta=SessionMeta(session_id="s1", started_at=TS),
    )
    return Fixture(
        conversation=conv,
        llm_recording=[{"request_key": "k1", "request": {}, "response": {"text": "hi"}}],
        tool_recording=[{"tool": "search_slots", "args": {}, "result": {"slots": []}}],
        spans=[SpanRecord(trace_id="t1", span_id="s1", parent_id=None,
                          operation="chat", attributes={}, start_ns=1, end_ns=2)],
        meta=FixtureMeta(scenario="booking", agent_version="abc123", model="claude-haiku-4-5", recorded_at=TS),
    )


def test_write_then_read_roundtrips(tmp_path):
    write_fixture(str(tmp_path / "fx"), _fixture())
    loaded = read_fixture(str(tmp_path / "fx"))
    assert loaded.conversation.id == "c1"
    assert loaded.llm_recording[0]["request_key"] == "k1"
    assert loaded.tool_recording[0]["tool"] == "search_slots"
    assert loaded.spans[0].span_id == "s1"
    assert loaded.meta.agent_version == "abc123"


def test_files_are_created(tmp_path):
    write_fixture(str(tmp_path / "fx"), _fixture())
    for name in ["conversation.json", "llm_recording.json", "tool_recording.json", "spans.jsonl", "meta.json"]:
        assert (tmp_path / "fx" / name).exists()
