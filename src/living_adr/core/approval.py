"""Approved-review capability contract and approval-boundary errors (feature 006).

``ApprovedReviewDecision`` is the capability object that authorizes authoritative
graph mutation. This module defines its *shape* and the specific errors the
approval boundary raises. It deliberately stops short of durable minting,
one-shot persistence, TTL storage, and audit durability — those belong to
feature 010. Here we define enough for ``ApprovalBoundMutationService`` to
validate a decision and reject invalid mutations before any adapter call
(architecture #service-boundaries; SM-05; FM-13).

The capability binds, at minimum: the repository scope, the reviewer, the exact
reviewed draft (via SHA-256 ``adr_draft_content_hash``), the structural-change
event, and a ``target_fingerprint`` that pins the decision to one specific
mutation target for idempotent-retry checks.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator

from living_adr.core.repository import RepositoryIdentity


class ApprovedReviewDecision(BaseModel):
    """Capability minted only by an approved review; required to mutate the graph.

    A decision with ``approved=False`` (or ``None`` in a mutation request) can
    never authorize a write. ``target_fingerprint`` binds the capability to a
    single mutation target so a decision for one mutation cannot be replayed
    against another (architecture ``ApprovedReviewDecision`` semantics).
    """

    model_config = ConfigDict(frozen=True)

    repository: RepositoryIdentity
    decision_id: str
    reviewer_id: str
    adr_draft_id: str
    adr_draft_content_hash: str
    structural_change_event_id: str | None = None
    target_fingerprint: str
    decision_version: int = 1
    minted_at: datetime
    consumed_at: datetime | None = None
    approved: bool = True

    @field_validator(
        "decision_id", "reviewer_id", "adr_draft_content_hash", "target_fingerprint"
    )
    @classmethod
    def _non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty or whitespace")
        return stripped


class ApprovalError(Exception):
    """Base class for all approval-boundary rejections (audit-friendly names)."""


class ApprovalRequiredError(ApprovalError):
    """Raised when a mutation is attempted with no/unapproved decision."""


class DecisionRepositoryMismatchError(ApprovalError):
    """Raised when a decision is scoped to a different repository than the mutation."""


class DraftContentMismatchError(ApprovalError):
    """Raised when current draft/record content differs from the approved hash."""


class MutationFingerprintMismatchError(ApprovalError):
    """Raised when a decision's target fingerprint does not match the mutation."""


class DecisionAlreadyConsumedError(ApprovalError):
    """Raised when a one-shot decision id is re-submitted for a new mutation."""


__all__ = [
    "ApprovedReviewDecision",
    "ApprovalError",
    "ApprovalRequiredError",
    "DecisionRepositoryMismatchError",
    "DraftContentMismatchError",
    "MutationFingerprintMismatchError",
    "DecisionAlreadyConsumedError",
]
