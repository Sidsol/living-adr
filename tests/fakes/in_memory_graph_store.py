"""In-memory ``ArchitectureGraphStore`` / ``ArchitectureContextQuery`` fake.

This is the reference test double feature 006 ships so the adapter conformance
suite has something concrete to validate *before* the real LlamaIndex adapter
exists (feature 007). It implements both ports using only LivingADR domain
values, enforces repository scoping, and counts writes so tests can assert that
invalid approvals make zero adapter calls.

It is intentionally **not** an approval gate: approval enforcement lives in
``ApprovalBoundMutationService``. Wiring this fake behind that service is exactly
how a real adapter is expected to be used.
"""

from __future__ import annotations

from living_adr.core.adr import ADRRecord
from living_adr.core.approval import ApprovedReviewDecision
from living_adr.core.graph.models import (
    ADRPath,
    ADRRef,
    GraphEdge,
    MigrationResult,
    NodeId,
    ProvenancedADR,
    RelationshipType,
    SchemaVersion,
    WhyAnswer,
)
from living_adr.core.models import StructuralChange
from living_adr.core.repository import RepositoryIdentity


class InMemoryGraphStore:
    """Repository-scoped in-memory graph store + query (domain values only)."""

    def __init__(self) -> None:
        self.write_calls = 0
        # repository.key -> {node_value: ADRRecord}
        self._nodes: dict[str, dict[str, ADRRecord]] = {}
        # repository.key -> list[GraphEdge]
        self._edges: dict[str, list[GraphEdge]] = {}
        # repository.key -> SchemaVersion
        self._schema: dict[str, SchemaVersion] = {}

    @staticmethod
    def _require_scope(
        repository: RepositoryIdentity, scoped: RepositoryIdentity
    ) -> None:
        if repository != scoped:
            raise ValueError("repository scope mismatch in graph store")

    # ----------------------------------------------------------------- writes
    def upsert_adr_node(
        self,
        repository: RepositoryIdentity,
        adr: ADRRecord,
        decision: ApprovedReviewDecision,
    ) -> NodeId:
        self._require_scope(repository, adr.repository)
        self.write_calls += 1
        node = NodeId(repository=repository, value=f"node:{adr.adr_id}")
        self._nodes.setdefault(repository.key, {})[node.value] = adr
        return node

    def add_relationship(
        self,
        repository: RepositoryIdentity,
        from_node: NodeId,
        to_node: NodeId,
        relationship: RelationshipType,
        decision: ApprovedReviewDecision,
    ) -> GraphEdge:
        self.write_calls += 1
        edge = GraphEdge(
            repository=repository,
            from_node=from_node,
            to_node=to_node,
            relationship=relationship,
        )
        self._edges.setdefault(repository.key, []).append(edge)
        return edge

    def record_structural_change(
        self,
        repository: RepositoryIdentity,
        change: StructuralChange,
        linked_adr: NodeId,
        decision: ApprovedReviewDecision,
    ) -> NodeId:
        self._require_scope(repository, change.repository)
        self.write_calls += 1
        return NodeId(repository=repository, value=f"change:{change.change_id}")

    def supersede_adr(
        self,
        repository: RepositoryIdentity,
        prior_adr: NodeId,
        superseding_adr: NodeId,
        decision: ApprovedReviewDecision,
        reason: str,
    ) -> GraphEdge:
        self.write_calls += 1
        edge = GraphEdge(
            repository=repository,
            from_node=superseding_adr,
            to_node=prior_adr,
            relationship=RelationshipType.SUPERSEDES,
            reason=reason,
        )
        self._edges.setdefault(repository.key, []).append(edge)
        return edge

    def retract_adr(
        self,
        repository: RepositoryIdentity,
        adr: NodeId,
        decision: ApprovedReviewDecision,
        reason: str,
    ) -> GraphEdge:
        self.write_calls += 1
        edge = GraphEdge(
            repository=repository,
            from_node=adr,
            to_node=adr,
            relationship=RelationshipType.RETRACTS,
            reason=reason,
        )
        self._edges.setdefault(repository.key, []).append(edge)
        return edge

    def migrate_schema(
        self,
        repository: RepositoryIdentity,
        target_version: SchemaVersion,
        decision: ApprovedReviewDecision,
    ) -> MigrationResult:
        self.write_calls += 1
        current = self._schema.get(repository.key, SchemaVersion(major=1, minor=0))
        self._schema[repository.key] = target_version
        return MigrationResult(
            repository=repository,
            from_version=current,
            to_version=target_version,
            applied=True,
        )

    # ------------------------------------------------------------------ reads
    def traverse_from_code_area(
        self,
        repository: RepositoryIdentity,
        code_area_id: str,
        relationship_types: set[RelationshipType] | None = None,
        max_depth: int = 2,
        snapshot=None,
    ) -> list[ADRPath]:
        records = self._nodes.get(repository.key, {})
        if not records:
            return []
        adrs = tuple(
            ADRRef(
                repository=repository,
                adr_id=rec.adr_id,
                title=rec.title,
                status=rec.status.value,
            )
            for rec in records.values()
        )
        return [
            ADRPath(
                repository=repository,
                code_area_id=code_area_id,
                edges=tuple(self._edges.get(repository.key, [])),
                adrs=adrs,
            )
        ]

    def answer_why(
        self,
        repository: RepositoryIdentity,
        question: str,
        code_area_id: str | None = None,
        snapshot=None,
        limit: int = 5,
    ) -> WhyAnswer:
        records = list(self._nodes.get(repository.key, {}).values())
        if not records:
            return WhyAnswer(
                repository=repository,
                question=question,
                answer="No approved ADR context is available for this repository.",
                adr_id=None,
                citations=(),
                found=False,
            )
        rec = records[0]
        ref = ADRRef(
            repository=repository,
            adr_id=rec.adr_id,
            title=rec.title,
            status=rec.status.value,
        )
        return WhyAnswer(
            repository=repository,
            question=question,
            answer=f"Approved decision {rec.adr_id}: {rec.title}.",
            adr_id=rec.adr_id,
            citations=(f"adr:{rec.adr_id}",),
            found=True,
            provenance=(
                ProvenancedADR(
                    repository=repository,
                    adr=ref,
                    citations=(f"adr:{rec.adr_id}",),
                ),
            ),
        )


__all__ = ["InMemoryGraphStore"]
