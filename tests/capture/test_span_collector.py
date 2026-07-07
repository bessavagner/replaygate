from replaygate.capture.spans import SpanCollector


def _counter_clock():
    """A deterministic monotonic clock: returns 1, 2, 3, … on each call."""
    t = [0]

    def clock() -> int:
        t[0] += 1
        return t[0]

    return clock


def test_span_nests_child_under_open_parent():
    c = SpanCollector(trace_id="conv-1", clock=_counter_clock())
    with c.span("conversation", {"scenario": "x"}) as root_id:
        with c.span("llm.create", {"gen_ai.request.model": "m"}) as child_id:
            pass
    by_op = {s.operation: s for s in c.spans}
    assert by_op["conversation"].parent_id is None
    assert by_op["conversation"].span_id == root_id
    assert by_op["llm.create"].span_id == child_id
    assert by_op["llm.create"].parent_id == root_id
    assert by_op["conversation"].trace_id == "conv-1"


def test_siblings_share_parent_and_get_distinct_ids():
    c = SpanCollector(trace_id="t", clock=_counter_clock())
    with c.span("conversation", {}) as root_id:
        with c.span("tool.call", {"tool.name": "a"}):
            pass
        with c.span("tool.call", {"tool.name": "b"}):
            pass
    tools = [s for s in c.spans if s.operation == "tool.call"]
    assert len(tools) == 2
    assert {s.parent_id for s in tools} == {root_id}
    assert len({s.span_id for s in c.spans}) == len(c.spans)  # all ids unique


def test_clock_records_monotonic_start_and_end():
    c = SpanCollector(trace_id="t", clock=_counter_clock())
    with c.span("conversation", {}):
        with c.span("llm.create", {}):
            pass
    root = next(s for s in c.spans if s.operation == "conversation")
    child = next(s for s in c.spans if s.operation == "llm.create")
    # Each span's start precedes its end, and the child is fully enclosed by the root.
    assert root.start_ns < child.start_ns < child.end_ns < root.end_ns
