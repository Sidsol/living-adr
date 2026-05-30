"""Slice 2 — SQLite checkpointer factory and durable persistence (feature 015).

Covers FR-5/NFR-1/NFR-5 and US-2: WAL + busy timeout configured, checkpoint DB
path created under workflow-service state storage, and in-flight workflow state
(including pydantic sub-models) persists across separate checkpointer instances
(a simulated process restart) without unregistered-type deserialization warnings.
"""

from __future__ import annotations

import warnings
from pathlib import Path

from langgraph.graph import END, START, StateGraph

from living_adr.workflow.checkpointing import (
    WorkflowCheckpointConfig,
    create_checkpointer,
)
from living_adr.workflow.state import DraftRef, WorkflowState, WorkflowStatus


def _config(tmp_path: Path) -> WorkflowCheckpointConfig:
    return WorkflowCheckpointConfig(
        db_path=tmp_path / "nested" / "state" / "checkpoints.db",
        busy_timeout_ms=2500,
    )


def _one_node_graph():
    """A trivial graph that records a draft + status into persisted state."""

    def persist(state: WorkflowState) -> dict:
        return {
            "status": WorkflowStatus.AWAITING_REVIEW,
            "draft": DraftRef(
                draft_id="draft-1", content_hash="abc123", preview="# preview"
            ),
        }

    builder = StateGraph(WorkflowState)
    builder.add_node("persist", persist)
    builder.add_edge(START, "persist")
    builder.add_edge("persist", END)
    return builder


def test_wal_mode_and_busy_timeout_configured(tmp_path: Path) -> None:
    with create_checkpointer(_config(tmp_path)) as cp:
        assert cp.journal_mode() == "wal"
        assert cp.busy_timeout() == 2500


def test_checkpoint_path_created(tmp_path: Path) -> None:
    config = _config(tmp_path)
    assert not config.db_path.exists()
    with create_checkpointer(config) as cp:
        assert config.db_path.parent.exists()
        # Touching the saver creates the on-disk DB file.
        cp.saver.setup()
    assert config.db_path.exists()


def test_default_path_under_workflow_service_state() -> None:
    config = WorkflowCheckpointConfig()
    parts = config.db_path.parts
    assert "workflow_service" in parts
    assert "state" in parts


def test_state_persists_across_separate_checkpointer_instances(
    tmp_path: Path,
) -> None:
    config = _config(tmp_path)
    cfg = {"configurable": {"thread_id": "thread-persist"}}

    # First instance writes a checkpoint, then "the process restarts".
    cp1 = create_checkpointer(config)
    app1 = _one_node_graph().compile(checkpointer=cp1.saver)
    app1.invoke(WorkflowState(), cfg)
    cp1.close()

    # A fresh checkpointer on the same path reloads the persisted state.
    cp2 = create_checkpointer(config)
    app2 = _one_node_graph().compile(checkpointer=cp2.saver)
    snapshot = app2.get_state(cfg)
    cp2.close()

    assert snapshot.values["status"] == WorkflowStatus.AWAITING_REVIEW
    reloaded_draft = snapshot.values["draft"]
    assert isinstance(reloaded_draft, DraftRef)
    assert reloaded_draft.draft_id == "draft-1"


def test_reload_emits_no_unregistered_type_warning(tmp_path: Path) -> None:
    config = _config(tmp_path)
    cfg = {"configurable": {"thread_id": "thread-warn"}}

    cp1 = create_checkpointer(config)
    app1 = _one_node_graph().compile(checkpointer=cp1.saver)
    app1.invoke(WorkflowState(), cfg)
    cp1.close()

    cp2 = create_checkpointer(config)
    app2 = _one_node_graph().compile(checkpointer=cp2.saver)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        app2.get_state(cfg)
    cp2.close()

    messages = [str(w.message) for w in caught]
    assert not any("unregistered type" in m.lower() for m in messages), messages
