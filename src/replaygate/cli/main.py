from __future__ import annotations

from datetime import datetime, timezone

import typer

from replaygate.capture.adapters import DirectAdapter
from replaygate.capture.record import record_conversation
from replaygate.examples.booking_agent import BookingAgent
from replaygate.examples.scenarios import BUILTIN_SCENARIOS, scripted_llm_for
from replaygate.store.fixtures import write_fixture

app = typer.Typer(help="ReplayGate — regression testing for multi-turn AI agents")


@app.callback()
def main() -> None:
    """ReplayGate CLI."""


@app.command()
def record(scenario_name: str, out_dir: str, channel: str = "direct") -> None:
    """Record a built-in scenario into a fixture directory (offline)."""
    scenario = BUILTIN_SCENARIOS[scenario_name]
    fixture = record_conversation(
        agent_factory=lambda llm, tools: BookingAgent(llm=llm, tools=tools),
        inner_llm=scripted_llm_for(scenario_name),
        scenario=scenario,
        adapter=DirectAdapter(),
        agent_version="dev",
        model="claude-haiku-4-5",
        recorded_at=datetime.now(timezone.utc),
    )
    write_fixture(out_dir, fixture)
    typer.echo(f"recorded {scenario_name} → {out_dir}")
