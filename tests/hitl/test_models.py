"""SL-001/SL-004 tests: HITL review view models, mapping, validation, hashing.

These exercise the pure, framework-free UI layer that transforms a feature 015
``ReviewRequestPayload`` into a renderable page model (no orchestration, no graph
state redefinition) and validates/hashes reviewer-edited draft content for the
approve-after-edit path. No raw draft text leaks into telemetry-safe summaries.
"""

from __future__ import annotations

import pytest

from living_adr.core.models import RepositoryIdentity
from living_adr.hitl.models import (
    ConfidenceBand,
    PendingReviewSummary,
    ReviewPageModel,
    page_model_from_payload,
    pending_summary_from_payload,
)
from living_adr.workflow.state import ReviewAction, ReviewRequestPayload


def _repo() -> RepositoryIdentity:
    return RepositoryIdentity(
        host="github.com", owner="acme", repo="widgets", repo_id="r-1"
    )


def _payload(**overrides) -> ReviewRequestPayload:
    base = dict(
        repository=_repo(),
        normalized_event_key="github:github.com/acme/widgets:42:d-1",
        draft_id="draft-1",
        draft_content_hash="abc123",
        draft_preview="# Title\n\nProvisional draft preview body.",
        evidence_ids=("ev-1", "ev-2"),
        confidence=0.82,
        allowed_actions=(
            ReviewAction.APPROVE,
            ReviewAction.APPROVE_AFTER_EDIT,
            ReviewAction.REJECT,
            ReviewAction.DEFER,
        ),
    )
    base.update(overrides)
    return ReviewRequestPayload(**base)


def test_page_model_maps_all_payload_fields() -> None:
    payload = _payload()
    model = page_model_from_payload(payload, thread_id="wf-thread-1")
    assert model.thread_id == "wf-thread-1"
    assert model.repository_key == "github.com/acme/widgets"
    assert model.event_key == payload.normalized_event_key
    assert model.draft_id == "draft-1"
    assert model.draft_content_hash == "abc123"
    assert model.draft_preview == payload.draft_preview
    assert model.evidence_ids == ("ev-1", "ev-2")
    assert model.confidence == pytest.approx(0.82)
    assert model.allowed_actions == payload.allowed_actions
    assert model.provisional is True
    assert "provisional" in model.provisional_notice.lower()


def test_page_model_is_a_review_page_model_instance() -> None:
    model = page_model_from_payload(_payload(), thread_id="wf-1")
    assert isinstance(model, ReviewPageModel)


def test_confidence_band_is_text_not_only_color() -> None:
    # Color must not be the only indicator: a textual band accompanies the number.
    high = page_model_from_payload(_payload(confidence=0.9), thread_id="t")
    medium = page_model_from_payload(_payload(confidence=0.5), thread_id="t")
    low = page_model_from_payload(_payload(confidence=0.1), thread_id="t")
    assert high.confidence_band is ConfidenceBand.HIGH
    assert medium.confidence_band is ConfidenceBand.MEDIUM
    assert low.confidence_band is ConfidenceBand.LOW
    assert high.confidence_band.label
    assert high.confidence_percent == 90


def test_allowed_action_values_are_safe_strings() -> None:
    model = page_model_from_payload(_payload(), thread_id="t")
    values = model.allowed_action_values
    assert values == ("approve", "approve_after_edit", "reject", "defer")


def test_pending_summary_from_payload_is_metadata_only() -> None:
    payload = _payload()
    summary = pending_summary_from_payload("wf-thread-1", payload)
    assert isinstance(summary, PendingReviewSummary)
    assert summary.thread_id == "wf-thread-1"
    assert summary.repository_key == "github.com/acme/widgets"
    assert summary.draft_id == "draft-1"
    assert summary.evidence_count == 2
    # The bounded preview body must never be embedded in a list summary.
    assert "Provisional draft preview body" not in repr(summary)
