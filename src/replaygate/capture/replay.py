"""Replay a recorded fixture offline and diff it against the recording.

This is the flight-recorder playback: re-run the agent against the recorded LLM
and tool exchanges (keyed by content), with zero network. Because replay drives
``RecordingLLMClient``/``ToolRecorder`` in replay mode, no provider SDK is
imported and no API key is needed — a fixture recorded against any provider
replays identically.
"""

from __future__ import annotations

from typing import Callable

from replaygate.capture.llm import RecordingLLMClient
from replaygate.capture.tools import ToolRecorder
from replaygate.store.fixtures import Fixture
from replaygate.trace.models import Conversation, Message, Turn


def replay_conversation(
    fixture: Fixture,
    agent_factory: Callable[[RecordingLLMClient, ToolRecorder], object],
    tools: dict[str, Callable[..., dict]],
) -> Conversation:
    """Re-run the agent over the fixture's user turns, served from the recording."""
    rec_llm = RecordingLLMClient(inner=None, mode="replay", recording=fixture.llm_recording)
    rec_tools = ToolRecorder(tools, mode="replay", recording=fixture.tool_recording)
    agent = agent_factory(rec_llm, rec_tools)

    ts = fixture.conversation.session_meta.started_at
    history: list[dict] = []
    turns: list[Turn] = []
    for turn in fixture.conversation.turns:
        for m in turn.user_messages:
            history.append({"role": "user", "content": m.content})
        step = agent.respond(history)
        history.append({"role": "assistant", "content": step.assistant_text})
        turns.append(Turn(
            index=turn.index,
            user_messages=turn.user_messages,
            assistant_messages=[Message(role="assistant", content=step.assistant_text, ts=ts)],
            tool_calls=step.tool_calls,
        ))

    original = fixture.conversation
    return original.model_copy(update={"turns": turns})


def _tool_sig(tc) -> tuple:
    return (tc.name, tc.arguments, tc.result)


def diff_conversations(recorded: Conversation, replayed: Conversation) -> list[str]:
    """Return human-readable differences; empty list means a faithful replay."""
    diffs: list[str] = []
    if len(recorded.turns) != len(replayed.turns):
        diffs.append(f"turn count: recorded {len(recorded.turns)} != replayed {len(replayed.turns)}")
        return diffs

    for rec, rep in zip(recorded.turns, replayed.turns):
        rec_text = " ".join(m.content for m in rec.assistant_messages)
        rep_text = " ".join(m.content for m in rep.assistant_messages)
        if rec_text != rep_text:
            diffs.append(f"turn {rec.index} assistant text: {rec_text!r} != {rep_text!r}")
        rec_calls = [_tool_sig(tc) for tc in rec.tool_calls]
        rep_calls = [_tool_sig(tc) for tc in rep.tool_calls]
        if rec_calls != rep_calls:
            diffs.append(f"turn {rec.index} tool calls: {rec_calls} != {rep_calls}")
    return diffs
