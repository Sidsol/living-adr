"""Slice S010-07: workflow resume → durable approval-bound mutation integration.

Exercises the real feature-010 seam wiring end to end at the node boundary:
:class:`ApprovalMintingNode` mints a one-shot capability from a reviewer's resume
command and attaches it to workflow state; :class:`StubMutationHandoffNode`, wired
with the :class:`DurableApprovalBoundMutationService`, performs the approval-bound,
durably-audited write. Proves a non-authorising outcome mutates nothing, an
approving outcome mutates exactly once with a durable audit trail, retries are
idempotent, and the audit survives a SQLite restart (US-3/US-4/US-7).
"""

from __future__ import annotations

from pathlib import Path

from tests.approval._helpers import (
    DRAFT_HASH,
    DRAFT_MARKDOWN,
    FixedClock,
    SequentialIds,
    build_repo,
)
from tests.fakes.in_memory_graph_store import InMemoryGraphStore

from living_adr.approval.audit_queries import build_decision_audit_trail
from living_adr.approval.models import ApprovedReviewDecision, AuditEventType
from living_adr.approval.mutation_service import DurableApprovalBoundMutationService
from living_adr.approval.repository import (
    InMemoryApprovalAuditRepository,
    SqliteApprovalAuditRepository,
)
from living_adr.workflow.approval_node import ApprovalMintingNode
from living_adr.workflow.nodes.stubs import StubMutationHandoffNode
from living_adr.workflow.state import (
    DraftRef,
    MutationOutcome,
    ReviewAction,
    ReviewResumeCommand,
    WorkflowState,
    WorkflowStatus,
)


def _draft() -> DraftRef:
    return DraftRef(
        draft_id="draft-1",
        content_hash=DRAFT_HASH,
        preview=DRAFT_MARKDOWN,
        citation_ids=("ev-1",),
        structural_change_id="change-1",
    )


def _state(action: ReviewAction) -> WorkflowState:
    return WorkflowState(
        repository=build_repo(),
        normalized_event_key="github:acme/living-adr:7:delivery-1",
        draft=_draft(),
        resume_command=ReviewResumeCommand(action=action, reviewer_id="lead-1"),
        status=WorkflowStatus.RESUMING,
    )


def _mint_node(audit):
    return ApprovalMintingNode(
        audit, clock=FixedClock(), id_provider=SequentialIds("mint")
    )


def _service(store, audit):
    return DurableApprovalBoundMutationService(
        store, audit, clock=FixedClock(), id_provider=SequentialIds("audit")
    )


# --- approve: mint, attach, mutate once, audit durably -------------------


def test_approve_mints_capability_and_mutates_through_service() -> None:
    audit = InMemoryApprovalAuditRepository()
    store = InMemoryGraphStore()
    state = _state(ReviewAction.APPROVE)

    update = _mint_node(audit)(state)
    decision = update["approved_decision"]
    assert isinstance(decision, ApprovedReviewDecision)
    assert decision.approved is True

    authorised = state.model_copy(update={"approved_decision": decision})
    handoff = StubMutationHandoffNode(_service(store, audit))
    result = handoff(authorised)

    mutation = result["mutation_result"]
    assert mutation.outcome is MutationOutcome.MUTATED
    assert mutation.service_called is True
    assert mutation.decision_id == decision.decision_id
    assert store.write_calls == 1

    trail = build_decision_audit_trail(audit, decision.decision_id)
    assert trail.was_minted is True
    assert trail.was_mutated is True
    assert trail.mutation_node_id == mutation.node_id
    assert AuditEventType.CAPABILITY_MINTED in trail.event_types
    assert AuditEventType.MUTATION_PERFORMED in trail.event_types


def test_repeated_handoff_is_idempotent() -> None:
    audit = InMemoryApprovalAuditRepository()
    store = InMemoryGraphStore()
    state = _state(ReviewAction.APPROVE)
    decision = _mint_node(audit)(state)["approved_decision"]
    authorised = state.model_copy(update={"approved_decision": decision})
    handoff = StubMutationHandoffNode(_service(store, audit))

    first = handoff(authorised)["mutation_result"]
    second = handoff(authorised)["mutation_result"]

    assert first.node_id == second.node_id
    assert store.write_calls == 1


# --- reject: record outcome, mint nothing, mutate nothing ----------------


def test_reject_records_outcome_without_minting_or_mutating() -> None:
    audit = InMemoryApprovalAuditRepository()
    store = InMemoryGraphStore()
    state = _state(ReviewAction.REJECT)

    update = _mint_node(audit)(state)
    assert update["approved_decision"] is None
    # The reviewer outcome is still durably recorded (FR-2).
    assert audit.list_review_events()

    handoff = StubMutationHandoffNode(_service(store, audit))
    result = handoff(state)
    assert result["mutation_result"].outcome is MutationOutcome.REJECTED
    assert store.write_calls == 0


# --- durability across SQLite restart (US-7) -----------------------------


def test_audit_trail_survives_restart(tmp_path: Path) -> None:
    db = tmp_path / "approval_audit.sqlite"
    store = InMemoryGraphStore()
    audit = SqliteApprovalAuditRepository(db)
    state = _state(ReviewAction.APPROVE)
    decision = _mint_node(audit)(state)["approved_decision"]
    authorised = state.model_copy(update={"approved_decision": decision})
    StubMutationHandoffNode(_service(store, audit))(authorised)
    audit.close()

    reopened = SqliteApprovalAuditRepository(db)
    trail = build_decision_audit_trail(reopened, decision.decision_id)
    assert trail.was_mutated is True
    assert trail.was_consumed is True
    assert reopened.find_review_event_for_decision(decision.decision_id) is not None
    reopened.close()
