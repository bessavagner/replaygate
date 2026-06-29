from types import SimpleNamespace

import pytest

from replaygate.capture.providers import (
    AnthropicClient,
    GeminiClient,
    OllamaClient,
    OpenAICompatibleClient,
    make_client,
)

TOOLS = [{
    "name": "search_slots",
    "description": "List slots.",
    "input_schema": {"type": "object", "properties": {"date": {"type": "string"}}, "required": ["date"]},
}]


class FakeAnthropicMessages:
    def __init__(self, response):
        self._response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


class FakeAnthropicClient:
    def __init__(self, response):
        self.messages = FakeAnthropicMessages(response)


def test_anthropic_translates_request_and_parses_response():
    response = SimpleNamespace(
        id="msg_1",
        stop_reason="tool_use",
        model="claude-haiku-4-5",
        content=[
            SimpleNamespace(type="text", text="Booking 3pm."),
            SimpleNamespace(type="tool_use", name="book_appointment", input={"slot": "3pm"}),
        ],
    )
    fake = FakeAnthropicClient(response)
    agent_llm = AnthropicClient(client=fake, max_tokens=512)

    result = agent_llm.create("claude-haiku-4-5", "be helpful", [{"role": "user", "content": "hi"}], TOOLS)

    sent = fake.messages.calls[0]
    assert sent["model"] == "claude-haiku-4-5"
    assert sent["max_tokens"] == 512
    assert sent["system"] == "be helpful"
    assert sent["tools"][0]["input_schema"]["required"] == ["date"]  # native Anthropic shape
    assert result.text == "Booking 3pm."
    assert result.tool_calls == [{"name": "book_appointment", "arguments": {"slot": "3pm"}}]


def test_anthropic_model_override_wins_over_requested_model():
    response = SimpleNamespace(id="m", stop_reason="end_turn", model="x", content=[])
    fake = FakeAnthropicClient(response)
    AnthropicClient(client=fake, model="claude-opus-4-8").create("claude-haiku-4-5", "", [], [])
    assert fake.messages.calls[0]["model"] == "claude-opus-4-8"


class FakeChatCompletions:
    def __init__(self, response):
        self._response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


class FakeOpenAIClient:
    def __init__(self, response):
        self.chat = SimpleNamespace(completions=FakeChatCompletions(response))


def _openai_response(content, tool_calls=()):
    message = SimpleNamespace(content=content, tool_calls=list(tool_calls))
    choice = SimpleNamespace(message=message, finish_reason="stop")
    return SimpleNamespace(id="cmpl_1", model="gpt-x", choices=[choice])


def test_openai_prepends_system_and_translates_tools():
    fake = FakeOpenAIClient(_openai_response("hello"))
    OpenAICompatibleClient(client=fake).create("gpt-x", "be terse", [{"role": "user", "content": "hi"}], TOOLS)

    sent = fake.chat.completions.calls[0]
    assert sent["messages"][0] == {"role": "system", "content": "be terse"}
    assert sent["messages"][1] == {"role": "user", "content": "hi"}
    assert sent["tools"][0]["type"] == "function"
    assert sent["tools"][0]["function"]["name"] == "search_slots"


def test_openai_parses_tool_calls_with_json_arguments():
    tc = SimpleNamespace(function=SimpleNamespace(name="book_appointment", arguments='{"slot": "3pm"}'))
    fake = FakeOpenAIClient(_openai_response(None, tool_calls=[tc]))
    result = OpenAICompatibleClient(client=fake).create("gpt-x", "", [{"role": "user", "content": "hi"}], [])

    assert result.text == ""
    assert result.tool_calls == [{"name": "book_appointment", "arguments": {"slot": "3pm"}}]


def test_openai_tolerates_unparseable_tool_arguments():
    tc = SimpleNamespace(function=SimpleNamespace(name="x", arguments="not json"))
    fake = FakeOpenAIClient(_openai_response("", tool_calls=[tc]))
    result = OpenAICompatibleClient(client=fake).create("gpt-x", "", [], [])
    assert result.tool_calls == [{"name": "x", "arguments": {}}]


def test_ollama_uses_local_base_url_and_dummy_key(monkeypatch):
    captured = {}

    class FakeOpenAISDK:
        def __init__(self, api_key=None, base_url=None):
            captured["api_key"] = api_key
            captured["base_url"] = base_url
            self.chat = SimpleNamespace(completions=FakeChatCompletions(_openai_response("hi")))

    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    monkeypatch.setattr("openai.OpenAI", FakeOpenAISDK)
    OllamaClient(model="llama3").create("llama3", "", [], [])
    assert captured["base_url"] == "http://localhost:11434/v1"
    assert captured["api_key"] == "ollama"


def test_gemini_uses_google_openai_endpoint_and_key(monkeypatch):
    captured = {}

    class FakeOpenAISDK:
        def __init__(self, api_key=None, base_url=None):
            captured["api_key"] = api_key
            captured["base_url"] = base_url
            self.chat = SimpleNamespace(completions=FakeChatCompletions(_openai_response("hi")))

    monkeypatch.setenv("GOOGLE_API_KEY", "g-key")
    monkeypatch.setattr("openai.OpenAI", FakeOpenAISDK)
    GeminiClient(model="gemini-2.5-flash").create("gemini-2.5-flash", "", [], [])
    assert captured["base_url"] == "https://generativelanguage.googleapis.com/v1beta/openai/"
    assert captured["api_key"] == "g-key"


def test_make_client_dispatch_and_unknown_provider():
    response = SimpleNamespace(id="m", stop_reason="end_turn", model="x", content=[])
    assert isinstance(make_client("anthropic", client=FakeAnthropicClient(response)), AnthropicClient)
    with pytest.raises(ValueError, match="unknown provider"):
        make_client("cohere")
