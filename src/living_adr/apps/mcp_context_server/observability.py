"""Observability bootstrap + metadata-only tool telemetry for mcp-context-server.

The bootstrap (:func:`build_observability_for_app`, feature 013) builds the
:class:`Observability` provider from the environment without importing the
LangSmith SDK. Feature 012 adds a **metadata-only** tool-call wrapper that emits
non-sensitive summaries (tool name, repository key, status, result count, latency
bucket, error type) and never raw questions, answers, ADR bodies, citations, or
secrets (US-6, FR-9; architecture #cross-cutting FM-21 default-deny).
"""

from __future__ import annotations

import os
from collections.abc import Mapping

from living_adr.core.observability import Observability
from living_adr.observability.config import LangSmithSettings
from living_adr.observability.factory import build_observability

#: Event/counter names for MCP tool telemetry.
TOOL_EVENT_NAME = "mcp.tool_call"
TOOL_COUNTER_NAME = "mcp.tool_calls"


def build_observability_for_app(
    env: Mapping[str, str] | None = None,
) -> Observability:
    """Return the configured provider; no-op when LangSmith is unconfigured."""

    settings = LangSmithSettings.from_env(env if env is not None else os.environ)
    return build_observability(settings)


def latency_bucket(elapsed_seconds: float) -> str:
    """Bucket a latency into a coarse, non-identifying label.

    Buckets (not raw timings) keep telemetry low-cardinality and prevent timing
    side channels from leaking request specifics.
    """

    millis = max(elapsed_seconds, 0.0) * 1000.0
    if millis < 50:
        return "lt_50ms"
    if millis < 250:
        return "lt_250ms"
    if millis < 1000:
        return "lt_1s"
    return "ge_1s"


def tool_call_metadata(
    *,
    tool: str,
    repository_key: str | None,
    status: str,
    elapsed_seconds: float,
    result_count: int | None = None,
    error_type: str | None = None,
) -> dict[str, object]:
    """Build the metadata-only payload for one MCP tool call.

    Only the whitelisted, non-sensitive fields below are ever included — no
    question text, answer body, ADR content, citations, prompts, or secrets.
    """

    metadata: dict[str, object] = {
        "tool": tool,
        "repository": repository_key,
        "status": status,
        "latency_bucket": latency_bucket(elapsed_seconds),
    }
    if result_count is not None:
        metadata["result_count"] = result_count
    if error_type is not None:
        metadata["error_type"] = error_type
    return metadata


def record_tool_call(
    observability: Observability,
    *,
    tool: str,
    repository_key: str | None,
    status: str,
    elapsed_seconds: float,
    result_count: int | None = None,
    error_type: str | None = None,
) -> None:
    """Emit a metadata-only event + counter for one MCP tool call."""

    metadata = tool_call_metadata(
        tool=tool,
        repository_key=repository_key,
        status=status,
        elapsed_seconds=elapsed_seconds,
        result_count=result_count,
        error_type=error_type,
    )
    observability.record_event(TOOL_EVENT_NAME, metadata)
    observability.increment_counter(
        TOOL_COUNTER_NAME, 1, {"tool": tool, "status": status}
    )


__all__ = [
    "TOOL_EVENT_NAME",
    "TOOL_COUNTER_NAME",
    "build_observability_for_app",
    "latency_bucket",
    "tool_call_metadata",
    "record_tool_call",
]
