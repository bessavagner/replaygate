"""Concrete scenario→dimensions mappings for the built-in example scenarios.

Importing this module registers each mapping in the framework registry
(``replaygate.judge.registry``), analogous to ``replaygate.examples.invariants``.
"""

from __future__ import annotations

from replaygate.judge.models import GOAL_COMPLETION, RELEVANCE, TONE
from replaygate.judge.registry import register

register("booking_happy", [GOAL_COMPLETION, RELEVANCE, TONE])
register("support_happy", [GOAL_COMPLETION, RELEVANCE, TONE])
register("profile_happy", [GOAL_COMPLETION, RELEVANCE, TONE])
