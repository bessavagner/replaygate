"""The semantic judge: scores conversation dimensions deterministic predicates can't.

Scenario-agnostic, like ``replaygate.invariants``. The ``Judge`` protocol isolates
the (network-bound) LLM call so the offline suite never touches the ``anthropic`` SDK.
"""

from __future__ import annotations

from typing import Protocol

from replaygate.judge.models import JudgeVerdict
from replaygate.trace.models import Conversation


class Judge(Protocol):
    def judge(self, conversation: Conversation, dimensions: list[str]) -> JudgeVerdict: ...
