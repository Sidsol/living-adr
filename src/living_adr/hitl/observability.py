"""Metadata-only review telemetry builder for the HITL UI (feature 009).

The review UI handles sensitive material — provisional draft bodies, reviewer
edits, and rejection reasons. None of it may ever reach observability. This
builder enforces the default-deny contract from
``living_adr.core.observability`` by allow-listing a small set of metadata-safe
keys (identifiers, enums, counts, durations, error classes) and dropping
everything else, so a raw draft/comment can never be emitted even by accident.
"""

from __future__ import annotations

from living_adr.core.observability import Observability

#: The only keys permitted in HITL review telemetry. Everything else is dropped.
ALLOWED_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "thread_id",
        "repository",
        "draft_id",
        "draft_content_hash",
        "action",
        "result",
        "status",
        "latency_ms",
        "error_class",
        "pending_count",
        "evidence_count",
    }
)


def review_event_metadata(**fields: object) -> dict[str, object]:
    """Return a metadata-only payload: allow-listed, non-null keys only."""

    return {
        key: value
        for key, value in fields.items()
        if key in ALLOWED_METADATA_KEYS and value is not None
    }


def emit_review_event(
    observability: Observability, name: str, **fields: object
) -> None:
    """Record a metadata-only review event through the Observability port."""

    observability.record_event(name, review_event_metadata(**fields))


__all__ = [
    "ALLOWED_METADATA_KEYS",
    "review_event_metadata",
    "emit_review_event",
]
