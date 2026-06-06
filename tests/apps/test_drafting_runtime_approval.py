"""Phase 5A: approve drives mint -> approval-bound graph write through the runtime.

End to end over the shared runtime (no network, in-memory graph store + audit):
a scheduled draft, then a HITL approve, mints a one-shot capability inside the
graph and performs exactly one approval-bound graph write; a reject writes
nothing.
"""

from __future__ import annotations

from pathlib import Path

from tests.fakes.in_memory_graph_store import InMemoryGraphStore
from tests.workflow.orchestration.fixtures import make_event
from tests.workflow.test_live_nodes import (
    _VALID_MARKDOWN,
    _candidate,
    _change,
    _config,
    _evidence,
    _FakeProducer,
    _result,
)

from living_adr.approval.repository import InMemoryApprovalAuditRepository
from living_adr.apps.workflow_service.drafting_runner import build_drafting_runtime
from living_adr.core.llm import FakeClaudeClient
from living_adr.persistence.ingestion_store import SqliteIngestionStore
from living_adr.workflow.checkpointing import (
    WorkflowCheckpointConfig,
    create_checkpointer,
)
from living_adr.workflow.state import (
    ReviewAction,
    ReviewResumeCommand,
    WorkflowStatus,
    default_event_key,
    derive_thread_id,
)


def _runtime(tmp_path: Path, audit, store):
    db_path = tmp_path / "ingestion.db"
    seed = SqliteIngestionStore(db_path)
    seed.put_evidence(_candidate())
    seed.close()
    cp = create_checkpointer(WorkflowCheckpointConfig(db_path=tmp_path / "cp.db"))
    runtime = build_drafting_runtime(
        db_path=db_path,
        config=_config(),
        claude_client=FakeClaudeClient(response_text=_VALID_MARKDOWN),
        checkpointer=cp,
        producer=_FakeProducer(_result(changes=(_change(),), evidence=(_evidence(),))),
        audit=audit,
        graph_store=store,
    )
    return runtime, cp


def _draft_then_thread(runtime):
    event = make_event()
    runtime.scheduler(event, ("pr-1",))
    return derive_thread_id(event.repository, default_event_key(event))


def test_approve_performs_one_approval_bound_graph_write(tmp_path: Path) -> None:
    audit = InMemoryApprovalAuditRepository()
    store = InMemoryGraphStore()
    runtime, cp = _runtime(tmp_path, audit, store)
    try:
        thread_id = _draft_then_thread(runtime)
        outcome = runtime.gateway.submit_resume(
            thread_id,
            ReviewResumeCommand(action=ReviewAction.APPROVE, reviewer_id="lead-1"),
        )
        # COMPLETED + exactly one write proves a valid capability was minted and
        # consumed (the mutation handoff fails closed without one).
        assert outcome.status is WorkflowStatus.COMPLETED
        assert store.write_calls == 1
    finally:
        cp.close()


def test_reject_writes_nothing_to_the_graph(tmp_path: Path) -> None:
    audit = InMemoryApprovalAuditRepository()
    store = InMemoryGraphStore()
    runtime, cp = _runtime(tmp_path, audit, store)
    try:
        thread_id = _draft_then_thread(runtime)
        outcome = runtime.gateway.submit_resume(
            thread_id,
            ReviewResumeCommand(action=ReviewAction.REJECT, reviewer_id="lead-1"),
        )
        assert outcome.status is WorkflowStatus.REJECTED
        assert store.write_calls == 0
    finally:
        cp.close()
