from __future__ import annotations

import json
from typing import Callable, Literal

from replaygate.capture.errors import DivergenceError
from replaygate.capture.spans import SpanCollector


class ToolRecorder:
    def __init__(
        self,
        registry: dict[str, Callable[..., dict]],
        mode: Literal["record", "replay"],
        recording: list[dict],
        on_miss: Literal["raise", "live"] = "raise",
        spans: SpanCollector | None = None,
    ):
        self._registry = registry
        self._mode = mode
        self._recording = recording
        self._on_miss = on_miss
        self._spans = spans

    def _invoke(self, name: str, args: dict) -> dict:
        fn = self._registry[name]
        if self._spans is None:
            return fn(**args)
        with self._spans.span("tool.call", {"tool.name": name}):
            return fn(**args)

    def call(self, name: str, args: dict) -> dict:
        if self._mode == "replay":
            for entry in self._recording:
                if entry["tool"] == name and entry["args"] == args:
                    return entry["result"]
            if self._on_miss == "live":
                if name not in self._registry:
                    raise KeyError(f"unknown tool {name!r}; available: {', '.join(self._registry)}")
                result = self._invoke(name, args)
                self._recording.append({"tool": name, "args": args, "result": result})
                return result
            raise DivergenceError(
                "tool",
                f"no recorded result for tool {name} args {json.dumps(args, sort_keys=True)}",
                key=f"{name}:{json.dumps(args, sort_keys=True)}",
            )
        if name not in self._registry:
            raise KeyError(f"unknown tool {name!r}; available: {', '.join(self._registry)}")
        result = self._invoke(name, args)
        self._recording.append({"tool": name, "args": args, "result": result})
        return result
