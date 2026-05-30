"""Deterministic stub node implementations for the workflow graph (feature 015).

These stubs make the assembled LangGraph graph executable **before** features
008 (classifier/draft), 009 (review UI), and 010 (approval/audit durability)
land. They are deterministic, perform no Claude/UI/GitHub calls, and import no
concrete graph adapter (no LlamaIndex) — authoritative writes flow only through
feature 006's ``ApprovalBoundMutationService`` (FR-3/FR-8; US-5).

The classifier/draft stubs reuse the existing walking-skeleton smoke logic in
:mod:`living_adr.workflow.smoke_flow` so deterministic output stays consistent
with feature 001 rather than forking a second rule.
"""

from __future__ import annotations

import hashlib
from typing import Protocol, runtime_checkable

from langgraph.types import interrupt

from living_adr.core.adr import ADRRecord, ADRStatus
from living_adr.core.approval import ApprovedReviewDecision
from living_adr.core.graph.models import NodeId
from living_adr.core.models import RepositoryIdentity
from living_adr.workflow.nodes.protocols import StateUpdate
from living_adr.workflow.smoke_flow import classify_structural_change, draft_adr
from living_adr.workflow.state import (
    ClassificationResult,
    DraftRef,
    MutationOutcome,
    MutationResult,
    ReviewAction,
    ReviewRequestPayload,
    ReviewResumeCommand,
    WorkflowState,
    WorkflowStatus,
    default_event_key,
)


@runtime_checkable
class GraphMutationService(Protocol):
    """Minimal write seam the mutation handoff depends on (feature 006).

    Deliberately narrower than ``ArchitectureGraphStore`` and approval-bound:
    the only implementation orchestration uses is
    ``ApprovalBoundMutationService``. Typing against this Protocol keeps the
    workflow node decoupled from concrete graph adapters.
    """

    def upsert_adr_node(
        self,
        repository: RepositoryIdentity,
        adr: ADRRecord,
        decision: ApprovedReviewDecision | None,
    ) -> NodeId: ...


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _coerce_resume_command(value: object) -> ReviewResumeCommand:
    """Map a LangGraph resume value into a typed :class:`ReviewResumeCommand`.

    Accepts an already-typed command (the production path from feature 009), a
    mapping (synthetic test input), or a bare action string/:class:`ReviewAction`
    for the simplest test resumes.
    """

    if isinstance(value, ReviewResumeCommand):
        return value
    if isinstance(value, ReviewAction):
        return ReviewResumeCommand(action=value, reviewer_id="stub-reviewer")
    if isinstance(value, str):
        return ReviewResumeCommand(
            action=ReviewAction(value), reviewer_id="stub-reviewer"
        )
    if isinstance(value, dict):
        return ReviewResumeCommand(**value)
    raise TypeError(
        "HITL resume value must be a ReviewResumeCommand, mapping, ReviewAction, "
        f"or action string; got {type(value)!r}"
    )


class StubIntakeNode:
    """Normalize a seeded ``SCMEvent`` into intake state (references only)."""

    def __call__(self, state: WorkflowState) -> StateUpdate:
        if state.event is None:
            raise ValueError("intake requires a normalized SCMEvent")
        key = state.normalized_event_key or default_event_key(state.event)
        return {
            "normalized_event_key": key,
            "status": WorkflowStatus.CLASSIFYING,
        }


class StubClassifierNode:
    """Deterministic classifier stub (feature 008 supplies the real classifier).

    Emits exactly one dependency-type ``StructuralChange`` (via the smoke
    classifier) for the ADR-needed path, or an explicit no-ADR result.
    """

    def __init__(
        self,
        *,
        adr_needed: bool = True,
        confidence: float = 0.9,
        no_adr_reason: str = "no architecture-significant change detected",
    ) -> None:
        self._adr_needed = adr_needed
        self._confidence = confidence
        self._no_adr_reason = no_adr_reason

    def __call__(self, state: WorkflowState) -> StateUpdate:
        if state.event is None:
            raise ValueError("classifier requires a normalized SCMEvent")
        if not self._adr_needed:
            return {
                "classification": ClassificationResult(
                    adr_needed=False, no_adr_reason=self._no_adr_reason
                ),
                "status": WorkflowStatus.NO_ADR_NEEDED,
            }
        change, evidence = classify_structural_change(state.event)
        evidence_refs = state.evidence_refs or (evidence.evidence_id,)
        return {
            "classification": ClassificationResult(
                adr_needed=True,
                changes=(change,),
                confidence=self._confidence,
                evidence_ids=(evidence.evidence_id,),
            ),
            "evidence_refs": evidence_refs,
            "status": WorkflowStatus.CLASSIFYING,
        }


class StubDraftNode:
    """Deterministic ADR draft stub (feature 008 supplies Claude drafting).

    Renders the smoke Markdown draft and binds it to a stable SHA-256
    ``content_hash``. No external LLM call.
    """

    def __call__(self, state: WorkflowState) -> StateUpdate:
        if state.event is None:
            raise ValueError("draft requires a normalized SCMEvent")
        change, evidence = classify_structural_change(state.event)
        draft = draft_adr(change, evidence)
        return {
            "draft": DraftRef(
                draft_id=draft.draft_id,
                content_hash=_sha256(draft.rendered_markdown),
                preview=draft.rendered_markdown,
                citation_ids=draft.citations,
                structural_change_id=change.change_id,
                provisional=True,
            ),
            "status": WorkflowStatus.DRAFTING,
        }


