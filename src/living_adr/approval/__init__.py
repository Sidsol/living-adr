"""Feature 010 approval capability and audit durability package.

Public surface for durable approval authority:

* Models: :class:`ApprovalEvent`, :class:`MintedDecisionRecord`,
  :class:`ConsumptionRecord`, :class:`AuditEvent`, plus the reused feature 006
  :class:`ApprovedReviewDecision` capability and its boundary errors.
* Repository: :class:`ApprovalAuditRepository` (protocol) with in-memory and
  SQLite implementations.
* Minting: :func:`record_review_outcome`, :func:`mint_approved_decision`.

Higher slices add validation, the durable mutation boundary, audit queries, and
the workflow seam; they are imported lazily by callers to keep this package's
import graph free of workflow/graph cycles.
"""

from __future__ import annotations

from living_adr.approval.audit_queries import (
    DecisionAuditTrail,
    DecisionMutationLink,
    audit_timeline,
    build_decision_audit_trail,
    decision_mutation_links,
)
from living_adr.approval.hashing import (
    canonical_adr_hash,
    canonicalize_adr_content,
    content_matches_hash,
)
from living_adr.approval.minting import (
    MintResult,
    ReviewContext,
    mint_approved_decision,
    record_review_outcome,
)
from living_adr.approval.models import (
    DEFAULT_DECISION_TTL,
    ApprovalError,
    ApprovalEvent,
    ApprovalRequiredError,
    ApprovedReviewDecision,
    AuditDurabilityError,
    AuditEvent,
    AuditEventType,
    ConsumptionRecord,
    DecisionAlreadyConsumedError,
    DecisionExpiredError,
    DecisionNotApprovedError,
    DecisionRepositoryMismatchError,
    DraftContentMismatchError,
    MintedDecisionRecord,
    MutationFingerprintMismatchError,
    TargetMutationMismatchError,
)
from living_adr.approval.mutation_service import (
    AuthorizedMutationResult,
    DurableApprovalBoundMutationService,
)
from living_adr.approval.repository import (
    ApprovalAuditRepository,
    InMemoryApprovalAuditRepository,
    SqliteApprovalAuditRepository,
)
from living_adr.approval.validation import validate_decision, validate_for_mutation

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
    "AuditEvent",
    "AuditEventType",
    "ApprovalAuditRepository",
    "InMemoryApprovalAuditRepository",
    "SqliteApprovalAuditRepository",
    "ReviewContext",
    "MintResult",
    "record_review_outcome",
    "mint_approved_decision",
    "canonical_adr_hash",
    "canonicalize_adr_content",
    "content_matches_hash",
    "validate_decision",
    "validate_for_mutation",
    "DurableApprovalBoundMutationService",
    "AuthorizedMutationResult",
    "DecisionAuditTrail",
    "DecisionMutationLink",
    "build_decision_audit_trail",
    "decision_mutation_links",
    "audit_timeline",
]
