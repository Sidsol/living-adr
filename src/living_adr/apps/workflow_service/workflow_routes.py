"""Internal workflow-service hooks for start/resume/replay (feature 015).

A thin, UI-free seam the workflow-service entrypoint (and operator tests) call to
drive the orchestration graph. Feature 009 later renders reviewer UI on top of
these hooks; this module commits to **no** public HTTP/UI surface and renders no
templates (slice 4 context note: app hooks remain internal and UI-free).

Every hook delegates to :class:`ReviewResumeService` / the replay bridge so the
deterministic thread-id derivation, checkpointing, and approval-bound mutation
boundary are honored identically whether invoked by a webhook handler, an
operator script, or a test.
"""

from __future__ import annotations

from living_adr.core.models import SCMEvent
from living_adr.workflow.orchestration_replay import WorkflowReplayService
from living_adr.workflow.review_resume import ReviewResumeService, WorkflowRunResult
from living_adr.workflow.state import (
    ReviewResumeCommand,
    WorkflowReplayMetadata,
)


class WorkflowRoutes:
    """Internal handler seam binding workflow-service callers to the graph."""

    def __init__(
        self,
        service: ReviewResumeService,
        replay_service: WorkflowReplayService | None = None,
    ) -> None:
        self._service = service
        self._replay = replay_service or WorkflowReplayService(service)

    def start(
        self,
        event: SCMEvent,
        *,
        evidence_refs: tuple[str, ...] = (),
        replay: WorkflowReplayMetadata | None = None,
    ) -> WorkflowRunResult:
        """Start a workflow thread for a normalized merged-PR event."""

        return self._service.start_workflow_for_event(
            event, evidence_refs=evidence_refs, replay=replay
        )

    def resume(
        self, thread_id: str, command: ReviewResumeCommand
    ) -> WorkflowRunResult:
        """Resume a paused HITL review with a typed reviewer command."""

        return self._service.resume_review(thread_id, command)

    def replay(
        self,
        event: SCMEvent,
        *,
        source_delivery_id: str | None = None,
        evidence_refs: tuple[str, ...] = (),
    ) -> WorkflowRunResult:
        """Idempotently replay a stored event into its deterministic thread."""

        return self._replay.replay_event(
            event,
            source_delivery_id=source_delivery_id,
            evidence_refs=evidence_refs,
        )


__all__ = ["WorkflowRoutes"]