class StubHITLGateNode:
    """HITL interrupt stub — feature 009 UI / feature 010 capability plug in here.

    ``build_request`` constructs the typed :class:`ReviewRequestPayload` (testable
    in isolation). ``__call__`` raises a LangGraph ``interrupt`` with that payload
    and maps the resume value into a :class:`ReviewResumeCommand`.
    """

    def build_request(self, state: WorkflowState) -> ReviewRequestPayload:
        if state.repository is None or state.draft is None:
            raise ValueError("HITL gate requires repository scope and a draft")
        classification = state.classification
        return ReviewRequestPayload(
            repository=state.repository,
            normalized_event_key=state.normalized_event_key or "",
            draft_id=state.draft.draft_id,
            draft_content_hash=state.draft.content_hash,
            draft_preview=state.draft.preview,
            evidence_ids=state.draft.citation_ids,
            confidence=classification.confidence if classification else 0.0,
        )

    def __call__(self, state: WorkflowState) -> StateUpdate:
        request = self.build_request(state)
        resume_value = interrupt(request)
        command = _coerce_resume_command(resume_value)
        return {
            "review_request": request,
            "resume_command": command,
            "approved_decision": command.approved_decision,
            "status": WorkflowStatus.RESUMING,
        }


class RejectionTerminalNode:
    """Terminal node for rejected reviews — never routes to mutation handoff."""

    def __call__(self, state: WorkflowState) -> StateUpdate:
        return {
            "mutation_result": MutationResult(
                outcome=MutationOutcome.REJECTED,
                detail="reviewer rejected the draft; no mutation performed",
            ),
            "status": WorkflowStatus.REJECTED,
        }


class DeferralTerminalNode:
    """Terminal node for deferred reviews — never routes to mutation handoff."""

    def __call__(self, state: WorkflowState) -> StateUpdate:
        return {
            "mutation_result": MutationResult(
                outcome=MutationOutcome.DEFERRED,
                detail="reviewer deferred the draft; no mutation performed",
            ),
            "status": WorkflowStatus.DEFERRED,
        }


class StubMutationHandoffNode:
    """Mutation handoff stub enforcing the approval-bound write boundary (US-5).

    Calls ``ApprovalBoundMutationService.upsert_adr_node`` **only** when the
    resume command authorizes mutation (approve / approve_after_edit) and a valid
    approved decision capability is present. Missing capability, rejection, or
    deferral produce a terminal no-mutation result with **no** service call. The
    node never imports or calls a concrete graph adapter.
    """

    def __init__(self, mutation_service: GraphMutationService | None = None) -> None:
        self._service = mutation_service

    def build_adr_record(self, state: WorkflowState) -> ADRRecord:
        """Deterministically build the authoritative record an approval covers."""

        if state.repository is None or state.draft is None:
            raise ValueError("mutation handoff requires repository scope and a draft")
        decision = state.approved_decision
        change_id = (
            state.classification.changes[0].change_id
            if state.classification and state.classification.changes
            else state.draft.structural_change_id
        )
        title = f"Approved ADR for change {change_id}" if change_id else "Approved ADR"
        return ADRRecord(
            repository=state.repository,
            adr_id=state.draft.draft_id,
            title=title,
            status=ADRStatus.APPROVED,
            content_hash=state.draft.content_hash,
            decision_id=decision.decision_id if decision else "pending",
            structural_change_id=change_id,
            evidence_ids=state.draft.citation_ids,
            markdown=state.draft.preview,
        )

    def __call__(self, state: WorkflowState) -> StateUpdate:
        command = state.resume_command
        decision = state.approved_decision

        if command is None:
            return {
                "mutation_result": MutationResult(
                    outcome=MutationOutcome.BLOCKED,
                    detail="mutation handoff reached without a resume command",
                ),
                "status": WorkflowStatus.FAILED,
            }
        if command.action is ReviewAction.REJECT:
            return RejectionTerminalNode()(state)
        if command.action is ReviewAction.DEFER:
            return DeferralTerminalNode()(state)

        # approve / approve_after_edit from here on.
        if decision is None or not decision.approved:
            return {
                "mutation_result": MutationResult(
                    outcome=MutationOutcome.NO_MUTATION,
                    detail="approved action without a valid approved capability",
                ),
                "status": WorkflowStatus.FAILED,
            }
        if self._service is None:
            # Seam present but no service wired (default/local execution): record
            # intent without performing an authoritative write.
            return {
                "mutation_result": MutationResult(
                    outcome=MutationOutcome.NO_MUTATION,
                    detail="no mutation service configured; write seam not invoked",
                    decision_id=decision.decision_id,
                ),
                "status": WorkflowStatus.COMPLETED,
            }

        record = self.build_adr_record(state)
        node_id = self._service.upsert_adr_node(state.repository, record, decision)
        return {
            "mutation_result": MutationResult(
                outcome=MutationOutcome.MUTATED,
                detail="approval-bound mutation performed",
                node_id=node_id.value,
                decision_id=decision.decision_id,
                service_called=True,
            ),
            "status": WorkflowStatus.COMPLETED,
        }


__all__ = [
    "GraphMutationService",
    "StubIntakeNode",
    "StubClassifierNode",
    "StubDraftNode",
    "StubHITLGateNode",
    "RejectionTerminalNode",
    "DeferralTerminalNode",
    "StubMutationHandoffNode",
]
