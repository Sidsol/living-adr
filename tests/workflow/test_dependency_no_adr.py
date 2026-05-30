"""Slice S-004 RED tests: deterministic below-threshold no-ADR outcomes.

Low-signal dependency churn must produce explicit, persisted ``NoAdrOutcome``
records (never silent drops, FM-03) and must never leak a draft-eligible change.
Malformed/uncertain evidence must yield a typed uncertain outcome instead of an
unhandled exception (US-3, US-4).
"""

from __future__ import annotations

from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import (
    CandidateEvidence,
    ChangedFileMetadata,
    DiffEvidence,
    SCMProviderName,
)
from living_adr.core.structural_change import ADRRecommendation, ReasonCode
from living_adr.workflow.dependency_classifier import (
    DEFAULT_DRAFT_THRESHOLD,
    DependencyChangeClassifier,
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


def test_lockfile_only_churn_is_suppressed_below_threshold() -> None:
    candidate = _candidate(
        ChangedFileMetadata(
            filename="package-lock.json", status="modified", additions=120, deletions=80
        ),
    )
    result = DependencyChangeClassifier().classify(candidate)
    assert result.changes == ()
    (outcome,) = result.no_adr_outcomes
    assert outcome.reason_code == ReasonCode.LOCKFILE_ONLY
    assert outcome.confidence < DEFAULT_DRAFT_THRESHOLD
    assert outcome.adr_recommendation is ADRRecommendation.NO_ADR_NEEDED
    # Outcome retains source paths + evidence ids for replay/observability.
    assert outcome.source_paths == ("package-lock.json",)
    assert outcome.evidence_ids
    assert set(outcome.evidence_ids) <= {e.id for e in result.evidence}


def test_malformed_manifest_evidence_is_uncertain_not_raised() -> None:
    # Recognized manifest but no inferable operation (no status hint, 0/0 deltas).
    candidate = _candidate(
        ChangedFileMetadata(
            filename="pyproject.toml", status="modified", additions=0, deletions=0
        ),
    )
    result = DependencyChangeClassifier().classify(candidate)
    assert result.changes == ()
    (outcome,) = result.no_adr_outcomes
    assert outcome.reason_code == ReasonCode.MALFORMED_EVIDENCE
    assert outcome.confidence < DEFAULT_DRAFT_THRESHOLD


def test_below_threshold_manifest_change_is_suppressed() -> None:
    candidate = _candidate(
        ChangedFileMetadata(filename="package.json", status="modified", additions=2),
    )
    # A strict threshold demotes an otherwise draft-eligible add to no-ADR.
    result = DependencyChangeClassifier(draft_threshold=0.95).classify(candidate)
    assert result.changes == ()
    (outcome,) = result.no_adr_outcomes
    assert outcome.reason_code == ReasonCode.LOW_CONFIDENCE
    assert outcome.source_paths == ("package.json",)


def test_no_dependency_files_yields_empty_deterministic_result() -> None:
    candidate = _candidate(
        ChangedFileMetadata(filename="README.md", status="modified", additions=3),
        ChangedFileMetadata(filename="src/app.py", status="modified", additions=9),
    )
    result = DependencyChangeClassifier().classify(candidate)
    assert result.changes == ()
    assert result.no_adr_outcomes == ()
    assert result.evidence == ()


def test_draft_and_no_adr_paths_do_not_cross_contaminate() -> None:
    # npm manifest add (draft) + python lockfile-only churn (suppressed).
    candidate = _candidate(
        ChangedFileMetadata(filename="package.json", status="modified", additions=2),
        ChangedFileMetadata(
            filename="poetry.lock", status="modified", additions=30, deletions=10
        ),
    )
    result = DependencyChangeClassifier().classify(candidate)
    assert len(result.changes) == 1
    assert result.changes[0].dependency_ecosystem == "npm"
    assert len(result.no_adr_outcomes) == 1
    assert result.no_adr_outcomes[0].reason_code == ReasonCode.LOCKFILE_ONLY


def test_no_adr_outcomes_are_deterministic_under_replay() -> None:
    candidate = _candidate(
        ChangedFileMetadata(
            filename="package-lock.json", status="modified", additions=12
        ),
        ChangedFileMetadata(
            filename="pyproject.toml", status="modified", additions=0, deletions=0
        ),
    )
    classifier = DependencyChangeClassifier()
    assert classifier.classify(candidate) == classifier.classify(candidate)
