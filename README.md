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
`booked_only_after_confirmation` evaluated over the entire replayed conversation.

> **Status: v0.** The trace contract, span store, app-seam record/replay wrappers, a channel
> adapter, offline replay-and-diff, the **cross-turn invariant suite**, OpenTelemetry span emission
> through the capture loop, the `record` / `replay` / `regress` CLI, an advisory **semantic
> judge** (`--judge` / `--judge-gate`), and a **read-only dashboard** are shipped and tested
> (fully offline). Channel adapters beyond `direct` are next — see [Roadmap](#roadmap).

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

Replay a *different* candidate agent against a recording and gate on the same invariants. A
key-miss means the candidate left the recorded trajectory — under the default `pinned` policy
that's a first-class *divergence* (exit 3); `--policy live` falls back to the real provider and
evaluates invariants over the candidate's actual run:

```bash
replaygate regress ./fx --candidate support_reworded               # exit 3: diverged (offline)
replaygate regress ./fx --candidate support_reworded --policy live # invariants over the real run
replaygate regress ./fx --candidate support_regressed              # exit 1: invariant violated
```

## Semantic judge (`--judge`)

For dimensions a deterministic predicate can't express — goal completion, relevance, tone — a
recorded judge verdict can be replayed alongside the invariants. Like the LLM/tool calls, judge
calls are captured and replayed offline, keyed by the conversation and requested dimensions.

Record a verdict into an existing fixture once (a live Anthropic call), then replay it offline
forever:

```bash
replaygate judge-record ./fx          # live: score the fixture, persist judge_recording.json
replaygate regress ./fx --judge       # per-dimension verdicts, advisory, fully offline
replaygate regress ./fx --judge-gate  # opt-in: judge failures fail the run (exit 4)
replaygate regress ./fx               # unchanged: deterministic gate only
```

`judge-record` is the only step that touches the network; it reads `ANTHROPIC_API_KEY` from the
environment (or a local `.env`) and defaults to `claude-opus-4-8` (override with `--model`).
Re-running it overwrites the fixture's prior verdict. Without a recorded verdict, `regress
--judge` is a no-op advisory ("no recorded verdict"), while `--judge-gate` refuses to run at all
(exit 2) — a gate that cannot be evaluated must not report a pass.

A verdict is keyed to the exact conversation it scored, so it only replays for the fixture's own
agent. Running `regress --judge --candidate X` (or `--policy live`) judges a *different*
trajectory and finds no matching verdict: under `--judge` that stays advisory, and under
`--judge-gate` it is an exit 2. Record a verdict for that candidate if you want to gate on it.

`--judge` is **advisory** — it prints per-dimension scores but never changes the exit code.
Gating is opt-in via `--judge-gate`, which fails the run (exit 4) if any judged dimension scores
below `PASS_THRESHOLD`, and exits 2 if it has no verdict to score. The deterministic invariant
gate stays authoritative either way: a violated invariant is exit 1 before the judge is consulted.

## Read-only dashboard

A baseline-vs-current conversation diff for a recorded fixture: turns side by side, the
divergent turn highlighted, cross-turn invariant chips and advisory judge chips above it.
Read-only and fixture-driven — no write path, no database, no auth.

```bash
uv pip install -e '.[dashboard]'
cd src/frontend && npm ci && npm run build && cd ../..
replaygate dashboard serve --fixtures ./fixtures --frontend ./src/frontend/dist
```

The screen worth looking at replays a recorded conversation against a *different* agent:

```bash
# baseline: support_happy   candidate: an agent that forgets the order id
open 'http://localhost:8000/runs/support_happy_judged?candidate=support_regressed'
```

`fixtures/support_happy_judged/` is the one fixture this repo ships — a `support_happy`
recording that also carries a real recorded judge verdict. Open it without a candidate
(`/runs/support_happy_judged`) to see the judge chips populated; with the candidate above
the verdict no longer applies, because a judge verdict is keyed to the conversation it
judged, so the screen honestly says no verdict was recorded for that run.

Turn 0 is identical. Turn 1 diverges — the candidate answers `"Sure — what's your order
number?"` and makes no tool call, and `order_id_never_reasked` fails with *"turn 1: re-asked
for an order id already given on turn 0"*. That is the whole thesis in one screen: turn 1 is
individually plausible and only wrong in the context of turn 0.

The frontend is Vite + React + Tailwind 4 + daisyUI 5 under `src/frontend/`; the API is
FastAPI under `src/replaygate/api/`.

### Operating it

`--fixtures` points at the *parent* of the fixture directories, not at one fixture. Omit
`--frontend` to serve the JSON API alone. Exit 2 `the dashboard extra is not installed`
means you skipped `uv pip install -e '.[dashboard]'`.

Frontend development loop — Vite serves on 5173 and proxies `/api` to 8000, so there is no
CORS configuration:

```bash
replaygate dashboard serve --fixtures ./fixtures --port 8000 &
cd src/frontend && npm run dev
```

Container — the image generates its demo fixtures at build time and listens on `$PORT`
(default 8080):

```bash
docker build -f deploy/Dockerfile -t replaygate-dashboard .
docker run --rm -p 8080:8080 replaygate-dashboard
```

The ignore file is `deploy/Dockerfile.dockerignore`, **not** `deploy/.dockerignore`: Docker
reads `.dockerignore` from the build-context root, and for a Dockerfile outside that root
BuildKit reads `<dockerfile-path>.dockerignore`. With the wrong name the rules are silently
skipped and the context grows from ~2 kB to ~200 MB.

Cloud Run — `--allow-unauthenticated` is deliberate; the surface is read-only with no write
path and no secrets in the image:

```bash
docker build -f deploy/Dockerfile -t gcr.io/YOUR_PROJECT_ID/replaygate-dashboard .
docker push gcr.io/YOUR_PROJECT_ID/replaygate-dashboard
gcloud run deploy replaygate-dashboard \
  --image gcr.io/YOUR_PROJECT_ID/replaygate-dashboard \
  --region us-central1 --allow-unauthenticated --port 8080
```

### The `regress` exit-code contract

| Exit | Meaning |
|---|---|
| 0 | every invariant held |
| 1 | an invariant was violated |
| 2 | the run could not be evaluated (no invariants, unreadable fixture, `--judge-gate` with no verdict) |
| 3 | the candidate left the recorded trajectory (divergence, `--policy pinned`) |
| 4 | `--judge-gate` only: a judged dimension scored below `PASS_THRESHOLD` (0.5) |

`--judge` is advisory and never changes the exit code. Only `--judge-gate` can produce 4.

## The trace contract

Everything hangs off a small tree of Pydantic models — `Message`, `ToolCall`, `Turn`,
`Conversation`. `Conversation` carries the cross-turn query helpers the invariants need
(`all_tool_calls`, `tool_results`); scenario-specific predicates like `user_confirmed_before` live
with the example invariants that use them (`replaygate.examples.invariants`). The bundled booking
agent ships with an `inject_regression` flag that trips the "booked before confirmation" defect on
demand — a reference target for the replay-and-diff work.

## Develop

```bash
uv pip install -e '.[dev]'
python -m pytest -q     # 143 passed, fully offline
ruff check .
```

The Anthropic SDK is a dependency but is **never imported in a test** — the suite runs with zero
network calls.

## Roadmap

- **Semantic judge** — shipped. An LLM judge for the dimensions deterministic predicates can't
  cover (goal completion, relevance, tone), behind `--judge` / `--judge-gate` and kept advisory,
  out of the deterministic PR gate by default.
- **Read-only dashboard** — shipped. A baseline-vs-current conversation diff with divergence
  highlights and invariant/judge chips, served by a read-only FastAPI + React app.
- **Channel adapters** beyond `direct` — WhatsApp first, for agents deployed on real messaging
  channels.

## Build log

I'm building ReplayGate in public. Follow the series at
[bessavagner.com/building/replaygate](https://bessavagner.com/building/replaygate/).

## License

MIT — see [LICENSE](LICENSE).
