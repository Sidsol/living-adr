"""Graph schema governance for the LlamaIndex property-graph adapter.

Centralizing the schema version, the allowed entity labels, and the allowed
relationship labels here is the adapter's primary defence against property-graph
drift and GraphRAG false edges (architecture #anti-patterns, FM-08/FM-10): the
adapter persists *only* labels enumerated in this module, and any change to the
projection shape must bump :data:`ADAPTER_SCHEMA_VERSION`.

Slice 1 introduces the version constant and error types the adapter needs to
initialize/open a repository graph; slice 2 expands this module with the metadata
DTO, allowed-label sets, and migration mapping.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from living_adr.core.graph.models import (
    RelationshipType,
    SchemaVersion,
    UnsupportedRelationshipError,
)
from living_adr.core.repository import RepositoryIdentity

#: Human-readable adapter identity recorded in graph metadata and conformance.
ADAPTER_NAME = "llamaindex-property-graph"

#: The single schema version this adapter writes and supports reading.
ADAPTER_SCHEMA_VERSION = SchemaVersion(major=1, minor=0)

# --- allowed entity labels (schema-constrained extraction, FM-08/FM-10) ------
ENTITY_LABEL_ADR = "adr"
ENTITY_LABEL_COMPONENT = "component"
ENTITY_LABEL_EVIDENCE = "evidence"
ENTITY_LABEL_STRUCTURAL_CHANGE = "structural_change"
ENTITY_LABEL_API = "api"
ENTITY_LABEL_SCHEMA = "schema"
ENTITY_LABEL_PR = "pull_request"
ENTITY_LABEL_COMMIT = "commit"

#: The only entity labels this adapter will persist. Anything else is an
#: unsupported extraction and must be rejected/quarantined before persistence.
ENTITY_LABELS: frozenset[str] = frozenset(
    {
        ENTITY_LABEL_ADR,
        ENTITY_LABEL_COMPONENT,
        ENTITY_LABEL_EVIDENCE,
        ENTITY_LABEL_STRUCTURAL_CHANGE,
        ENTITY_LABEL_API,
        ENTITY_LABEL_SCHEMA,
        ENTITY_LABEL_PR,
        ENTITY_LABEL_COMMIT,
    }
)

#: Allowed relationship labels, sourced from feature 006's ``RelationshipType``
#: (the single source of truth) so the adapter can never widen the edge
#: vocabulary without a model change there.
RELATIONSHIP_LABELS: frozenset[str] = frozenset(m.value for m in RelationshipType)


class SchemaMetadataError(Exception):
    """Base error for schema-metadata problems (missing/unsupported/mismatch)."""


class UnsupportedSchemaVersionError(SchemaMetadataError):
    """Raised when a persisted graph declares a version this adapter cannot read."""


class UnsupportedEntityLabelError(ValueError):
    """Raised when an entity label is not in the adapter's allowed set."""


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class GraphSchemaMetadata(_Frozen):
    """Typed view of a repository graph's persisted schema metadata."""

    repository: RepositoryIdentity
    schema_version: SchemaVersion
    adapter_name: str
    revision: int = 0


def is_supported(version: SchemaVersion) -> bool:
    """Return whether ``version`` is readable by this adapter build."""

    return (version.major, version.minor) == (
        ADAPTER_SCHEMA_VERSION.major,
        ADAPTER_SCHEMA_VERSION.minor,
    )


def validate_relationship_label(label: str) -> RelationshipType:
    """Return the ``RelationshipType`` for ``label`` or raise on an unknown one.

    Delegates to feature 006's ``RelationshipType.from_label`` so the failure
    mode (``UnsupportedRelationshipError``) is identical across the codebase.
    """

    return RelationshipType.from_label(label)


def validate_entity_label(label: str) -> str:
    """Return ``label`` if it is an allowed entity label, else raise.

    Schema-constrained entity persistence is the adapter's defence against
    false nodes from unconstrained extractors (US-7, FM-08/FM-10).
    """

    if label not in ENTITY_LABELS:
        supported = ", ".join(sorted(ENTITY_LABELS))
        raise UnsupportedEntityLabelError(
            f"Unsupported entity label {label!r}; supported: {supported}."
        )
    return label


__all__ = [
    "ADAPTER_NAME",
    "ADAPTER_SCHEMA_VERSION",
    "ENTITY_LABELS",
    "ENTITY_LABEL_ADR",
    "ENTITY_LABEL_API",
    "ENTITY_LABEL_COMMIT",
    "ENTITY_LABEL_COMPONENT",
    "ENTITY_LABEL_EVIDENCE",
    "ENTITY_LABEL_PR",
    "ENTITY_LABEL_SCHEMA",
    "ENTITY_LABEL_STRUCTURAL_CHANGE",
    "RELATIONSHIP_LABELS",
    "GraphSchemaMetadata",
    "SchemaMetadataError",
    "UnsupportedEntityLabelError",
    "UnsupportedRelationshipError",
    "UnsupportedSchemaVersionError",
    "is_supported",
    "validate_entity_label",
    "validate_relationship_label",
]
