from replaygate.judge.registry import _REGISTRY, dimensions_for, register


def test_register_then_dimensions_for(monkeypatch):
    monkeypatch.setitem(_REGISTRY, "some_scenario", [])
    register("some_scenario", ["goal_completion", "tone"])
    assert dimensions_for("some_scenario") == ["goal_completion", "tone"]


def test_dimensions_for_unknown_scenario_is_empty():
    assert dimensions_for("does_not_exist") == []


def test_register_dedupes():
    _REGISTRY.pop("dedupe_scenario", None)
    register("dedupe_scenario", ["tone"])
    register("dedupe_scenario", ["tone", "relevance"])
    assert dimensions_for("dedupe_scenario") == ["tone", "relevance"]


def test_builtin_booking_happy_has_dimensions():
    # Importing the examples registers the concrete mappings (Step 8/9).
    import replaygate.examples.scenarios  # noqa: F401

    assert set(dimensions_for("booking_happy")) == {"goal_completion", "relevance", "tone"}
