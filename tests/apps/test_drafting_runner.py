"""Phase 3: the off-request draft scheduler drives the live graph to a draft.

build_draft_scheduler runs the live workflow graph in a worker-thread-safe way
(its own ingestion-store connection), driving an accepted PR's persisted
evidence through the real classifier + Claude draft node to the HITL interrupt.
Uses FakeClaudeClient, so the real Claude call is exercised without a network
hop; a missing evidence record is a safe no-op.
"""

from __future__ import annotations

from pathlib import Path

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

from living_adr.apps.workflow_service.drafting_runner import build_draft_scheduler
from living_adr.core.llm import FakeClaudeClient
from living_adr.persistence.ingestion_store import SqliteIngestionStore
from living_adr.workflow.checkpointing import (
    WorkflowCheckpointConfig,
    create_checkpointer,
)


def _seed_evidence(db_path: Path) -> None:
    store = SqliteIngestionStore(db_path)
    store.put_evidence(_candidate())
    store.close()


def test_scheduler_drives_graph_to_real_claude_draft(tmp_path: Path) -> None:
    db_path = tmp_path / "ingestion.db"
    _seed_evidence(db_path)
    cp = create_checkpointer(WorkflowCheckpointConfig(db_path=tmp_path / "cp.db"))
    client = FakeClaudeClient(response_text=_VALID_MARKDOWN)
    producer = _FakeProducer(_result(changes=(_change(),), evidence=(_evidence(),)))
    run = build_draft_scheduler(
        db_path=db_path,
        config=_config(),
        claude_client=client,
        checkpointer=cp.saver,
        producer=producer,
    )

    try:
        run(make_event(), ("pr-1",))
        assert len(client.calls) == 1
    finally:
        cp.close()


def test_scheduler_is_noop_when_evidence_missing(tmp_path: Path) -> None:
    db_path = tmp_path / "ingestion.db"
    SqliteIngestionStore(db_path).close()  # empty store, schema created
    cp = create_checkpointer(WorkflowCheckpointConfig(db_path=tmp_path / "cp.db"))
    client = FakeClaudeClient(response_text=_VALID_MARKDOWN)
    producer = _FakeProducer(_result(changes=(_change(),), evidence=(_evidence(),)))
    run = build_draft_scheduler(
        db_path=db_path,
        config=_config(),
        claude_client=client,
        checkpointer=cp.saver,
        producer=producer,
    )

    try:
        run(make_event(), ("pr-1",))
        assert len(client.calls) == 0
    finally:
        cp.close()
