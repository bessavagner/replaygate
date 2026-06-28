from __future__ import annotations

from replaygate.capture.adapters import Scenario
from replaygate.capture.llm import LLMClient, LLMResponse

BUILTIN_SCENARIOS: dict[str, Scenario] = {
    "booking_happy": Scenario(
        name="booking_happy",
        user_turns=[["what slots are there on 2026-07-01?"], ["yes, book 3pm"]],
    ),
}

_SCRIPTS: dict[str, list[LLMResponse]] = {
    "booking_happy": [
        LLMResponse(text="There are 10am and 3pm available.",
                    tool_calls=[{"name": "search_slots", "arguments": {"date": "2026-07-01"}}]),
        LLMResponse(text="Booked 3pm. See you then!",
                    tool_calls=[{"name": "book_appointment", "arguments": {"slot": "3pm"}}]),
    ],
}


class _ScriptedLLM:
    def __init__(self, responses: list[LLMResponse]):
        self._responses = list(responses)

    def create(self, model, system, messages, tools) -> LLMResponse:
        return self._responses.pop(0)


def scripted_llm_for(scenario_name: str) -> LLMClient:
    return _ScriptedLLM(list(_SCRIPTS[scenario_name]))
