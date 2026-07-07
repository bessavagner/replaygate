from __future__ import annotations

from pydantic import BaseModel, Field

GOAL_COMPLETION = "goal_completion"
RELEVANCE = "relevance"
TONE = "tone"
DIMENSIONS: tuple[str, ...] = (GOAL_COMPLETION, RELEVANCE, TONE)

# A dimension scoring below this score is treated as a judge-gate failure.
PASS_THRESHOLD: float = 0.5


class DimensionVerdict(BaseModel):
    dimension: str
    score: float
    rationale: str


class JudgeVerdict(BaseModel):
    scenario: str
    verdicts: list[DimensionVerdict] = Field(default_factory=list)

    def failures(self, threshold: float = PASS_THRESHOLD) -> list[DimensionVerdict]:
        """Dimensions scoring below ``threshold`` — the judge-gate failure set."""
        return [v for v in self.verdicts if v.score < threshold]
