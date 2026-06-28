from replaygate.store.spans import SpanStore
from replaygate.trace.models import SpanRecord


def test_write_then_read_roundtrips(tmp_path):
    store = SpanStore(str(tmp_path / "t.duckdb"))
    spans = [
        SpanRecord(
            trace_id="t1", span_id="s1", parent_id=None,
            operation="invoke_agent", attributes={"gen_ai.agent.name": "booking"},
            start_ns=1, end_ns=2,
        ),
        SpanRecord(
            trace_id="t1", span_id="s2", parent_id="s1",
            operation="chat", attributes={"gen_ai.request.model": "claude-haiku-4-5"},
            start_ns=3, end_ns=4,
        ),
    ]
    store.write(spans)
    got = store.read("t1")
    assert {s.span_id for s in got} == {"s1", "s2"}
    chat = next(s for s in got if s.operation == "chat")
    assert chat.attributes["gen_ai.request.model"] == "claude-haiku-4-5"
