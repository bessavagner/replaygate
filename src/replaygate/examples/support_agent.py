from __future__ import annotations

import re
from typing import Callable

from replaygate.capture.llm import LLMClient
from replaygate.capture.tools import ToolRecorder
from replaygate.trace.models import AgentStep, ToolCall

_ORDERS = {
    "ORD-1234": {"status": "shipped", "eta": "2026-07-02"},
}

_ORDER_RE = re.compile(r"\b([A-Z]{2,}-\d+)\b")


def support_tools() -> dict[str, Callable[..., dict]]:
    def lookup_order(order_id: str) -> dict:
        record = _ORDERS.get(order_id, {"status": "unknown"})
        return {"order_id": order_id, **record}

    return {"lookup_order": lookup_order}


class SupportAgent:
    """Answers order questions.

    Cross-turn invariant: once the customer has given an order id, never re-ask
    for it on a later turn — carry it forward from the conversation history.
    """

    SYSTEM = "You are a support agent. Reuse the order id the customer already gave you."

    def __init__(self, llm: LLMClient, tools: ToolRecorder, inject_regression: bool = False):
        self._llm = llm
        self._tools = tools
        self._inject_regression = inject_regression
        self._counter = 0

    def _last_user_text(self, history: list[dict]) -> str:
        for msg in reversed(history):
            if msg["role"] == "user":
                return msg["content"]
        return ""

    def _remembered_order_id(self, history: list[dict]) -> str | None:
        for msg in history:
            if msg["role"] != "user":
                continue
            m = _ORDER_RE.search(msg["content"])
            if m:
                return m.group(1)
        return None

    def respond(self, history: list[dict]) -> AgentStep:
        resp = self._llm.create("claude-haiku-4-5", self.SYSTEM, history, [])
        if self._inject_regression:
            # Deliberate cross-turn bug: only look at the current turn, so an
            # order id given on an earlier turn is forgotten and re-requested.
            m = _ORDER_RE.search(self._last_user_text(history))
            order_id = m.group(1) if m else None
        else:
            order_id = self._remembered_order_id(history)

        if order_id is None:
            return AgentStep(assistant_text="Sure — what's your order number?", tool_calls=[])

        self._counter += 1
        result = self._tools.call("lookup_order", {"order_id": order_id})
        return AgentStep(assistant_text=resp.text, tool_calls=[ToolCall(
            name="lookup_order", arguments={"order_id": order_id}, result=result,
            call_id=f"call-{self._counter}",
        )])
