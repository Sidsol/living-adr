"""Slice S010-02: ApprovedReviewDecision minting + canonical content hashing.

Proves canonical hashing is cross-platform stable and byte-compatible with the
feature 008/009 rendered-draft hash, that approve / approve-after-edit mint a
capability bound to the exact reviewed content hash, and that reject / defer mint
no capability.
"""

from __future__ import annotations

from tests.approval._helpers import (
    DRAFT_HASH,
    DRAFT_MARKDOWN,
    FixedClock,
    SequentialIds,
    build_command,
    build_context,
    build_repo,
    sha256_lf,
)

from living_adr.approval.hashing import (
    canonical_adr_hash,
    content_matches_hash,
)
from living_adr.approval.minting import mint_approved_decision
from living_adr.approval.models import (
    ApprovedReviewDecision,
    MintedDecisionRecord,
)
from living_adr.approval.repository import InMemoryApprovalAuditRepository
from living_adr.core.approval import ApprovedReviewDecision as CoreDecision
from living_adr.hitl.hashing import compute_edited_draft_hash
from living_adr.workflow.state import ReviewAction

# --- canonical hashing -----------------------------------------------------


def test_canonical_hash_is_line_ending_invariant() -> None:
    lf = "# Title\n## Status\nProposed\n"
    crlf = "# Title\r\n## Status\r\nProposed\r\n"
    cr = "# Title\r## Status\rProposed\r"
    assert canonical_adr_hash(lf) == canonical_adr_hash(crlf) == canonical_adr_hash(cr)


def test_canonical_hash_byte_compatible_with_feature_009() -> None:
    # For LF/UTF-8 content the canonical hash equals feature 009's edited hash
    # and the helper's plain SHA-256 — so capabilities verify against the hash
    # the reviewer approved.
    assert canonical_adr_hash(DRAFT_MARKDOWN) == sha256_lf(DRAFT_MARKDOWN)
    assert canonical_adr_hash(DRAFT_MARKDOWN) == compute_edited_draft_hash(
        DRAFT_MARKDOWN
    )
    assert content_matches_hash(DRAFT_MARKDOWN, DRAFT_HASH)


# --- minting ---------------------------------------------------------------


def test_approve_mints_capability_bound_to_original_hash() -> None:
    audit = InMemoryApprovalAuditRepository()
    repo = build_repo()
    result = mint_approved_decision(
        repo,
        build_command(ReviewAction.APPROVE),
        build_context(repo),
        target_fingerprint="fp-upsert-1",
        audit=audit,
        clock=FixedClock(),
        id_provider=SequentialIds("id"),
    )
    decision = result.decision
    assert isinstance(decision, ApprovedReviewDecision)
    # Reuses the feature 006 capability type byte-compatibly.
    assert isinstance(decision, CoreDecision)
    assert decision.approved is True
    assert decision.repository == repo
    assert decision.reviewer_id == "lead-1"
    assert decision.adr_draft_id == "draft-1"
    assert decision.adr_draft_content_hash == DRAFT_HASH
    assert decision.target_fingerprint == "fp-upsert-1"
    assert decision.consumed_at is None

    # The capability is durably persisted with its TTL metadata.
    stored = audit.get_minted_decision(decision.decision_id)
    assert isinstance(stored, MintedDecisionRecord)
    assert stored.adr_draft_content_hash == DRAFT_HASH
    assert stored.ttl_seconds == 600  # PoC default 10 minutes
    # The review event references the minted capability.
    event = audit.get_review_event(result.event.review_event_id)
    assert event is not None
    assert event.decision_id == decision.decision_id


def test_approve_after_edit_binds_edited_hash() -> None:
    audit = InMemoryApprovalAuditRepository()
    repo = build_repo()
    edited = (
        "# Title: Edited decision\n## Status\nProposed\n## Context\nc\n"
        "## Decision\nuse durable audit\n## Consequences\ne\n"
    )
    edited_hash = canonical_adr_hash(edited)
    result = mint_approved_decision(
        repo,
        build_command(
            ReviewAction.APPROVE_AFTER_EDIT,
            edited_content=edited,
            edited_content_hash=edited_hash,
        ),
        build_context(repo),
        target_fingerprint="fp-upsert-2",
        audit=audit,
        clock=FixedClock(),
        id_provider=SequentialIds("id"),
    )
    assert result.decision is not None
    assert result.decision.adr_draft_content_hash == edited_hash
    assert result.decision.adr_draft_content_hash != DRAFT_HASH


def test_reject_and_defer_mint_no_capability() -> None:
    for action in (ReviewAction.REJECT, ReviewAction.DEFER):
        audit = InMemoryApprovalAuditRepository()
        repo = build_repo()
        result = mint_approved_decision(
            repo,
            build_command(action),
            build_context(repo),
            audit=audit,
            clock=FixedClock(),
            id_provider=SequentialIds("id"),
            reason="not significant",
        )
        assert result.decision is None
        assert result.minted_record is None
        # The outcome is still durably recorded.
        events = audit.list_review_events(repository_key=repo.key)
        assert len(events) == 1
        assert events[0].action is action
        assert events[0].decision_id is None
        assert events[0].authorizing is False


def test_minted_capability_serializes_for_workflow_state() -> None:
    audit = InMemoryApprovalAuditRepository()
    repo = build_repo()
    result = mint_approved_decision(
        repo,
        build_command(ReviewAction.APPROVE),
        build_context(repo),
        target_fingerprint="fp-upsert-3",
        audit=audit,
        clock=FixedClock(),
        id_provider=SequentialIds("id"),
    )
    decision = result.decision
    assert decision is not None
    # Round-trips through JSON so feature 015 can carry it in workflow state.
    rehydrated = ApprovedReviewDecision.model_validate_json(
        decision.model_dump_json()
    )
    assert rehydrated == decision
