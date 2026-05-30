"""SL-002 RED tests: deterministic stub classification and ADR drafting.

The smoke classifier must emit exactly one architecture-significant
``StructuralChange`` plus one immutable ``ChangeEvidence`` for the seeded fixture,
and the draft renderer must produce one provisional ``ADRDraft`` that cites the
evidence and is explicitly labeled as deterministic smoke-stub output (not Claude).
"""

from __future__ import annotations

from living_adr.core.models import ADRDraft, ChangeEvidence, StructuralChange
from living_adr.workflow.smoke_fixture import (
    merged_pr_fixture,
    normalize_to_scm_event,
    smoke_repository,
)
from living_adr.workflow.smoke_flow import (
    classify_structural_change,
    draft_adr,
)


def _event():
    return normalize_to_scm_event(merged_pr_fixture())


def test_classifier_emits_one_dependency_structural_change() -> None:
    change, evidence = classify_structural_change(_event())
    assert isinstance(change, StructuralChange)
    assert isinstance(evidence, ChangeEvidence)
    assert change.repository == smoke_repository()
    assert change.change_type == "dependency"
    # Evidence is immutable and linked to the change.
    assert change.evidence_id == evidence.evidence_id
    assert evidence.pr_number == 42


def test_classifier_is_deterministic() -> None:
    first = classify_structural_change(_event())
    second = classify_structural_change(_event())
    assert first[0] == second[0]
    assert first[1] == second[1]


def test_change_evidence_is_immutable() -> None:
    _, evidence = classify_structural_change(_event())
    try:
        evidence.diff_summary = "tampered"  # type: ignore[misc]
    except Exception:  # noqa: BLE001 - pydantic frozen raises ValidationError
        return
    raise AssertionError("ChangeEvidence must be immutable")


def test_draft_has_required_sections_and_citation() -> None:
    change, evidence = classify_structural_change(_event())
    draft = draft_adr(change, evidence)
    assert isinstance(draft, ADRDraft)
    assert draft.repository == smoke_repository()
    assert draft.status == "proposed"
    assert draft.context
    assert draft.decision
    assert draft.consequences
    assert draft.alternatives  # alternatives placeholder present
    # Citations reference the fixture evidence only.
    assert evidence.evidence_id in draft.citations
    assert draft.structural_change_id == change.change_id


def test_draft_is_labeled_as_smoke_stub() -> None:
    change, evidence = classify_structural_change(_event())
    draft = draft_adr(change, evidence)
    assert draft.is_stub is True
    rendered = draft.rendered_markdown.lower()
    assert "smoke" in rendered and "stub" in rendered
    # Must not claim production Claude authorship.
    assert "claude" not in rendered


def test_draft_is_deterministic() -> None:
    change, evidence = classify_structural_change(_event())
    assert draft_adr(change, evidence) == draft_adr(change, evidence)
