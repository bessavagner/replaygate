"""Record & replay judge calls — mirrors ``RecordingLLMClient`` in ``capture/llm.py``.

Each call is keyed by a stable sha256 over the conversation and the requested
dimensions. Offline replay matches on key with ``on_miss="raise"`` so a miss is a
loud ``DivergenceError``, never a silent live call.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from replaygate.capture.errors import DivergenceError
from replaygate.judge import Judge
from replaygate.judge.models import JudgeVerdict
from replaygate.trace.models import Conversation


def judge_key(conversation: Conversation, dimensions: list[str]) -> str:
    payload = json.dumps(
        {"conversation": conversation.model_dump(mode="json"), "dimensions": sorted(dimensions)},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


class RecordingJudge:
    def __init__(
        self,
        inner: Judge | None,
        mode: Literal["record", "replay"],
        recording: list[dict],
        on_miss: Literal["raise", "live"] = "raise",
    ):
        self._inner = inner
        self._mode = mode
        self._recording = recording
        self._on_miss = on_miss

    def judge(self, conversation: Conversation, dimensions: list[str]) -> JudgeVerdict:
        key = judge_key(conversation, dimensions)
        if self._mode == "replay":
            for entry in self._recording:
                if entry["judge_key"] == key:
                    return JudgeVerdict.model_validate(entry["verdict"])
            if self._on_miss == "live":
                if self._inner is None:
                    raise RuntimeError("live judge replay needs an inner Judge")
                verdict = self._inner.judge(conversation, dimensions)
                self._recording.append({"judge_key": key, "verdict": verdict.model_dump(mode="json")})
                return verdict
            raise DivergenceError(
                "judge", f"no recorded judge verdict for key {key[:12]}…", key=key
            )
        if self._inner is None:
            raise RuntimeError("cannot record without an inner Judge")
        verdict = self._inner.judge(conversation, dimensions)
        self._recording.append({"judge_key": key, "verdict": verdict.model_dump(mode="json")})
        return verdict
