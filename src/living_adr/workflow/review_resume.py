"""HITL start/resume service for the workflow graph (feature 015, slice 4).

Provides the workflow-service-callable API to start a graph thread for a
normalized event and to resume a paused HITL review with a typed
:class:`ReviewResumeCommand` (US-3). Thread identity is the deterministic
repository + normalized-event-key derivation, so the same event always targets
the same durable checkpoint (resume is safe across process restarts; FR-6/FR-7).

This module owns orchestration control flow only. It renders no UI (feature 009)
and mints no approval capability (feature 010); it merely carries the typed
review command into the graph and reports the resulting state. Observability is
metadata-only via the feature 002 :class:`Observability` seam.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command

from living_adr.core.models import SCMEvent
from living_adr.core.observability import NoOpObservability, Observability
from living_adr.workflow.graph import build_default_workflow_graph
from living_adr.workflow.nodes.protocols import StructuralClassifierNode
from living_adr.workflow.nodes.stubs import GraphMutationService
from living_adr.workflow.state import (
    MutationResult,
    ReviewRequestPayload,
    ReviewResumeCommand,
    WorkflowReplayMetadata,
    WorkflowState,
    WorkflowStatus,
    default_event_key,
    derive_thread_id,
)


class NoPendingReviewError(RuntimeError):
    """Raised when resuming a thread that has no pending HITL interrupt.

    Guards against resuming an unknown/wrong ``thread_id`` or a thread that has
    already terminated — a resume command must correspond to a real paused
    review (US-3).
    """


@dataclass(frozen=True)
class WorkflowRunResult:
    """Typed outcome of a start/resume invocation (metadata + payload refs)."""

    thread_id: str
    status: WorkflowStatus | None
    interrupted: bool
    review_request: ReviewRequestPayload | None = None
    mutation_result: MutationResult | None = None
    values: dict[str, Any] = field(default_factory=dict)


class ReviewResumeService:
    """Start/resume orchestration over a compiled workflow graph."""

    def __init__(
        self,
        app: CompiledStateGraph,
        *,
        observability: Observability | None = None,
    ) -> None:
        self._app = app
        self._obs: Observability = observability or NoOpObservability()

    @classmethod
    def with_stub_graph(
        cls,
        *,
        checkpointer: BaseCheckpointSaver,
        classifier: StructuralClassifierNode | None = None,
        mutation_service: GraphMutationService | None = None,
        observability: Observability | None = None,
    ) -> ReviewResumeService:
        """Convenience constructor wiring the default stub graph + checkpointer."""

        app = build_default_workflow_graph(
            checkpointer=checkpointer,
            classifier=classifier,
            mutation_service=mutation_service,
        )
        return cls(app, observability=observability)

    def thread_id_for_event(
        self, event: SCMEvent, *, normalized_event_key: str | None = None
    ) -> str:
        """Deterministic ``thread_id`` for an event (override-free derivation)."""

        key = normalized_event_key or default_event_key(event)
        return derive_thread_id(event.repository, key)

    def start_workflow_for_event(
        self,
        event: SCMEvent,
        *,
        evidence_refs: tuple[str, ...] = (),
        replay: WorkflowReplayMetadata | None = None,
        normalized_event_key: str | None = None,
        thread_id: str | None = None,
    ) -> WorkflowRunResult:
        """Start (or idempotently re-enter) a graph thread for ``event``."""

        key = (
            normalized_event_key
            or (replay.normalized_event_key if replay else None)
            or default_event_key(event)
        )
        tid = thread_id or derive_thread_id(event.repository, key)
        config = {"configurable": {"thread_id": tid}}
        state = WorkflowState.for_event(
            event,
            normalized_event_key=key,
            evidence_refs=evidence_refs,
            replay=replay,
        )
        self._obs.record_event(
            "workflow.started",
            {"thread_id": tid, "repository": event.repository.key},
        )
        output = self._app.invoke(state, config)
        return self._build_result(tid, output, config)

    def resume_review(
        self, thread_id: str, command: ReviewResumeCommand
    ) -> WorkflowRunResult:
        """Resume a paused HITL review with a typed reviewer command."""

        config = {"configurable": {"thread_id": thread_id}}
        snapshot = self._app.get_state(config)
        if not snapshot.next:
            raise NoPendingReviewError(
                f"No pending HITL review for thread {thread_id!r}"
            )
        self._obs.record_event(
            "workflow.resumed",
            {"thread_id": thread_id, "action": command.action.value},
        )
        output = self._app.invoke(Command(resume=command), config)
        return self._build_result(thread_id, output, config)

    def _build_result(
        self, thread_id: str, output: dict[str, Any], config: dict[str, Any]
    ) -> WorkflowRunResult:
        interrupted = "__interrupt__" in output
        review_request: ReviewRequestPayload | None = None
        if interrupted:
            value = output["__interrupt__"][0].value
            if isinstance(value, ReviewRequestPayload):
                review_request = value

        snapshot = self._app.get_state(config)
        values = dict(snapshot.values)
        status = values.get("status")
        if review_request is None:
            candidate = values.get("review_request")
            if isinstance(candidate, ReviewRequestPayload):
                review_request = candidate

        if interrupted:
            self._obs.record_event(
                "workflow.interrupted",
                {"thread_id": thread_id, "status": getattr(status, "value", None)},
            )
        else:
            self._obs.record_event(
                "workflow.settled",
                {"thread_id": thread_id, "status": getattr(status, "value", None)},
            )

        return WorkflowRunResult(
            thread_id=thread_id,
            status=status,
            interrupted=interrupted,
            review_request=review_request,
            mutation_result=values.get("mutation_result"),
            values=values,
        )


__all__ = [
    "NoPendingReviewError",
    "WorkflowRunResult",
    "ReviewResumeService",
]
