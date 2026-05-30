"""Shared deterministic builders for feature-015 orchestration tests.

Reuses the feature-001 smoke fixture so orchestration tests run against the same
deterministic merged-PR ``SCMEvent`` the walking skeleton uses — no GitHub,
Claude, UI, or graph adapter.
"""

from __future__ import annotations

from datetime import UTC, datetime

from living_adr.core.adr import ADRRecord
from living_adr.core.approval import ApprovedReviewDecision
from living_adr.core.graph.approval_bound_mutation import upsert_fingerprint
from living_adr.core.models import RepositoryIdentity, SCMEvent
from living_adr.workflow.nodes.stubs import StubMutationHandoffNode
from living_adr.workflow.smoke_fixture import (
    merged_pr_fixture,
    normalize_to_scm_event,
    smoke_repository,
)
from living_adr.workflow.state import (
    ReviewAction,
    ReviewResumeCommand,
    WorkflowState,
)


def make_event() -> SCMEvent:
    """The deterministic seeded merged-PR event used across orchestration tests."""

    return normalize_to_scm_event(merged_pr_fixture())


def make_repository() -> RepositoryIdentity:
    return smoke_repository()


def build_drafted_state() -> WorkflowState:
    """Run intake/classify/draft stubs to produce a state awaiting HITL review."""

    from living_adr.workflow.nodes.stubs import (
        StubClassifierNode,
        StubDraftNode,
        StubIntakeNode,
    )

    state = WorkflowState.for_event(make_event())
    state = state.model_copy(update=dict(StubIntakeNode()(state)))
    state = state.model_copy(update=dict(StubClassifierNode()(state)))
    state = state.model_copy(update=dict(StubDraftNode()(state)))
    return state


def mint_decision_for_state(
    state: WorkflowState, *, reviewer_id: str = "reviewer-1"
) -> ApprovedReviewDecision:
    """Mint a valid feature-006 capability matching the state's draft + ADR record.

    Computes the exact ``upsert_fingerprint`` for the ADR record the mutation
    handoff will build, so the real ``ApprovalBoundMutationService`` accepts it.
    """

    assert state.draft is not None and state.repository is not None
    record: ADRRecord = StubMutationHandoffNode().build_adr_record(
        state.model_copy(
            update={
                "approved_decision": _placeholder_decision(state, reviewer_id),
            }
        )
    )
    return ApprovedReviewDecision(
        repository=state.repository,
        decision_id=f"decision-{state.draft.draft_id}",
        reviewer_id=reviewer_id,
        adr_draft_id=state.draft.draft_id,
        adr_draft_content_hash=state.draft.content_hash,
        structural_change_event_id=record.structural_change_id,
        target_fingerprint=upsert_fingerprint(state.repository, record),
        minted_at=datetime(2024, 1, 16, 9, 0, 0, tzinfo=UTC),
        approved=True,
    )


def _placeholder_decision(
    state: WorkflowState, reviewer_id: str
) -> ApprovedReviewDecision:
    assert state.draft is not None and state.repository is not None
    return ApprovedReviewDecision(
        repository=state.repository,
        decision_id=f"decision-{state.draft.draft_id}",
        reviewer_id=reviewer_id,
        adr_draft_id=state.draft.draft_id,
        adr_draft_content_hash=state.draft.content_hash,
        target_fingerprint="placeholder",
        minted_at=datetime(2024, 1, 16, 9, 0, 0, tzinfo=UTC),
        approved=True,
    )


def approve_command(
    state: WorkflowState,
    *,
    action: ReviewAction = ReviewAction.APPROVE,
    reviewer_id: str = "reviewer-1",
) -> ReviewResumeCommand:
    """A resume command carrying a valid approved capability for ``state``."""

    return ReviewResumeCommand(
        action=action,
        reviewer_id=reviewer_id,
        approved_decision=mint_decision_for_state(state, reviewer_id=reviewer_id),
    )
