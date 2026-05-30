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

from living_adr.core.graph.models import SchemaVersion

#: Human-readable adapter identity recorded in graph metadata and conformance.
ADAPTER_NAME = "llamaindex-property-graph"

#: The single schema version this adapter writes and supports reading.
ADAPTER_SCHEMA_VERSION = SchemaVersion(major=1, minor=0)


class SchemaMetadataError(Exception):
    """Base error for schema-metadata problems (missing/unsupported/mismatch)."""


class UnsupportedSchemaVersionError(SchemaMetadataError):
    """Raised when a persisted graph declares a version this adapter cannot read."""


def is_supported(version: SchemaVersion) -> bool:
    """Return whether ``version`` is readable by this adapter build."""

    return (version.major, version.minor) == (
        ADAPTER_SCHEMA_VERSION.major,
        ADAPTER_SCHEMA_VERSION.minor,
    )


__all__ = [
    "ADAPTER_NAME",
    "ADAPTER_SCHEMA_VERSION",
    "SchemaMetadataError",
    "UnsupportedSchemaVersionError",
    "is_supported",
]
