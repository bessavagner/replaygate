from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from replaygate.capture.adapters import Scenario
from replaygate.capture.llm import LLMClient, LLMResponse
from replaygate.capture.tools import ToolRecorder
from replaygate.examples import invariants as _invariants  # noqa: F401  # registers scenario invariants
from replaygate.examples import judge_dimensions as _judge_dimensions  # noqa: F401  # registers scenario dimensions
from replaygate.examples.booking_agent import BookingAgent, booking_tools
from replaygate.examples.profile_agent import ProfileAgent, menu_tools
from replaygate.examples.support_agent import RewordedSupportAgent, SupportAgent, support_tools
from replaygate.judge.models import DimensionVerdict, JudgeVerdict


@dataclass(frozen=True)
class ExampleSpec:
    """Everything the recorder needs to replay one built-in scenario offline."""

    scenario: Scenario
    build_agent: Callable[[LLMClient, ToolRecorder], object]
    tools: Callable[[], dict[str, Callable[..., dict]]]
    script: list[LLMResponse]
    model: str = "claude-haiku-4-5"


EXAMPLES: dict[str, ExampleSpec] = {
    "booking_happy": ExampleSpec(
        scenario=Scenario(
            name="booking_happy",
            user_turns=[["what slots are there on 2026-07-01?"], ["yes, book 3pm"]],
        ),
        build_agent=lambda llm, tools: BookingAgent(llm=llm, tools=tools),
        tools=booking_tools,
        script=[
            LLMResponse(text="There are 10am and 3pm available.",
                        tool_calls=[{"name": "search_slots", "arguments": {"date": "2026-07-01"}}]),
            LLMResponse(text="Booked 3pm. See you then!",
                        tool_calls=[{"name": "book_appointment", "arguments": {"slot": "3pm"}}]),
        ],
    ),
    # BookingAgent regressed: books on a turn where the user never confirmed.
    "booking_books_without_confirm_regression": ExampleSpec(
        scenario=Scenario(
            name="booking_books_without_confirm_regression",
            user_turns=[["what slots are there on 2026-07-01?"], ["hmm, let me think about it"]],
        ),
        build_agent=lambda llm, tools: BookingAgent(llm=llm, tools=tools, inject_regression=True),
        tools=booking_tools,
        script=[
            LLMResponse(text="There are 10am and 3pm available.",
                        tool_calls=[{"name": "search_slots", "arguments": {"date": "2026-07-01"}}]),
            # No tool_calls here → inject_regression makes the agent book anyway.
            LLMResponse(text="Let me go ahead and book that."),
        ],
    ),
    # SupportAgent — invariant: never re-ask for an order id given on an earlier turn.
    "support_happy": ExampleSpec(
        scenario=Scenario(
            name="support_happy",
            user_turns=[["my order ORD-1234 — has it shipped?"], ["any update on the delivery?"]],
        ),
        build_agent=lambda llm, tools: SupportAgent(llm=llm, tools=tools),
        tools=support_tools,
        script=[
            LLMResponse(text="Let me check ORD-1234 for you."),
            LLMResponse(text="ORD-1234 has shipped — ETA 2026-07-02."),
        ],
    ),
    "support_reask_regression": ExampleSpec(
        scenario=Scenario(
            name="support_reask_regression",
            user_turns=[["my order ORD-1234 — has it shipped?"], ["any update on the delivery?"]],
        ),
        build_agent=lambda llm, tools: SupportAgent(llm=llm, tools=tools, inject_regression=True),
        tools=support_tools,
        script=[
            LLMResponse(text="Let me check ORD-1234 for you."),
            LLMResponse(text="ORD-1234 has shipped — ETA 2026-07-02."),
        ],
    ),
    # ProfileAgent — invariant: honor a dietary constraint set on an earlier turn.
    "profile_happy": ExampleSpec(
        scenario=Scenario(
            name="profile_happy",
            user_turns=[["hi, I'm vegan — no dairy please"], ["what should I order for dinner?"]],
        ),
        build_agent=lambda llm, tools: ProfileAgent(llm=llm, tools=tools),
        tools=menu_tools,
        script=[
            LLMResponse(text="Noted — no dairy."),
            LLMResponse(text="I recommend the veggie stir-fry."),
        ],
    ),
    "profile_forgets_regression": ExampleSpec(
        scenario=Scenario(
            name="profile_forgets_regression",
            user_turns=[["hi, I'm vegan — no dairy please"], ["what should I order for dinner?"]],
        ),
        build_agent=lambda llm, tools: ProfileAgent(llm=llm, tools=tools, inject_regression=True),
        tools=menu_tools,
        script=[
            LLMResponse(text="Noted — no dairy."),
            LLMResponse(text="I recommend the margherita pizza."),
        ],
    ),
}

