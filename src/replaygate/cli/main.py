from __future__ import annotations

from datetime import datetime, timezone

import typer

from replaygate.capture.adapters import DirectAdapter
from replaygate.capture.record import record_conversation
from replaygate.capture.replay import diff_conversations, replay_conversation
from replaygate.examples.scenarios import CANDIDATES, EXAMPLES, scripted_llm_for
from replaygate.regress import run_regress
from replaygate.store.fixtures import read_fixture, write_fixture

app = typer.Typer(help="ReplayGate — regression testing for multi-turn AI agents")


@app.callback()
def main() -> None:
    """ReplayGate CLI."""


def _spec_for(scenario_name: str):
    try:
        return EXAMPLES[scenario_name]
    except KeyError:
        raise typer.BadParameter(
            f"unknown scenario {scenario_name!r}; choose from: {', '.join(EXAMPLES)}"
        ) from None


@app.command()
def record(scenario_name: str, out_dir: str, channel: str = "direct") -> None:
    """Record a built-in scenario into a fixture directory (offline)."""
    spec = _spec_for(scenario_name)
    fixture = record_conversation(
        agent_factory=spec.build_agent,
        inner_llm=scripted_llm_for(scenario_name),
        scenario=spec.scenario,
        adapter=DirectAdapter(),
        tools=spec.tools(),
        agent_version="dev",
        model=spec.model,
        recorded_at=datetime.now(timezone.utc),
    )
    write_fixture(out_dir, fixture)
    typer.echo(f"recorded {scenario_name} → {out_dir}")


@app.command(name="record-live")
def record_live(
    scenario_name: str,
    out_dir: str,
    provider: str = "anthropic",
    model: str | None = None,
    channel: str = "direct",
) -> None:
    """Record a built-in scenario against a real provider (anthropic|openai|openrouter|ollama).

    Reads API keys from the environment (and a local .env if present). Use --model
    to override the model the agent requests, e.g. to run on OpenAI or Ollama.
    """
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ModuleNotFoundError:
        pass  # .env support is optional; env vars may already be set

    from replaygate.capture.providers import make_client

    spec = _spec_for(scenario_name)
    try:
        inner_llm = make_client(provider, model=model)
    except ValueError as e:
        raise typer.BadParameter(str(e)) from None
    fixture = record_conversation(
        agent_factory=spec.build_agent,
        inner_llm=inner_llm,
        scenario=spec.scenario,
        adapter=DirectAdapter(),
        tools=spec.tools(),
        agent_version=f"live-{provider}",
        model=model or spec.model,
        recorded_at=datetime.now(timezone.utc),
    )
    write_fixture(out_dir, fixture)
    typer.echo(f"recorded {scenario_name} live via {provider} → {out_dir}")


@app.command()
def replay(fixture_dir: str) -> None:
    """Replay a recorded fixture offline and diff it against the recording (zero network)."""
    try:
        fixture = read_fixture(fixture_dir)
    except (FileNotFoundError, NotADirectoryError) as e:
        typer.echo(f"cannot read fixture at {fixture_dir!r}: {e}", err=True)
        raise typer.Exit(2) from None
    scenario = fixture.conversation.scenario
    if scenario not in EXAMPLES:
        typer.echo(f"fixture scenario {scenario!r} is not a built-in example", err=True)
        raise typer.Exit(2)
    spec = EXAMPLES[scenario]
    replayed = replay_conversation(fixture, spec.build_agent, spec.tools())
    diffs = diff_conversations(fixture.conversation, replayed)
    if diffs:
        typer.echo(f"replay MISMATCH ({fixture.conversation.scenario}):")
        for d in diffs:
            typer.echo(f"  - {d}")
        raise typer.Exit(1)
    typer.echo(f"replay OK — {len(replayed.turns)} turns reproduced offline, zero network")


@app.command()
def regress(
    fixture_dir: str,
    candidate: str = typer.Option(
        None, help="candidate agent from the registry; default replays the fixture's own agent"
    ),
    policy: str = typer.Option(
        "pinned", help="pinned (offline) | live (network fallback on divergence)"
    ),
    provider: str = typer.Option("anthropic", help="provider for --policy live"),
) -> None:
    """Replay a fixture and assert its cross-turn invariants — the regression gate.

    With --candidate, replay a *different* agent against the recording. Under
    --policy pinned a divergence is exit 3; under live it falls back to the
    provider and evaluates invariants over the candidate's real trajectory.
    """
    try:
        fixture = read_fixture(fixture_dir)
    except (FileNotFoundError, NotADirectoryError) as e:
        typer.echo(f"cannot read fixture at {fixture_dir!r}: {e}", err=True)
        raise typer.Exit(2) from None
    scenario = fixture.conversation.scenario
    if scenario not in EXAMPLES:
        typer.echo(f"fixture scenario {scenario!r} is not a built-in example", err=True)
        raise typer.Exit(2)
    if policy not in ("pinned", "live"):
        raise typer.BadParameter("policy must be 'pinned' or 'live'")

    if candidate is None:
        spec = EXAMPLES[scenario]
        build_agent, tools = spec.build_agent, spec.tools()
    else:
        if candidate not in CANDIDATES:
            raise typer.BadParameter(
                f"unknown candidate {candidate!r}; choose from: {', '.join(CANDIDATES)}"
            )
        cand = CANDIDATES[candidate]
        build_agent, tools = cand.build_agent, cand.tools()

    inner_llm = None
    if policy == "live":
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except ModuleNotFoundError:
            pass  # .env support is optional; env vars may already be set
        from replaygate.capture.providers import make_client

        try:
            inner_llm = make_client(provider, model=fixture.meta.model)
        except ValueError as e:
            raise typer.BadParameter(str(e)) from None

    report = run_regress(fixture, build_agent, tools, policy=policy, inner_llm=inner_llm)

    if report.status == "diverged":
        typer.echo(f"regress DIVERGED ({scenario}): candidate left the recorded trajectory")
        for d in report.divergences:
            typer.echo(f"  - turn {d.turn_index} [{d.kind}]: {d.summary}")
        typer.echo("  invariants not evaluated (candidate left recorded trajectory)")
        raise typer.Exit(3)

    if not report.results:
        typer.echo(f"no invariants registered for scenario {scenario!r}", err=True)
        raise typer.Exit(2)
    for r in report.results:
        typer.echo(f"  [{'PASS' if r.passed else 'FAIL'}] {r.name}: {r.detail}")
    failed = [r for r in report.results if not r.passed]
    if failed:
        typer.echo(f"regress FAILED ({scenario}): {len(failed)} invariant(s) violated")
        raise typer.Exit(1)
    typer.echo(f"regress OK ({scenario}): {len(report.results)} invariant(s) held")
