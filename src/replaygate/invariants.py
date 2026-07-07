"""Cross-turn invariants: properties that span a whole conversation.

An invariant is a pure function ``Conversation -> InvariantResult`` — the layer
that catches regressions a per-turn assertion structurally misses, e.g. booking
before the user confirmed (three turns back).

This module is scenario-agnostic: it defines the result type, a registry mapping
scenario names to their invariants, and a runner. Concrete invariants live with
the code they guard — the built-in examples register theirs in
``replaygate.examples.invariants``.
"""

from __future__ import annotations

from typing import Callable

from pydantic import BaseModel

from replaygate.trace.models import Conversation


class InvariantResult(BaseModel):
    name: str
    passed: bool
    detail: str


_REGISTRY: dict[str, list[Callable[[Conversation], InvariantResult]]] = {}


def register(scenario: str, invariant: Callable[[Conversation], InvariantResult]) -> None:
    """Register an invariant that must hold for ``scenario``."""
    _REGISTRY.setdefault(scenario, []).append(invariant)


def invariants_for(scenario: str) -> list[Callable[[Conversation], InvariantResult]]:
    return list(_REGISTRY.get(scenario, []))


def check_conversation(
    conv: Conversation, invariants: list[Callable[[Conversation], InvariantResult]]
) -> list[InvariantResult]:
    return [inv(conv) for inv in invariants]
