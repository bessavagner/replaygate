"""Timing-span collection for a recording run.

A recording is a single trace: a ``conversation`` root span with ``llm.create``
and ``tool.call`` children, timed as they happen and aligned to OpenTelemetry's
GenAI semantic conventions. ``SpanCollector.span`` is a context manager that opens
a child of the currently-open span and closes it on exit, so nesting follows the
call stack. Timing comes from an injectable nanosecond clock — ``time.perf_counter_ns``
in production, a deterministic counter in tests — so recordings never depend on
wall-clock wobble.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Callable, Iterator

from replaygate.trace.models import SpanRecord


class SpanCollector:
    def __init__(self, trace_id: str, clock: Callable[[], int] = time.perf_counter_ns):
        self.trace_id = trace_id
        self._clock = clock
        self._counter = 0
        self._parent_id: str | None = None
        self.spans: list[SpanRecord] = []

    def _next_id(self) -> str:
        self._counter += 1
        return f"{self.trace_id}-span-{self._counter}"

    @contextmanager
    def span(self, operation: str, attributes: dict) -> Iterator[str]:
        span_id = self._next_id()
        parent_id = self._parent_id
        start_ns = self._clock()
        self._parent_id = span_id
        try:
            yield span_id
        finally:
            self._parent_id = parent_id
            self.spans.append(SpanRecord(
                trace_id=self.trace_id, span_id=span_id, parent_id=parent_id,
                operation=operation, attributes=attributes,
                start_ns=start_ns, end_ns=self._clock(),
            ))
