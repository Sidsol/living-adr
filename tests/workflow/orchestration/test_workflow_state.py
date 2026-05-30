"""Slice 1 — workflow state model and HITL/replay payload contracts (feature 015).

Covers FR-1/FR-6 and the NFR-3/NFR-4 raw-payload-exclusion guarantee: required
intake fields, deterministic thread-id derivation, review-action semantics, and
that no raw provider payload can be smuggled into graph state or review payloads.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError
from tests.workflow.orchestration.fixtures import make_event, make_repository

from living_adr.workflow.state import (
    DraftRef,
    ReviewAction,
    ReviewRequestPayload,
    ReviewResumeCommand,
    WorkflowState,
    WorkflowStatus,
    default_event_key,
    derive_thread_id,
)


def test_for_event_requires_concrete_event_and_sets_scope() -> None:
    event = make_event()
    state = WorkflowState.for_event(event)
    assert state.repository == event.repository
    assert state.event == event
    assert state.normalized_event_key == default_event_key(event)
    assert state.status is WorkflowStatus.INTAKE


def test_for_event_rejects_missing_event() -> None:
    with pytest.raises((AttributeError, ValidationError, TypeError)):
        WorkflowState.for_event(None)  # type: ignore[arg-type]


def test_default_event_key_is_not_pr_number_alone() -> None:
    event = make_event()
    key = default_event_key(event)
    # Must bind provider + repo key + delivery id, never the bare PR number.
    assert str(event.pr_number) in key
    assert event.repository.key in key
    assert event.delivery_id in key
    assert key != str(event.pr_number)


def test_derive_thread_id_is_deterministic_and_scoped() -> None:
    repo = make_repository()
    key = "github:host/owner/repo:42:delivery-1"
    a = derive_thread_id(repo, key)
    b = derive_thread_id(repo, key)
    assert a == b
    assert a.startswith("wf-")
    # A different event key derives a different thread.
    other = derive_thread_id(repo, "github:host/owner/repo:43:delivery-2")
    assert other != a


def test_review_action_authorizes_mutation_only_for_approvals() -> None:
    assert ReviewAction.APPROVE.authorizes_mutation is True
    assert ReviewAction.APPROVE_AFTER_EDIT.authorizes_mutation is True
    assert ReviewAction.REJECT.authorizes_mutation is False
    assert ReviewAction.DEFER.authorizes_mutation is False


def test_workflow_state_forbids_raw_payload_field() -> None:
    # The raw-payload-exclusion contract: arbitrary provider payloads cannot
    # enter graph state.
    with pytest.raises(ValidationError):
        WorkflowState(raw_github_payload={"secret": "x"})  # type: ignore[call-arg]


def test_review_request_payload_forbids_extra_fields() -> None:
    repo = make_repository()
    with pytest.raises(ValidationError):
        ReviewRequestPayload(
            repository=repo,
            normalized_event_key="k",
            draft_id="d1",
            draft_content_hash="h1",
            draft_preview="preview",
            raw_diff="SECRET DIFF",  # type: ignore[call-arg]
        )


def test_review_request_payload_defaults_to_all_actions() -> None:
    repo = make_repository()
    payload = ReviewRequestPayload(
        repository=repo,
        normalized_event_key="k",
        draft_id="d1",
        draft_content_hash="h1",
        draft_preview="preview",
    )
    assert set(payload.allowed_actions) == set(ReviewAction)


def test_draft_ref_requires_non_empty_id_and_hash() -> None:
    with pytest.raises(ValidationError):
        DraftRef(draft_id="  ", content_hash="h", preview="p")
    with pytest.raises(ValidationError):
        DraftRef(draft_id="d", content_hash="   ", preview="p")


def test_resume_command_requires_reviewer() -> None:
    with pytest.raises(ValidationError):
        ReviewResumeCommand(action=ReviewAction.APPROVE, reviewer_id="  ")
