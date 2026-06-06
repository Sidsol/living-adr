"""Off-request drafting runner for the workflow-service (Phase 3).

Builds the callable the webhook receiver schedules (via FastAPI background
tasks) after a merged PR is accepted: it drives the live workflow graph (real
classifier + Claude draft node) to a provisional ADR draft paused at the HITL
gate. The slow Claude call therefore runs in a background worker thread, never on
the webhook request path.

Thread-safety: each run opens its **own** :class:`SqliteIngestionStore`
connection for the (immutable) evidence read, so the request thread's store
connection is never crossed into the worker thread. The durable LangGraph
checkpointer is opened with ``check_same_thread=False`` and shared across runs.
Failures are swallowed (metadata-only) so a drafting error never crashes the
service or affects the already-returned 202.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from living_adr.approval.mutation_service import DurableApprovalBoundMutationService
from living_adr.apps.workflow_service.startup import APP_ID_ENV
from living_adr.core.observability import NoOpObservability
from living_adr.hitl.gateway import ReviewResumeServiceGateway
from living_adr.persistence.ingestion_store import SqliteIngestionStore
from living_adr.workflow.approval_node import ApprovalMintingNode
from living_adr.workflow.checkpointing import (
    WorkflowCheckpointConfig,
    WorkflowCheckpointer,
    create_checkpointer,
)
from living_adr.workflow.drafting.claude_adapter import build_anthropic_claude_client
from living_adr.workflow.live_graph import build_live_review_service

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping

    from langgraph.checkpoint.base import BaseCheckpointSaver

    from living_adr.approval.repository import ApprovalAuditRepository
    from living_adr.core.config import LivingADRConfig
    from living_adr.core.graph.ports import ArchitectureGraphStore
    from living_adr.core.llm import ClaudeClient
    from living_adr.core.models import SCMEvent
    from living_adr.core.observability import Observability
    from living_adr.hitl.gateway import ReviewWorkflowGateway
    from living_adr.workflow.live_nodes import StructuralChangeProducer

ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"
CHECKPOINT_DB_NAME = "workflow_checkpoints.db"
INGESTION_DB_NAME = "ingestion.db"
APPROVAL_AUDIT_DB_NAME = "approval_audit.db"
GRAPH_DIR_NAME = "graph"


def build_draft_scheduler(
    *,
    db_path: Path,
    config: LivingADRConfig,
    claude_client: ClaudeClient,
    checkpointer: BaseCheckpointSaver,
    producer: StructuralChangeProducer | None = None,
    minting: object | None = None,
    mutation_service: object | None = None,
    observability: Observability | None = None,
) -> Callable[[SCMEvent, tuple[str, ...]], None]:
    """Build the off-request drafting callable.

    Each invocation opens a fresh read store on ``db_path`` (thread-local) and
    drives the live workflow graph for ``event``/``evidence_refs`` to the HITL
    interrupt. Errors are recorded as metadata-only events and never raised. The
    graph is compiled with the same ``minting``/``mutation_service`` seams as the
    review service so a checkpoint paused here resumes with an identical topology.
    """

    obs = observability or NoOpObservability()

    def _run(event: SCMEvent, evidence_refs: tuple[str, ...]) -> None:
        store = SqliteIngestionStore(db_path)
        try:
            service = build_live_review_service(
                source=store,
                config=config,
                claude_client=claude_client,
                checkpointer=checkpointer,
                producer=producer,
                minting=minting,
                mutation_service=mutation_service,
                observability=obs,
            )
            service.start_workflow_for_event(
                event, evidence_refs=tuple(evidence_refs)
            )
        except Exception as exc:  # noqa: BLE001 - never crash the worker thread
            obs.record_event(
                "workflow.draft_run_failed",
                {
                    "error_class": type(exc).__name__,
                    "repository": event.repository.key,
                },
            )
        finally:
            store.close()

    return _run


def _distinct_thread_ids(checkpointer: WorkflowCheckpointer) -> Iterator[str]:
    """Yield each distinct checkpointed thread id once (for the pending list).

    Queries the checkpointer's SQLite connection directly (a cheap distinct scan)
    rather than the saver's streaming ``list`` API.
    """

    try:
        rows = checkpointer.connection.execute(
            "SELECT DISTINCT thread_id FROM checkpoints"
        ).fetchall()
    except Exception:  # noqa: BLE001 - no checkpoints table yet (no runs)
        return
    seen: set[str] = set()
    for row in rows:
        thread_id = row[0]
        if thread_id and thread_id not in seen:
            seen.add(thread_id)
            yield thread_id


@dataclass(frozen=True)
class DraftingRuntime:
    """Shared drafting runtime: the off-request scheduler + the HITL gateway.

    Both share one durable checkpointer so a draft scheduled by the webhook is
    visible to (and resumable from) the HITL review UI. ``checkpointer`` is held
    so its SQLite connection stays open for the process lifetime.
    """

    scheduler: Callable[[SCMEvent, tuple[str, ...]], None]
    gateway: ReviewWorkflowGateway
    checkpointer: WorkflowCheckpointer


def build_drafting_runtime(
    *,
    db_path: Path,
    config: LivingADRConfig,
    claude_client: ClaudeClient,
    checkpointer: WorkflowCheckpointer,
    producer: StructuralChangeProducer | None = None,
    audit: ApprovalAuditRepository | None = None,
    graph_store: ArchitectureGraphStore | None = None,
    observability: Observability | None = None,
) -> DraftingRuntime:
    """Assemble the scheduler + HITL gateway over a shared checkpointer.

    The scheduler opens its own per-run store (worker thread); the gateway's
    review service only inspects/resumes the checkpointer, so its store is never
    crossed between threads. When both ``audit`` and ``graph_store`` are given,
    the approve path mints a one-shot capability (``ApprovalMintingNode``) and
    performs the approval-bound graph write (``DurableApprovalBoundMutationService``).
    """

    minting: object | None = None
    mutation_service: object | None = None
    if audit is not None and graph_store is not None:
        minting = ApprovalMintingNode(audit)
        mutation_service = DurableApprovalBoundMutationService(graph_store, audit)

    scheduler = build_draft_scheduler(
        db_path=db_path,
        config=config,
        claude_client=claude_client,
        checkpointer=checkpointer.saver,
        producer=producer,
        minting=minting,
        mutation_service=mutation_service,
        observability=observability,
    )
    review_service = build_live_review_service(
        source=SqliteIngestionStore(db_path),
        config=config,
        claude_client=claude_client,
        checkpointer=checkpointer.saver,
        producer=producer,
        minting=minting,
        mutation_service=mutation_service,
        observability=observability,
    )
    gateway = ReviewResumeServiceGateway(
        review_service,
        pending_thread_ids=lambda: _distinct_thread_ids(checkpointer),
    )
    return DraftingRuntime(
        scheduler=scheduler, gateway=gateway, checkpointer=checkpointer
    )


def build_drafting_runtime_from_env(
    *,
    config: LivingADRConfig,
    storage_dir: Path,
    env: Mapping[str, str] | None = None,
    observability: Observability | None = None,
) -> DraftingRuntime | None:
    """Build the drafting runtime from env, or ``None`` when not configured.

    Requires ``ANTHROPIC_API_KEY`` (real Claude drafting) and ``GITHUB_APP_ID``
    (the provider that fetches the evidence drafting reads). When either is
    absent the receiver stays receive -> verify -> filter -> persist with no
    drafting and no review UI. The durable checkpointer, approval-audit store,
    and property-graph store are created once here.
    """

    resolved = os.environ if env is None else env
    api_key = (resolved.get(ANTHROPIC_API_KEY_ENV) or "").strip()
    app_id = (resolved.get(APP_ID_ENV) or "").strip()
    if not api_key or not app_id:
        return None

    claude_client = build_anthropic_claude_client(api_key=api_key)
    checkpointer = create_checkpointer(
        WorkflowCheckpointConfig(db_path=storage_dir / CHECKPOINT_DB_NAME)
    )
    # Lazy import: the property-graph adapter pulls in llama-index.
    from living_adr.approval.repository import SqliteApprovalAuditRepository
    from living_adr.graph.llamaindex_adapter import LlamaIndexPropertyGraphAdapter
    from living_adr.graph.persistence import GraphPersistenceConfig

    audit = SqliteApprovalAuditRepository(storage_dir / APPROVAL_AUDIT_DB_NAME)
    graph_store = LlamaIndexPropertyGraphAdapter(
        GraphPersistenceConfig(graph_root=storage_dir / GRAPH_DIR_NAME)
    )
    return build_drafting_runtime(
        db_path=storage_dir / INGESTION_DB_NAME,
        config=config,
        claude_client=claude_client,
        checkpointer=checkpointer,
        audit=audit,
        graph_store=graph_store,
        observability=observability,
    )


__all__ = [
    "DraftingRuntime",
    "build_draft_scheduler",
    "build_drafting_runtime",
    "build_drafting_runtime_from_env",
]
