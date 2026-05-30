"""Typed workflow state and HITL/replay payloads (feature 015, slice 1).

This module defines the durable orchestration state model carried through the
LangGraph workflow assembled in :mod:`living_adr.workflow.graph`, plus the typed
review/replay payloads that features 008, 009, and 010 plug into.

Source-of-truth + safety discipline (architecture #data-model, #cross-cutting)
-----------------------------------------------------------------------------
* The state carries **references, hashes, and summaries** — never raw GitHub
  payloads or raw diff text. ``WorkflowState`` is ``extra="forbid"`` so an
  arbitrary ``raw_github_payload=...`` field cannot be smuggled into graph state
  (NFR-3/NFR-4; FM-21). Provider-specific data stays behind the feature 003
  ``SCMProvider`` / opaque evidence handles.
* Untrusted SCM data and model output remain **inert** workflow state until a
  human approves at the HITL gate and the approval-bound mutation boundary
  validates the capability (NFR-3).

The state holds the canonical feature-001 :class:`SCMEvent` (which itself carries
only a ``diff_summary``, not raw diff text); richer normalization context is
referenced by ``normalized_event_key`` rather than copied in.
"""

from __future__ import annotations

import hashlib
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator

from living_adr.core.approval import ApprovedReviewDecision
from living_adr.core.models import RepositoryIdentity, SCMEvent, StructuralChange


class WorkflowStatus(StrEnum):
    """Lifecycle status of one workflow thread.

    These statuses are durable, metadata-safe enums (suitable for observability)
    and drive deterministic routing in the assembled graph.
    """

    INTAKE = "intake"
    CLASSIFYING = "classifying"
    NO_ADR_NEEDED = "no_adr_needed"
    DRAFTING = "drafting"
    AWAITING_REVIEW = "awaiting_review"
    RESUMING = "resuming"
    MUTATING = "mutating"
    COMPLETED = "completed"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    FAILED = "failed"


class ReviewAction(StrEnum):
    """Allowed reviewer actions at the HITL gate (feature 009/010 supply these)."""

    APPROVE = "approve"
    APPROVE_AFTER_EDIT = "approve_after_edit"
    REJECT = "reject"
    DEFER = "defer"

    @property
    def authorizes_mutation(self) -> bool:
        """True only for actions that may route to the mutation handoff."""

        return self in (ReviewAction.APPROVE, ReviewAction.APPROVE_AFTER_EDIT)


class ClassificationResult(BaseModel):
    """Output of the classifier seam (feature 008 supplies the real classifier).

    Carries zero or more :class:`StructuralChange` values plus confidence and
    evidence ids, or ``adr_needed=False`` with an explicit ``no_adr_reason``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    adr_needed: bool
    changes: tuple[StructuralChange, ...] = ()
    confidence: float = 0.0
    evidence_ids: tuple[str, ...] = ()
    no_adr_reason: str | None = None


class DraftRef(BaseModel):
    """Reference to a provisional ADR draft (feature 008 supplies the real draft).

    Holds the draft id, the SHA-256 ``content_hash`` of the exact rendered draft,
    a short ``preview`` for HITL display, evidence citation ids, and the
    ``provisional`` flag. The draft is **never authoritative** until approved.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    draft_id: str
    content_hash: str
    preview: str
    citation_ids: tuple[str, ...] = ()
    structural_change_id: str | None = None
    provisional: bool = True

    @field_validator("draft_id", "content_hash")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty or whitespace")
        return stripped


class ReviewRequestPayload(BaseModel):
    """Typed HITL interrupt payload rendered by feature 009.

    Contains only metadata-safe review context: repository scope, normalized
    event key, draft id/hash, a bounded preview, evidence ids, confidence, and
    the allowed reviewer actions. No secrets and no raw provider payloads.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    repository: RepositoryIdentity
    normalized_event_key: str
    draft_id: str
    draft_content_hash: str
    draft_preview: str
    evidence_ids: tuple[str, ...] = ()
    confidence: float = 0.0
    allowed_actions: tuple[ReviewAction, ...] = (
        ReviewAction.APPROVE,
        ReviewAction.APPROVE_AFTER_EDIT,
        ReviewAction.REJECT,
        ReviewAction.DEFER,
    )


class ReviewResumeCommand(BaseModel):
    """Typed resume command submitted by feature 009 / minted by feature 010.

    ``approved_decision`` is the feature-006 capability minted by feature 010;
    when present (and the action authorizes mutation) the mutation handoff may
    call the approval-bound mutation service. Reject/defer never carry a usable
    capability. The seam is versioned (``command_version``) so features 009/010
    can extend it backwards-compatibly.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    action: ReviewAction
    reviewer_id: str
    edited_content: str | None = None
    edited_content_hash: str | None = None
    approved_decision: ApprovedReviewDecision | None = None
    command_version: int = 1

    @field_validator("reviewer_id")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty or whitespace")
        return stripped


