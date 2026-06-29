from replaygate.capture.llm import LLMResponse
from replaygate.capture.tools import ToolRecorder
from replaygate.examples.profile_agent import ProfileAgent, menu_tools


class ScriptedLLM:
    """Returns queued responses in order, ignoring inputs."""
    def __init__(self, responses):
        self._responses = list(responses)

    def create(self, model, system, messages, tools):
        return self._responses.pop(0)


def _recorder():
    return ToolRecorder(menu_tools(), mode="record", recording=[])


def _run_two_turns(agent):
    history = [{"role": "user", "content": "hi, I'm vegan — no dairy please"}]
    step0 = agent.respond(history)
    history.append({"role": "assistant", "content": step0.assistant_text})
    history.append({"role": "user", "content": "what should I order for dinner?"})
    step1 = agent.respond(history)
    return step0, step1


def test_constraint_set_earlier_is_honored_on_recommendation():
    llm = ScriptedLLM([LLMResponse(text="Noted."), LLMResponse(text="Try the stir-fry.")])
    agent = ProfileAgent(llm=llm, tools=_recorder(), inject_regression=False)
    step0, step1 = _run_two_turns(agent)
    # First turn only acknowledges; no recommendation requested yet.
    assert step0.tool_calls == []
    rec = step1.tool_calls[0]
    assert rec.name == "recommend_dish"
    assert rec.arguments == {"avoid_dairy": True}
    assert rec.result["contains_dairy"] is False


def test_regression_forgets_constraint_and_recommends_dairy():
    llm = ScriptedLLM([LLMResponse(text="Noted."), LLMResponse(text="Try the pizza.")])
    agent = ProfileAgent(llm=llm, tools=_recorder(), inject_regression=True)
    _, step1 = _run_two_turns(agent)
    rec = step1.tool_calls[0]
    assert rec.arguments == {"avoid_dairy": False}
    assert rec.result["contains_dairy"] is True
