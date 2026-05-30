"""SL-001 tests: ReviewWorkflowGateway binds to the feature 015 seam.

The gateway is a thin adapter over feature 015's pending-review inspection and
typed resume command. It must pass the byte-compatible ``ReviewRequestPayload``
and ``ReviewResumeCommand`` straight through to feature 015 without redefining
the graph state, checkpointing, or routing, and must surface a metadata-only
``ResumeOutcome`` back to the UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from living_adr.core.models import RepositoryIdentity
from living_adr.hitl.gateway import (
    ResumeOutcome,
    ReviewResumeServiceGateway,
    ReviewWorkflowGateway,
)
from living_adr.hitl.models import PendingReviewSummary
from living_adr.workflow.review_resume import WorkflowRunResult
from living_adr.workflow.state import (
    ReviewAction,
    ReviewRequestPayload,
    ReviewResumeCommand,
    WorkflowStatus,
)


def _repo() -> RepositoryIdentity:
    return RepositoryIdentity(
        host="github.com", owner="acme", repo="widgets", repo_id="r-1"
    )


def _payload() -> ReviewRequestPayload:
    return ReviewRequestPayload(
        repository=_repo(),
        normalized_event_key="github:github.com/acme/widgets:42:d-1",
        draft_id="draft-1",
        draft_content_hash="abc123",
        draft_preview="preview body",
        evidence_ids=("ev-1",),
        confidence=0.7,
    )


@dataclass
class FakeResumeService:
    """Records the inspect/resume calls feature 009's gateway makes into 015."""

    pending: dict[str, ReviewRequestPayload] = field(default_factory=dict)
    resume_calls: list[tuple[str, ReviewResumeCommand]] = field(default_factory=list)
    resume_status: WorkflowStatus = WorkflowStatus.COMPLETED

    def inspect(self, thread_id: str) -> WorkflowRunResult | None:
        payload = self.pending.get(thread_id)
        if payload is None:
            return None
        return WorkflowRunResult(
            thread_id=thread_id,
            status=WorkflowStatus.AWAITING_REVIEW,
            interrupted=True,
            review_request=payload,
        )

    def resume_review(
        self, thread_id: str, command: ReviewResumeCommand
    ) -> WorkflowRunResult:
        self.resume_calls.append((thread_id, command))
        return WorkflowRunResult(
            thread_id=thread_id,
            status=self.resume_status,
            interrupted=False,
        )


def test_gateway_is_review_workflow_gateway() -> None:
    service = FakeResumeService()
    gateway = ReviewResumeServiceGateway(service)
    assert isinstance(gateway, ReviewWorkflowGateway)


def test_get_pending_review_returns_payload_unchanged() -> None:
    payload = _payload()
    service = FakeResumeService(pending={"wf-1": payload})
    gateway = ReviewResumeServiceGateway(service)
    fetched = gateway.get_pending_review("wf-1")
    assert fetched is payload  # byte-compatible passthrough, no re-derivation


def test_get_pending_review_missing_thread_returns_none() -> None:
    gateway = ReviewResumeServiceGateway(FakeResumeService())
    assert gateway.get_pending_review("nope") is None


def test_list_pending_maps_to_summaries() -> None:
    payload = _payload()
    service = FakeResumeService(pending={"wf-1": payload})
    gateway = ReviewResumeServiceGateway(
        service, pending_thread_ids=lambda: ("wf-1", "missing")
    )
    summaries = gateway.list_pending()
    assert len(summaries) == 1
    assert isinstance(summaries[0], PendingReviewSummary)
    assert summaries[0].thread_id == "wf-1"


def test_submit_resume_passes_command_through_and_maps_outcome() -> None:
    payload = _payload()
    service = FakeResumeService(pending={"wf-1": payload})
    gateway = ReviewResumeServiceGateway(service)
    command = ReviewResumeCommand(action=ReviewAction.APPROVE, reviewer_id="lead-1")
    outcome = gateway.submit_resume("wf-1", command)
    # Feature 015 received exactly the typed command, unchanged.
    assert service.resume_calls == [("wf-1", command)]
    assert isinstance(outcome, ResumeOutcome)
    assert outcome.thread_id == "wf-1"
    assert outcome.action is ReviewAction.APPROVE
    assert outcome.status is WorkflowStatus.COMPLETED
    # The UI gateway never mints an approval capability.
    assert command.approved_decision is None
