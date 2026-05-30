"""Slice 6 — replay/recovery integration (feature 015).

Covers US-4/NFR-2: replay derives the same deterministic thread id for the same
repository/event, a pending HITL checkpoint is recovered (not restarted) on
replay, and duplicate replay never duplicates the mutation service call. Replay
metadata is attached on first-time replay.
"""

from __future__ import annotations

from pathlib import Path

from tests.workflow.orchestration.fixtures import (
    approve_command,
    build_drafted_state,
    make_event,
)

from living_adr.apps.workflow_service.workflow_routes import WorkflowRoutes
from living_adr.core.adr import ADRRecord
from living_adr.core.approval import ApprovedReviewDecision
from living_adr.core.graph.models import NodeId
from living_adr.core.models import RepositoryIdentity
from living_adr.workflow.checkpointing import (
    WorkflowCheckpointConfig,
    create_checkpointer,
)
from living_adr.workflow.orchestration_replay import WorkflowReplayService
from living_adr.workflow.review_resume import ReviewResumeService
from living_adr.workflow.state import (
    WorkflowReplayMetadata,
    WorkflowStatus,
)


class CountingMutationService:
    def __init__(self) -> None:
        self.calls: list[ADRRecord] = []

    def upsert_adr_node(
        self,
        repository: RepositoryIdentity,
        adr: ADRRecord,
        decision: ApprovedReviewDecision | None,
    ) -> NodeId:
        self.calls.append(adr)
        return NodeId(repository=repository, value=f"node-{adr.adr_id}")


def _replay_service(
    tmp_path: Path, name: str, mutation_service=None
) -> WorkflowReplayService:
    cp = create_checkpointer(WorkflowCheckpointConfig(db_path=tmp_path / name))
    service = ReviewResumeService.with_stub_graph(
        checkpointer=cp.saver, mutation_service=mutation_service
    )
    return WorkflowReplayService(service)


def test_replay_derives_same_thread_id(tmp_path: Path) -> None:
    replay = _replay_service(tmp_path, "thread.db")
    event = make_event()
    expected = replay.thread_id_for_event(event)
    first = replay.replay_event(event, source_delivery_id="d1")
    second = replay.replay_event(event, source_delivery_id="d1")
    assert first.thread_id == second.thread_id == expected
    assert first.thread_id.startswith("wf-")


def test_replay_attaches_metadata_on_first_run(tmp_path: Path) -> None:
    replay = _replay_service(tmp_path, "meta.db")
    result = replay.replay_event(make_event(), source_delivery_id="delivery-9")
    meta = result.values.get("replay")
    assert isinstance(meta, WorkflowReplayMetadata)
    assert meta.source_delivery_id == "delivery-9"
    assert meta.thread_id == result.thread_id


def test_replay_recovers_pending_interrupt_without_restart(tmp_path: Path) -> None:
    replay = _replay_service(tmp_path, "recover.db")
    event = make_event()
    first = replay.replay_event(event)
    assert first.interrupted is True
    assert first.review_request is not None

    # Replaying the same event recovers the same pending review (idempotent).
    again = replay.replay_event(event)
    assert again.interrupted is True
    assert again.review_request is not None
    assert again.review_request.draft_id == first.review_request.draft_id
    assert again.status is first.status


def test_duplicate_replay_does_not_duplicate_mutation(tmp_path: Path) -> None:
    mutation = CountingMutationService()
    cp = create_checkpointer(WorkflowCheckpointConfig(db_path=tmp_path / "dup.db"))
    service = ReviewResumeService.with_stub_graph(
        checkpointer=cp.saver, mutation_service=mutation
    )
    replay = WorkflowReplayService(service)
    event = make_event()

    start = replay.replay_event(event)
    # Approve once -> exactly one authoritative mutation.
    resumed = service.resume_review(
        start.thread_id, approve_command(build_drafted_state())
    )
    assert resumed.status is WorkflowStatus.COMPLETED
    assert len(mutation.calls) == 1

    # A duplicate replay must not re-run the graph or mutate again.
    duplicate = replay.replay_event(event)
    assert duplicate.status is WorkflowStatus.COMPLETED
    assert len(mutation.calls) == 1


def test_routes_replay_seam(tmp_path: Path) -> None:
    cp = create_checkpointer(WorkflowCheckpointConfig(db_path=tmp_path / "routes.db"))
    routes = WorkflowRoutes(
        ReviewResumeService.with_stub_graph(checkpointer=cp.saver)
    )
    result = routes.replay(make_event(), source_delivery_id="d-routes")
    assert result.interrupted is True
    assert result.thread_id.startswith("wf-")
