"""Slice 1 — node protocols and deterministic stub behavior (feature 015).

Covers FR-2/FR-3: stubs satisfy the runtime-checkable node seams, classifier and
draft output is deterministic and stable, the HITL gate builds the expected typed
review payload, and the mutation handoff performs no write without an approved
capability.
"""

from __future__ import annotations

from tests.workflow.orchestration.fixtures import build_drafted_state, make_event

from living_adr.workflow.nodes.protocols import (
    ADRDraftNode,
    HITLGateNode,
    IntakeNode,
    MutationHandoffNode,
    StructuralClassifierNode,
)
from living_adr.workflow.nodes.stubs import (
    StubClassifierNode,
    StubDraftNode,
    StubHITLGateNode,
    StubIntakeNode,
    StubMutationHandoffNode,
)
from living_adr.workflow.state import (
    ClassificationResult,
    DraftRef,
    MutationOutcome,
    ReviewAction,
    ReviewRequestPayload,
    ReviewResumeCommand,
    WorkflowState,
    WorkflowStatus,
)


def test_stubs_satisfy_node_protocols() -> None:
    assert isinstance(StubIntakeNode(), IntakeNode)
    assert isinstance(StubClassifierNode(), StructuralClassifierNode)
    assert isinstance(StubDraftNode(), ADRDraftNode)
    assert isinstance(StubHITLGateNode(), HITLGateNode)
    assert isinstance(StubMutationHandoffNode(), MutationHandoffNode)


def test_classifier_stub_emits_stable_classification() -> None:
    state = WorkflowState.for_event(make_event())
    state = state.model_copy(update=dict(StubIntakeNode()(state)))
    first = dict(StubClassifierNode()(state))
    second = dict(StubClassifierNode()(state))
    classification = first["classification"]
    assert isinstance(classification, ClassificationResult)
    assert classification.adr_needed is True
    assert len(classification.changes) == 1
    assert classification.changes[0].change_type == "dependency"
    # Deterministic across invocations.
    assert second["classification"] == classification


def test_classifier_stub_no_adr_variant() -> None:
    state = WorkflowState.for_event(make_event())
    update = dict(StubClassifierNode(adr_needed=False)(state))
    classification = update["classification"]
    assert classification.adr_needed is False
    assert classification.no_adr_reason
    assert update["status"] is WorkflowStatus.NO_ADR_NEEDED


def test_draft_stub_produces_stable_content_hash() -> None:
    state = build_drafted_state()
    draft = state.draft
    assert isinstance(draft, DraftRef)
    assert draft.provisional is True
    assert draft.content_hash
    # Rebuilding draft from the same event yields the same hash.
    again = dict(StubDraftNode()(state))
    assert again["draft"].content_hash == draft.content_hash


def test_hitl_gate_builds_expected_review_payload() -> None:
    state = build_drafted_state()
    payload = StubHITLGateNode().build_request(state)
    assert isinstance(payload, ReviewRequestPayload)
    assert payload.repository == state.repository
    assert payload.draft_id == state.draft.draft_id
    assert payload.draft_content_hash == state.draft.content_hash
    assert ReviewAction.APPROVE in payload.allowed_actions


def test_mutation_handoff_no_call_without_capability() -> None:
    state = build_drafted_state()
    # An approve action but no approved decision capability present.
    state = state.model_copy(
        update={
            "resume_command": ReviewResumeCommand(
                action=ReviewAction.APPROVE, reviewer_id="r1"
            )
        }
    )
    result = dict(StubMutationHandoffNode()(state))["mutation_result"]
    assert result.outcome is MutationOutcome.NO_MUTATION
    assert result.service_called is False


def test_mutation_handoff_rejection_is_terminal() -> None:
    state = build_drafted_state()
    state = state.model_copy(
        update={
            "resume_command": ReviewResumeCommand(
                action=ReviewAction.REJECT, reviewer_id="r1"
            )
        }
    )
    update = dict(StubMutationHandoffNode()(state))
    assert update["mutation_result"].outcome is MutationOutcome.REJECTED
    assert update["status"] is WorkflowStatus.REJECTED
