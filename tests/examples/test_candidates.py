from replaygate.capture.llm import RecordingLLMClient
from replaygate.capture.tools import ToolRecorder
from replaygate.examples.scenarios import CANDIDATES
from replaygate.examples.support_agent import RewordedSupportAgent, SupportAgent


def test_registry_has_the_three_support_variants():
    assert set(CANDIDATES) >= {"support_control", "support_reworded", "support_regressed"}


def test_reworded_uses_a_different_system_prompt():
    assert RewordedSupportAgent.SYSTEM != SupportAgent.SYSTEM


def test_candidate_build_agent_constructs_something_respondable():
    cand = CANDIDATES["support_control"]
    agent = cand.build_agent(
        RecordingLLMClient(inner=None, mode="replay", recording=[]),
        ToolRecorder(cand.tools(), mode="replay", recording=[]),
    )
    assert hasattr(agent, "respond")
