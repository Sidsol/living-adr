"""Architecture graph read/write ports — the swap seam (feature 006).

These Protocols are the *only* contract workflow, MCP, and graph adapters share.
They are deliberately backend-agnostic: parameters and return types are
LivingADR domain values (``RepositoryIdentity``, ``ADRRecord``, ``NodeId``,
``GraphEdge``, ``WhyAnswer``, ...) and standard scalars/collections. No
LlamaIndex, LangSmith, FastAPI, MCP, or database type appears here, so a Neo4j,
RDF, or other adapter can replace the backing without changing callers
(architecture #service-boundaries).

Write/read separation is structural:

* :class:`ArchitectureGraphStore` (write side) requires both a
  ``RepositoryIdentity`` scope and an ``ApprovedReviewDecision`` on every method.
  In practice writes flow through ``ApprovalBoundMutationService`` — the only
  component allowed to call these methods.
* :class:`ArchitectureContextQuery` (read side) is repository-scoped and
  read-only: it exposes no mutation method and accepts no approval credential.
  The MCP context server depends only on this port.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from living_adr.core.adr import ADRRecord
from living_adr.core.approval import ApprovedReviewDecision
from living_adr.core.graph.models import (
    ADRPath,
    GraphEdge,
    GraphSnapshotRef,
    MigrationResult,
    NodeId,
    RelationshipType,
    SchemaVersion,
    WhyAnswer,
)
from living_adr.core.models import StructuralChange
from living_adr.core.repository import RepositoryIdentity


@runtime_checkable
class ArchitectureGraphStore(Protocol):
    """Write-side port for the architecture graph.

    Every mutation requires the repository scope and an ``ApprovedReviewDecision``
    capability; passing an invalid/None decision or a scope mismatch must raise
    before any backing write (the ``ApprovalBoundMutationService`` enforces this
    before delegating here).
    """

    def upsert_adr_node(
        self,
        repository: RepositoryIdentity,
        adr: ADRRecord,
        decision: ApprovedReviewDecision,
    ) -> NodeId: ...

    def add_relationship(
        self,
        repository: RepositoryIdentity,
        from_node: NodeId,
        to_node: NodeId,
        relationship: RelationshipType,
        decision: ApprovedReviewDecision,
    ) -> GraphEdge: ...

    def record_structural_change(
        self,
        repository: RepositoryIdentity,
        change: StructuralChange,
        linked_adr: NodeId,
        decision: ApprovedReviewDecision,
    ) -> NodeId: ...

    def supersede_adr(
        self,
        repository: RepositoryIdentity,
        prior_adr: NodeId,
        superseding_adr: NodeId,
        decision: ApprovedReviewDecision,
        reason: str,
    ) -> GraphEdge: ...

    def retract_adr(
        self,
        repository: RepositoryIdentity,
        adr: NodeId,
        decision: ApprovedReviewDecision,
        reason: str,
    ) -> GraphEdge: ...

    def migrate_schema(
        self,
        repository: RepositoryIdentity,
        target_version: SchemaVersion,
        decision: ApprovedReviewDecision,
    ) -> MigrationResult: ...


@runtime_checkable
class ArchitectureContextQuery(Protocol):
    """Read-side port for approved architecture context.

    Repository-scoped and read-only: no mutation method, no write credential, no
    SCM secrets. Returns domain DTOs that cite approved ADRs — never backend
    objects.
    """

    def traverse_from_code_area(
        self,
        repository: RepositoryIdentity,
        code_area_id: str,
        relationship_types: set[RelationshipType] | None = None,
        max_depth: int = 2,
        snapshot: GraphSnapshotRef | None = None,
    ) -> list[ADRPath]: ...

    def answer_why(
        self,
        repository: RepositoryIdentity,
        question: str,
        code_area_id: str | None = None,
        snapshot: GraphSnapshotRef | None = None,
        limit: int = 5,
    ) -> WhyAnswer: ...


__all__ = [
    "ArchitectureGraphStore",
    "ArchitectureContextQuery",
]
