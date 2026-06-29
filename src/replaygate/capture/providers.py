"""Real LLMClient implementations for recording live agent conversations.

Each class satisfies the ``LLMClient`` protocol (``create(model, system, messages,
tools) -> LLMResponse``) so a recorder can sit in front of it unchanged. Anthropic
goes through the official ``anthropic`` SDK; OpenAI, OpenRouter, and Ollama share
the OpenAI-compatible ``openai`` SDK. SDK imports are lazy so the core package
stays dependency-free and offline — install extras with ``pip install -e .[providers]``.

Keys come from the environment (``ANTHROPIC_API_KEY``, ``OPENAI_API_KEY``,
``OPENROUTER_API_KEY``, ``GOOGLE_API_KEY``); Ollama needs none. Pass ``model=`` to override the model
the agent requests — needed to run a Claude-targeted agent against OpenAI/Ollama.
"""

from __future__ import annotations

import json
import os
from typing import Any

from replaygate.capture.llm import LLMResponse

# Neutral tool-schema shape: {"name", "description", "input_schema"}.


def _tool_schema(tool: dict) -> dict:
    return tool.get("input_schema") or tool.get("parameters") or {"type": "object", "properties": {}}


def _to_anthropic_tool(tool: dict) -> dict:
    return {
        "name": tool["name"],
        "description": tool.get("description", ""),
        "input_schema": _tool_schema(tool),
    }


def _to_openai_tool(tool: dict) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": _tool_schema(tool),
        },
    }


class AnthropicClient:
    """Calls Claude through the official ``anthropic`` SDK."""

    def __init__(self, *, model: str | None = None, api_key: str | None = None,
                 max_tokens: int = 4096, client: Any = None):
        if client is None:
            from anthropic import Anthropic  # lazy: keeps core offline

            client = Anthropic(api_key=api_key)  # api_key=None → ANTHROPIC_API_KEY
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    def create(self, model: str, system: str, messages: list[dict], tools: list[dict]) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self._model or model,
            "max_tokens": self._max_tokens,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system
        if tools:
            kwargs["tools"] = [_to_anthropic_tool(t) for t in tools]
        resp = self._client.messages.create(**kwargs)
        text = "".join(getattr(b, "text", "") for b in resp.content if b.type == "text")
        tool_calls = [
            {"name": b.name, "arguments": dict(b.input)}
            for b in resp.content if b.type == "tool_use"
        ]
        return LLMResponse(text=text, tool_calls=tool_calls,
                           raw={"id": resp.id, "stop_reason": resp.stop_reason, "model": resp.model})


class OpenAICompatibleClient:
    """Calls any OpenAI-compatible chat-completions endpoint via the ``openai`` SDK."""

    def __init__(self, *, model: str | None = None, api_key: str | None = None,
                 base_url: str | None = None, max_tokens: int = 4096, client: Any = None):
        if client is None:
            from openai import OpenAI  # lazy: keeps core offline

            client = OpenAI(api_key=api_key, base_url=base_url)
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    def create(self, model: str, system: str, messages: list[dict], tools: list[dict]) -> LLMResponse:
        oai_messages = ([{"role": "system", "content": system}] if system else []) + messages
        kwargs: dict[str, Any] = {
            "model": self._model or model,
            "max_tokens": self._max_tokens,
            "messages": oai_messages,
        }
        if tools:
            kwargs["tools"] = [_to_openai_tool(t) for t in tools]
        resp = self._client.chat.completions.create(**kwargs)
        if not resp.choices:
            raise ValueError("provider returned no choices")
        choice = resp.choices[0]
        text = choice.message.content or ""
        tool_calls = []
        for tc in (choice.message.tool_calls or []):
            try:
                arguments = json.loads(tc.function.arguments)
            except (TypeError, json.JSONDecodeError):
                arguments = {}
            tool_calls.append({"name": tc.function.name, "arguments": arguments})
        return LLMResponse(text=text, tool_calls=tool_calls,
                           raw={"id": resp.id, "finish_reason": choice.finish_reason, "model": resp.model})


class OpenAIClient(OpenAICompatibleClient):
    """OpenAI proper (api.openai.com); reads ``OPENAI_API_KEY``."""


class OpenRouterClient(OpenAICompatibleClient):
    """OpenRouter; reads ``OPENROUTER_API_KEY``."""

    def __init__(self, *, model: str | None = None, api_key: str | None = None,
                 max_tokens: int = 4096, client: Any = None):
        super().__init__(
            model=model,
            api_key=api_key or os.environ.get("OPENROUTER_API_KEY"),
            base_url="https://openrouter.ai/api/v1",
            max_tokens=max_tokens,
            client=client,
        )


class OllamaClient(OpenAICompatibleClient):
    """Local Ollama via its OpenAI-compatible endpoint; no API key required."""

    def __init__(self, *, model: str | None = None, base_url: str | None = None,
                 max_tokens: int = 4096, client: Any = None):
        super().__init__(
            model=model,
            api_key="ollama",  # Ollama ignores the key but the SDK requires a non-empty value
            base_url=base_url or os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
            max_tokens=max_tokens,
            client=client,
        )


class GeminiClient(OpenAICompatibleClient):
    """Google Gemini via its OpenAI-compatible endpoint; reads ``GOOGLE_API_KEY``."""

    def __init__(self, *, model: str | None = None, api_key: str | None = None,
                 max_tokens: int = 4096, client: Any = None):
        super().__init__(
            model=model,
            api_key=api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"),
            base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
            max_tokens=max_tokens,
            client=client,
        )


_PROVIDERS = {
    "anthropic": AnthropicClient,
    "openai": OpenAIClient,
    "openrouter": OpenRouterClient,
    "ollama": OllamaClient,
    "gemini": GeminiClient,
}


def make_client(provider: str, **kwargs: Any) -> Any:
    """Build a provider client by name: anthropic | openai | openrouter | ollama."""
    try:
        cls = _PROVIDERS[provider.lower()]
    except KeyError:
        raise ValueError(
            f"unknown provider {provider!r}; choose from {', '.join(sorted(_PROVIDERS))}"
        ) from None
    return cls(**kwargs)
