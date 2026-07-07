"""Scenario→dimensions registry — exactly analogous to ``invariants._REGISTRY``.

Scenario-agnostic: the framework owns the mapping shape; concrete mappings are
registered by the examples (``replaygate.examples.judge_dimensions``).
"""

from __future__ import annotations

_REGISTRY: dict[str, list[str]] = {}


def register(scenario: str, dimensions: list[str]) -> None:
    """Register the judged dimensions for ``scenario`` (idempotent per dimension)."""
    bucket = _REGISTRY.setdefault(scenario, [])
    for dimension in dimensions:
        if dimension not in bucket:
            bucket.append(dimension)


def dimensions_for(scenario: str) -> list[str]:
    return list(_REGISTRY.get(scenario, []))
