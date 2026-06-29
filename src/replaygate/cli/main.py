from __future__ import annotations

from datetime import datetime, timezone

import typer

from replaygate.capture.adapters import DirectAdapter
from replaygate.capture.record import record_conversation
from replaygate.capture.replay import diff_conversations, replay_conversation
from replaygate.examples.scenarios import EXAMPLES, scripted_llm_for
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
