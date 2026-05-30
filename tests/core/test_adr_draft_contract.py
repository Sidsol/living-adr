"""S-001 RED tests: provisional ADR draft contract (feature 008).

These tests pin the provisional draft DTO that feature 008 produces from a
Claude completion: provisional flag, evidence/ADR citations, model metadata, a
draft-record *candidate* projection (never an authoritative ``ADRRecord``), and a
deterministic SHA-256 content hash that excludes provider metadata so identical
drafting inputs always hash identically (NFR-3).
"""

from __future__ import annotations

from living_adr.core.adr import ADRStatus
from living_adr.core.adr_draft import (
    ADRDraft,
    CitationKind,
    DraftADRRecordCandidate,
    DraftCitation,
    ModelMetadata,
    compute_draft_content_hash,
)
from living_adr.core.models import RepositoryIdentity


def _repo() -> RepositoryIdentity:
    return RepositoryIdentity(
        host="github.com", owner="acme", repo="widgets", repo_id="r1"
    )


def _citations() -> tuple[DraftCitation, ...]:
    return (
        DraftCitation(kind=CitationKind.EVIDENCE, ref="ev-1"),
        DraftCitation(kind=CitationKind.ADR, ref="adr-7"),
    )


def _draft(**overrides: object) -> ADRDraft:
    fields: dict[str, object] = {
        "repository": _repo(),
        "draft_id": "draft-1",
        "structural_change_id": "chg-1",
        "title": "Adopt requests 2.x",
        "status": "proposed",
        "context": "A direct dependency was added.",
        "decision": "Adopt the dependency.",
        "alternatives": "Vendor the code; do nothing.",
        "consequences": "New transitive surface.",
        "citations": _citations(),
        "rendered_markdown": "# Adopt requests 2.x\n\nprovisional draft body",
        "model_metadata": ModelMetadata(
            model_id="claude-sonnet-4-6", input_tokens=1200, output_tokens=300
        ),
    }
    fields.update(overrides)
    content_hash = compute_draft_content_hash(
        repository=fields["repository"],  # type: ignore[arg-type]
        structural_change_id=fields["structural_change_id"],  # type: ignore[arg-type]
        title=fields["title"],  # type: ignore[arg-type]
        context=fields["context"],  # type: ignore[arg-type]
        decision=fields["decision"],  # type: ignore[arg-type]
        alternatives=fields["alternatives"],  # type: ignore[arg-type]
        consequences=fields["consequences"],  # type: ignore[arg-type]
        citations=fields["citations"],  # type: ignore[arg-type]
    )
    return ADRDraft(content_hash=content_hash, **fields)  # type: ignore[arg-type]


def test_draft_is_provisional_by_default() -> None:
    draft = _draft()
    assert draft.provisional is True


def test_draft_carries_evidence_and_adr_citations() -> None:
    draft = _draft()
    kinds = {c.kind for c in draft.citations}
    assert CitationKind.EVIDENCE in kinds
    assert CitationKind.ADR in kinds
    assert draft.evidence_ids == ("ev-1",)
    assert draft.adr_citation_ids == ("adr-7",)


def test_draft_carries_model_metadata() -> None:
    draft = _draft()
    assert draft.model_metadata is not None
    assert draft.model_metadata.model_id == "claude-sonnet-4-6"
    assert draft.model_metadata.input_tokens == 1200
    assert draft.model_metadata.output_tokens == 300


def test_content_hash_is_deterministic_for_identical_inputs() -> None:
    assert _draft().content_hash == _draft().content_hash


def test_content_hash_excludes_provider_metadata() -> None:
    """Different provider/token metadata must not change the content hash."""

    a = _draft(
        model_metadata=ModelMetadata(
            model_id="claude-sonnet-4-6", input_tokens=10, output_tokens=20
        )
    )
    b = _draft(
        model_metadata=ModelMetadata(
            model_id="claude-other", input_tokens=999, output_tokens=1
        )
    )
    assert a.content_hash == b.content_hash


def test_content_hash_changes_with_content() -> None:
    base = _draft()
    changed = _draft(decision="Reject the dependency.")
    assert base.content_hash != changed.content_hash


def test_record_candidate_is_proposed_and_non_authoritative() -> None:
    candidate = _draft().to_record_candidate()
    assert isinstance(candidate, DraftADRRecordCandidate)
    assert candidate.status is ADRStatus.PROPOSED
    assert candidate.provisional is True
    assert candidate.adr_id == "draft-1"
    assert candidate.structural_change_id == "chg-1"
    assert candidate.evidence_ids == ("ev-1",)
    # The candidate intentionally has no approved decision linkage.
    assert not hasattr(candidate, "decision_id")
