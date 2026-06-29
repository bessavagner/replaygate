from __future__ import annotations

from datetime import datetime
from typing import Callable, Protocol

from replaygate.capture.adapters import ChannelAdapter, Scenario
from replaygate.capture.llm import LLMClient, RecordingLLMClient
from replaygate.capture.tools import ToolRecorder
from replaygate.examples.booking_agent import AgentStep
from replaygate.store.fixtures import Fixture, FixtureMeta
from replaygate.trace.models import (
    Conversation,
    Message,
    SessionMeta,
    Turn,
)


class Agent(Protocol):
    def respond(self, history: list[dict]) -> AgentStep: ...


def record_conversation(
    agent_factory: Callable[[RecordingLLMClient, ToolRecorder], Agent],
    inner_llm: LLMClient,
    scenario: Scenario,
    adapter: ChannelAdapter,
    *,
    tools: dict[str, Callable[..., dict]],
    agent_version: str,
    model: str,
    recorded_at: datetime,
) -> Fixture:
    llm_recording: list[dict] = []
    tool_recording: list[dict] = []
    rec_llm = RecordingLLMClient(inner_llm, mode="record", recording=llm_recording)
    rec_tools = ToolRecorder(tools, mode="record", recording=tool_recording)
    agent = agent_factory(rec_llm, rec_tools)

    history: list[dict] = []
    turns: list[Turn] = []
    for idx, user_msgs in enumerate(adapter.user_turns(scenario)):
        for m in user_msgs:
            history.append({"role": "user", "content": m.content})
        step = agent.respond(history)
        history.append({"role": "assistant", "content": step.assistant_text})
        assistant_msgs = [Message(role="assistant", content=step.assistant_text, ts=recorded_at)]
        turns.append(Turn(
            index=idx,
            user_messages=user_msgs,
            assistant_messages=assistant_msgs,
            tool_calls=step.tool_calls,
        ))

    conversation = Conversation(
        id=f"{scenario.name}-{recorded_at.isoformat()}",
        scenario=scenario.name,
        channel=adapter.channel,
        session_meta=SessionMeta(session_id=scenario.name, started_at=recorded_at),
        turns=turns,
        agent_version=agent_version,
        model=model,
    )
    return Fixture(
        conversation=conversation,
        llm_recording=llm_recording,
        tool_recording=tool_recording,
        spans=[],
        meta=FixtureMeta(scenario=scenario.name, agent_version=agent_version,
                         model=model, recorded_at=recorded_at),
    )
