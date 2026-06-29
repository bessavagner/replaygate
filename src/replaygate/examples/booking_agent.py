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


def booking_tool_schemas() -> list[dict]:
    """Tool declarations sent to the LLM (neutral shape; translated per provider).

    Distinct from booking_tools(): these tell the model what it *may* call;
    booking_tools() is what actually runs when it does.
    """
    return [
        {
            "name": "search_slots",
            "description": "List available appointment slots for a date (YYYY-MM-DD).",
            "input_schema": {
                "type": "object",
                "properties": {"date": {"type": "string", "description": "Date as YYYY-MM-DD"}},
                "required": ["date"],
            },
        },
        {
            "name": "book_appointment",
            "description": "Book an appointment for a slot, only after the user confirms.",
            "input_schema": {
                "type": "object",
                "properties": {"slot": {"type": "string", "description": "Slot to book, e.g. 3pm"}},
                "required": ["slot"],
            },
        },
    ]


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
        resp = self._llm.create("claude-haiku-4-5", self.SYSTEM, history, booking_tool_schemas())
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
