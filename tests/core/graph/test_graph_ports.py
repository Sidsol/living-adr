"""Slice 3 (US-3, US-6) tests: graph read/write port signatures.

These tests pin the swap-seam contract: every write method requires both a
``repository`` scope and an ``ApprovedReviewDecision`` (``decision``); every read
method requires ``repository`` and exposes no mutation capability and no
write credential. Both ports are runtime-checkable Protocols built only from
LivingADR domain values.
"""

from __future__ import annotations

import inspect

from living_adr.core.adr import ADRRecord
from living_adr.core.approval import ApprovedReviewDecision
from living_adr.core.graph.models import (
    ADRPath,
    GraphEdge,
    MigrationResult,
    NodeId,
    RelationshipType,
    SchemaVersion,
    WhyAnswer,
)
from living_adr.core.graph.ports import (
    ArchitectureContextQuery,
    ArchitectureGraphStore,
)
from living_adr.core.repository import RepositoryIdentity

WRITE_METHODS = (
    "upsert_adr_node",
    "add_relationship",
    "record_structural_change",
    "supersede_adr",
    "retract_adr",
    "migrate_schema",
)
READ_METHODS = ("traverse_from_code_area", "answer_why")


def _params(cls: type, method: str) -> set[str]:
    sig = inspect.signature(getattr(cls, method))
    return {p for p in sig.parameters if p != "self"}


def test_every_write_method_requires_repository_and_decision() -> None:
    for method in WRITE_METHODS:
        params = _params(ArchitectureGraphStore, method)
        assert "repository" in params, f"{method} missing repository scope"
        assert "decision" in params, f"{method} missing approved decision"


def test_every_read_method_requires_repository() -> None:
    for method in READ_METHODS:
        params = _params(ArchitectureContextQuery, method)
        assert "repository" in params, f"{method} missing repository scope"


def test_read_port_exposes_no_mutation_or_write_credential() -> None:
    query_methods = {
        name
        for name, _ in inspect.getmembers(
            ArchitectureContextQuery, predicate=inspect.isfunction
        )
        if not name.startswith("_")
    }
    # No write-side method names leak onto the read port.
    assert query_methods.isdisjoint(set(WRITE_METHODS))
    # No method on the read port accepts an approval/decision credential.
    for method in READ_METHODS:
        assert "decision" not in _params(ArchitectureContextQuery, method)


def test_ports_are_runtime_checkable_protocols() -> None:
    class Store:
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
            change: object,
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

    class Query:
        def traverse_from_code_area(
            self,
            repository: RepositoryIdentity,
            code_area_id: str,
            relationship_types: set[RelationshipType] | None = None,
            max_depth: int = 2,
            snapshot: object | None = None,
        ) -> list[ADRPath]:
            return []

        def answer_why(
            self,
            repository: RepositoryIdentity,
            question: str,
            code_area_id: str | None = None,
            snapshot: object | None = None,
            limit: int = 5,
        ) -> WhyAnswer:
            raise NotImplementedError

    assert isinstance(Store(), ArchitectureGraphStore)
    assert isinstance(Query(), ArchitectureContextQuery)
    # A read-only object is NOT a valid write store.
    assert not isinstance(Query(), ArchitectureGraphStore)
