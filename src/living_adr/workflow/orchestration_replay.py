"""Orchestration replay/recovery bridge (feature 015, slice 6).

Bridges feature-003 stored merged-PR events into the durable LangGraph workflow
with deterministic thread identity and idempotency (US-4; FM-01 missed ADRs,
FM-17 webhook gaps/duplicates). Replaying the same repository/event derives the
**same** ``thread_id``, so a duplicate replay resumes (or simply observes) the
existing checkpoint instead of starting a second, side-effect-duplicating run —
no duplicate review request and no duplicate authoritative mutation (NFR-2).

This module is **not** feature 003's ``living_adr.workflow.replay`` (delivery
re-fetch / dead-letter recovery) — it is the orchestration-layer counterpart that
consumes a normalized event and drives the graph. It lives in a distinct module
so feature 003's replay seam is reused unchanged rather than forked.

Node-seam ownership for replay: feature 003 owns delivery/evidence persistence
and re-fetch; this feature owns deterministic graph thread derivation and
checkpoint recovery; features 008/009/010 own the node bodies the recovered
thread resumes into.
"""

from __future__ import annotations

from living_adr.core.models import SCMEvent
from living_adr.core.observability import NoOpObservability, Observability
from living_adr.workflow.review_resume import ReviewResumeService, WorkflowRunResult
from living_adr.workflow.state import (
    WorkflowReplayMetadata,
    default_event_key,
    derive_thread_id,
)


class WorkflowReplayService:
    """Deterministic, idempotent replay of stored events into the graph."""

    def __init__(
        self,
        service: ReviewResumeService,
        *,
        observability: Observability | None = None,
    ) -> None:
        self._service = service
        self._obs: Observability = observability or NoOpObservability()

    def thread_id_for_event(
        self, event: SCMEvent, *, normalized_event_key: str | None = None
    ) -> str:
        key = normalized_event_key or default_event_key(event)
        return derive_thread_id(event.repository, key)

    def replay_event(
        self,
        event: SCMEvent,
        *,
        source_delivery_id: str | None = None,
        evidence_refs: tuple[str, ...] = (),
        normalized_event_key: str | None = None,
    ) -> WorkflowRunResult:
        """Start or idempotently re-enter the graph thread for ``event``.

        If the thread already has persisted state (paused at HITL or terminal),
        the existing durable state is returned **without** re-invoking the graph,
        so duplicate replays never duplicate review requests or mutations. A
        first-time replay starts the thread with attached replay metadata.
        """

        key = normalized_event_key or default_event_key(event)
        thread_id = derive_thread_id(event.repository, key)

        existing = self._service.inspect(thread_id)
        if existing is not None:
            self._obs.record_event(
                "workflow.replay_idempotent",
                {
                    "thread_id": thread_id,
                    "repository": event.repository.key,
                    "status": getattr(existing.status, "value", None),
                },
            )
            return existing

        replay_meta = WorkflowReplayMetadata(
            normalized_event_key=key,
            thread_id=thread_id,
            source_delivery_id=source_delivery_id,
            replay_count=0,
            is_replay=False,
        )
        self._obs.record_event(
            "workflow.replay_started",
            {"thread_id": thread_id, "repository": event.repository.key},
        )
        return self._service.start_workflow_for_event(
            event,
            evidence_refs=evidence_refs,
            replay=replay_meta,
            normalized_event_key=key,
            thread_id=thread_id,
        )


__all__ = ["WorkflowReplayService"]
