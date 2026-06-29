from replaygate.capture.llm import LLMResponse
from replaygate.capture.tools import ToolRecorder
from replaygate.examples.support_agent import SupportAgent, support_tools


class ScriptedLLM:
    """Returns queued responses in order, ignoring inputs."""
    def __init__(self, responses):
        self._responses = list(responses)

    def create(self, model, system, messages, tools):
        return self._responses.pop(0)


def _recorder():
    return ToolRecorder(support_tools(), mode="record", recording=[])


def _run_two_turns(agent):
    history = [{"role": "user", "content": "my order ORD-1234 — has it shipped?"}]
    step0 = agent.respond(history)
    history.append({"role": "assistant", "content": step0.assistant_text})
    history.append({"role": "user", "content": "any update on the delivery?"})
    step1 = agent.respond(history)
    return step0, step1


def test_agent_remembers_order_id_across_turns():
    llm = ScriptedLLM([LLMResponse(text="Checking ORD-1234."), LLMResponse(text="Shipped.")])
    agent = SupportAgent(llm=llm, tools=_recorder(), inject_regression=False)
    _, step1 = _run_two_turns(agent)
    # The later turn looks the order up again without re-asking the customer.
    assert [tc.name for tc in step1.tool_calls] == ["lookup_order"]
    assert step1.tool_calls[0].arguments == {"order_id": "ORD-1234"}


def test_regression_reasks_for_order_id_on_later_turn():
    llm = ScriptedLLM([LLMResponse(text="Checking ORD-1234."), LLMResponse(text="Shipped.")])
    agent = SupportAgent(llm=llm, tools=_recorder(), inject_regression=True)
    _, step1 = _run_two_turns(agent)
    # The buggy agent forgot the order id and re-asks instead of looking it up.
    assert step1.tool_calls == []
    assert "order number" in step1.assistant_text.lower()