class WorkflowReplayMetadata(BaseModel):
    """Replay/idempotency metadata bridging feature 003 ingestion into the graph.

    ``thread_id`` is the deterministic graph thread derived from repository
    identity + normalized event key. ``source_delivery_id`` links back to the
    feature-003 stored delivery for FM-01/FM-17 recovery. ``replay_count`` and
    ``is_replay`` make duplicate replays observable without duplicating side
    effects (NFR-2).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    normalized_event_key: str
    thread_id: str
    source_delivery_id: str | None = None
    replay_count: int = 0
    is_replay: bool = False


class MutationOutcome(StrEnum):
    """Terminal outcome of the mutation handoff node."""

    MUTATED = "mutated"
    NO_MUTATION = "no_mutation"
    REJECTED = "rejected"
    DEFERRED = "deferred"
    BLOCKED = "blocked"


class MutationResult(BaseModel):
    """Result of the mutation handoff (metadata-safe; no raw content)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    outcome: MutationOutcome
    detail: str = ""
    node_id: str | None = None
    decision_id: str | None = None
    service_called: bool = False


class WorkflowError(BaseModel):
    """Structured, metadata-safe error captured for replay/recovery triage."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    node: str
    category: str
    detail: str


class WorkflowState(BaseModel):
    """Durable in-flight workflow state — the LangGraph state schema.

    Every field defaults so LangGraph can construct/merge partial node updates.
    ``extra="forbid"`` enforces the raw-payload-exclusion contract: only the
    declared reference/hash/summary fields may exist on graph state, so raw
    GitHub JSON or raw diff text cannot enter the orchestration path.
    """

    model_config = ConfigDict(extra="forbid")

    repository: RepositoryIdentity | None = None
    event: SCMEvent | None = None
    normalized_event_key: str | None = None
    evidence_refs: tuple[str, ...] = ()
    classification: ClassificationResult | None = None
    draft: DraftRef | None = None
    review_request: ReviewRequestPayload | None = None
    resume_command: ReviewResumeCommand | None = None
    approved_decision: ApprovedReviewDecision | None = None
    mutation_result: MutationResult | None = None
    error: WorkflowError | None = None
    replay: WorkflowReplayMetadata | None = None
    status: WorkflowStatus = WorkflowStatus.INTAKE

    @classmethod
    def for_event(
        cls,
        event: SCMEvent,
        *,
        normalized_event_key: str | None = None,
        evidence_refs: tuple[str, ...] = (),
        replay: WorkflowReplayMetadata | None = None,
    ) -> WorkflowState:
        """Build initial intake state from a normalized event (references only).

        Requires a concrete ``SCMEvent`` with a repository scope. The normalized
        event key defaults to the provider-neutral derivation when not supplied
        by feature 003's envelope.
        """

        key = normalized_event_key or default_event_key(event)
        return cls(
            repository=event.repository,
            event=event,
            normalized_event_key=key,
            evidence_refs=evidence_refs,
            replay=replay,
            status=WorkflowStatus.INTAKE,
        )


def default_event_key(event: SCMEvent) -> str:
    """Provider-neutral normalized event key derived from a canonical event.

    Mirrors feature 003's normalized PR key shape closely enough for
    deterministic thread derivation when no richer envelope key is supplied:
    ``<provider>:<repo key>:<pr number>:<delivery id>``. Never uses the PR number
    alone (architecture #anti-patterns).
    """

    return (
        f"{event.provider}:{event.repository.key}:"
        f"{event.pr_number}:{event.delivery_id}"
    )


def derive_thread_id(
    repository: RepositoryIdentity, normalized_event_key: str
) -> str:
    """Deterministic LangGraph ``thread_id`` for a repository + event key.

    Replaying the same repository/event always derives the same thread id, so a
    duplicate replay resumes the existing checkpoint instead of starting a new,
    side-effect-duplicating run (NFR-2; US-4).
    """

    digest = hashlib.sha256(
        f"{repository.key}|{normalized_event_key}".encode()
    ).hexdigest()
    return f"wf-{digest[:32]}"


__all__ = [
    "WorkflowStatus",
    "ReviewAction",
    "ClassificationResult",
    "DraftRef",
    "ReviewRequestPayload",
    "ReviewResumeCommand",
    "WorkflowReplayMetadata",
    "MutationOutcome",
    "MutationResult",
    "WorkflowError",
    "WorkflowState",
    "default_event_key",
    "derive_thread_id",
]
