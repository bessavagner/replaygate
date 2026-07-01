"""The regression gate: replay a fixture offline and assert its cross-turn invariants.

``run_regress`` re-runs the recorded conversation against a candidate agent (served
from the recording) and evaluates the invariants registered for the fixture's
scenario. A call the candidate makes that is absent from the recording is a
*divergence* — under ``pinned`` a distinct outcome (invariants not evaluated),
under ``live`` resolved by the real provider so invariants run over the real path.
"""

from __future__ import annotations

from typing import Callable, Literal

from pydantic import BaseModel, Field

from replaygate.capture.errors import DivergenceError
from replaygate.capture.llm import LLMClient
from replaygate.capture.replay import replay_conversation
from replaygate.invariants import InvariantResult, check_conversation, invariants_for
from replaygate.store.fixtures import Fixture
from replaygate.trace.models import Conversation


class Divergence(BaseModel):
    turn_index: int
    kind: Literal["llm", "tool"]
    summary: str


class RegressReport(BaseModel):
    scenario: str
    policy: Literal["pinned", "live"] = "pinned"
    results: list[InvariantResult] = Field(default_factory=list)
    divergences: list[Divergence] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        # A divergence is not a pass. Otherwise: vacuously True when no invariants
        # are registered — the CLI guards that case (exit 2) before consulting this.
        return not self.divergences and all(r.passed for r in self.results)

    @property
    def status(self) -> Literal["ok", "failed", "diverged"]:
        if self.divergences:
            return "diverged"
        if any(not r.passed for r in self.results):
            return "failed"
        return "ok"


def run_regress(
    fixture: Fixture,
    build_agent: Callable[..., object],
    tools: dict[str, Callable[..., dict]],
    *,
    policy: Literal["pinned", "live"] = "pinned",
    inner_llm: LLMClient | None = None,
) -> RegressReport:
    if policy == "live" and inner_llm is None:
        raise ValueError("policy='live' requires an inner_llm to resolve divergences")
    scenario = fixture.conversation.scenario
    try:
        replayed: Conversation = replay_conversation(
            fixture, build_agent, tools, policy=policy, inner_llm=inner_llm
        )
    except DivergenceError as e:
        div = Divergence(
            turn_index=e.turn_index if e.turn_index is not None else -1,
            kind=e.kind,
            summary=e.summary,
        )
        return RegressReport(scenario=scenario, policy=policy, results=[], divergences=[div])
    results = check_conversation(replayed, invariants_for(scenario))
    return RegressReport(scenario=scenario, policy=policy, results=results)
