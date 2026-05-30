"""Approval/audit domain models for feature 010 (durable approval capability).

This module defines the *durable* records that feature 010 owns and that are
intentionally distinct from feature 015's LangGraph checkpoint state:

* :class:`ApprovalEvent` — an immutable record of one reviewer outcome
  (approve / approve-after-edit / reject / defer). Non-approving outcomes are
  still recorded but mint no capability.
* :class:`MintedDecisionRecord` — durable metadata for a minted
  :class:`~living_adr.core.approval.ApprovedReviewDecision` (capability), so TTL
  and content binding survive process restarts.
* :class:`ConsumptionRecord` — the one-shot consumption fact keyed by
  ``decision_id`` (a capability may be consumed exactly once).
* :class:`AuditEvent` — the append-only SM-05 audit taxonomy linking review,
  minting, validation failure, consumption, mutation, and downstream
  publication by ``decision_id``.

The capability object itself (:class:`ApprovedReviewDecision`) is **reused
byte-compatibly** from :mod:`living_adr.core.approval` (feature 006) — feature
010 mints and persists it but never redefines its shape or weakens its
validation. The new typed errors here extend feature 006's
:class:`~living_adr.core.approval.ApprovalError` hierarchy.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator

# Re-export the feature 006 capability + boundary errors so downstream callers
# can depend on a single ``living_adr.approval`` surface without reaching past
# it into core. These are reused verbatim (do not redefine).
from living_adr.core.approval import (
    ApprovalError,
    ApprovalRequiredError,
    ApprovedReviewDecision,
    DecisionAlreadyConsumedError,
    DecisionRepositoryMismatchError,
    DraftContentMismatchError,
    MutationFingerprintMismatchError,
)
from living_adr.core.models import RepositoryIdentity
from living_adr.workflow.state import ReviewAction

#: PoC default capability lifetime (architecture #service-boundaries; FR-6).
DEFAULT_DECISION_TTL: timedelta = timedelta(minutes=10)


class DecisionExpiredError(ApprovalError):
    """Raised when a capability is validated after its TTL has elapsed (US-3)."""


class DecisionNotApprovedError(ApprovalRequiredError):
    """Raised when an outcome that does not authorise mutation is used (US-2)."""


class TargetMutationMismatchError(MutationFingerprintMismatchError):
    """Spec-named alias: the decision does not authorise this mutation target."""


class AuditDurabilityError(ApprovalError):
    """Raised when audit persistence fails; mutation must fail closed (NFR-1)."""


def _stripped_nonempty(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        raise ValueError("must not be empty or whitespace")
    return stripped


class ApprovalEvent(BaseModel):
    """Immutable record of one reviewer decision outcome (FR-2).

    Recorded for *every* outcome. ``authorizing`` is ``True`` only for approve /
    approve-after-edit; ``decision_id`` is populated only once feature 010 mints
    a capability for an authorising outcome.
    """

    model_config = ConfigDict(frozen=True)

    review_event_id: str
    repository: RepositoryIdentity
    reviewer_id: str
    action: ReviewAction
    workflow_thread_id: str
    normalized_event_key: str
    adr_draft_id: str
    adr_draft_content_hash: str
    structural_change_event_id: str | None = None
    adr_record_id: str | None = None
    decision_version: int = 1
    recorded_at: datetime
    decision_id: str | None = None
    reason: str | None = None
    authorizing: bool = False

    @field_validator(
        "review_event_id",
        "reviewer_id",
        "adr_draft_id",
        "adr_draft_content_hash",
        "workflow_thread_id",
    )
    @classmethod
    def _non_empty(cls, value: str) -> str:
        return _stripped_nonempty(value)

    @property
    def authorizes_mutation(self) -> bool:
        return self.action.authorizes_mutation


class MintedDecisionRecord(BaseModel):
    """Durable metadata for a minted capability (TTL + binding survive restart)."""

    model_config = ConfigDict(frozen=True)

    decision_id: str
    review_event_id: str
    repository_key: str
    reviewer_id: str
    adr_draft_id: str
    adr_record_id: str
    adr_draft_content_hash: str
    target_fingerprint: str | None = None
    decision_version: int = 1
    minted_at: datetime
    ttl_seconds: int

    @property
    def ttl(self) -> timedelta:
        return timedelta(seconds=self.ttl_seconds)

    def expires_at(self) -> datetime:
        return self.minted_at + self.ttl


class ConsumptionRecord(BaseModel):
    """One-shot consumption fact keyed by ``decision_id`` (FR-7/FR-8)."""

    model_config = ConfigDict(frozen=True)

    decision_id: str
    target_fingerprint: str
    repository_key: str
    outcome: str
    node_id: str | None = None
    detail: str = ""
    consumed_at: datetime

    @field_validator("decision_id", "target_fingerprint")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        return _stripped_nonempty(value)


class AuditEventType(StrEnum):
    """SM-05 audit taxonomy (FR-10)."""

    REVIEW_RECORDED = "review_recorded"
    CAPABILITY_MINTED = "capability_minted"
    VALIDATION_FAILED = "validation_failed"
    CONSUMPTION_RECORDED = "consumption_recorded"
    MUTATION_PERFORMED = "mutation_performed"
    PUBLICATION_LINKED = "publication_linked"


class AuditEvent(BaseModel):
    """Append-only, metadata-only audit entry joined by ``decision_id`` (FR-10).

    Carries identifiers, keys, and short typed details only — never raw drafts,
    reviewer comments, prompts, or diffs (NFR-6; architecture #cross-cutting).
    """

    model_config = ConfigDict(frozen=True)

    audit_id: str
    event_type: AuditEventType
    repository_key: str
    recorded_at: datetime
    decision_id: str | None = None
    review_event_id: str | None = None
    reviewer_id: str | None = None
    target_fingerprint: str | None = None
    failure_kind: str | None = None
    detail: str = ""

    @field_validator("audit_id")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        return _stripped_nonempty(value)


__all__ = [
    "DEFAULT_DECISION_TTL",
    "ApprovedReviewDecision",
    "ApprovalError",
    "ApprovalRequiredError",
    "DecisionRepositoryMismatchError",
    "DraftContentMismatchError",
    "MutationFingerprintMismatchError",
    "DecisionAlreadyConsumedError",
    "DecisionExpiredError",
    "DecisionNotApprovedError",
    "TargetMutationMismatchError",
    "AuditDurabilityError",
    "ApprovalEvent",
    "MintedDecisionRecord",
    "ConsumptionRecord",
    "AuditEventType",
    "AuditEvent",
]
