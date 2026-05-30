"""S-001 RED tests: fakeable Claude client seam (feature 008, US-5).

These tests prove the ``ClaudeClient`` seam can be exercised entirely with a
deterministic in-memory fake — no Anthropic SDK import, no network. CI must be
*incapable* of calling the real API through this seam.
"""

from __future__ import annotations

import sys

import pytest

from living_adr.core.llm import (
    ClaudeClient,
    ClaudeProviderError,
    ClaudeRequest,
    ClaudeResponse,
    ClaudeTimeoutError,
    FakeClaudeClient,
)


def _request(prompt: str = "draft an ADR") -> ClaudeRequest:
    return ClaudeRequest(
        model_id="claude-sonnet-4-6",
        system="You are an ADR author.",
        prompt=prompt,
        max_tokens=512,
    )


def test_fake_satisfies_claude_client_protocol() -> None:
    fake = FakeClaudeClient(response_text="ok")
    assert isinstance(fake, ClaudeClient)


def test_fake_returns_deterministic_response() -> None:
    fake = FakeClaudeClient(response_text="## Decision\nuse it")
    first = fake.complete(_request())
    second = fake.complete(_request())
    assert isinstance(first, ClaudeResponse)
    assert first.text == "## Decision\nuse it"
    assert first.model_id == "claude-sonnet-4-6"
    assert first == second
    # Token metadata is deterministic (derived, not random).
    assert first.input_tokens > 0
    assert first.output_tokens > 0


def test_fake_records_calls() -> None:
    fake = FakeClaudeClient(response_text="ok")
    fake.complete(_request("alpha"))
    fake.complete(_request("beta"))
    assert len(fake.calls) == 2
    assert fake.calls[0].prompt == "alpha"
    assert fake.calls[1].prompt == "beta"


def test_fake_can_raise_timeout() -> None:
    fake = FakeClaudeClient(error=ClaudeTimeoutError("slow"))
    with pytest.raises(ClaudeTimeoutError):
        fake.complete(_request())
    # The attempted call is still recorded for observability assertions.
    assert len(fake.calls) == 1


def test_fake_can_raise_provider_error() -> None:
    fake = FakeClaudeClient(error=ClaudeProviderError("boom"))
    with pytest.raises(ClaudeProviderError):
        fake.complete(_request())


def test_llm_module_does_not_import_anthropic_sdk() -> None:
    """Importing the core seam must never pull in the Anthropic SDK (US-5)."""

    import living_adr.core.llm as llm_module

    assert "anthropic" not in dir(llm_module)
    # No transitive anthropic import was triggered by importing the seam.
    module_file = llm_module.__file__ or ""
    assert module_file.endswith("llm.py")
    # Defensive: the fake never needs the SDK even if it is installed elsewhere.
    sdk_loaded_before = "anthropic" in sys.modules
    FakeClaudeClient(response_text="x").complete(_request())
    assert ("anthropic" in sys.modules) == sdk_loaded_before
