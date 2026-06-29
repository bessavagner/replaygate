from __future__ import annotations

import re
from typing import Callable

from pydantic import BaseModel

from replaygate.capture.llm import LLMClient
from replaygate.capture.tools import ToolRecorder
from replaygate.trace.models import ToolCall

_MENU = [
    {"dish": "margherita pizza", "contains_dairy": True},
    {"dish": "veggie stir-fry", "contains_dairy": False},
]

_NO_DAIRY_RE = re.compile(r"\b(no dairy|dairy[- ]free|vegan|lactose)\b", re.IGNORECASE)
_ASK_RE = re.compile(r"\b(recommend|suggest|what should|dinner|eat|order)\b", re.IGNORECASE)


def menu_tools() -> dict[str, Callable[..., dict]]:
    def recommend_dish(avoid_dairy: bool) -> dict:
        for dish in _MENU:
            if avoid_dairy and dish["contains_dairy"]:
                continue
            return dict(dish)
        return {"dish": None, "contains_dairy": False}

    return {"recommend_dish": recommend_dish}


class AgentStep(BaseModel):
    assistant_text: str
    tool_calls: list[ToolCall]


class ProfileAgent:
    """Recommends a dish on request.

    Cross-turn invariant: honor a dietary constraint the customer set on an
    earlier turn (e.g. "no dairy") when recommending on a later turn.
    """

    SYSTEM = "You are a dining assistant. Respect the customer's dietary constraints."

    def __init__(self, llm: LLMClient, tools: ToolRecorder, inject_regression: bool = False):
        self._llm = llm
        self._tools = tools
        self._inject_regression = inject_regression
        self._counter = 0

    def _no_dairy(self, history: list[dict]) -> bool:
        return any(
            msg["role"] == "user" and _NO_DAIRY_RE.search(msg["content"])
            for msg in history
        )

    def respond(self, history: list[dict]) -> AgentStep:
        resp = self._llm.create("claude-haiku-4-5", self.SYSTEM, history, [])
        last_user = history[-1]["content"] if history else ""
        if not _ASK_RE.search(last_user):
            # No recommendation requested yet — just acknowledge.
            return AgentStep(assistant_text=resp.text, tool_calls=[])

        avoid_dairy = self._no_dairy(history)
        if self._inject_regression:
            # Deliberate cross-turn bug: forget the constraint set earlier and
            # recommend without filtering for it.
            avoid_dairy = False

        self._counter += 1
        result = self._tools.call("recommend_dish", {"avoid_dairy": avoid_dairy})
        return AgentStep(assistant_text=resp.text, tool_calls=[ToolCall(
            name="recommend_dish", arguments={"avoid_dairy": avoid_dairy}, result=result,
            call_id=f"call-{self._counter}",
        )])
