"""Slice S010-03: TTL, scope, content, and target validation (fail closed).

Clock-controlled tests prove a capability is rejected when expired, scoped to the
wrong repository, used for the wrong target fingerprint, applied to a
non-approved outcome, or when the rendered content drifted since approval. Each
failure is a typed error and (via ``validate_for_mutation``) a durable audit row.
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from tests.approval._helpers import (
    DRAFT_MARKDOWN,
    FixedClock,
    SequentialIds,
    build_command,
    build_context,
    build_repo,
)

from living_adr.approval.minting import mint_approved_decision
from living_adr.approval.models import (
    ApprovalRequiredError,
    AuditEventType,
    DecisionExpiredError,
    DecisionNotApprovedError,
    DecisionRepositoryMismatchError,
    DraftContentMismatchError,
    MutationFingerprintMismatchError,
    TargetMutationMismatchError,
)
from living_adr.approval.repository import InMemoryApprovalAuditRepository
from living_adr.approval.validation import validate_decision, validate_for_mutation
from living_adr.workflow.state import ReviewAction

FP = "fp-upsert-1"


def _mint(audit, repo, clock, *, content_hash=None):
    ctx = build_context(repo)
    if content_hash is not None:
        ctx = build_context(repo, content_hash=content_hash)
    return mint_approved_decision(
        repo,
        build_command(ReviewAction.APPROVE),
        ctx,
        target_fingerprint=FP,
        audit=audit,
        clock=clock,
        id_provider=SequentialIds("id"),
    )


def test_decision_valid_within_ttl() -> None:
    audit = InMemoryApprovalAuditRepository()
    repo = build_repo()
    clock = FixedClock()
    result = _mint(audit, repo, clock)
    clock.advance(timedelta(minutes=9, seconds=59))
    decision = validate_decision(
        result.decision,
        repository=repo,
        expected_fingerprint=FP,
        current_content=DRAFT_MARKDOWN,
        clock=clock,
        minted_record=result.minted_record,
    )
    assert decision is result.decision


def test_decision_expired_after_default_ttl() -> None:
    audit = InMemoryApprovalAuditRepository()
    repo = build_repo()
    clock = FixedClock()
    result = _mint(audit, repo, clock)
    clock.advance(timedelta(minutes=10, seconds=1))
    with pytest.raises(DecisionExpiredError):
        validate_decision(
            result.decision,
            repository=repo,
            expected_fingerprint=FP,
            clock=clock,
            minted_record=result.minted_record,
        )


def test_repository_mismatch_rejected() -> None:
    audit = InMemoryApprovalAuditRepository()
    repo = build_repo()
    other = build_repo("other-repo")
    result = _mint(audit, repo, FixedClock())
    with pytest.raises(DecisionRepositoryMismatchError):
        validate_decision(
            result.decision,
            repository=other,
            expected_fingerprint=FP,
            clock=FixedClock(),
            minted_record=result.minted_record,
        )


def test_target_fingerprint_mismatch_rejected() -> None:
    audit = InMemoryApprovalAuditRepository()
    repo = build_repo()
    result = _mint(audit, repo, FixedClock())
    with pytest.raises(TargetMutationMismatchError) as excinfo:
        validate_decision(
            result.decision,
            repository=repo,
            expected_fingerprint="fp-different",
            clock=FixedClock(),
            minted_record=result.minted_record,
        )
    # Spec-named alias is byte-compatible with the feature 006 error.
    assert isinstance(excinfo.value, MutationFingerprintMismatchError)


def test_unapproved_decision_rejected() -> None:
    repo = build_repo()
    with pytest.raises(DecisionNotApprovedError) as excinfo:
        validate_decision(
            None,
            repository=repo,
            expected_fingerprint=FP,
            clock=FixedClock(),
        )
    assert isinstance(excinfo.value, ApprovalRequiredError)


def test_content_tampering_detected() -> None:
    audit = InMemoryApprovalAuditRepository()
    repo = build_repo()
    result = _mint(audit, repo, FixedClock())
    tampered = DRAFT_MARKDOWN + "\n## Sneaky\nInjected after approval.\n"
    with pytest.raises(DraftContentMismatchError):
        validate_decision(
            result.decision,
            repository=repo,
            expected_fingerprint=FP,
            current_content=tampered,
            clock=FixedClock(),
            minted_record=result.minted_record,
        )


def test_unchanged_content_passes() -> None:
    audit = InMemoryApprovalAuditRepository()
    repo = build_repo()
    result = _mint(audit, repo, FixedClock())
    decision = validate_decision(
        result.decision,
        repository=repo,
        expected_fingerprint=FP,
        current_content=DRAFT_MARKDOWN,
        clock=FixedClock(),
        minted_record=result.minted_record,
    )
    assert decision is result.decision


def test_validate_for_mutation_records_failure_audit() -> None:
    audit = InMemoryApprovalAuditRepository()
    repo = build_repo()
    clock = FixedClock()
    result = _mint(audit, repo, clock)
    clock.advance(timedelta(minutes=11))
    before = len(audit.list_audit_events())
    with pytest.raises(DecisionExpiredError):
        validate_for_mutation(
            result.decision,
            repository=repo,
            expected_fingerprint=FP,
            audit=audit,
            clock=clock,
            minted_record=result.minted_record,
            id_provider=SequentialIds("audit"),
        )
    failures = audit.list_audit_events(decision_id=result.decision.decision_id)
    failures = [
        e for e in failures if e.event_type is AuditEventType.VALIDATION_FAILED
    ]
    assert len(failures) == 1
    assert failures[0].failure_kind == "DecisionExpiredError"
    assert len(audit.list_audit_events()) == before + 1


def test_validate_for_mutation_no_audit_on_success() -> None:
    audit = InMemoryApprovalAuditRepository()
    repo = build_repo()
    result = _mint(audit, repo, FixedClock())
    before = len(audit.list_audit_events())
    validate_for_mutation(
        result.decision,
        repository=repo,
        expected_fingerprint=FP,
        audit=audit,
        current_content=DRAFT_MARKDOWN,
        clock=FixedClock(),
        minted_record=result.minted_record,
        id_provider=SequentialIds("audit"),
    )
    assert len(audit.list_audit_events()) == before
