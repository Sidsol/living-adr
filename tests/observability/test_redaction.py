"""Slice 2: default-deny metadata redaction policy (FM-21).

Proves that the redaction layer enforces metadata-only traces: forbidden raw
fields (diffs, prompts, drafts, reviewer comments, retrieved context, code
snippets, secrets, personal data) are stripped before export, while safe
identifiers/counts/durations pass through. Opt-in raw export is honored only for
non-sensitive repositories. Diagnostics never carry the raw value.
"""

from __future__ import annotations

from living_adr.observability.config import LangSmithSettings
from living_adr.observability.logging import SafeStructuredLogger
from living_adr.observability.redaction import (
    RedactionReason,
    redact_metadata,
)


def _reasons(result) -> set[str]:
    return {r.reason for r in result.redactions}


def _paths(result) -> set[str]:
    return {r.path for r in result.redactions}


# ---------------------------------------------------------------- forbidden keys


def test_safe_metadata_passes_through_unchanged() -> None:
    meta = {
        "repository": "github.com/o/r",
        "draft_id": "draft-7",
        "decision_id": "dec-1",
        "change_class": "structural",
        "outcome": "approved",
        "latency_ms": 1234,
        "prompt_tokens": 1500,
        "retry_count": 2,
    }
    result = redact_metadata("review.recorded", meta)
    assert result.safe == meta
    assert result.redactions == ()


def test_raw_diff_is_redacted() -> None:
    result = redact_metadata("pr.observed", {"raw_diff": "- a\n+ b"})
    assert "raw_diff" not in result.safe
    assert RedactionReason.FORBIDDEN_KEY in _reasons(result)


def test_forbidden_string_fields_are_stripped() -> None:
    meta = {
        "prompt": "You are an architect...",
        "draft_body": "## Decision ...",
        "reviewer_comment": "looks risky",
        "retrieved_context": "chunk of code",
        "code_snippet": "def f(): ...",
        "secret": "hunter2",
        "api_key": "ls-xxxx",
        "email": "a@b.com",
        "repository": "github.com/o/r",
    }
    result = redact_metadata("model.called", meta)
    assert set(result.safe) == {"repository"}
    assert _reasons(result) == {RedactionReason.FORBIDDEN_KEY}
    # Diagnostics never echo the raw value.
    for red in result.redactions:
        assert "hunter2" not in red.path
        assert "You are" not in red.path


def test_numeric_token_counts_survive_despite_token_in_key() -> None:
    meta = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
    result = redact_metadata("model.tokens", meta)
    assert result.safe == meta
    assert result.redactions == ()


def test_nested_objects_are_redacted_recursively() -> None:
    meta = {
        "repository": "github.com/o/r",
        "stage": {"name": "draft", "prompt": "secret prompt"},
        "items": [{"draft_id": "d1"}, {"reviewer_comment": "no"}],
    }
    result = redact_metadata("workflow.stage", meta)
    assert result.safe["stage"] == {"name": "draft"}
    assert result.safe["items"][0] == {"draft_id": "d1"}
    assert result.safe["items"][1] == {}
    assert "stage.prompt" in _paths(result)
    assert "items[1].reviewer_comment" in _paths(result)


def test_oversized_string_is_redacted_even_for_safe_key() -> None:
    meta = {"note": "x" * 5000}
    result = redact_metadata("evt", meta)
    assert "note" not in result.safe
    assert RedactionReason.OVERSIZED_VALUE in _reasons(result)


def test_unsupported_type_is_redacted() -> None:
    meta = {"repository": "github.com/o/r", "blob": object()}
    result = redact_metadata("evt", meta)
    assert "blob" not in result.safe
    assert RedactionReason.UNSUPPORTED_TYPE in _reasons(result)


# ------------------------------------------------------------- raw export policy


def test_raw_export_denied_by_default() -> None:
    settings = LangSmithSettings(enabled=True, api_key="k")  # raw_export_debug=False
    result = redact_metadata(
        "evt", {"raw_diff": "x"}, settings=settings, repository_key="github.com/o/r"
    )
    assert "raw_diff" not in result.safe
    assert result.raw_export_allowed is False


def test_raw_export_allowed_for_non_sensitive_when_debug_enabled() -> None:
    settings = LangSmithSettings(
        enabled=True, api_key="k", raw_export_debug=True
    )
    result = redact_metadata(
        "evt",
        {"raw_diff": "x", "repository": "github.com/o/r"},
        settings=settings,
        repository_key="github.com/o/r",
    )
    assert result.raw_export_allowed is True
    assert result.safe["raw_diff"] == "x"


def test_raw_export_denied_for_sensitive_repository_even_when_debug_enabled() -> None:
    settings = LangSmithSettings(
        enabled=True,
        api_key="k",
        raw_export_debug=True,
        sensitive_repositories=("github.com/o/secret",),
    )
    result = redact_metadata(
        "evt",
        {"raw_diff": "x"},
        settings=settings,
        repository_key="github.com/o/secret",
    )
    assert result.raw_export_allowed is False
    assert "raw_diff" not in result.safe
    assert RedactionReason.RAW_EXPORT_DENIED_SENSITIVE in _reasons(result)


# ------------------------------------------------------------- structured logger


def test_safe_logger_event_record_has_safe_shape() -> None:
    logger = SafeStructuredLogger()
    record = logger.log_event("pr.classified", {"repository": "github.com/o/r"})
    assert record["kind"] == "event"
    assert record["name"] == "pr.classified"
    assert record["metadata"] == {"repository": "github.com/o/r"}


def test_safe_logger_redaction_record_omits_values() -> None:
    logger = SafeStructuredLogger()
    result = redact_metadata("evt", {"prompt": "secret"})
    record = logger.log_redaction("evt", result.redactions)
    assert record["kind"] == "redaction"
    assert record["name"] == "evt"
    assert record["redactions"][0]["reason"] == RedactionReason.FORBIDDEN_KEY
    assert record["redactions"][0]["path"] == "prompt"
    assert "secret" not in str(record)


# ------------------------------------------------------------- adapter wiring


def test_adapter_redacts_before_sink() -> None:
    from living_adr.observability.factory import build_observability

    class RecordingSink:
        def __init__(self) -> None:
            self.events: list[tuple[str, dict]] = []

        def on_event(self, name, metadata):
            self.events.append((name, dict(metadata)))

        def on_counter(self, name, value, metadata):  # pragma: no cover
            pass

        def on_span_start(self, name, metadata):  # pragma: no cover
            return "s"

        def on_span_end(self, span_id, metadata, error):  # pragma: no cover
            pass

    sink = RecordingSink()
    settings = LangSmithSettings(enabled=True, api_key="k")
    obs = build_observability(settings, sink=sink)
    obs.record_event(
        "model.called", {"repository": "github.com/o/r", "prompt": "leak me"}
    )
    assert sink.events == [("model.called", {"repository": "github.com/o/r"})]
