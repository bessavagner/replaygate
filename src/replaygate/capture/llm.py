from __future__ import annotations

import hashlib
import json
from typing import Literal, Protocol

from pydantic import BaseModel, Field

from replaygate.capture.errors import DivergenceError
from replaygate.capture.spans import SpanCollector


class LLMResponse(BaseModel):
    text: str
    tool_calls: list[dict] = Field(default_factory=list)
    raw: dict = Field(default_factory=dict)


class LLMClient(Protocol):
    def create(self, model: str, system: str, messages: list[dict], tools: list[dict]) -> LLMResponse: ...


def request_key(model: str, system: str, messages: list[dict], tools: list[dict]) -> str:
    payload = json.dumps(
        {"model": model, "system": system, "messages": messages, "tools": tools},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


class RecordingLLMClient:
    def __init__(
        self,
        inner: LLMClient | None,
        mode: Literal["record", "replay"],
        recording: list[dict],
        on_miss: Literal["raise", "live"] = "raise",
        spans: SpanCollector | None = None,
    ):
        self._inner = inner
        self._mode = mode
        self._recording = recording
        self._on_miss = on_miss
        self._spans = spans

    def _create(self, model: str, system: str, messages: list[dict], tools: list[dict]) -> LLMResponse:
        if self._spans is None:
            return self._inner.create(model, system, messages, tools)
        attrs = {"gen_ai.operation.name": "chat", "gen_ai.request.model": model}
        with self._spans.span("llm.create", attrs):
            return self._inner.create(model, system, messages, tools)

    def create(self, model: str, system: str, messages: list[dict], tools: list[dict]) -> LLMResponse:
        key = request_key(model, system, messages, tools)
        if self._mode == "replay":
            for entry in self._recording:
                if entry["request_key"] == key:
                    return LLMResponse.model_validate(entry["response"])
            if self._on_miss == "live":
                if self._inner is None:
                    raise RuntimeError("live replay needs an inner LLMClient")
                response = self._create(model, system, messages, tools)
                self._recording.append({
                    "request_key": key,
                    "request": {"model": model, "system": system, "messages": messages, "tools": tools},
                    "response": response.model_dump(),
                })
                return response
            raise DivergenceError(
                "llm", f"no recorded LLM response for request_key {key[:12]}…", key=key
            )
        if self._inner is None:
            raise RuntimeError("cannot record without an inner LLMClient")
        response = self._create(model, system, messages, tools)
        self._recording.append({
            "request_key": key,
            "request": {"model": model, "system": system, "messages": messages, "tools": tools},
            "response": response.model_dump(),
        })
        return response
