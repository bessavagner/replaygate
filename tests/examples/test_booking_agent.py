from replaygate.capture.llm import LLMResponse
from replaygate.capture.tools import ToolRecorder
from replaygate.examples.booking_agent import BookingAgent, booking_tools


class ScriptedLLM:
    """Returns queued responses in order, ignoring inputs."""
    def __init__(self, responses):
        self._responses = list(responses)

    def create(self, model, system, messages, tools):
        return self._responses.pop(0)


def _recorder():
    return ToolRecorder(booking_tools(), mode="record", recording=[])


def test_agent_books_only_after_confirm_signal():
    llm = ScriptedLLM([LLMResponse(text="OK, booking now.", tool_calls=[
        {"name": "book_appointment", "arguments": {"slot": "3pm"}}
    ])])
    agent = BookingAgent(llm=llm, tools=_recorder(), inject_regression=False)
    step = agent.respond(history=[{"role": "user", "content": "yes"}])
    assert any(tc.name == "book_appointment" for tc in step.tool_calls)


def test_regression_flag_books_without_confirm_signal():
    # LLM response carries NO tool_calls, but the buggy agent books anyway
    llm = ScriptedLLM([LLMResponse(text="Sure!", tool_calls=[])])
    agent = BookingAgent(llm=llm, tools=_recorder(), inject_regression=True)
    step = agent.respond(history=[{"role": "user", "content": "what slots are there?"}])
    assert any(tc.name == "book_appointment" for tc in step.tool_calls)
