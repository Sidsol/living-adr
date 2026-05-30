"""Stable graph contract exports (feature 006).

Downstream features import the graph vocabulary, ports, and approval-bound
mutation service from this stable package path rather than from individual
modules. Concrete adapters (feature 007+) live elsewhere and are never imported
here, keeping the seam backend-agnostic.
"""

from living_adr.core.graph.models import (
    ADRPath,
    ADRRef,
    ConformanceReport,
    GraphEdge,
    GraphSnapshotRef,
    MigrationResult,
    NodeId,
    ProvenancedADR,
    RelationshipType,
    SchemaVersion,
    UnsupportedRelationshipError,
    WhyAnswer,
    utc_now,
)
from living_adr.core.graph.ports import (
    ArchitectureContextQuery,
    ArchitectureGraphStore,
)

__all__ = [
    "ADRPath",
    "ADRRef",
    "ArchitectureContextQuery",
    "ArchitectureGraphStore",
    "ConformanceReport",
    "GraphEdge",
    "GraphSnapshotRef",
    "MigrationResult",
    "NodeId",
    "ProvenancedADR",
    "RelationshipType",
    "SchemaVersion",
    "UnsupportedRelationshipError",
    "WhyAnswer",
    "utc_now",
]
