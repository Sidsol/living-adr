"""Slice S-003 RED tests: draft-eligible direct dependency classification.

Manifest-backed direct dependency add/remove/version changes produce a single
draft-eligible ``StructuralChange`` per ecosystem when confidence meets the
threshold. Manifest + lockfile changes for the same ecosystem deduplicate into one
change carrying both source paths. Ambiguous manifest churn does not draft.
"""

from __future__ import annotations

from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import (
    CandidateEvidence,
    ChangedFileMetadata,
    DiffEvidence,
    SCMProviderName,
)
from living_adr.core.structural_change import (
    ADRRecommendation,
    ChangeOperation,
    ChangeType,
    ReasonCode,
)
from living_adr.workflow.dependency_classifier import (
    DEFAULT_DRAFT_THRESHOLD,
    DependencyChangeClassifier,
    DependencyClassificationResult,
)

REPO = RepositoryIdentity(
    host="github.com", owner="acme", repo="widgets", repo_id="100"
)


def _candidate(*files: ChangedFileMetadata) -> CandidateEvidence:
    return CandidateEvidence(
        repository=REPO,
        source_delivery_id="d-1",
        normalized_pr_key="github:github.com/acme/widgets:42:mergesha",
        pr_number=42,
        pr_title="Update deps",
        changed_files=files,
        diff=DiffEvidence(diff_handle="github:pulls/42/files", summary="changed"),
        provider=SCMProviderName.GITHUB,
    )


def test_npm_direct_addition_is_draft_eligible() -> None:
    candidate = _candidate(
        ChangedFileMetadata(filename="package.json", status="modified", additions=2),
    )
    result = DependencyChangeClassifier().classify(candidate)
    assert isinstance(result, DependencyClassificationResult)
    assert len(result.changes) == 1
    change = result.changes[0]
    assert change.change_type is ChangeType.DEPENDENCY
    assert change.operation is ChangeOperation.ADDED
    assert change.dependency_ecosystem == "npm"
    assert change.source_paths == ("package.json",)
    assert change.confidence >= DEFAULT_DRAFT_THRESHOLD
    assert change.adr_recommendation is ADRRecommendation.DRAFT
    assert change.reason_code == ReasonCode.DIRECT_MANIFEST_ADD
    assert change.evidence_ids  # links to immutable evidence
    assert change.affected_dependency is None  # metadata-only evidence


def test_python_direct_removal_emits_evidence_linked_change() -> None:
    candidate = _candidate(
        ChangedFileMetadata(
            filename="pyproject.toml", status="modified", additions=0, deletions=3
        ),
    )
    result = DependencyChangeClassifier().classify(candidate)
    (change,) = result.changes
    assert change.operation is ChangeOperation.REMOVED
    assert change.reason_code == ReasonCode.DIRECT_MANIFEST_REMOVE
    assert change.adr_recommendation is ADRRecommendation.DRAFT
    # Every evidence id on the change resolves to an emitted evidence record.
    evidence_ids = {e.id for e in result.evidence}
    assert set(change.evidence_ids) <= evidence_ids
    assert change.provider_delivery_id == "d-1"


def test_manifest_and_lockfile_dedupe_into_single_change() -> None:
    candidate = _candidate(
        ChangedFileMetadata(filename="package.json", status="modified", additions=2),
        ChangedFileMetadata(
            filename="package-lock.json", status="modified", additions=50
        ),
    )
    result = DependencyChangeClassifier().classify(candidate)
    assert len(result.changes) == 1
    change = result.changes[0]
    assert change.source_paths == ("package-lock.json", "package.json")
    assert change.reason_code == ReasonCode.MANIFEST_LOCKFILE_PAIR
    assert change.adr_recommendation is ADRRecommendation.DRAFT
    assert len(change.evidence_ids) == 2


def test_version_change_is_draft_eligible() -> None:
    candidate = _candidate(
        ChangedFileMetadata(
            filename="go.mod", status="modified", additions=2, deletions=2
        ),
    )
    (change,) = DependencyChangeClassifier().classify(candidate).changes
    assert change.operation is ChangeOperation.VERSION_CHANGED
    assert change.reason_code == ReasonCode.DIRECT_MANIFEST_VERSION_CHANGE
    assert change.confidence >= DEFAULT_DRAFT_THRESHOLD


def test_separate_ecosystems_produce_separate_changes() -> None:
    candidate = _candidate(
        ChangedFileMetadata(filename="package.json", status="modified", additions=2),
        ChangedFileMetadata(filename="go.mod", status="modified", additions=1),
    )
    result = DependencyChangeClassifier().classify(candidate)
    ecosystems = sorted(c.dependency_ecosystem for c in result.changes)
    assert ecosystems == ["go", "npm"]


def test_ambiguous_manifest_change_is_not_draft_eligible() -> None:
    # No line deltas and a plain "modified" status => operation cannot be inferred.
    candidate = _candidate(
        ChangedFileMetadata(
            filename="requirements.txt", status="modified", additions=0, deletions=0
        ),
    )
    result = DependencyChangeClassifier().classify(candidate)
    assert result.changes == ()


def test_classification_is_deterministic() -> None:
    candidate = _candidate(
        ChangedFileMetadata(filename="package.json", status="modified", additions=2),
        ChangedFileMetadata(
            filename="package-lock.json", status="modified", additions=50
        ),
    )
    classifier = DependencyChangeClassifier()
    assert classifier.classify(candidate) == classifier.classify(candidate)
