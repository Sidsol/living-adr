"""Just-in-time approval validation: TTL, scope, content, and target (feature 010).

These checks run immediately before any authoritative mutation and fail closed
with typed, audit-friendly errors (US-3/US-5; NFR-1). The order is deterministic:

1. approval state — the outcome must authorise mutation (``approved``).
2. repository scope — the capability must match the mutation's repository.
3. TTL / expiry — the capability must be within its lifetime.
4. content binding — the current rendered ADR content must still hash to the
   exact reviewed ``adr_draft_content_hash`` (post-approval tampering detection).
5. target fingerprint — the capability must authorise *this* mutation target.

:func:`validate_for_mutation` wraps the pure :func:`validate_decision` to append a
``VALIDATION_FAILED`` audit row on rejection, so every failed authorisation is
durably evidenced without leaking raw content (metadata-only).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from living_adr.approval.hashing import canonical_adr_hash
from living_adr.approval.models import (
    DEFAULT_DECISION_TTL,
    ApprovalError,
    ApprovedReviewDecision,
    AuditEventType,
    DecisionExpiredError,
    DecisionNotApprovedError,
    DecisionRepositoryMismatchError,
    DraftContentMismatchError,
    MintedDecisionRecord,
    TargetMutationMismatchError,
)
from living_adr.approval.repository import ApprovalAuditRepository
from living_adr.core.repository import RepositoryIdentity

Clock = Callable[[], datetime]
IdProvider = Callable[[], str]


def _default_clock() -> datetime:
    return datetime.now(UTC)


def _default_id() -> str:
    return str(uuid.uuid4())


def _expiry_for(
    decision: ApprovedReviewDecision,
    ttl: timedelta,
    minted_record: MintedDecisionRecord | None,
) -> datetime:
    if minted_record is not None:
        return minted_record.expires_at()
    return decision.minted_at + ttl


def validate_decision(
    decision: ApprovedReviewDecision | None,
    *,
    repository: RepositoryIdentity,
    expected_fingerprint: str,
    current_content: str | None = None,
    clock: Clock = _default_clock,
    ttl: timedelta = DEFAULT_DECISION_TTL,
    minted_record: MintedDecisionRecord | None = None,
) -> ApprovedReviewDecision:
    """Validate a capability for one mutation target; raise on any failure."""

    if decision is None or not decision.approved:
        raise DecisionNotApprovedError(
            "an approved review decision is required to mutate"
        )
    if decision.repository != repository:
        raise DecisionRepositoryMismatchError(
            "approved decision is scoped to a different repository"
        )
    if clock() > _expiry_for(decision, ttl, minted_record):
        raise DecisionExpiredError(
            "approval capability has expired; a fresh review is required"
        )
    if current_content is not None:
        if canonical_adr_hash(current_content) != decision.adr_draft_content_hash:
            raise DraftContentMismatchError(
                "content changed since approval; a fresh review is required"
            )
    if decision.target_fingerprint != expected_fingerprint:
        raise TargetMutationMismatchError(
            "approved decision does not authorise this mutation target"
        )
    return decision


def validate_for_mutation(
    decision: ApprovedReviewDecision | None,
    *,
    repository: RepositoryIdentity,
    expected_fingerprint: str,
    audit: ApprovalAuditRepository,
    current_content: str | None = None,
    clock: Clock = _default_clock,
    ttl: timedelta = DEFAULT_DECISION_TTL,
    minted_record: MintedDecisionRecord | None = None,
    id_provider: IdProvider = _default_id,
) -> ApprovedReviewDecision:
    """Validate and, on failure, append a metadata-only ``VALIDATION_FAILED`` audit."""

    try:
        return validate_decision(
            decision,
            repository=repository,
            expected_fingerprint=expected_fingerprint,
            current_content=current_content,
            clock=clock,
            ttl=ttl,
            minted_record=minted_record,
        )
    except ApprovalError as exc:
        decision_id = decision.decision_id if decision is not None else None
        reviewer_id = decision.reviewer_id if decision is not None else None
        audit.record_audit_event(
            _validation_failed_event(
                audit_id=id_provider(),
                repository_key=repository.key,
                recorded_at=clock(),
                decision_id=decision_id,
                reviewer_id=reviewer_id,
                target_fingerprint=expected_fingerprint,
                failure_kind=type(exc).__name__,
            )
        )
        raise


def _validation_failed_event(
    *,
    audit_id: str,
    repository_key: str,
    recorded_at: datetime,
    decision_id: str | None,
    reviewer_id: str | None,
    target_fingerprint: str,
    failure_kind: str,
):
    from living_adr.approval.models import AuditEvent

    return AuditEvent(
        audit_id=audit_id,
        event_type=AuditEventType.VALIDATION_FAILED,
        repository_key=repository_key,
        recorded_at=recorded_at,
        decision_id=decision_id,
        reviewer_id=reviewer_id,
        target_fingerprint=target_fingerprint,
        failure_kind=failure_kind,
        detail=failure_kind,
    )


__all__ = [
    "validate_decision",
    "validate_for_mutation",
]
