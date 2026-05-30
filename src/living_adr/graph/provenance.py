"""Provenance records for extracted graph entities and edges.

Every node and edge this adapter persists must cite the approved ADR/evidence it
was derived from, so false edges can be audited and repaired (US-4, US-7,
FM-08/FM-10). Provenance is stored as flat string properties on the underlying
LlamaIndex nodes/relations (keys namespaced with a ``prov_`` prefix), and is
reconstructed into a typed :class:`EntityProvenance` on read.

This module is pure domain logic — it imports no LlamaIndex types — so the
completeness rules can be tested in isolation.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator

from living_adr.core.graph.models import SchemaVersion
from living_adr.core.repository import RepositoryIdentity


class ExtractionMethod(StrEnum):
    """How an entity/edge was derived. Default extraction is deterministic."""

    DETERMINISTIC_ADR_PROJECTION = "deterministic_adr_projection"
    STRUCTURAL_CHANGE_PROJECTION = "structural_change_projection"
    SCHEMA_CONSTRAINED_EXTRACTION = "schema_constrained_extraction"


# --- provenance property keys (namespaced, stored on nodes/relations) --------
PROV_SCOPE_KEY = "prov_scope_key"
PROV_SOURCE_ADR_ID = "prov_source_adr_id"
PROV_EVIDENCE_ID = "prov_evidence_id"
PROV_DECISION_ID = "prov_decision_id"
PROV_EXTRACTION_METHOD = "prov_extraction_method"
PROV_EXTRACTED_AT = "prov_extracted_at"
PROV_SCHEMA_VERSION = "prov_schema_version"

#: Keys that must be present and non-empty for provenance to be considered
#: complete. ``evidence_id`` is intentionally optional (an ADR node may have no
#: single evidence id) but the decision/ADR/extraction lineage is mandatory.
REQUIRED_PROV_KEYS: tuple[str, ...] = (
    PROV_SCOPE_KEY,
    PROV_SOURCE_ADR_ID,
    PROV_DECISION_ID,
    PROV_EXTRACTION_METHOD,
    PROV_EXTRACTED_AT,
    PROV_SCHEMA_VERSION,
)


class MissingProvenanceError(ValueError):
    """Raised when a node/edge lacks required provenance before persistence."""


class ProvenanceRepositoryMismatchError(ValueError):
    """Raised when provenance scope does not match the querying repository."""


class _Frozen(BaseModel):
    model_config = ConfigDict(frozen=True)


class EntityProvenance(_Frozen):
    """Typed provenance for a single persisted node or edge."""

    repository: RepositoryIdentity
    source_adr_id: str
    decision_id: str
    extraction_method: ExtractionMethod
    extracted_at: datetime
    schema_version: SchemaVersion
    evidence_id: str | None = None

    @field_validator("source_adr_id", "decision_id")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("provenance ids must not be empty or whitespace")
        return stripped


def scope_key(repository: RepositoryIdentity) -> str:
    """A repository scope key that also distinguishes equal keys by opaque id."""

    return f"{repository.key}#{repository.repo_id}"


def _parse_schema_version(label: str) -> SchemaVersion:
    text = label.strip().lstrip("vV")
    major, _, minor = text.partition(".")
    return SchemaVersion(major=int(major), minor=int(minor or 0))


def provenance_to_properties(prov: EntityProvenance) -> dict[str, str]:
    """Flatten provenance to namespaced string properties for storage."""

    return {
        PROV_SCOPE_KEY: scope_key(prov.repository),
        PROV_SOURCE_ADR_ID: prov.source_adr_id,
        PROV_DECISION_ID: prov.decision_id,
        PROV_EXTRACTION_METHOD: prov.extraction_method.value,
        PROV_EXTRACTED_AT: prov.extracted_at.isoformat(),
        PROV_SCHEMA_VERSION: prov.schema_version.label,
        PROV_EVIDENCE_ID: prov.evidence_id or "",
    }


def assert_complete(properties: dict) -> None:
    """Raise :class:`MissingProvenanceError` if required prov keys are absent."""

    missing = [k for k in REQUIRED_PROV_KEYS if not str(properties.get(k, "")).strip()]
    if missing:
        raise MissingProvenanceError(
            f"node/edge is missing required provenance: {', '.join(sorted(missing))}"
        )


def assert_scope(repository: RepositoryIdentity, properties: dict) -> None:
    """Raise if stored provenance scope does not match ``repository``."""

    stored = str(properties.get(PROV_SCOPE_KEY, "")).strip()
    if stored != scope_key(repository):
        raise ProvenanceRepositoryMismatchError(
            f"provenance scope {stored!r} does not match repository "
            f"{scope_key(repository)!r}"
        )


def provenance_from_properties(
    repository: RepositoryIdentity, properties: dict
) -> EntityProvenance:
    """Rebuild a typed :class:`EntityProvenance` from stored properties."""

    assert_complete(properties)
    assert_scope(repository, properties)
    evidence = str(properties.get(PROV_EVIDENCE_ID, "")).strip() or None
    return EntityProvenance(
        repository=repository,
        source_adr_id=str(properties[PROV_SOURCE_ADR_ID]),
        decision_id=str(properties[PROV_DECISION_ID]),
        extraction_method=ExtractionMethod(str(properties[PROV_EXTRACTION_METHOD])),
        extracted_at=datetime.fromisoformat(str(properties[PROV_EXTRACTED_AT])),
        schema_version=_parse_schema_version(str(properties[PROV_SCHEMA_VERSION])),
        evidence_id=evidence,
    )


__all__ = [
    "PROV_DECISION_ID",
    "PROV_EVIDENCE_ID",
    "PROV_EXTRACTED_AT",
    "PROV_EXTRACTION_METHOD",
    "PROV_SCHEMA_VERSION",
    "PROV_SCOPE_KEY",
    "PROV_SOURCE_ADR_ID",
    "REQUIRED_PROV_KEYS",
    "EntityProvenance",
    "ExtractionMethod",
    "MissingProvenanceError",
    "ProvenanceRepositoryMismatchError",
    "assert_complete",
    "assert_scope",
    "provenance_from_properties",
    "provenance_to_properties",
    "scope_key",
]
