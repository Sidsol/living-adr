"""Domain <-> LlamaIndex property-graph mapping (the only LlamaIndex boundary).

This module is the one place that converts LivingADR domain values
(``ADRRecord``, ``GraphEdge``, ``StructuralChange`` + provenance) into the
LlamaIndex ``EntityNode``/``Relation`` payloads the backing store understands,
validating every entity and relationship label against the adapter schema before
anything is persisted. Schema-constrained mapping is the adapter's defence
against unconstrained-extractor false edges (US-7, FM-08/FM-10): an unsupported
label is rejected/quarantined here, never written.
"""

from __future__ import annotations

from llama_index.core.graph_stores.types import EntityNode, Relation

from living_adr.core.adr import ADRRecord
from living_adr.core.graph.models import GraphEdge, UnsupportedRelationshipError
from living_adr.core.models import StructuralChange
from living_adr.core.repository import RepositoryIdentity
from living_adr.graph.provenance import (
    EntityProvenance,
    provenance_to_properties,
    scope_key,
)
from living_adr.graph.schema import (
    ENTITY_LABEL_ADR,
    ENTITY_LABEL_STRUCTURAL_CHANGE,
    UnsupportedEntityLabelError,
    validate_entity_label,
    validate_relationship_label,
)

# --- non-provenance node/edge property keys ----------------------------------
SCOPE_KEY_PROP = "scope_key"
NODE_KIND_KEY = "node_kind"
ADR_ID_KEY = "adr_id"
TITLE_KEY = "title"
STATUS_KEY = "status"
CONTENT_HASH_KEY = "content_hash"
CHANGE_ID_KEY = "change_id"
CHANGE_TYPE_KEY = "change_type"
REASON_KEY = "reason"


class MappingValidationError(ValueError):
    """Raised when a domain value cannot be mapped to a valid graph payload."""


def adr_node_value(adr: ADRRecord) -> str:
    return f"adr:{adr.adr_id}"


def structural_change_node_value(change: StructuralChange) -> str:
    return f"change:{change.change_id}"


def adr_to_entity_node(
    repository: RepositoryIdentity,
    adr: ADRRecord,
    provenance: EntityProvenance,
) -> EntityNode:
    """Map an approved ``ADRRecord`` to a validated, provenanced ``EntityNode``."""

    label = validate_entity_label(ENTITY_LABEL_ADR)
    properties: dict[str, str] = {
        SCOPE_KEY_PROP: scope_key(repository),
        NODE_KIND_KEY: ENTITY_LABEL_ADR,
        ADR_ID_KEY: adr.adr_id,
        TITLE_KEY: adr.title,
        STATUS_KEY: adr.status.value,
        CONTENT_HASH_KEY: adr.content_hash,
    }
    properties.update(provenance_to_properties(provenance))
    return EntityNode(label=label, name=adr_node_value(adr), properties=properties)


def structural_change_to_entity_node(
    repository: RepositoryIdentity,
    change: StructuralChange,
    provenance: EntityProvenance,
) -> EntityNode:
    """Map a ``StructuralChange`` to a validated, provenanced ``EntityNode``."""

    label = validate_entity_label(ENTITY_LABEL_STRUCTURAL_CHANGE)
    properties: dict[str, str] = {
        SCOPE_KEY_PROP: scope_key(repository),
        NODE_KIND_KEY: ENTITY_LABEL_STRUCTURAL_CHANGE,
        CHANGE_ID_KEY: change.change_id,
        CHANGE_TYPE_KEY: change.change_type,
    }
    properties.update(provenance_to_properties(provenance))
    return EntityNode(
        label=label,
        name=structural_change_node_value(change),
        properties=properties,
    )


def edge_to_relation(edge: GraphEdge, provenance: EntityProvenance) -> Relation:
    """Map a domain ``GraphEdge`` to a validated, provenanced ``Relation``."""

    label = validate_relationship_label(edge.relationship.value).value
    properties: dict[str, str] = {
        SCOPE_KEY_PROP: scope_key(edge.repository),
        REASON_KEY: edge.reason or "",
    }
    properties.update(provenance_to_properties(provenance))
    return Relation(
        label=label,
        source_id=edge.from_node.value,
        target_id=edge.to_node.value,
        properties=properties,
    )


def validate_extracted_triple(
    source_label: str, relationship_label: str, target_label: str
) -> None:
    """Validate an *extracted* triple's labels before it can be persisted.

    Unsupported entity or relationship labels (typical of unconstrained LLM
    path extraction) are quarantined here as a :class:`MappingValidationError`
    rather than becoming authoritative graph edges.
    """

    try:
        validate_entity_label(source_label)
        validate_entity_label(target_label)
        validate_relationship_label(relationship_label)
    except (UnsupportedEntityLabelError, UnsupportedRelationshipError) as exc:
        raise MappingValidationError(
            f"quarantined unsupported extracted triple "
            f"({source_label!r})-[{relationship_label!r}]->({target_label!r}): {exc}"
        ) from exc


__all__ = [
    "ADR_ID_KEY",
    "CHANGE_ID_KEY",
    "CHANGE_TYPE_KEY",
    "CONTENT_HASH_KEY",
    "NODE_KIND_KEY",
    "REASON_KEY",
    "SCOPE_KEY_PROP",
    "STATUS_KEY",
    "TITLE_KEY",
    "MappingValidationError",
    "adr_node_value",
    "adr_to_entity_node",
    "edge_to_relation",
    "structural_change_node_value",
    "structural_change_to_entity_node",
    "validate_extracted_triple",
]
