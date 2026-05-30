"""Slice 5: no-op Observability core port.

The port must be thin, metadata-first, dependency-free in ``core`` (no LangSmith),
and safe on both success and exception paths. Feature 013 later swaps in the real
LangSmith-backed adapter; nothing here may couple downstream features to it.
"""

from __future__ import annotations

import inspect

import pytest

import living_adr.core.observability as obs_mod
from living_adr.core.observability import (
    NoOpObservability,
    Observability,
    ObservationSpan,
)


def test_noop_satisfies_observability_protocol() -> None:
    obs = NoOpObservability()
    assert isinstance(obs, Observability)


def test_record_event_is_safe_with_metadata() -> None:
    obs = NoOpObservability()
    assert obs.record_event("pr.classified", {"repository": "github.com/o/r"}) is None
    assert obs.record_event("pr.classified") is None


def test_increment_counter_is_safe_with_metadata() -> None:
    obs = NoOpObservability()
    assert obs.increment_counter("drafts.created") is None
    assert obs.increment_counter("drafts.created", 3, {"repo": "x"}) is None


def test_start_span_yields_span_and_exits_cleanly_on_success() -> None:
    obs = NoOpObservability()
    with obs.start_span("classify", {"repo": "x"}) as span:
        assert isinstance(span, ObservationSpan)
        assert span.record_event("inner", {"k": "v"}) is None


def test_start_span_exits_cleanly_on_exception() -> None:
    obs = NoOpObservability()
    with pytest.raises(ValueError):
        with obs.start_span("classify") as span:
            assert isinstance(span, ObservationSpan)
            raise ValueError("boom")


def test_core_observability_imports_no_langsmith() -> None:
    source = inspect.getsource(obs_mod).lower()
    # The contract may *mention* LangSmith conceptually, but must never import it.
    assert "import langsmith" not in source
    assert "from langsmith" not in source
    # And the imported module must not have pulled langsmith into its namespace.
    assert not hasattr(obs_mod, "langsmith")


def test_contract_documents_default_deny_raw_export() -> None:
    doc = ((NoOpObservability.__doc__ or "") + (obs_mod.__doc__ or "")).lower()
    assert "default-deny" in doc
    for category in ["diff", "prompt", "draft", "reviewer", "secret", "context"]:
        assert category in doc
