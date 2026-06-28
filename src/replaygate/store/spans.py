from __future__ import annotations

import json

import duckdb

from replaygate.trace.models import SpanRecord


class SpanStore:
    def __init__(self, db_path: str):
        self._con = duckdb.connect(db_path)
        self._con.execute(
            """
            CREATE TABLE IF NOT EXISTS spans (
                trace_id TEXT, span_id TEXT, parent_id TEXT,
                operation TEXT, attributes JSON, start_ns BIGINT, end_ns BIGINT
            )
            """
        )

    def write(self, spans: list[SpanRecord]) -> None:
        for s in spans:
            self._con.execute(
                "INSERT INTO spans VALUES (?, ?, ?, ?, ?, ?, ?)",
                [s.trace_id, s.span_id, s.parent_id, s.operation,
                 json.dumps(s.attributes), s.start_ns, s.end_ns],
            )

    def read(self, trace_id: str) -> list[SpanRecord]:
        rows = self._con.execute(
            "SELECT trace_id, span_id, parent_id, operation, attributes, start_ns, end_ns "
            "FROM spans WHERE trace_id = ?",
            [trace_id],
        ).fetchall()
        return [
            SpanRecord(
                trace_id=r[0], span_id=r[1], parent_id=r[2], operation=r[3],
                attributes=json.loads(r[4]), start_ns=r[5], end_ns=r[6],
            )
            for r in rows
        ]
