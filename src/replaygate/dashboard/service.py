"""Fixture-directory reads for the dashboard — read-only by construction.

``load_run`` re-runs the existing regression gate (``run_regress``) over a fixture
and reshapes the result into a ``DiffView``. It is a *view over the gate*, not a
second implementation of it: if the CLI says a run failed, so does the dashboard.
"""

from __future__ import annotations

from pathlib import Path

from replaygate.capture.replay import turn_diff_flags
from replaygate.dashboard.models import (
    DiffView,
    DivergenceView,
    InvariantChip,
    JudgeChip,
    RunSummary,
    ToolCallView,
    TurnDiff,
    TurnSide,
)
from replaygate.examples.scenarios import CANDIDATES, EXAMPLES
from replaygate.judge.record import RecordingJudge
from replaygate.judge.registry import dimensions_for
from replaygate.regress import RegressReport, run_regress
from replaygate.store.fixtures import Fixture, read_fixture
from replaygate.trace.models import Turn


class RunNotFound(LookupError):
    """No readable fixture directory named ``run_id`` under the configured root."""


class UnknownCandidate(LookupError):
    """The requested candidate agent is not in the candidate registry."""


def _is_fixture_dir(path: Path) -> bool:
    return path.is_dir() and (path / "conversation.json").is_file()


def list_runs(root: Path) -> list[RunSummary]:
    """Every fixture directory directly under ``root``, sorted by run id."""
    if not root.is_dir():
        return []
    summaries: list[RunSummary] = []
    for child in sorted(root.iterdir()):
        if not _is_fixture_dir(child):
            continue
        fixture = read_fixture(str(child))
        summaries.append(
            RunSummary(
                run_id=child.name,
                scenario=fixture.conversation.scenario,
                channel=fixture.conversation.channel,
                model=fixture.meta.model,
                agent_version=fixture.meta.agent_version,
                recorded_at=fixture.meta.recorded_at,
                turn_count=len(fixture.conversation.turns),
            )
        )
    return summaries


def _resolve(root: Path, run_id: str) -> Path:
    """Resolve ``run_id`` to a fixture directory, refusing anything but a direct child.

    This surface is public and unauthenticated and ``run_id`` arrives from the URL,
    so a name that is not a single path segment is refused outright rather than
    normalized.
    """
    if run_id in ("", ".", "..") or run_id != Path(run_id).name:
        raise RunNotFound(run_id)
    path = root / run_id
    if not _is_fixture_dir(path):
        raise RunNotFound(run_id)
    return path


def _assistant_text(turn: Turn) -> str:
    return " ".join(m.content for m in turn.assistant_messages)


def _user_text(turn: Turn) -> str:
    return " ".join(m.content for m in turn.user_messages)


def _side(turn: Turn) -> TurnSide:
    return TurnSide(
        assistant_text=_assistant_text(turn),
        tool_calls=[
            ToolCallView(
                name=tc.name, arguments=tc.arguments, result=tc.result, error=tc.error
            )
            for tc in turn.tool_calls
        ],
    )


def _judge_chips(report: RegressReport, scenario: str) -> tuple[list[JudgeChip], str | None]:
    if report.judge_verdict is not None:
        chips = [
            JudgeChip(dimension=v.dimension, score=v.score, rationale=v.rationale)
            for v in report.judge_verdict.verdicts
        ]
        return chips, None
    if not dimensions_for(scenario):
        return [], f"no judge dimensions registered for scenario {scenario!r}"
    return [], "no recorded verdict for this fixture; run `replaygate judge-record` first"


def _build_diff_view(
    run_id: str, fixture: Fixture, report: RegressReport, candidate: str | None
) -> DiffView:
    baseline = fixture.conversation
    replayed = report.replayed
    turns: list[TurnDiff] = []
    for position, recorded in enumerate(baseline.turns):
        current = (
            replayed.turns[position]
            if replayed is not None and position < len(replayed.turns)
            else None
        )
        text_changed, tools_changed = (
            turn_diff_flags(recorded, current) if current is not None else (False, False)
        )
        turns.append(
            TurnDiff(
                index=recorded.index,
                user_text=_user_text(recorded),
                baseline=_side(recorded),
                current=_side(current) if current is not None else None,
                text_changed=text_changed,
                tools_changed=tools_changed,
            )
        )

    judge, judge_note = _judge_chips(report, baseline.scenario)
    return DiffView(
        run_id=run_id,
        scenario=baseline.scenario,
        candidate=candidate,
        status=report.status,
        channel=baseline.channel,
        model=fixture.meta.model,
        agent_version=fixture.meta.agent_version,
        recorded_at=fixture.meta.recorded_at,
        turns=turns,
        divergences=[
            DivergenceView(turn_index=d.turn_index, kind=d.kind, summary=d.summary)
            for d in report.divergences
        ],
        invariants=[
            InvariantChip(name=r.name, passed=r.passed, detail=r.detail) for r in report.results
        ],
        judge=judge,
        judge_note=judge_note,
    )


def load_run(root: Path, run_id: str, candidate: str | None = None) -> DiffView:
    """Replay ``run_id`` (optionally against ``candidate``) and shape it for the UI."""
    fixture = read_fixture(str(_resolve(root, run_id)))
    scenario = fixture.conversation.scenario
    if scenario not in EXAMPLES:
        raise RunNotFound(run_id)

    if candidate is None:
        spec = EXAMPLES[scenario]
        build_agent, tools = spec.build_agent, spec.tools()
    else:
        if candidate not in CANDIDATES:
            raise UnknownCandidate(candidate)
        cand = CANDIDATES[candidate]
        build_agent, tools = cand.build_agent, cand.tools()

    # Replay-mode judge with on_miss="raise": a verdict that was never recorded stays
    # a missing verdict. The dashboard must never make a live call.
    judge = RecordingJudge(
        inner=None, mode="replay", recording=fixture.judge_recording, on_miss="raise"
    )
    report = run_regress(fixture, build_agent, tools, judge=judge)
    return _build_diff_view(run_id, fixture, report, candidate)
