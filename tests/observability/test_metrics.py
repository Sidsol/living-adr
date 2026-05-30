"""Slice 3: latency, token, and structured metric helpers.

Helpers build safe, repository-scoped metadata and emit it through feature 002's
``Observability`` port. They never import LangSmith and never carry raw payloads
(stack traces, prompt bodies, model responses). Tests use an in-memory fake port
— no credentials, no network.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager

import pytest

from living_adr.core.observability import ObservationSpan
from living_adr.observability import metrics
from living_adr.observability.metrics import MetricName
from living_adr.observability.redaction import redact_metadata

REPO = "github.com/o/r"


class FakeObservability:
    """Records port calls for assertions. Implements the feature 002 port."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []
        self.counters: list[tuple[str, int, dict]] = []
        self.spans: list[ObservationSpan] = []

    def record_event(self, name, metadata=None):
        self.events.append((name, dict(metadata or {})))

    def increment_counter(self, name, value=1, metadata=None):
        self.counters.append((name, value, dict(metadata or {})))

    @contextmanager
    def start_span(self, name, metadata=None) -> Iterator[ObservationSpan]:
        span = ObservationSpan(name, metadata)
        self.spans.append(span)
        yield span


def _assert_redaction_safe(metadata: Mapping[str, object]) -> None:
    result = redact_metadata("probe", dict(metadata))
    assert result.safe == dict(metadata)
    assert result.redactions == ()


def test_scope_metadata_includes_repository_and_run() -> None:
    meta = metrics.scope_metadata(REPO, run_id="run-1", stage="draft")
    assert meta["repository"] == REPO
    assert meta["run_id"] == "run-1"
    assert meta["stage"] == "draft"
    _assert_redaction_safe(meta)


def test_token_usage_metadata_is_numeric_only() -> None:
    meta = metrics.token_usage_metadata(
        prompt_tokens=1200, completion_tokens=300
    )
    assert meta == {
        "prompt_tokens": 1200,
        "completion_tokens": 300,
        "total_tokens": 1500,
    }
    assert all(isinstance(v, int) for v in meta.values())
    _assert_redaction_safe(meta)


def test_token_usage_metadata_rejects_non_numeric() -> None:
    with pytest.raises((ValueError, TypeError)):
        metrics.token_usage_metadata(
            prompt_tokens="lots",  # type: ignore[arg-type]
            completion_tokens=10,
        )


def test_record_token_usage_emits_event_without_bodies() -> None:
    obs = FakeObservability()
    metrics.record_token_usage(
        obs,
        repository_key=REPO,
        prompt_tokens=10,
        completion_tokens=20,
        run_id="run-1",
        model="claude-x",
    )
    name, meta = obs.events[0]
    assert name == MetricName.MODEL_TOKENS
    assert meta["prompt_tokens"] == 10
    assert meta["total_tokens"] == 30
    assert meta["repository"] == REPO
    assert "prompt" not in meta and "response" not in meta
    _assert_redaction_safe(meta)


def test_stage_span_emits_latency_and_scope() -> None:
    obs = FakeObservability()
    with metrics.stage_span(
        obs, stage="drafting", repository_key=REPO, run_id="run-1"
    ) as span:
        assert isinstance(span, ObservationSpan)
    span = obs.spans[0]
    assert span.metadata["stage"] == "drafting"
    assert span.metadata["repository"] == REPO
    assert isinstance(span.metadata["latency_ms"], int)
    assert span.metadata["latency_ms"] >= 0
    _assert_redaction_safe(span.metadata)


def test_record_latency_emits_numeric_latency() -> None:
    obs = FakeObservability()
    metrics.record_latency(
        obs,
        MetricName.PR_TO_DRAFT_LATENCY,
        repository_key=REPO,
        latency_ms=4200,
        run_id="run-1",
    )
    name, meta = obs.events[0]
    assert name == MetricName.PR_TO_DRAFT_LATENCY
    assert meta["latency_ms"] == 4200
    _assert_redaction_safe(meta)


def test_record_retry_emits_type_and_count_no_stack() -> None:
    obs = FakeObservability()
    metrics.record_retry(
        obs, repository_key=REPO, error_type="TimeoutError", attempt=2
    )
    name, value, meta = obs.counters[0]
    assert name == MetricName.RUN_RETRY
    assert value == 1
    assert meta["error_type"] == "TimeoutError"
    assert meta["attempt"] == 2
    assert "stack" not in meta and "traceback" not in meta and "message" not in meta
    _assert_redaction_safe(meta)


def test_record_error_emits_type_only() -> None:
    obs = FakeObservability()
    metrics.record_error(
        obs, repository_key=REPO, error_type="ValueError", stage="drafting"
    )
    name, meta = obs.events[0]
    assert name == MetricName.RUN_ERROR
    assert meta["error_type"] == "ValueError"
    assert meta["stage"] == "drafting"
    _assert_redaction_safe(meta)


def test_metrics_module_does_not_import_langsmith() -> None:
    import inspect
    import re

    source = inspect.getsource(metrics)
    assert re.search(r"\b(import|from)\s+langsmith\b", source) is None
