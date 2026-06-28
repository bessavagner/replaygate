# ReplayGate

**Conversation-level regression testing for multi-turn, channel-native AI agents.**

ReplayGate records a real agent conversation once — every LLM call, tool call, and session
transition — into a deterministic fixture, then replays it offline against a new model, prompt, or
agent version and asserts **cross-turn invariants**: the properties that span a whole conversation,
not a single reply.

The bet is the one a flight recorder makes: capture the run exactly once, then replay it as many
times as you want.

## Why cross-turn

Most agent-testing tools assert one turn at a time — did *this* reply contain the right string, call
the right tool, stay under budget. That structurally misses the regressions that only exist
*between* turns:

- the agent **books before the user confirmed** (three turns back)
- it **re-asks for something it was already told**
- it **forgets a constraint** the user set earlier in the session

These are the bugs that survive a prompt tweak, pass every per-turn assertion, and break in
production. ReplayGate exists to catch exactly this class — invariants like
`user_confirmed_before(turn_index)` evaluated over the entire replayed conversation.

> **Status: v0, record half.** The trace contract, span store, app-seam record/replay wrappers, a
> channel adapter, and a `record` CLI are shipped and tested (20 tests, zero network).
> Replay-and-diff, the cross-turn assertion suite, the `regress` command, and the CI gate are next —
> see [Roadmap](#roadmap).

## Channel-native by design

Agents don't run as abstract Python calls — they run on WhatsApp, Slack, voice. A conversation that's
correct in a unit test can break on the channel because of message ordering, session windows, or
delivery quirks. ReplayGate models the channel as a first-class part of the trace
(`channel: Literal["direct", "whatsapp"]`, a `ChannelAdapter` protocol) so the same recorded
conversation can be replayed as it actually ran. The `direct` adapter ships today; channel adapters
(WhatsApp first) are on the roadmap.

## Why record at the application seam

The obvious place to capture an agent is the wire (HTTP cassettes). ReplayGate deliberately doesn't.
It wraps the agent's **`LLMClient` protocol** and its **tool registry** and logs calls there, keyed
by a stable `sha256` over `(model, system, messages, tools)`. Recording at this layer means the
fixture is readable JSON about *what the agent actually did*, and replay matches on meaning rather
than byte order. The agent only depends on a one-method protocol, so a recorder slots in front of
the real client with no change to the agent.

## Install

```bash
uv pip install -e .        # or: pip install -e .
```

Python 3.12+. Core deps: Pydantic v2, DuckDB, Typer.

## Quickstart

Record one of the built-in reference scenarios into a fixture directory:

```bash
replaygate record booking_happy ./fx
# recorded booking_happy → ./fx
```

Each recorded conversation is a fixture **directory**, not a blob:

```
conversation.json     # the trace contract, serialized
llm_recording.json    # every LLM exchange, keyed
tool_recording.json   # every tool call + result
spans.jsonl           # OpenTelemetry-aligned timing spans
meta.json             # scenario, agent version, model, recorded_at
```

Timing spans are stored in DuckDB with attributes aligned to OpenTelemetry's GenAI semantic
conventions (`gen_ai.request.model`, `gen_ai.agent.name`, …).

## The trace contract

Everything hangs off a small tree of Pydantic models — `Message`, `ToolCall`, `Turn`,
`Conversation`. `Conversation` carries the query helpers the regression detector needs, e.g.
`user_confirmed_before(turn_index)`. The bundled booking agent ships with an `inject_regression`
flag that trips the "booked before confirmation" defect on demand — a reference target for the
replay-and-diff work.

## Develop

```bash
uv pip install -e '.[dev]'
python -m pytest -q     # 20 passed, fully offline
ruff check .
```

The Anthropic SDK is a dependency but is **never imported in a test** — the suite runs with zero
network calls.

## Roadmap

- **Replay half:** feed `llm_recording` / `tool_recording` back in replay mode, run the recorded
  conversation against the current agent, and diff the two into a `ConversationDiff`.
- **Cross-turn assertion suite** over the replayed conversation (the `user_confirmed_before` class).
- **`replaygate regress`** command + a CI gate that fails on divergence.
- Wire OpenTelemetry spans through the capture loop now that there's a consumer for them.
- **Channel adapters** beyond `direct` — WhatsApp first, for agents deployed on real messaging
  channels.

## Build log

I'm building ReplayGate in public. Follow the series at
[bessavagner.com/building/replaygate](https://bessavagner.com/building/replaygate/).
