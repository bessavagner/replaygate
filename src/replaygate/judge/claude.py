"""Claude-backed ``Judge`` using forced ``tool_use`` for structured verdicts.

The verdict tool is the only allowed tool (``tool_choice`` pins it), so the model
returns validated JSON, not prose. The ``anthropic`` import is lazy and the client
is injectable — the offline suite drives a fake client and never imports the SDK.
Schema shape confirmed against the Anthropic tool_use / tool_choice docs.
"""

from __future__ import annotations

from typing import Any

from replaygate.judge.models import DimensionVerdict, JudgeVerdict
from replaygate.trace.models import Conversation

_VERDICT_TOOL_NAME = "record_verdict"

SYSTEM = (
    "You are an offline evaluation judge. For each requested dimension, score the "
    "conversation from 0.0 (fails the dimension) to 1.0 (fully satisfies it) and give "
    "a one-sentence rationale. Call the record_verdict tool exactly once, covering "
    "every requested dimension."
)


def _verdict_tool(dimensions: list[str]) -> dict:
    return {
        "name": _VERDICT_TOOL_NAME,
        "description": "Record the per-dimension verdict for the conversation.",
        "input_schema": {
            "type": "object",
            "properties": {
                "verdicts": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "dimension": {"type": "string", "enum": list(dimensions)},
                            "score": {"type": "number"},
                            "rationale": {"type": "string"},
                        },
                        "required": ["dimension", "score", "rationale"],
                    },
                },
            },
            "required": ["verdicts"],
        },
    }


def _render(conversation: Conversation) -> str:
    lines: list[str] = []
    for turn in conversation.turns:
        for m in turn.user_messages:
            lines.append(f"User: {m.content}")
        for m in turn.assistant_messages:
            lines.append(f"Assistant: {m.content}")
    return "\n".join(lines)


class ClaudeJudge:
    """Judges a conversation via Claude with a single forced verdict tool call."""

    def __init__(self, *, model: str = "claude-opus-4-8", api_key: str | None = None,
                 max_tokens: int = 1024, client: Any = None):
        if client is None:
            from anthropic import Anthropic  # lazy: keeps the offline core anthropic-free

            client = Anthropic(api_key=api_key)  # api_key=None → ANTHROPIC_API_KEY
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    def judge(self, conversation: Conversation, dimensions: list[str]) -> JudgeVerdict:
        content = (
            f"Dimensions to score: {', '.join(dimensions)}\n\n"
            f"Conversation:\n{_render(conversation)}"
        )
        resp = self._client.messages.create(
            model=self._model,
            max_tokens=self._max_tokens,
            system=SYSTEM,
            messages=[{"role": "user", "content": content}],
            tools=[_verdict_tool(dimensions)],
            tool_choice={"type": "tool", "name": _VERDICT_TOOL_NAME},
        )
        block = next(b for b in resp.content if b.type == "tool_use")
        return JudgeVerdict(
            scenario=conversation.scenario,
            verdicts=[DimensionVerdict.model_validate(v) for v in dict(block.input)["verdicts"]],
        )
