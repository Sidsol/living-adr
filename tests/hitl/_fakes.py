"""Fake review gateway shared by feature 009 route/template tests.

Records submitted resume commands so tests can prove the exact feature 015
``ReviewResumeCommand`` was handed back, and serves canned pending payloads.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from living_adr.core.models import RepositoryIdentity
from living_adr.hitl.gateway import ResumeOutcome
from living_adr.hitl.models import (
    PendingReviewSummary,
    pending_summary_from_payload,
)
from living_adr.workflow.state import (
    ReviewRequestPayload,
    ReviewResumeCommand,
    WorkflowStatus,
)


def sample_repo() -> RepositoryIdentity:
    return RepositoryIdentity(
        host="github.com", owner="acme", repo="widgets", repo_id="r-1"
    )


def sample_payload(**overrides) -> ReviewRequestPayload:
    base = dict(
        repository=sample_repo(),
        normalized_event_key="github:github.com/acme/widgets:42:d-1",
        draft_id="draft-1",
        draft_content_hash="abc123def456",
        draft_preview=(
            "# Title: Adopt event sourcing\n\n"
            "## Status\nProposed\n\n## Context\nWe need <audit> & history.\n\n"
            "## Decision\nUse an append-only log.\n\n"
            "## Consequences\nMore storage.\n"
        ),
        evidence_ids=("ev-1", "ev-2"),
        confidence=0.82,
    )
    base.update(overrides)
    return ReviewRequestPayload(**base)


@dataclass
class FakeGateway:
    """In-memory ReviewWorkflowGateway for route/template tests."""

    pending: dict[str, ReviewRequestPayload] = field(default_factory=dict)
    submitted: list[tuple[str, ReviewResumeCommand]] = field(default_factory=list)
    resume_status: WorkflowStatus = WorkflowStatus.COMPLETED

    def get_pending_review(self, thread_id: str) -> ReviewRequestPayload | None:
        return self.pending.get(thread_id)

    def list_pending(self) -> tuple[PendingReviewSummary, ...]:
        return tuple(
            pending_summary_from_payload(tid, payload)
            for tid, payload in self.pending.items()
        )

    def submit_resume(
        self, thread_id: str, command: ReviewResumeCommand
    ) -> ResumeOutcome:
        self.submitted.append((thread_id, command))
        return ResumeOutcome(
            thread_id=thread_id,
            action=command.action,
            status=self.resume_status,
            interrupted=False,
        )


def gateway_with_one_pending(thread_id: str = "wf-1") -> FakeGateway:
    return FakeGateway(pending={thread_id: sample_payload()})
