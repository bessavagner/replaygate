from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from replaygate.trace.models import Conversation, SpanRecord


class FixtureMeta(BaseModel):
    scenario: str
    agent_version: str
    model: str
    recorded_at: datetime


class Fixture(BaseModel):
    conversation: Conversation
    llm_recording: list[dict]
    tool_recording: list[dict]
    spans: list[SpanRecord]
    meta: FixtureMeta


def write_fixture(dir_path: str, fixture: Fixture) -> None:
    d = Path(dir_path)
    d.mkdir(parents=True, exist_ok=True)
    (d / "conversation.json").write_text(fixture.conversation.model_dump_json(indent=2))
    (d / "llm_recording.json").write_text(json.dumps(fixture.llm_recording, indent=2))
    (d / "tool_recording.json").write_text(json.dumps(fixture.tool_recording, indent=2))
    (d / "spans.jsonl").write_text("\n".join(s.model_dump_json() for s in fixture.spans))
    (d / "meta.json").write_text(fixture.meta.model_dump_json(indent=2))


def read_fixture(dir_path: str) -> Fixture:
    d = Path(dir_path)
    spans_text = (d / "spans.jsonl").read_text().strip()
    spans = [SpanRecord.model_validate_json(line) for line in spans_text.splitlines() if line]
    return Fixture(
        conversation=Conversation.model_validate_json((d / "conversation.json").read_text()),
        llm_recording=json.loads((d / "llm_recording.json").read_text()),
        tool_recording=json.loads((d / "tool_recording.json").read_text()),
        spans=spans,
        meta=FixtureMeta.model_validate_json((d / "meta.json").read_text()),
    )
