"""Draft outcome and mutation authorization observability (feature 013, slice 4).

Maps HITL review decisions (SM-01) and approval-bound graph mutation checks
(SM-05) to safe, identifier-only observability events through feature 002's
``Observability`` port. Emitted metadata is strictly allow-listed: repository
key, opaque ids, change class, outcome/reason enums, reviewer role, latency, and
status. ADR body text, reviewer comments, and raw draft content are never
included (``architecture.md#anti-patterns``; default-deny raw export).

These helpers are call-site ready for HITL review and
:class:`ApprovalBoundMutationService`. :func:`failure_reason_for` translates the
feature 006 approval errors into stable reason codes so audit anomalies are
visible without coupling observability to control flow.
"""

from __future__ import annotations

from enum import StrEnum

from living_adr.core.approval import (
    ApprovalRequiredError,
    DecisionAlreadyConsumedError,
    DecisionRepositoryMismatchError,
    DraftContentMismatchError,
    MutationFingerprintMismatchError,
)
from living_adr.core.observability import Observability


class DecisionEvent(StrEnum):
    """Stable event/counter names for decision + mutation observability."""

    DRAFT_OUTCOME = "draft.outcome"
    MUTATION_UNAUTHORIZED = "graph.mutation.unauthorized"
    MUTATION_AUTHORIZED = "graph.mutation.authorized"


class DraftOutcome(StrEnum):
    """HITL draft decision outcomes (SM-01)."""

    APPROVED = "approved"
    APPROVED_AFTER_EDIT = "approved_after_edit"
    REJECTED = "rejected"
    DEFERRED = "deferred"


class MutationAuthFailure(StrEnum):
    """Reason codes for an unauthorized graph mutation attempt (SM-05)."""

    MISSING_OR_UNAPPROVED = "missing_or_unapproved"
    EXPIRED = "expired"
    REUSED = "reused"
    FINGERPRINT_MISMATCH = "fingerprint_mismatch"
    REPOSITORY_MISMATCH = "repository_mismatch"
    CONTENT_DRIFT = "content_drift"
    REJECTED = "rejected"


# Map feature 006 approval errors to stable reason codes. Subclass-aware lookups
# happen in :func:`failure_reason_for`.
_ERROR_REASONS: tuple[tuple[type[Exception], MutationAuthFailure], ...] = (
    (DecisionAlreadyConsumedError, MutationAuthFailure.REUSED),
    (DecisionRepositoryMismatchError, MutationAuthFailure.REPOSITORY_MISMATCH),
    (DraftContentMismatchError, MutationAuthFailure.CONTENT_DRIFT),
    (MutationFingerprintMismatchError, MutationAuthFailure.FINGERPRINT_MISMATCH),
    (ApprovalRequiredError, MutationAuthFailure.MISSING_OR_UNAPPROVED),
)


def failure_reason_for(error: Exception) -> MutationAuthFailure:
    """Translate an approval-boundary error into a stable reason code."""

    for error_type, reason in _ERROR_REASONS:
        if isinstance(error, error_type):
            return reason
    # Unknown approval failures default to the most conservative reason.
    return MutationAuthFailure.MISSING_OR_UNAPPROVED


def record_draft_outcome(
    obs: Observability,
    *,
    repository_key: str,
    draft_id: str,
    change_class: str,
    outcome: DraftOutcome,
    reviewer_role: str,
    run_id: str | None = None,
) -> None:
    """Emit a draft-outcome counter (SM-01). Identifiers and enums only."""

    meta: dict[str, object] = {
        "repository": repository_key,
        "draft_id": draft_id,
        "change_class": change_class,
        "outcome": str(outcome),
        "reviewer_role": reviewer_role,
    }
    if run_id is not None:
        meta["run_id"] = run_id
    obs.increment_counter(DecisionEvent.DRAFT_OUTCOME, 1, meta)


def record_unauthorized_mutation(
    obs: Observability,
    *,
    repository_key: str,
    mutation_type: str,
    reason: MutationAuthFailure,
    decision_id: str | None = None,
    run_id: str | None = None,
) -> None:
    """Emit an unauthorized-mutation event with a reason code (SM-05)."""

    meta: dict[str, object] = {
        "repository": repository_key,
        "mutation_type": mutation_type,
        "reason": str(reason),
    }
    if decision_id is not None:
        meta["decision_id"] = decision_id
    if run_id is not None:
        meta["run_id"] = run_id
    obs.record_event(DecisionEvent.MUTATION_UNAUTHORIZED, meta)


def record_authorized_mutation(
    obs: Observability,
    *,
    repository_key: str,
    decision_id: str,
    mutation_type: str,
    latency_ms: int,
    status: str = "success",
    run_id: str | None = None,
) -> None:
    """Emit a successful approved-mutation event (SM-05). No ADR body text."""

    meta: dict[str, object] = {
        "repository": repository_key,
        "decision_id": decision_id,
        "mutation_type": mutation_type,
        "latency_ms": int(latency_ms),
        "status": status,
    }
    if run_id is not None:
        meta["run_id"] = run_id
    obs.record_event(DecisionEvent.MUTATION_AUTHORIZED, meta)


__all__ = [
    "DecisionEvent",
    "DraftOutcome",
    "MutationAuthFailure",
    "failure_reason_for",
    "record_draft_outcome",
    "record_unauthorized_mutation",
    "record_authorized_mutation",
]
