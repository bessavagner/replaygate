from types import SimpleNamespace

from replaygate.judge.claude import ClaudeJudge, _VERDICT_TOOL_NAME, _verdict_tool
from replaygate.trace.models import Conversation, Message, SessionMeta, Turn
from datetime import datetime, timezone

TS = datetime(2026, 7, 7, tzinfo=timezone.utc)


class FakeMessages:
    def __init__(self, response):
        self._response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


class FakeAnthropic:
    def __init__(self, response):
        self.messages = FakeMessages(response)


def _conversation():
    return Conversation(
        id="c1", scenario="booking_happy", channel="direct",
        session_meta=SessionMeta(session_id="s1", started_at=TS),
        turns=[Turn(
            index=0,
            user_messages=[Message(role="user", content="book 3pm please", ts=TS)],
            assistant_messages=[Message(role="assistant", content="Booked 3pm.", ts=TS)],
        )],
    )


def test_verdict_tool_pins_dimensions_as_enum():
    tool = _verdict_tool(["goal_completion", "tone"])
    item = tool["input_schema"]["properties"]["verdicts"]["items"]
    assert item["properties"]["dimension"]["enum"] == ["goal_completion", "tone"]


def test_judge_forces_the_verdict_tool_and_parses_the_result():
    response = SimpleNamespace(
        id="msg_1", stop_reason="tool_use", model="claude-opus-4-8",
        content=[
            SimpleNamespace(
                type="tool_use", name="record_verdict",
                input={"verdicts": [
                    {"dimension": "goal_completion", "score": 1.0, "rationale": "Booked 3pm."},
                    {"dimension": "tone", "score": 0.8, "rationale": "Friendly."},
                ]},
            ),
        ],
    )
    fake = FakeAnthropic(response)
    judge = ClaudeJudge(client=fake, max_tokens=256)

    verdict = judge.judge(_conversation(), ["goal_completion", "tone"])

    sent = fake.messages.calls[0]
    assert sent["model"] == "claude-opus-4-8"
    assert sent["max_tokens"] == 256
    assert sent["tool_choice"] == {"type": "tool", "name": _VERDICT_TOOL_NAME}
    assert len(sent["tools"]) == 1 and sent["tools"][0]["name"] == _VERDICT_TOOL_NAME
    assert verdict.scenario == "booking_happy"
    assert verdict.verdicts[0].dimension == "goal_completion"
    assert verdict.verdicts[0].score == 1.0
    assert verdict.verdicts[1].rationale == "Friendly."
