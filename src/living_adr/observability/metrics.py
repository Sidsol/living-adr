"""Structured metric helpers (feature 013, slice 3).

Typed helper functions that downstream workflow, drafting (Claude), retrieval,
MCP, HITL, and evaluation code can call to emit consistent latency, token-count,
retry, and error metrics through feature 002's ``Observability`` port — **without
importing LangSmith** and without knowing which adapter is bound.

Every metric is repository-scoped (``architecture.md#anti-patterns``: no
repository-agnostic metrics) and metadata-only: token *counts* but never prompt
bodies, error *types* but never stack traces or messages.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from enum import StrEnum

from living_adr.core.observability import Observability, ObservationSpan


class MetricName(StrEnum):
    """Stable metric/event names. Downstream callers reference these, not LangSmith."""

    STAGE_LATENCY = "stage.latency_ms"
    PR_TO_DRAFT_LATENCY = "pipeline.pr_to_draft.latency_ms"
    RETRIEVAL_LATENCY = "retrieval.latency_ms"
    MCP_ANSWER_LATENCY = "mcp.answer.latency_ms"
    MODEL_TOKENS = "model.tokens"
    RUN_RETRY = "run.retry"
    RUN_ERROR = "run.error"


def scope_metadata(
    repository_key: str, run_id: str | None = None, **extra: object
) -> dict[str, object]:
    """Build repository-scoped metadata with optional run id and safe extras."""

    meta: dict[str, object] = {"repository": repository_key}
    if run_id is not None:
        meta["run_id"] = run_id
    meta.update(extra)
    return meta


def _as_count(name: str, value: object) -> int:
    """Coerce a token/retry count to a non-negative int; reject non-numeric."""

    if isinstance(value, bool) or not isinstance(value, int | float):
        raise ValueError(f"{name} must be a numeric count, got {type(value).__name__}")
    count = int(value)
    if count < 0:
        raise ValueError(f"{name} must not be negative")
    return count


def token_usage_metadata(
    *,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int | None = None,
) -> dict[str, object]:
    """Numeric-only token usage metadata. Never carries prompt/response text."""

    prompt = _as_count("prompt_tokens", prompt_tokens)
    completion = _as_count("completion_tokens", completion_tokens)
    total = (
        _as_count("total_tokens", total_tokens)
        if total_tokens is not None
        else prompt + completion
    )
    return {
        "prompt_tokens": prompt,
        "completion_tokens": completion,
        "total_tokens": total,
    }


def record_token_usage(
    obs: Observability,
    *,
    repository_key: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int | None = None,
    run_id: str | None = None,
    model: str | None = None,
) -> None:
    """Emit token-count metadata for a model call (US-2, SM-02)."""

    meta = scope_metadata(repository_key, run_id)
    meta.update(
        token_usage_metadata(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
    )
    if model is not None:
        meta["model"] = model
    obs.record_event(MetricName.MODEL_TOKENS, meta)


def record_latency(
    obs: Observability,
    metric: MetricName,
    *,
    repository_key: str,
    latency_ms: int,
    run_id: str | None = None,
    **extra: object,
) -> None:
    """Emit a latency metric (milliseconds) for a stage/pipeline/retrieval/MCP step."""

    meta = scope_metadata(repository_key, run_id, **extra)
    meta["latency_ms"] = _as_count("latency_ms", latency_ms)
    obs.record_event(metric, meta)


def record_pr_to_draft_latency(
    obs: Observability,
    *,
    repository_key: str,
    latency_ms: int,
    run_id: str | None = None,
) -> None:
    """Convenience wrapper for the headline PR-to-draft latency (SM-02)."""

    record_latency(
        obs,
        MetricName.PR_TO_DRAFT_LATENCY,
        repository_key=repository_key,
        latency_ms=latency_ms,
        run_id=run_id,
    )


def record_retry(
    obs: Observability,
    *,
    repository_key: str,
    error_type: str,
    attempt: int,
    run_id: str | None = None,
) -> None:
    """Emit a retry counter with error *type* and attempt — never a stack trace."""

    meta = scope_metadata(repository_key, run_id)
    meta["error_type"] = error_type
    meta["attempt"] = _as_count("attempt", attempt)
    obs.increment_counter(MetricName.RUN_RETRY, 1, meta)


def record_error(
    obs: Observability,
    *,
    repository_key: str,
    error_type: str,
    run_id: str | None = None,
    stage: str | None = None,
) -> None:
    """Emit an error event with the exception *type* only (no message/stack)."""

    meta = scope_metadata(repository_key, run_id)
    meta["error_type"] = error_type
    if stage is not None:
        meta["stage"] = stage
    obs.record_event(MetricName.RUN_ERROR, meta)


@contextmanager
def stage_span(
    obs: Observability,
    *,
    stage: str,
    repository_key: str,
    run_id: str | None = None,
    **extra: object,
) -> Iterator[ObservationSpan]:
    """Time a workflow stage and attach safe latency/scope metadata to its span."""

    meta = scope_metadata(repository_key, run_id, stage=stage, **extra)
    start = time.perf_counter()
    with obs.start_span(f"{MetricName.STAGE_LATENCY}:{stage}", meta) as span:
        try:
            yield span
        finally:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            span.set_metadata("repository", repository_key)
            span.set_metadata("stage", stage)
            if run_id is not None:
                span.set_metadata("run_id", run_id)
            span.set_metadata("latency_ms", elapsed_ms)


__all__ = [
    "MetricName",
    "scope_metadata",
    "token_usage_metadata",
    "record_token_usage",
    "record_latency",
    "record_pr_to_draft_latency",
    "record_retry",
    "record_error",
    "stage_span",
]
