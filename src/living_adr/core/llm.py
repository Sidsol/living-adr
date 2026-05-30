"""Fakeable Claude client seam (feature 008, slice S-001).

This module is the **swappable, SDK-free** boundary the drafting workflow depends
on (architecture #tech-stack, NFR-5, US-5):

* :class:`ClaudeRequest` / :class:`ClaudeResponse` are LivingADR domain DTOs — no
  Anthropic SDK types appear here.
* :class:`ClaudeClient` is the ``Protocol`` the workflow targets; the real
  Anthropic adapter (slice S-005) and :class:`FakeClaudeClient` both satisfy it.
* :class:`FakeClaudeClient` is deterministic and records every request, so tests
  never call the real API and CI cannot reach the network through this seam.

The Anthropic SDK is intentionally **not** imported in this module — only the
concrete adapter in :mod:`living_adr.workflow.drafting.claude_adapter` imports it.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, field_validator


class ClaudeError(Exception):
    """Base class for provider-seam errors mapped out of the adapter.

    ``error_class`` is a stable, metadata-safe label suitable for observability
    (never a raw provider payload or message body).
    """

    error_class: str = "claude_error"


class ClaudeTimeoutError(ClaudeError):
    """The provider call exceeded its configured timeout."""

    error_class = "timeout"


class ClaudeProviderError(ClaudeError):
    """The provider returned an error or an otherwise unusable response."""

    error_class = "provider_error"


class ClaudeRequest(BaseModel):
    """A provider-neutral completion request (no SDK types)."""

    model_config = ConfigDict(frozen=True)

    model_id: str
    system: str
    prompt: str
    max_tokens: int = 1024
    temperature: float = 0.0
    stop_sequences: tuple[str, ...] = ()

    @field_validator("model_id", "prompt")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty or whitespace")
        return value


class ClaudeResponse(BaseModel):
    """A provider-neutral completion response (no SDK types)."""

    model_config = ConfigDict(frozen=True)

    text: str
    model_id: str
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str | None = None


@runtime_checkable
class ClaudeClient(Protocol):
    """The swappable completion seam the drafting workflow depends on."""

    def complete(self, request: ClaudeRequest) -> ClaudeResponse: ...


def _estimate_tokens(text: str) -> int:
    """Deterministic, dependency-free token estimate (~4 chars/token)."""

    return max(1, (len(text) + 3) // 4)


class FakeClaudeClient:
    """Deterministic, network-free :class:`ClaudeClient` for tests (US-5).

    Returns a fixed ``response_text`` (or one computed by ``responder``) with
    deterministic token metadata, and records every :class:`ClaudeRequest` in
    ``calls``. If ``error`` is provided, :meth:`complete` records the call and
    raises it — useful for provider-error/timeout routing tests.
    """

    def __init__(
        self,
        *,
        response_text: str = "",
        responder: object | None = None,
        error: ClaudeError | None = None,
        stop_reason: str = "end_turn",
    ) -> None:
        self._response_text = response_text
        self._responder = responder
        self._error = error
        self._stop_reason = stop_reason
        self.calls: list[ClaudeRequest] = []

    def complete(self, request: ClaudeRequest) -> ClaudeResponse:
        self.calls.append(request)
        if self._error is not None:
            raise self._error
        if callable(self._responder):
            text = str(self._responder(request))
        else:
            text = self._response_text
        return ClaudeResponse(
            text=text,
            model_id=request.model_id,
            input_tokens=_estimate_tokens(request.system + request.prompt),
            output_tokens=_estimate_tokens(text),
            stop_reason=self._stop_reason,
        )


__all__ = [
    "ClaudeError",
    "ClaudeTimeoutError",
    "ClaudeProviderError",
    "ClaudeRequest",
    "ClaudeResponse",
    "ClaudeClient",
    "FakeClaudeClient",
]
