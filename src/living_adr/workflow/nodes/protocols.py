"""Workflow node-seam protocols (feature 015, slice 1).

These ``Protocol`` definitions are the extension points downstream features plug
real implementations into, **without changing graph assembly** (FR-2; US-1/US-5):

* :class:`StructuralClassifierNode` — implemented by **feature 008** (real
  structural-change classification).
* :class:`ADRDraftNode` — implemented by **feature 008** (Claude-authored ADR
  drafting; this feature ships only a deterministic stub).
* :class:`HITLGateNode` — the interrupt/resume seam rendered by **feature 009**
  and whose approval capability is minted by **feature 010**.
* :class:`MutationHandoffNode` — routes approved decisions through feature 006's
  ``ApprovalBoundMutationService`` (**never** a graph adapter directly);
  durable decision/audit lifecycle is owned by **feature 010**.

A LangGraph node is a callable ``(WorkflowState) -> StateUpdate`` where
``StateUpdate`` is a partial mapping of :class:`WorkflowState` field names to new
values (LangGraph merges it into the running state). Conceptually each node
returns the next ``WorkflowState``; concretely it returns the subset of fields it
changed. Protocols are ``runtime_checkable`` so stubs/fakes can be asserted to
satisfy the seam in tests via ``isinstance``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any, Protocol, runtime_checkable

from living_adr.workflow.state import WorkflowState

#: Partial mapping of ``WorkflowState`` field names to updated values, merged
#: into the running graph state by LangGraph.
StateUpdate = Mapping[str, Any]


@runtime_checkable
class IntakeNode(Protocol):
    """Normalizes a feature-003 ``SCMEvent`` into initial graph state.

    Inputs: a :class:`WorkflowState` seeded with ``event`` (and optional replay
    metadata). Outputs: ``normalized_event_key``, ``evidence_refs``, and the
    advanced ``status``. No raw provider payloads enter the graph here.
    """

    def __call__(self, state: WorkflowState) -> StateUpdate: ...


@runtime_checkable
class StructuralClassifierNode(Protocol):
    """Classifier seam implemented by **feature 008**.

    Inputs: repository, normalized event, evidence references, and configured
    structural-change thresholds. Outputs: a ``classification`` result with zero
    or more ``StructuralChange`` values plus confidence/evidence ids, or
    ``adr_needed=False`` with a reason.
    """

    def __call__(self, state: WorkflowState) -> StateUpdate: ...


@runtime_checkable
class ADRDraftNode(Protocol):
    """Draft seam implemented by **feature 008**.

    Inputs: one selected ``StructuralChange``, change evidence, repository config,
    and an optional graph context query. Outputs: a provisional ``DraftRef`` with
    ``content_hash`` and citation ids. The stub renders deterministic Markdown
    with a stable hash and makes **no** external LLM call.
    """

    def __call__(self, state: WorkflowState) -> StateUpdate: ...


@runtime_checkable
class HITLGateNode(Protocol):
    """HITL interrupt/resume seam — UI by **feature 009**, capability by **010**.

    On invocation the node raises a LangGraph ``interrupt`` carrying a
    :class:`~living_adr.workflow.state.ReviewRequestPayload` and persists the
    pending checkpoint. It resumes from a
    :class:`~living_adr.workflow.state.ReviewResumeCommand`. The stub returns the
    payload and accepts synthetic resume commands in tests; it does not render UI
    or persist audit records.
    """

    def __call__(self, state: WorkflowState) -> StateUpdate: ...


@runtime_checkable
class MutationHandoffNode(Protocol):
    """Mutation handoff seam bound to feature 006 / completed by **feature 010**.

    Inputs: approved decision capability, draft/ADR reference, structural change,
    and the mutation request. Outputs: a ``MutationResult`` (mutation or terminal
    rejection/defer). Contract: call ``ApprovalBoundMutationService`` only; never
    call ``ArchitectureGraphStore`` directly. Capability minting, one-shot
    consumption, TTL, and audit durability are owned by feature 010.
    """

    def __call__(self, state: WorkflowState) -> StateUpdate: ...


__all__ = [
    "StateUpdate",
    "IntakeNode",
    "StructuralClassifierNode",
    "ADRDraftNode",
    "HITLGateNode",
    "MutationHandoffNode",
]
