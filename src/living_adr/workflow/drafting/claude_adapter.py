"""Anthropic-backed Claude adapter (feature 008, slice S-005, NFR-5).

This is the **only** module that knows about the Anthropic SDK. It satisfies the
SDK-free :class:`~living_adr.core.llm.ClaudeClient` seam by translating a domain
:class:`~living_adr.core.llm.ClaudeRequest` into an SDK ``messages.create`` call
and the SDK response/usage back into a domain
:class:`~living_adr.core.llm.ClaudeResponse`. Provider timeouts and errors are
mapped onto the domain :class:`~living_adr.core.llm.ClaudeTimeoutError` /
:class:`~living_adr.core.llm.ClaudeProviderError`, so no SDK exception type leaks
into the workflow (architecture #service-boundaries).

The SDK client is **injected** (any object exposing ``messages.create``); tests
pass a deterministic fake, so this seam can never reach the network in CI (US-5).
"""

from __future__ import annotations

from typing import Protocol

from pydantic import BaseModel, ConfigDict

from living_adr.core.llm import (
    ClaudeProviderError,
    ClaudeRequest,
    ClaudeResponse,
    ClaudeTimeoutError,
)


class _SDKMessages(Protocol):
    def create(self, **kwargs: object) -> object: ...


class _SDKClient(Protocol):
    messages: _SDKMessages


class ClaudeAdapterConfig(BaseModel):
    """Configuration for the Anthropic adapter (model id, limits, timeout)."""

    model_config = ConfigDict(frozen=True)

    model_id: str = "claude-sonnet-4-6"
    max_tokens: int = 2000
    temperature: float = 0.0
    timeout_s: float = 60.0


def _is_timeout(exc: BaseException) -> bool:
    """Best-effort, SDK-version-tolerant timeout classification.

    Prefers the installed Anthropic timeout type; falls back to a class-name
    heuristic so the mapping holds even if the SDK exception hierarchy shifts.
    """

    try:  # pragma: no cover - import guard
        import anthropic

        timeout_type = getattr(anthropic, "APITimeoutError", None)
        if timeout_type is not None and isinstance(exc, timeout_type):
            return True
    except Exception:  # pragma: no cover - anthropic optional at runtime
        pass
    return "timeout" in type(exc).__name__.lower()


class AnthropicClaudeClient:
    """Adapter binding the Anthropic SDK to the ``ClaudeClient`` seam."""

    def __init__(
        self,
        *,
        client: _SDKClient,
        config: ClaudeAdapterConfig | None = None,
    ) -> None:
        self._client = client
        self._config = config or ClaudeAdapterConfig()

    def complete(self, request: ClaudeRequest) -> ClaudeResponse:
        try:
            raw = self._client.messages.create(
                model=request.model_id,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                system=request.system,
                messages=[{"role": "user", "content": request.prompt}],
                timeout=self._config.timeout_s,
            )
        except Exception as exc:  # noqa: BLE001 - mapped to domain errors
            if _is_timeout(exc):
                raise ClaudeTimeoutError(str(exc)) from exc
            raise ClaudeProviderError(str(exc)) from exc

        return self._to_response(request, raw)

    def _to_response(self, request: ClaudeRequest, raw: object) -> ClaudeResponse:
        text = self._extract_text(raw)
        if not text.strip():
            raise ClaudeProviderError("provider returned empty content")
        usage = getattr(raw, "usage", None)
        return ClaudeResponse(
            text=text,
            model_id=request.model_id,
            input_tokens=int(getattr(usage, "input_tokens", 0) or 0),
            output_tokens=int(getattr(usage, "output_tokens", 0) or 0),
            stop_reason=getattr(raw, "stop_reason", None),
        )

    @staticmethod
    def _extract_text(raw: object) -> str:
        content = getattr(raw, "content", None)
        if not content:
            return ""
        parts = [
            block.text
            for block in content
            if getattr(block, "text", None) is not None
        ]
        return "".join(parts)


__all__ = [
    "ClaudeAdapterConfig",
    "AnthropicClaudeClient",
]
