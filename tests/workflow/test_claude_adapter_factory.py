"""Phase 3 test: the Anthropic Claude client factory wires the SDK adapter.

build_anthropic_claude_client constructs the Anthropic SDK client (no network at
construction) and wraps it in the AnthropicClaudeClient adapter behind the
ClaudeClient seam.
"""

from __future__ import annotations

from living_adr.workflow.drafting.claude_adapter import (
    AnthropicClaudeClient,
    ClaudeAdapterConfig,
    build_anthropic_claude_client,
)


def test_build_returns_anthropic_claude_client() -> None:
    client = build_anthropic_claude_client(api_key="sk-ant-test")

    assert isinstance(client, AnthropicClaudeClient)
    assert callable(client.complete)


def test_build_accepts_adapter_config() -> None:
    config = ClaudeAdapterConfig(model_id="claude-test", max_tokens=16)

    client = build_anthropic_claude_client(api_key="sk-ant-test", config=config)

    assert isinstance(client, AnthropicClaudeClient)
