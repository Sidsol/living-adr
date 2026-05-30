"""LangGraph workflow assembly with stub-node seams (feature 015, slice 3).

Compiles the production orchestration topology:

``intake -> classify -> [adr_needed?] -> draft -> HITL interrupt -> [action?]``
routing approved reviews to the mutation handoff and reject/defer to terminal
nodes. The classifier and draft nodes are injected seams (feature 008), the HITL
gate is the feature 009/010 interrupt seam, and the mutation handoff routes only
through feature 006's ``ApprovalBoundMutationService`` (US-1; FR-4).

The graph is fully executable with the deterministic stubs in
:mod:`living_adr.workflow.nodes.stubs`, so this topology and routing are testable
and replayable before the real nodes land. The checkpointer (feature 015 slice 2)
is injected so in-flight state is durable.
"""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from living_adr.workflow.nodes.protocols import (
    ADRDraftNode,
    HITLGateNode,
    IntakeNode,
    MutationHandoffNode,
    StructuralClassifierNode,
)
from living_adr.workflow.nodes.stubs import (
    DeferralTerminalNode,
    GraphMutationService,
    RejectionTerminalNode,
    StubClassifierNode,
    StubDraftNode,
    StubHITLGateNode,
    StubIntakeNode,
    StubMutationHandoffNode,
)
from living_adr.workflow.state import ReviewAction, WorkflowState

# Stable node names — also the values surfaced in checkpoint ``next`` tuples.
NODE_INTAKE = "intake"
NODE_CLASSIFY = "classify"
NODE_DRAFT = "draft"
NODE_HITL = "hitl"
NODE_MUTATION = "mutation"
NODE_REJECTION = "rejection"
NODE_DEFERRAL = "deferral"


def _route_after_classify(state: WorkflowState) -> str:
    """Branch to drafting when an ADR is needed, else terminate (no-ADR path)."""

    if state.classification is not None and state.classification.adr_needed:
        return NODE_DRAFT
    return END


def _route_after_hitl(state: WorkflowState) -> str:
    """Route by reviewer action: approvals mutate, reject/defer terminate.

    Reject and defer must **never** reach the mutation handoff (US-3/US-5).
    """

    command = state.resume_command
    if command is not None and command.action.authorizes_mutation:
        return NODE_MUTATION
    if command is not None and command.action is ReviewAction.DEFER:
        return NODE_DEFERRAL
    return NODE_REJECTION


def build_workflow_graph(
    *,
    intake: IntakeNode,
    classifier: StructuralClassifierNode,
    draft: ADRDraftNode,
    hitl: HITLGateNode,
    mutation: MutationHandoffNode,
    rejection: object,
    deferral: object,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    """Assemble and compile the workflow graph from injected node seams."""

    builder = StateGraph(WorkflowState)
    builder.add_node(NODE_INTAKE, intake)
    builder.add_node(NODE_CLASSIFY, classifier)
    builder.add_node(NODE_DRAFT, draft)
    builder.add_node(NODE_HITL, hitl)
    builder.add_node(NODE_MUTATION, mutation)
    builder.add_node(NODE_REJECTION, rejection)
    builder.add_node(NODE_DEFERRAL, deferral)

    builder.add_edge(START, NODE_INTAKE)
    builder.add_edge(NODE_INTAKE, NODE_CLASSIFY)
    builder.add_conditional_edges(
        NODE_CLASSIFY, _route_after_classify, {NODE_DRAFT: NODE_DRAFT, END: END}
    )
    builder.add_edge(NODE_DRAFT, NODE_HITL)
    builder.add_conditional_edges(
        NODE_HITL,
        _route_after_hitl,
        {
            NODE_MUTATION: NODE_MUTATION,
            NODE_REJECTION: NODE_REJECTION,
            NODE_DEFERRAL: NODE_DEFERRAL,
        },
    )
    builder.add_edge(NODE_MUTATION, END)
    builder.add_edge(NODE_REJECTION, END)
    builder.add_edge(NODE_DEFERRAL, END)

    return builder.compile(checkpointer=checkpointer)


def build_default_workflow_graph(
    *,
    checkpointer: BaseCheckpointSaver | None = None,
    classifier: StructuralClassifierNode | None = None,
    mutation_service: GraphMutationService | None = None,
) -> CompiledStateGraph:
    """Compile the graph wired with the deterministic stub nodes.

    ``classifier`` may be overridden (e.g. a no-ADR variant for terminal-path
    tests); ``mutation_service`` injects feature 006's approval-bound service for
    the mutation handoff. With no service the handoff records intent without an
    authoritative write.
    """

    return build_workflow_graph(
        intake=StubIntakeNode(),
        classifier=classifier or StubClassifierNode(),
        draft=StubDraftNode(),
        hitl=StubHITLGateNode(),
        mutation=StubMutationHandoffNode(mutation_service),
        rejection=RejectionTerminalNode(),
        deferral=DeferralTerminalNode(),
        checkpointer=checkpointer,
    )


__all__ = [
    "NODE_INTAKE",
    "NODE_CLASSIFY",
    "NODE_DRAFT",
    "NODE_HITL",
    "NODE_MUTATION",
    "NODE_REJECTION",
    "NODE_DEFERRAL",
    "build_workflow_graph",
    "build_default_workflow_graph",
]
