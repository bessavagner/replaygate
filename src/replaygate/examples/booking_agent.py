from __future__ import annotations

from typing import Callable

from pydantic import BaseModel

from replaygate.capture.llm import LLMClient
from replaygate.capture.tools import ToolRecorder
from replaygate.trace.models import ToolCall

_SLOTS = {"2026-07-01": ["10am", "3pm"]}


def booking_tools() -> dict[str, Callable[..., dict]]:
    def search_slots(date: str) -> dict:
        return {"date": date, "slots": _SLOTS.get(date, [])}

    def book_appointment(slot: str) -> dict:
        return {"booked": True, "slot": slot}

    return {"search_slots": search_slots, "book_appointment": book_appointment}


class AgentStep(BaseModel):
    assistant_text: str
    tool_calls: list[ToolCall]


class BookingAgent:
    SYSTEM = "You are a booking assistant. Confirm with the user before booking."

    def __init__(self, llm: LLMClient, tools: ToolRecorder, inject_regression: bool = False):
        self._llm = llm
        self._tools = tools
        self._inject_regression = inject_regression
        self._counter = 0

    def respond(self, history: list[dict]) -> AgentStep:
        resp = self._llm.create("claude-haiku-4-5", self.SYSTEM, history, [])
        calls: list[ToolCall] = []
        requested = list(resp.tool_calls)
        if self._inject_regression and not requested:
            # Deliberate cross-turn bug: book without a confirmation step.
            requested = [{"name": "book_appointment", "arguments": {"slot": "3pm"}}]
        for rc in requested:
            self._counter += 1
            result = self._tools.call(rc["name"], rc["arguments"])
            calls.append(ToolCall(
                name=rc["name"], arguments=rc["arguments"], result=result,
                call_id=f"call-{self._counter}",
            ))
        return AgentStep(assistant_text=resp.text, tool_calls=calls)
