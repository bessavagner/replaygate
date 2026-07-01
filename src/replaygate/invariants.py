"""Cross-turn invariants: properties that span a whole conversation.

Each invariant is a pure function ``Conversation -> InvariantResult``. This is
the layer that catches regressions a per-turn assertion structurally misses,
e.g. booking before the user confirmed (three turns back).
"""

from __future__ import annotations

import re

from pydantic import BaseModel

from replaygate.trace.models import Conversation

_ORDER_RE = re.compile(r"\b[A-Z]{2,}-\d+\b")
_REASK_RE = re.compile(r"order\s+(number|id|#)", re.IGNORECASE)
_NO_DAIRY_RE = re.compile(r"\b(no dairy|dairy[- ]free|vegan|lactose)\b", re.IGNORECASE)


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


def order_id_never_reasked(conv: Conversation) -> InvariantResult:
    name = "order_id_never_reasked"
    given_at: int | None = None
    for turn in conv.turns:
        if any(_ORDER_RE.search(m.content) for m in turn.user_messages):
            given_at = turn.index
            break
    if given_at is None:
        return InvariantResult(name=name, passed=True, detail="no order id was ever given")
    for turn in conv.turns:
        if turn.index <= given_at:
            continue
        for m in turn.assistant_messages:
            if _REASK_RE.search(m.content):
                return InvariantResult(
                    name=name, passed=False,
                    detail=f"turn {turn.index}: re-asked for an order id already given on turn {given_at}",
                )
    return InvariantResult(name=name, passed=True, detail="order id carried forward, never re-asked")


def dietary_constraint_honored(conv: Conversation) -> InvariantResult:
    name = "dietary_constraint_honored"
    no_dairy = any(
        _NO_DAIRY_RE.search(m.content)
        for turn in conv.turns for m in turn.user_messages
    )
    if not no_dairy:
        return InvariantResult(name=name, passed=True, detail="no dietary constraint was set")
    for turn in conv.turns:
        for tc in turn.tool_calls:
            if tc.name == "recommend_dish" and tc.result and tc.result.get("contains_dairy"):
                return InvariantResult(
                    name=name, passed=False,
                    detail=f"turn {turn.index}: recommended a dairy dish despite a no-dairy constraint",
                )
    return InvariantResult(name=name, passed=True, detail="all recommendations honored the constraint")
