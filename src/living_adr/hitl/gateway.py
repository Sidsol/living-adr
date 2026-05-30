"""Thin gateway binding the review UI to the feature 015 HITL seam (feature 009).

``ReviewWorkflowGateway`` is the protocol the FastAPI routes depend on; it hides
feature 015's :class:`~living_adr.workflow.review_resume.ReviewResumeService`
behind three UI-shaped operations:

* :meth:`get_pending_review` — recover the typed ``ReviewRequestPayload`` paused
  at the HITL interrupt for a thread (or ``None`` if absent/settled).
* :meth:`list_pending` — project metadata-only summaries for the pending list.
* :meth:`submit_resume` — hand a typed ``ReviewResumeCommand`` back to feature
  015 unchanged and surface a metadata-only :class:`ResumeOutcome`.

The gateway redefines no graph topology, owns no checkpointer, and mints no
approval capability (feature 010). It only carries feature 015's own byte-
compatible payload/command across the UI boundary.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from living_adr.hitl.models import (
    PendingReviewSummary,
    pending_summary_from_payload,
)
from living_adr.workflow.review_resume import WorkflowRunResult
from living_adr.workflow.state import (
    ReviewAction,
    ReviewRequestPayload,
    ReviewResumeCommand,
    WorkflowStatus,
)


@dataclass(frozen=True)
class ResumeOutcome:
    """Metadata-only result of resuming a paused review (no raw content)."""

    thread_id: str
    action: ReviewAction
    status: WorkflowStatus | None
    interrupted: bool


@runtime_checkable
class ReviewWorkflowGateway(Protocol):
    """UI-facing seam over feature 015 pending review + resume."""

    def get_pending_review(self, thread_id: str) -> ReviewRequestPayload | None: ...

    def list_pending(self) -> tuple[PendingReviewSummary, ...]: ...

    def submit_resume(
        self, thread_id: str, command: ReviewResumeCommand
    ) -> ResumeOutcome: ...


class _ResumeServicePort(Protocol):
    """The narrow slice of feature 015's service the gateway actually uses."""

    def inspect(self, thread_id: str) -> WorkflowRunResult | None: ...

    def resume_review(
        self, thread_id: str, command: ReviewResumeCommand
    ) -> WorkflowRunResult: ...


class ReviewResumeServiceGateway:
    """Adapter wrapping feature 015's ``ReviewResumeService`` for the UI."""

    def __init__(
        self,
        service: _ResumeServicePort,
        *,
        pending_thread_ids: Callable[[], Iterable[str]] | None = None,
    ) -> None:
        self._service = service
        self._pending_thread_ids = pending_thread_ids or (lambda: ())

    def get_pending_review(self, thread_id: str) -> ReviewRequestPayload | None:
        result = self._service.inspect(thread_id)
        if result is None or not result.interrupted:
            return None
        return result.review_request

    def list_pending(self) -> tuple[PendingReviewSummary, ...]:
        summaries: list[PendingReviewSummary] = []
        for thread_id in self._pending_thread_ids():
            payload = self.get_pending_review(thread_id)
            if payload is not None:
                summaries.append(pending_summary_from_payload(thread_id, payload))
        return tuple(summaries)

    def submit_resume(
        self, thread_id: str, command: ReviewResumeCommand
    ) -> ResumeOutcome:
        result = self._service.resume_review(thread_id, command)
        return ResumeOutcome(
            thread_id=thread_id,
            action=command.action,
            status=result.status,
            interrupted=result.interrupted,
        )


__all__ = [
    "ResumeOutcome",
    "ReviewWorkflowGateway",
    "ReviewResumeServiceGateway",
]
