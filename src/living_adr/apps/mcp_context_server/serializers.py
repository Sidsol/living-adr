"""Domain DTO -> MCP-safe response serialization (feature 012).

Tool handlers must return plain, JSON-serialisable mappings that cite approved
ADRs/evidence — never LlamaIndex objects, storage handles, SQLite handles, or
internal graph adapter types (FR-6). Repository scope is rendered as the stable
canonical ``host/owner/repo`` key, carrying no secrets.
"""

from __future__ import annotations

from living_adr.core.graph.models import ADRRef, ProvenancedADR, WhyAnswer


def serialize_adr_ref(ref: ADRRef) -> dict[str, object]:
    """Serialize a lightweight approved-ADR reference (citation)."""

    return {
        "repository": ref.repository.key,
        "adr_id": ref.adr_id,
        "title": ref.title,
        "status": ref.status,
    }


def serialize_provenanced_adr(adr: ProvenancedADR) -> dict[str, object]:
    """Serialize an ADR reference plus its citations and snapshot provenance."""

    snapshot = None
    if adr.snapshot is not None:
        snapshot = {
            "repository": adr.snapshot.repository.key,
            "snapshot_id": adr.snapshot.snapshot_id,
            "schema_version": adr.snapshot.schema_version.label,
        }
    return {
        "repository": adr.repository.key,
        "adr": serialize_adr_ref(adr.adr),
        "citations": list(adr.citations),
        "snapshot": snapshot,
    }


def serialize_why_answer(answer: WhyAnswer) -> dict[str, object]:
    """Serialize a cited why-answer, preserving explicit no-context results."""

    return {
        "repository": answer.repository.key,
        "question": answer.question,
        "answer": answer.answer,
        "adr_id": answer.adr_id,
        "citations": list(answer.citations),
        "found": answer.found,
        "provenance": [
            serialize_provenanced_adr(p) for p in answer.provenance
        ],
    }


__all__ = [
    "serialize_adr_ref",
    "serialize_provenanced_adr",
    "serialize_why_answer",
]
