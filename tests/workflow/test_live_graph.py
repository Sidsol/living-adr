"""Phase 3 test: the live (real-node) workflow graph drafts and pauses at HITL.

Compiles the graph with the evidence-backed real classifier node and the
Claude-backed real draft node (FakeClaudeClient — no network), runs it over a
candidate placed in the evidence source, and asserts it produces a provisional
draft and interrupts at the HITL gate (or terminates on the no-ADR path).
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
    _FakeSource,
    _result,
)

from living_adr.core.llm import FakeClaudeClient
from living_adr.workflow.checkpointing import (
    WorkflowCheckpointConfig,
    create_checkpointer,
)
from living_adr.workflow.live_graph import build_live_review_service


def _service(tmp_path: Path, producer, name: str = "cp.db"):
    cp = create_checkpointer(WorkflowCheckpointConfig(db_path=tmp_path / name))
    service = build_live_review_service(
        source=_FakeSource(_candidate()),
        config=_config(),
        claude_client=FakeClaudeClient(response_text=_VALID_MARKDOWN),
        checkpointer=cp.saver,
        context_query=None,
        producer=producer,
    )
    return service, cp


def test_live_graph_drafts_and_interrupts_at_hitl(tmp_path: Path) -> None:
    producer = _FakeProducer(_result(changes=(_change(),), evidence=(_evidence(),)))
    service, cp = _service(tmp_path, producer)
    try:
        result = service.start_workflow_for_event(
            make_event(), evidence_refs=("pr-1",)
        )
        assert result.interrupted is True
        assert result.review_request is not None
        assert result.review_request.draft_id
        assert "ev-1" in result.review_request.evidence_ids
    finally:
        cp.close()


def test_live_graph_no_adr_path_terminates(tmp_path: Path) -> None:
    producer = _FakeProducer(_result(changes=(), evidence=()))
    service, cp = _service(tmp_path, producer)
    try:
        result = service.start_workflow_for_event(
            make_event(), evidence_refs=("pr-1",)
        )
        assert result.interrupted is False
    finally:
        cp.close()
