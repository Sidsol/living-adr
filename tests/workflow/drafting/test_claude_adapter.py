"""S-005 RED tests: Anthropic-backed Claude adapter (feature 008, US-5/NFR-5).

The adapter satisfies the ``ClaudeClient`` seam using an **injected** SDK-like
client (duck-typed ``messages.create``) so tests never touch the network. It maps
config onto the SDK call, extracts token metadata, and maps SDK timeout/errors
onto the domain ``ClaudeTimeoutError`` / ``ClaudeProviderError``.
"""

from __future__ import annotations

import pytest

from living_adr.core.llm import (
    ClaudeClient,
    ClaudeProviderError,
    ClaudeRequest,
    ClaudeTimeoutError,
)
from living_adr.workflow.drafting.claude_adapter import (
    AnthropicClaudeClient,
    ClaudeAdapterConfig,
)


class _Block:
    def __init__(self, text: str) -> None:
        self.text = text


class _Usage:
    def __init__(self, input_tokens: int, output_tokens: int) -> None:
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens


class _Response:
    def __init__(self, text: str, *, in_tok: int, out_tok: int) -> None:
        self.content = [_Block(text)]
        self.usage = _Usage(in_tok, out_tok)
        self.stop_reason = "end_turn"


class _FakeMessages:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self._response = response
        self._error = error
        self.calls: list[dict[str, object]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self._error is not None:
            raise self._error
        return self._response


class _FakeSDK:
    def __init__(self, response=None, error: Exception | None = None) -> None:
        self.messages = _FakeMessages(response, error)


class _FakeTimeoutError(Exception):
    """Stand-in whose class name triggers timeout classification."""


def _request() -> ClaudeRequest:
    return ClaudeRequest(
        model_id="claude-sonnet-4-6",
        system="sys",
        prompt="draft it",
        max_tokens=777,
        temperature=0.0,
    )


def test_adapter_satisfies_protocol() -> None:
    sdk = _FakeSDK(response=_Response("ok", in_tok=1, out_tok=1))
    adapter = AnthropicClaudeClient(client=sdk)
    assert isinstance(adapter, ClaudeClient)


def test_adapter_passes_config_to_sdk() -> None:
    sdk = _FakeSDK(response=_Response("ok", in_tok=10, out_tok=5))
    config = ClaudeAdapterConfig(model_id="claude-sonnet-4-6", timeout_s=42.0)
    adapter = AnthropicClaudeClient(client=sdk, config=config)
    adapter.complete(_request())

    call = sdk.messages.calls[0]
    assert call["model"] == "claude-sonnet-4-6"
    assert call["max_tokens"] == 777
    assert call["temperature"] == 0.0
    assert call["system"] == "sys"
    assert call["messages"] == [{"role": "user", "content": "draft it"}]
    assert call["timeout"] == 42.0


def test_adapter_extracts_text_and_token_metadata() -> None:
    sdk = _FakeSDK(response=_Response("## Decision\nuse it", in_tok=123, out_tok=45))
    adapter = AnthropicClaudeClient(client=sdk)
    response = adapter.complete(_request())
    assert response.text == "## Decision\nuse it"
    assert response.input_tokens == 123
    assert response.output_tokens == 45
    assert response.model_id == "claude-sonnet-4-6"
    assert response.stop_reason == "end_turn"


def test_adapter_maps_timeout_error() -> None:
    sdk = _FakeSDK(error=_FakeTimeoutError("slow"))
    adapter = AnthropicClaudeClient(client=sdk)
    with pytest.raises(ClaudeTimeoutError):
        adapter.complete(_request())


def test_adapter_maps_generic_error() -> None:
    sdk = _FakeSDK(error=ValueError("boom"))
    adapter = AnthropicClaudeClient(client=sdk)
    with pytest.raises(ClaudeProviderError):
        adapter.complete(_request())


def test_adapter_maps_empty_content_to_provider_error() -> None:
    class _Empty:
        content: list[object] = []
        usage = _Usage(1, 0)
        stop_reason = "end_turn"

    sdk = _FakeSDK(response=_Empty())
    adapter = AnthropicClaudeClient(client=sdk)
    with pytest.raises(ClaudeProviderError):
        adapter.complete(_request())
