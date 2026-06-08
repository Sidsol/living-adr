"""Compile the live workflow graph wired with the REAL classifier + draft nodes.

This is the Phase 3 assembly point: it builds the orchestration graph with the
evidence-backed real classifier node and the Claude-backed real draft node (so a
merged PR yields a genuine, classifier-grounded ADR draft), keeping the intake,
HITL gate, mutation handoff, and terminal nodes as the existing deterministic
stubs (the HITL UI is feature 009 / Phase 4; the approval-bound mutation +
publish is Phase 5). The compiled graph is wrapped in a
:class:`ReviewResumeService` so the workflow-service drives it through the same
start/resume seam the stub graph uses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from living_adr.workflow.graph import build_workflow_graph
from living_adr.workflow.live_nodes import (
    CompositeStructuralChangeProducer,
    EvidenceBackedClassifierNode,
    EvidenceBackedDraftInputResolver,
)
from living_adr.workflow.nodes.adr_draft import ClaudeADRDraftNode
from living_adr.workflow.nodes.stubs import (
    DeferralTerminalNode,
    RejectionTerminalNode,
    StubHITLGateNode,
    StubIntakeNode,
    StubMutationHandoffNode,
)
from living_adr.workflow.review_resume import ReviewResumeService

if TYPE_CHECKING:
    from langgraph.checkpoint.base import BaseCheckpointSaver
    from langgraph.graph.state import CompiledStateGraph

    from living_adr.core.config import LivingADRConfig
    from living_adr.core.llm import ClaudeClient
    from living_adr.core.observability import Observability
    from living_adr.workflow.drafting.context import ContextQuery
    from living_adr.workflow.live_nodes import EvidenceSource, StructuralChangeProducer
    from living_adr.workflow.nodes.stubs import GraphMutationService


def build_live_workflow_app(
    *,
    source: EvidenceSource,
    config: LivingADRConfig,
    claude_client: ClaudeClient,
    checkpointer: BaseCheckpointSaver | None = None,
    context_query: ContextQuery | None = None,
    producer: StructuralChangeProducer | None = None,
    minting: object | None = None,
    mutation_service: GraphMutationService | None = None,
    model_id: str | None = None,
) -> CompiledStateGraph:
    """Compile the workflow graph with the real classifier + Claude draft nodes."""

    shared_producer = producer or CompositeStructuralChangeProducer()
    classifier = EvidenceBackedClassifierNode(
        source=source, producer=shared_producer
    )
    resolver = EvidenceBackedDraftInputResolver(
        source=source, config=config, producer=shared_producer
    )
    draft_kwargs: dict[str, object] = {
        "resolver": resolver,
        "claude_client": claude_client,
        "context_query": context_query,
    }
    if model_id is not None:
        draft_kwargs["model_id"] = model_id
    draft = ClaudeADRDraftNode(**draft_kwargs)

    return build_workflow_graph(
        intake=StubIntakeNode(),
        classifier=classifier,
        draft=draft,
        hitl=StubHITLGateNode(),
        mutation=StubMutationHandoffNode(mutation_service),
        rejection=RejectionTerminalNode(),
        deferral=DeferralTerminalNode(),
        minting=minting,
        checkpointer=checkpointer,
    )


def build_live_review_service(
    *,
    source: EvidenceSource,
    config: LivingADRConfig,
    claude_client: ClaudeClient,
    checkpointer: BaseCheckpointSaver | None = None,
    context_query: ContextQuery | None = None,
    producer: StructuralChangeProducer | None = None,
    minting: object | None = None,
    mutation_service: GraphMutationService | None = None,
    model_id: str | None = None,
    observability: Observability | None = None,
) -> ReviewResumeService:
    """Build the start/resume service over the live (real-node) workflow graph."""

    app = build_live_workflow_app(
        source=source,
        config=config,
        claude_client=claude_client,
        checkpointer=checkpointer,
        context_query=context_query,
        producer=producer,
        minting=minting,
        mutation_service=mutation_service,
        model_id=model_id,
    )
    return ReviewResumeService(app, observability=observability)


__all__ = ["build_live_workflow_app", "build_live_review_service"]
