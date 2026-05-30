"""SL-003 RED tests: accept-only stub HITL review minting an approved decision.

The smoke accept action must mint an ``ApprovedReviewDecision``-shaped capability
scoped to the same repository, carrying the reviewer id, draft id, structural-change
id, and a SHA-256 hash of the exact rendered draft reviewed. Mismatched
repository/draft inputs must fail *before* any persistence (architecture
#service-boundaries: approval-bound mutation; FM-20: meaningful approval).
"""

from __future__ import annotations

import hashlib

import pytest

from living_adr.core.models import ApprovedReviewDecision, RepositoryIdentity
from living_adr.hitl.stub_review import ReviewMismatchError, accept_draft
from living_adr.workflow.smoke_fixture import (
    merged_pr_fixture,
    normalize_to_scm_event,
)
from living_adr.workflow.smoke_flow import classify_structural_change, draft_adr


def _change_and_draft():
    event = normalize_to_scm_event(merged_pr_fixture())
    change, evidence = classify_structural_change(event)
    draft = draft_adr(change, evidence)
    return change, draft


def test_accept_mints_scoped_approved_decision() -> None:
    change, draft = _change_and_draft()
    decision = accept_draft(draft, change, reviewer_id="lead-1")
    assert isinstance(decision, ApprovedReviewDecision)
    assert decision.reviewer_id == "lead-1"
    assert decision.repository == draft.repository
    assert decision.adr_draft_id == draft.draft_id
    assert decision.structural_change_event_id == change.change_id
    assert decision.approved is True


def test_accept_hashes_exact_reviewed_draft_content() -> None:
    change, draft = _change_and_draft()
    decision = accept_draft(draft, change, reviewer_id="lead-1")
    expected = hashlib.sha256(draft.rendered_markdown.encode("utf-8")).hexdigest()
    assert decision.adr_draft_content_hash == expected


def test_accept_is_labeled_smoke_stub() -> None:
    change, draft = _change_and_draft()
    decision = accept_draft(draft, change, reviewer_id="lead-1")
    assert decision.is_stub is True


def test_repository_mismatch_is_rejected_before_persistence() -> None:
    change, draft = _change_and_draft()
    other_repo = RepositoryIdentity(
        host="github.com", owner="other", repo="x", repo_id="other-id"
    )
    mismatched = draft.model_copy(update={"repository": other_repo})
    with pytest.raises(ReviewMismatchError):
        accept_draft(mismatched, change, reviewer_id="lead-1")


def test_draft_change_linkage_mismatch_is_rejected() -> None:
    change, draft = _change_and_draft()
    mismatched = draft.model_copy(update={"structural_change_id": "chg-bogus"})
    with pytest.raises(ReviewMismatchError):
        accept_draft(mismatched, change, reviewer_id="lead-1")
