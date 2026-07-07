from replaygate.judge.models import (
    DIMENSIONS,
    GOAL_COMPLETION,
    PASS_THRESHOLD,
    DimensionVerdict,
    JudgeVerdict,
)


def test_dimension_constants_are_present():
    assert GOAL_COMPLETION == "goal_completion"
    assert set(DIMENSIONS) == {"goal_completion", "relevance", "tone"}


def test_verdict_round_trips_through_pydantic():
    verdict = JudgeVerdict(
        scenario="booking_happy",
        verdicts=[
            DimensionVerdict(dimension="goal_completion", score=1.0, rationale="Booked 3pm."),
            DimensionVerdict(dimension="tone", score=0.4, rationale="Curt."),
        ],
    )
    reloaded = JudgeVerdict.model_validate_json(verdict.model_dump_json())
    assert reloaded == verdict


def test_failures_returns_only_sub_threshold_dimensions():
    verdict = JudgeVerdict(
        scenario="s",
        verdicts=[
            DimensionVerdict(dimension="goal_completion", score=0.9, rationale="ok"),
            DimensionVerdict(dimension="tone", score=0.3, rationale="bad"),
        ],
    )
    failed = verdict.failures(PASS_THRESHOLD)
    assert [v.dimension for v in failed] == ["tone"]
