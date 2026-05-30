"""Slice 5 — approval-bound mutation handoff boundary (feature 015).

Covers US-5/FR-8: the mutation handoff calls the approval-bound mutation service
exactly once for an approved decision, never calls it for missing-capability,
rejected, or deferred states, enforces the feature-006 approval boundary (wrong
fingerprint / replayed capability are rejected before any store write), and the
workflow orchestration modules import no concrete graph adapter or LlamaIndex.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.workflow.orchestration.fixtures import (
    approve_command,
    build_drafted_state,
    mint_decision_for_state,
)

from living_adr.core.adr import ADRRecord
from living_adr.core.approval import (
    ApprovedReviewDecision,
    DecisionAlreadyConsumedError,
    MutationFingerprintMismatchError,
)
from living_adr.core.graph.approval_bound_mutation import ApprovalBoundMutationService
from living_adr.core.graph.models import NodeId
from living_adr.core.models import RepositoryIdentity
from living_adr.workflow.nodes.stubs import StubMutationHandoffNode
from living_adr.workflow.state import (
    MutationOutcome,
    ReviewAction,
    ReviewResumeCommand,
    WorkflowState,
)


class FakeMutationService:
    """Counts upsert calls; satisfies the GraphMutationService write seam."""

    def __init__(self) -> None:
        self.calls: list[ADRRecord] = []

    def upsert_adr_node(
        self,
        repository: RepositoryIdentity,
        adr: ADRRecord,
        decision: ApprovedReviewDecision | None,
    ) -> NodeId:
        self.calls.append(adr)
        return NodeId(repository=repository, value=f"node-{adr.adr_id}")


class FakeGraphStore:
    """Minimal ArchitectureGraphStore fake counting authoritative writes."""

    def __init__(self) -> None:
        self.writes: list[ADRRecord] = []

    def upsert_adr_node(
        self,
        repository: RepositoryIdentity,
        adr: ADRRecord,
        decision: ApprovedReviewDecision,
    ) -> NodeId:
        self.writes.append(adr)
        return NodeId(repository=repository, value=f"stored-{adr.adr_id}")


def _approved_state() -> WorkflowState:
    state = build_drafted_state()
    command = approve_command(state)
    return state.model_copy(
        update={
            "resume_command": command,
            "approved_decision": command.approved_decision,
        }
    )


def test_no_service_call_without_capability() -> None:
    state = build_drafted_state().model_copy(
        update={
            "resume_command": ReviewResumeCommand(
                action=ReviewAction.APPROVE, reviewer_id="r1"
            )
        }
    )
    service = FakeMutationService()
    result = dict(StubMutationHandoffNode(service)(state))["mutation_result"]
    assert result.outcome is MutationOutcome.NO_MUTATION
    assert service.calls == []


def test_no_service_call_on_reject() -> None:
    state = build_drafted_state().model_copy(
        update={
            "resume_command": ReviewResumeCommand(
                action=ReviewAction.REJECT, reviewer_id="r1"
            )
        }
    )
    service = FakeMutationService()
    result = dict(StubMutationHandoffNode(service)(state))["mutation_result"]
    assert result.outcome is MutationOutcome.REJECTED
    assert service.calls == []


def test_no_service_call_on_defer() -> None:
    state = build_drafted_state().model_copy(
        update={
            "resume_command": ReviewResumeCommand(
                action=ReviewAction.DEFER, reviewer_id="r1"
            )
        }
    )
    service = FakeMutationService()
    result = dict(StubMutationHandoffNode(service)(state))["mutation_result"]
    assert result.outcome is MutationOutcome.DEFERRED
    assert service.calls == []


def test_approved_state_calls_service_exactly_once() -> None:
    service = FakeMutationService()
    result = dict(StubMutationHandoffNode(service)(_approved_state()))[
        "mutation_result"
    ]
    assert result.outcome is MutationOutcome.MUTATED
    assert result.service_called is True
    assert len(service.calls) == 1


def test_approved_routes_through_real_approval_bound_service() -> None:
    store = FakeGraphStore()
    service = ApprovalBoundMutationService(store)
    update = dict(StubMutationHandoffNode(service)(_approved_state()))
    assert update["mutation_result"].outcome is MutationOutcome.MUTATED
    # Authoritative store write happened exactly once, via the approval boundary.
    assert len(store.writes) == 1


def test_replayed_capability_is_rejected_before_second_write() -> None:
    store = FakeGraphStore()
    service = ApprovalBoundMutationService(store)
    node = StubMutationHandoffNode(service)
    state = _approved_state()
    node(state)  # consumes the one-shot decision
    with pytest.raises(DecisionAlreadyConsumedError):
        node(state)
    assert len(store.writes) == 1  # no duplicate authoritative write


def test_wrong_fingerprint_capability_rejected_before_store_write() -> None:
    store = FakeGraphStore()
    service = ApprovalBoundMutationService(store)
    state = build_drafted_state()
    good = mint_decision_for_state(state)
    tampered = good.model_copy(update={"target_fingerprint": "not-the-target"})
    state = state.model_copy(
        update={
            "resume_command": ReviewResumeCommand(
                action=ReviewAction.APPROVE,
                reviewer_id="r1",
                approved_decision=tampered,
            ),
            "approved_decision": tampered,
        }
    )
    with pytest.raises(MutationFingerprintMismatchError):
        StubMutationHandoffNode(service)(state)
    assert store.writes == []


def test_workflow_modules_do_not_import_graph_adapters() -> None:
    workflow_dir = Path("src/living_adr/workflow")
    modules = [
        workflow_dir / "state.py",
        workflow_dir / "checkpointing.py",
        workflow_dir / "graph.py",
        workflow_dir / "review_resume.py",
        workflow_dir / "nodes" / "protocols.py",
        workflow_dir / "nodes" / "stubs.py",
    ]
    forbidden = ("llama_index", "living_adr.graph.llamaindex", "from living_adr.graph")
    for module in modules:
        text = module.read_text(encoding="utf-8")
        for needle in forbidden:
            assert needle not in text, f"{module} must not reference {needle!r}"
