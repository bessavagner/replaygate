"""Read models for the dashboard — the JSON contract the SPA renders.

Built from a ``Fixture`` plus a ``RegressReport``; never from a live agent.
Deliberately separate from the trace contract: the UI must be free to change
shape without touching ``Conversation``, which every fixture on disk is
serialized against.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field

RunStatus = Literal["ok", "failed", "diverged"]


class ToolCallView(BaseModel):
    name: str
    arguments: dict
    result: dict | None = None
    error: str | None = None


class TurnSide(BaseModel):
    """One side — baseline or current — of a single turn."""

    assistant_text: str
    tool_calls: list[ToolCallView] = Field(default_factory=list)


class TurnDiff(BaseModel):
    """One aligned turn. ``current`` is None when replay never reached this turn."""

    index: int
    user_text: str
    baseline: TurnSide
    current: TurnSide | None = None
    text_changed: bool = False
    tools_changed: bool = False

    @computed_field
    @property
    def changed(self) -> bool:
        return self.text_changed or self.tools_changed


class InvariantChip(BaseModel):
    name: str
    passed: bool
    detail: str


class JudgeChip(BaseModel):
    dimension: str
    score: float
    rationale: str


class DivergenceView(BaseModel):
    turn_index: int
    kind: Literal["llm", "tool"]
    summary: str


class RunSummary(BaseModel):
    run_id: str
    scenario: str
    channel: str
    model: str
    agent_version: str
    recorded_at: datetime
    turn_count: int


class DiffView(BaseModel):
    run_id: str
    scenario: str
    candidate: str | None = None
    status: RunStatus
    channel: str
    model: str
    agent_version: str
    recorded_at: datetime
    turns: list[TurnDiff] = Field(default_factory=list)
    divergences: list[DivergenceView] = Field(default_factory=list)
    invariants: list[InvariantChip] = Field(default_factory=list)
    judge: list[JudgeChip] = Field(default_factory=list)
    judge_note: str | None = None

    @computed_field
    @property
    def changed_turn_indexes(self) -> list[int]:
        return [t.index for t in self.turns if t.changed]
