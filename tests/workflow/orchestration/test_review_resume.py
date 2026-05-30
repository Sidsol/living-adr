"""Slice 4 — HITL start/resume service and restart-safe resume (feature 015).

Covers US-3/FR-6/FR-7: start interrupts with a typed review payload; approve,
approve-after-edit, reject, and defer resume commands route deterministically;
resuming an unknown thread is rejected; and a pending HITL checkpoint resumes
after a simulated process restart on the same SQLite database.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.workflow.orchestration.fixtures import (
    approve_command,
    build_drafted_state,
    make_event,
)

from living_adr.apps.workflow_service.workflow_routes import WorkflowRoutes
from living_adr.workflow.checkpointing import (
    WorkflowCheckpointConfig,
    create_checkpointer,
)
from living_adr.workflow.review_resume import (
    NoPendingReviewError,
    ReviewResumeService,
)
from living_adr.workflow.state import ReviewAction, ReviewResumeCommand, WorkflowStatus


def _service(tmp_path: Path, name: str = "cp.db") -> ReviewResumeService:
    cp = create_checkpointer(WorkflowCheckpointConfig(db_path=tmp_path / name))
    return ReviewResumeService.with_stub_graph(checkpointer=cp.saver)


def test_start_interrupts_with_review_payload(tmp_path: Path) -> None:
    service = _service(tmp_path)
    result = service.start_workflow_for_event(make_event())
    assert result.interrupted is True
    assert result.review_request is not None
    assert result.review_request.draft_id
    # Deterministic thread id derivation.
    assert result.thread_id == service.thread_id_for_event(make_event())


def test_resume_approve_completes(tmp_path: Path) -> None:
    service = _service(tmp_path)
    start = service.start_workflow_for_event(make_event())
    command = approve_command(build_drafted_state())
    result = service.resume_review(start.thread_id, command)
    assert result.status is WorkflowStatus.COMPLETED
    assert result.interrupted is False


def test_resume_approve_after_edit_completes(tmp_path: Path) -> None:
    service = _service(tmp_path)
    start = service.start_workflow_for_event(make_event())
    command = approve_command(
        build_drafted_state(), action=ReviewAction.APPROVE_AFTER_EDIT
    )
    result = service.resume_review(start.thread_id, command)
    assert result.status is WorkflowStatus.COMPLETED


def test_resume_reject_does_not_complete_mutation(tmp_path: Path) -> None:
    service = _service(tmp_path)
    start = service.start_workflow_for_event(make_event())
    command = ReviewResumeCommand(action=ReviewAction.REJECT, reviewer_id="r1")
    result = service.resume_review(start.thread_id, command)
    assert result.status is WorkflowStatus.REJECTED
    assert result.mutation_result is not None
    assert result.mutation_result.service_called is False


def test_resume_defer_is_terminal(tmp_path: Path) -> None:
    service = _service(tmp_path)
    start = service.start_workflow_for_event(make_event())
    command = ReviewResumeCommand(action=ReviewAction.DEFER, reviewer_id="r1")
    result = service.resume_review(start.thread_id, command)
    assert result.status is WorkflowStatus.DEFERRED
    assert result.mutation_result.service_called is False


def test_resume_unknown_thread_is_rejected(tmp_path: Path) -> None:
    service = _service(tmp_path)
    command = ReviewResumeCommand(action=ReviewAction.APPROVE, reviewer_id="r1")
    with pytest.raises(NoPendingReviewError):
        service.resume_review("wf-does-not-exist", command)


def test_resume_after_simulated_restart(tmp_path: Path) -> None:
    config = WorkflowCheckpointConfig(db_path=tmp_path / "restart.db")

    # Process 1: start and pause at HITL, then "restart".
    cp1 = create_checkpointer(config)
    service1 = ReviewResumeService.with_stub_graph(checkpointer=cp1.saver)
    start = service1.start_workflow_for_event(make_event())
    thread_id = start.thread_id
    cp1.close()

    # Process 2: fresh service on the same database resumes the pending review.
    cp2 = create_checkpointer(config)
    service2 = ReviewResumeService.with_stub_graph(checkpointer=cp2.saver)
    command = approve_command(build_drafted_state())
    result = service2.resume_review(thread_id, command)
    cp2.close()

    assert result.status is WorkflowStatus.COMPLETED


def test_workflow_routes_seam_start_and_resume(tmp_path: Path) -> None:
    routes = WorkflowRoutes(_service(tmp_path))
    start = routes.start(make_event())
    assert start.interrupted is True
    result = routes.resume(
        start.thread_id,
        ReviewResumeCommand(action=ReviewAction.REJECT, reviewer_id="r1"),
    )
    assert result.status is WorkflowStatus.REJECTED
