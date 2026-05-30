"""Slice 3 — stub graph assembly, routing, and interrupt order (feature 015).

Covers FR-4/US-1: the compiled graph executes intake -> classify -> draft and
reaches the HITL interrupt with the expected typed payload, and the
no-ADR-needed classification terminates without drafting, interrupting, or
calling the mutation handoff.
"""

from __future__ import annotations

from pathlib import Path

from tests.workflow.orchestration.fixtures import make_event

from living_adr.workflow.checkpointing import (
    WorkflowCheckpointConfig,
    create_checkpointer,
)
from living_adr.workflow.graph import (
    NODE_HITL,
    build_default_workflow_graph,
)
from living_adr.workflow.nodes.stubs import StubClassifierNode
from living_adr.workflow.state import (
    ReviewRequestPayload,
    WorkflowState,
    WorkflowStatus,
)


def _checkpointer(tmp_path: Path):
    return create_checkpointer(
        WorkflowCheckpointConfig(db_path=tmp_path / "cp.db")
    )


def test_graph_reaches_hitl_interrupt_with_payload(tmp_path: Path) -> None:
    cp = _checkpointer(tmp_path)
    app = build_default_workflow_graph(checkpointer=cp.saver)
    cfg = {"configurable": {"thread_id": "t-hitl"}}

    result = app.invoke(WorkflowState.for_event(make_event()), cfg)

    # The graph paused at the HITL interrupt before any mutation.
    assert "__interrupt__" in result
    interrupt_value = result["__interrupt__"][0].value
    assert isinstance(interrupt_value, ReviewRequestPayload)

    snapshot = app.get_state(cfg)
    cp.close()
    # Paused exactly at the HITL gate, having completed intake/classify/draft.
    assert snapshot.next == (NODE_HITL,)
    assert snapshot.values["classification"].adr_needed is True
    assert snapshot.values["draft"] is not None
    assert snapshot.values["status"] is WorkflowStatus.DRAFTING
    assert interrupt_value.draft_id == snapshot.values["draft"].draft_id


def test_no_adr_path_terminates_without_draft_or_interrupt(tmp_path: Path) -> None:
    cp = _checkpointer(tmp_path)
    app = build_default_workflow_graph(
        checkpointer=cp.saver,
        classifier=StubClassifierNode(adr_needed=False),
    )
    cfg = {"configurable": {"thread_id": "t-noadr"}}

    result = app.invoke(WorkflowState.for_event(make_event()), cfg)
    snapshot = app.get_state(cfg)
    cp.close()

    assert "__interrupt__" not in result
    assert snapshot.next == ()  # terminated
    assert snapshot.values["status"] is WorkflowStatus.NO_ADR_NEEDED
    assert snapshot.values.get("draft") is None
    assert snapshot.values.get("mutation_result") is None


def test_graph_compiles_without_checkpointer() -> None:
    # Topology must compile for ad-hoc/local execution too.
    app = build_default_workflow_graph(checkpointer=None)
    assert app is not None
