"""Phase 4: the shared drafting runtime exposes scheduler + HITL gateway.

A draft scheduled (off-request) by the runtime's scheduler is visible to, and
resumable from, the HITL gateway through the shared checkpointer — no network
(FakeClaudeClient).
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

from living_adr.apps.workflow_service.drafting_runner import (
    build_drafting_runtime,
    build_drafting_runtime_from_env,
)
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


def _seed(db_path: Path) -> None:
    store = SqliteIngestionStore(db_path)
    store.put_evidence(_candidate())
    store.close()


def test_runtime_gateway_sees_scheduled_draft(tmp_path: Path) -> None:
    db_path = tmp_path / "ingestion.db"
    _seed(db_path)
    cp = create_checkpointer(WorkflowCheckpointConfig(db_path=tmp_path / "cp.db"))
    runtime = build_drafting_runtime(
        db_path=db_path,
        config=_config(),
        claude_client=FakeClaudeClient(response_text=_VALID_MARKDOWN),
        checkpointer=cp,
        producer=_FakeProducer(_result(changes=(_change(),), evidence=(_evidence(),))),
    )

    try:
        event = make_event()
        runtime.scheduler(event, ("pr-1",))
        thread_id = derive_thread_id(event.repository, default_event_key(event))

        payload = runtime.gateway.get_pending_review(thread_id)
        assert payload is not None
        assert payload.draft_id
        assert len(runtime.gateway.list_pending()) == 1

        outcome = runtime.gateway.submit_resume(
            thread_id,
            ReviewResumeCommand(action=ReviewAction.REJECT, reviewer_id="r1"),
        )
        assert outcome.status is WorkflowStatus.REJECTED
        assert runtime.gateway.get_pending_review(thread_id) is None
    finally:
        cp.close()


def test_runtime_from_env_is_none_without_anthropic_key(tmp_path: Path) -> None:
    assert (
        build_drafting_runtime_from_env(
            config=_config(), storage_dir=tmp_path, env={"GITHUB_APP_ID": "1"}
        )
        is None
    )