BUILTIN_SCENARIOS: dict[str, Scenario] = {name: spec.scenario for name, spec in EXAMPLES.items()}


class _ScriptedLLM:
    def __init__(self, responses: list[LLMResponse]):
        self._responses = list(responses)

    def create(self, model, system, messages, tools) -> LLMResponse:
        if not self._responses:
            raise RuntimeError(
                "scripted LLM exhausted: the agent made more calls than the scenario script provides"
            )
        return self._responses.pop(0)


def scripted_llm_for(scenario_name: str) -> LLMClient:
    return _ScriptedLLM(list(EXAMPLES[scenario_name].script))


_JUDGE_SCRIPT: dict[str, JudgeVerdict] = {
    "booking_happy": JudgeVerdict(scenario="booking_happy", verdicts=[
        DimensionVerdict(dimension="goal_completion", score=1.0, rationale="Booked the requested 3pm slot."),
        DimensionVerdict(dimension="relevance", score=1.0, rationale="Stayed on the booking task."),
        DimensionVerdict(dimension="tone", score=1.0, rationale="Friendly and clear."),
    ]),
    "support_happy": JudgeVerdict(scenario="support_happy", verdicts=[
        DimensionVerdict(dimension="goal_completion", score=1.0, rationale="Answered the shipping status."),
        DimensionVerdict(dimension="relevance", score=1.0, rationale="Addressed ORD-1234 directly."),
        DimensionVerdict(dimension="tone", score=1.0, rationale="Helpful and concise."),
    ]),
    "profile_happy": JudgeVerdict(scenario="profile_happy", verdicts=[
        DimensionVerdict(dimension="goal_completion", score=1.0, rationale="Recommended a compliant dish."),
        DimensionVerdict(dimension="relevance", score=1.0, rationale="Honored the dietary constraint."),
        DimensionVerdict(dimension="tone", score=1.0, rationale="Warm and clear."),
    ]),
}


class ScriptedJudge:
    """Deterministic judge for the offline suite — returns a canned verdict."""

    def __init__(self, verdict: JudgeVerdict):
        self._verdict = verdict

    def judge(self, conversation, dimensions) -> JudgeVerdict:
        return self._verdict


def scripted_judge_for(scenario_name: str) -> ScriptedJudge:
    return ScriptedJudge(_JUDGE_SCRIPT[scenario_name])


@dataclass(frozen=True)
class CandidateSpec:
    """A candidate agent B to replay against a fixture recorded from agent A."""

    build_agent: Callable[[LLMClient, ToolRecorder], object]
    tools: Callable[[], dict[str, Callable[..., dict]]]


CANDIDATES: dict[str, CandidateSpec] = {
    # Identical to the recorded agent — replays with zero divergence (back-compat control).
    "support_control": CandidateSpec(
        build_agent=lambda llm, tools: SupportAgent(llm=llm, tools=tools),
        tools=support_tools,
    ),
    # Reworded system prompt, same behavior — diverges under pinned, holds under live.
    "support_reworded": CandidateSpec(
        build_agent=lambda llm, tools: RewordedSupportAgent(llm=llm, tools=tools),
        tools=support_tools,
    ),
    # Genuinely broken: re-asks for an order id already given — fails its invariant offline.
    "support_regressed": CandidateSpec(
        build_agent=lambda llm, tools: SupportAgent(llm=llm, tools=tools, inject_regression=True),
        tools=support_tools,
    ),
}
