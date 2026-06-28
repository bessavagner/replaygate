from __future__ import annotations

import json
from typing import Callable, Literal


class ToolRecorder:
    def __init__(
        self,
        registry: dict[str, Callable[..., dict]],
        mode: Literal["record", "replay"],
        recording: list[dict],
    ):
        self._registry = registry
        self._mode = mode
        self._recording = recording

    def call(self, name: str, args: dict) -> dict:
        if self._mode == "replay":
            for entry in self._recording:
                if entry["tool"] == name and entry["args"] == args:
                    return entry["result"]
            raise KeyError(f"no recorded result for tool {name} args {json.dumps(args, sort_keys=True)}")
        result = self._registry[name](**args)
        self._recording.append({"tool": name, "args": args, "result": result})
        return result
