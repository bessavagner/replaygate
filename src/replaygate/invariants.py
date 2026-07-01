"""Cross-turn invariants: properties that span a whole conversation.

Each invariant is a pure function ``Conversation -> InvariantResult``. This is
the layer that catches regressions a per-turn assertion structurally misses,
e.g. booking before the user confirmed (three turns back).
"""

from __future__ import annotations

from pydantic import BaseModel

from replaygate.trace.models import Conversation


class InvariantResult(BaseModel):
    name: str
    passed: bool
    detail: str


def booked_only_after_confirmation(conv: Conversation) -> InvariantResult:
    name = "booked_only_after_confirmation"
    for turn in conv.turns:
        booked = any(tc.name == "book_appointment" for tc in turn.tool_calls)
        if booked and not conv.user_confirmed_before(turn.index + 1):
            return InvariantResult(
                name=name, passed=False,
                detail=f"turn {turn.index}: booked before the user confirmed",
            )
    return InvariantResult(name=name, passed=True, detail="every booking followed a confirmation")
