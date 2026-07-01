from __future__ import annotations

from typing import Literal


class DivergenceError(KeyError):
    """Raised in replay mode when a candidate agent makes a call absent from the
    recording — it left the recorded trajectory.

    Subclasses ``KeyError`` so existing replay-miss handling keeps working, while
    carrying structured fields the regress gate turns into a ``Divergence`` outcome.
    """

    def __init__(self, kind: Literal["llm", "tool"], summary: str, key: str | None = None):
        self.kind = kind
        self.summary = summary
        self.key = key
        self.turn_index: int | None = None
        super().__init__(summary)
