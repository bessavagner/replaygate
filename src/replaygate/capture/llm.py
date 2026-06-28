from __future__ import annotations

import hashlib
import json
from typing import Literal, Protocol

from pydantic import BaseModel, Field


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
    def __init__(self, inner: LLMClient, mode: Literal["record", "replay"], recording: list[dict]):
        self._inner = inner
        self._mode = mode
        self._recording = recording

    def create(self, model: str, system: str, messages: list[dict], tools: list[dict]) -> LLMResponse:
        key = request_key(model, system, messages, tools)
        if self._mode == "replay":
            for entry in self._recording:
                if entry["request_key"] == key:
                    return LLMResponse.model_validate(entry["response"])
            raise KeyError(f"no recorded LLM response for request_key {key[:12]}…")
        response = self._inner.create(model, system, messages, tools)
        self._recording.append({
            "request_key": key,
            "request": {"model": model, "system": system, "messages": messages, "tools": tools},
            "response": response.model_dump(),
        })
        return response
