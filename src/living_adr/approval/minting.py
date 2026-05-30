"""Review-outcome recording and capability minting (feature 010).

This module is the bridge from feature 009's reviewer intent (carried in a
feature 015 :class:`~living_adr.workflow.state.ReviewResumeCommand`) to feature
010's durable approval facts:

* :func:`record_review_outcome` persists an immutable :class:`ApprovalEvent` for
  **every** outcome (approve / approve-after-edit / reject / defer). Reject and
  defer mint no capability.
* :func:`mint_approved_decision` records the review event *and* mints a one-shot
  :class:`~living_adr.core.approval.ApprovedReviewDecision` capability for
  authorising outcomes only, binding it to the exact reviewed content hash and a
  target mutation fingerprint.

The capability is the feature 006 type, reused byte-compatibly. Observability is
metadata-only (NFR-6): only identifiers, keys, and outcome enums are emitted —
never raw drafts, reviewer comments, or diffs.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from living_adr.approval.models import (
    DEFAULT_DECISION_TTL,
    ApprovalEvent,
    ApprovedReviewDecision,
    AuditDurabilityError,
    AuditEvent,
    AuditEventType,
    DecisionNotApprovedError,
    MintedDecisionRecord,
)
from living_adr.approval.repository import ApprovalAuditRepository
from living_adr.core.models import RepositoryIdentity
from living_adr.core.observability import NoOpObservability, Observability
from living_adr.workflow.state import ReviewAction, ReviewResumeCommand

Clock = Callable[[], datetime]
IdProvider = Callable[[], str]


def _default_clock() -> datetime:
    return datetime.now(UTC)


def _default_id() -> str:
    return str(uuid.uuid4())


@dataclass(frozen=True)
class ReviewContext:
    """The durable, metadata-only review context a resume command is recorded in.

    Sourced from the feature 015 :class:`ReviewRequestPayload` plus the workflow
    thread id. Holds references and hashes only — never raw draft bodies.
    """

    repository: RepositoryIdentity
    workflow_thread_id: str
    normalized_event_key: str
    adr_draft_id: str
    adr_draft_content_hash: str
    structural_change_event_id: str | None = None
    adr_record_id: str = "adr-pending"
    decision_version: int = 1


@dataclass(frozen=True)
class MintResult:
    """Outcome of :func:`mint_approved_decision`."""

    event: ApprovalEvent
    decision: ApprovedReviewDecision | None
    minted_record: MintedDecisionRecord | None


def _reviewed_content_hash(
    command: ReviewResumeCommand, context: ReviewContext
) -> str:
    """The exact content hash the reviewer approved (edited hash wins)."""

    if (
        command.action is ReviewAction.APPROVE_AFTER_EDIT
        and command.edited_content_hash
    ):
        return command.edited_content_hash
    return context.adr_draft_content_hash


def _emit(obs: Observability, name: str, metadata: dict[str, object]) -> None:
    obs.record_event(name, metadata)


def _record_audit(
    audit: ApprovalAuditRepository,
    *,
    event_type: AuditEventType,
    repository_key: str,
    recorded_at: datetime,
    id_provider: IdProvider,
    decision_id: str | None = None,
    review_event_id: str | None = None,
    reviewer_id: str | None = None,
    target_fingerprint: str | None = None,
    failure_kind: str | None = None,
    detail: str = "",
) -> AuditEvent:
    """Append one audit row, failing closed on durability errors (NFR-1)."""

    event = AuditEvent(
        audit_id=id_provider(),
        event_type=event_type,
        repository_key=repository_key,
        recorded_at=recorded_at,
        decision_id=decision_id,
        review_event_id=review_event_id,
        reviewer_id=reviewer_id,
        target_fingerprint=target_fingerprint,
        failure_kind=failure_kind,
        detail=detail,
    )
    try:
        return audit.record_audit_event(event)
    except Exception as exc:  # noqa: BLE001 - fail closed on any audit failure
        raise AuditDurabilityError(
            "audit persistence failed; no approval recorded"
        ) from exc


def record_review_outcome(
    repository: RepositoryIdentity,
    command: ReviewResumeCommand,
    context: ReviewContext,
    *,
    audit: ApprovalAuditRepository,
    clock: Clock = _default_clock,
    id_provider: IdProvider = _default_id,
    observability: Observability | None = None,
    reason: str | None = None,
) -> ApprovalEvent:
    """Persist an immutable :class:`ApprovalEvent` for any reviewer outcome.

    No capability is minted here; reject/defer never authorise mutation and even
    approve/approve-after-edit only mint via :func:`mint_approved_decision`.
    """

    obs = observability or NoOpObservability()
    recorded_at = clock()
    event = ApprovalEvent(
        review_event_id=id_provider(),
        repository=repository,
        reviewer_id=command.reviewer_id,
        action=command.action,
        workflow_thread_id=context.workflow_thread_id,
        normalized_event_key=context.normalized_event_key,
        adr_draft_id=context.adr_draft_id,
        adr_draft_content_hash=_reviewed_content_hash(command, context),
        structural_change_event_id=context.structural_change_event_id,
        adr_record_id=context.adr_record_id,
        decision_version=context.decision_version,
        recorded_at=recorded_at,
        reason=reason,
        authorizing=command.action.authorizes_mutation,
    )
    try:
        audit.record_review_event(event)
    except ValueError:
        raise
    except Exception as exc:  # noqa: BLE001 - fail closed on durability errors
        raise AuditDurabilityError(
            "review event persistence failed; no approval recorded"
        ) from exc

    _emit(
        obs,
        "approval.review_recorded",
        {
            "repository": repository.key,
            "review_event_id": event.review_event_id,
            "action": event.action.value,
            "authorizing": event.authorizing,
        },
    )
    return event


def mint_approved_decision(
    repository: RepositoryIdentity,
    command: ReviewResumeCommand,
    context: ReviewContext,
    *,
    target_fingerprint: str | None = None,
    audit: ApprovalAuditRepository,
    ttl: timedelta = DEFAULT_DECISION_TTL,
    clock: Clock = _default_clock,
    id_provider: IdProvider = _default_id,
    observability: Observability | None = None,
    reason: str | None = None,
) -> MintResult:
    """Record the review event and mint a capability for authorising outcomes.

    For reject/defer, the review event is still recorded but ``decision`` and
    ``minted_record`` are ``None`` — there is no capability in the resume state.
    """

    obs = observability or NoOpObservability()
    minted_at = clock()
    reviewed_hash = _reviewed_content_hash(command, context)

    # Record the immutable review event first (decision_id filled below for
    # authorising outcomes so the event references the capability it minted).
    if not command.action.authorizes_mutation:
        event = record_review_outcome(
            repository,
            command,
            context,
            audit=audit,
            clock=lambda: minted_at,
            id_provider=id_provider,
            observability=obs,
            reason=reason,
        )
        return MintResult(event=event, decision=None, minted_record=None)

    review_event_id = id_provider()
    decision_id = id_provider()
    event = ApprovalEvent(
        review_event_id=review_event_id,
        repository=repository,
        reviewer_id=command.reviewer_id,
        action=command.action,
        workflow_thread_id=context.workflow_thread_id,
        normalized_event_key=context.normalized_event_key,
        adr_draft_id=context.adr_draft_id,
        adr_draft_content_hash=reviewed_hash,
        structural_change_event_id=context.structural_change_event_id,
        adr_record_id=context.adr_record_id,
        decision_version=context.decision_version,
        recorded_at=minted_at,
        reason=reason,
        decision_id=decision_id,
        authorizing=True,
    )
    try:
        audit.record_review_event(event)
    except Exception as exc:  # noqa: BLE001 - fail closed
        raise AuditDurabilityError(
            "review event persistence failed; no capability minted"
        ) from exc

    decision = ApprovedReviewDecision(
        repository=repository,
        decision_id=decision_id,
        reviewer_id=command.reviewer_id,
        adr_draft_id=context.adr_draft_id,
        adr_draft_content_hash=reviewed_hash,
        structural_change_event_id=context.structural_change_event_id,
        target_fingerprint=target_fingerprint or _pending_fingerprint(decision_id),
        decision_version=context.decision_version,
        minted_at=minted_at,
        approved=True,
    )
    minted_record = MintedDecisionRecord(
        decision_id=decision_id,
        review_event_id=review_event_id,
        repository_key=repository.key,
        reviewer_id=command.reviewer_id,
        adr_draft_id=context.adr_draft_id,
        adr_record_id=context.adr_record_id,
        adr_draft_content_hash=reviewed_hash,
        target_fingerprint=decision.target_fingerprint,
        decision_version=context.decision_version,
        minted_at=minted_at,
        ttl_seconds=int(ttl.total_seconds()),
    )
    try:
        audit.record_minted_decision(minted_record)
    except Exception as exc:  # noqa: BLE001 - fail closed
        raise AuditDurabilityError(
            "minted decision persistence failed; capability not durable"
        ) from exc

    _record_audit(
        audit,
        event_type=AuditEventType.CAPABILITY_MINTED,
        repository_key=repository.key,
        recorded_at=minted_at,
        id_provider=id_provider,
        decision_id=decision_id,
        review_event_id=review_event_id,
        reviewer_id=command.reviewer_id,
        target_fingerprint=decision.target_fingerprint,
        detail=command.action.value,
    )
    _emit(
        obs,
        "approval.capability_minted",
        {
            "repository": repository.key,
            "decision_id": decision_id,
            "decision_version": context.decision_version,
            "action": command.action.value,
        },
    )
    return MintResult(event=event, decision=decision, minted_record=minted_record)


def _pending_fingerprint(decision_id: str) -> str:
    """A non-empty placeholder fingerprint when no target is supplied at mint.

    The real authorised target is pinned by the caller (workflow approval node)
    via ``target_fingerprint``; this keeps the capability valid (non-empty) while
    making an unbound decision unusable against any concrete mutation target.
    """

    return f"unbound:{decision_id}"


def require_authorizing(command: ReviewResumeCommand) -> None:
    """Guard helper: raise if an outcome is asked to mint but cannot authorise."""

    if not command.action.authorizes_mutation:
        raise DecisionNotApprovedError(
            f"action {command.action.value!r} cannot mint an approval capability"
        )


__all__ = [
    "ReviewContext",
    "MintResult",
    "record_review_outcome",
    "mint_approved_decision",
    "require_authorizing",
]
