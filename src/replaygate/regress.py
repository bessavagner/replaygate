"""The regression gate: replay a fixture offline and assert its cross-turn invariants.

This is what turns a faithful replay into a *gate*. ``run_regress`` re-runs the
recorded conversation against the agent (zero network, served from the
recording) and evaluates the invariants registered for the fixture's scenario
over the replayed conversation.
"""

from __future__ import annotations

from typing import Callable

from pydantic import BaseModel

from replaygate.capture.replay import replay_conversation
from replaygate.invariants import InvariantResult, check_conversation, invariants_for
from replaygate.store.fixtures import Fixture
from replaygate.trace.models import Conversation


class RegressReport(BaseModel):
    scenario: str
    results: list[InvariantResult]

    @property
    def passed(self) -> bool:
        # Vacuously True when no invariants are registered for the scenario. The
        # CLI guards that case explicitly (exit 2) before consulting `passed`, so
        # an unguarded scenario never slips through as a false pass.
        return all(r.passed for r in self.results)


def run_regress(
    fixture: Fixture,
    build_agent: Callable[..., object],
    tools: dict[str, Callable[..., dict]],
) -> RegressReport:
    replayed: Conversation = replay_conversation(fixture, build_agent, tools)
    scenario = fixture.conversation.scenario
    results = check_conversation(replayed, invariants_for(scenario))
    return RegressReport(scenario=scenario, results=results)
