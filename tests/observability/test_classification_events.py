"""Slice S-005 RED tests: metadata-only classification telemetry.

Observability for the classifier must emit only non-sensitive metadata —
repository key, normalized PR key, counts, reason codes, source paths, and
confidence — and must never export raw diffs, diff handles, or file contents
(NFR-4, architecture #cross-cutting default-deny).
"""

from __future__ import annotations

import json

from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import (
    CandidateEvidence,
    ChangedFileMetadata,
    DiffEvidence,
    SCMProviderName,
)
from living_adr.observability.classification_events import (
    CLASSIFICATION_COMPLETED,
    CLASSIFICATION_STARTED,
    completed_metadata,
    error_metadata,
    started_metadata,
)
from living_adr.workflow.dependency_classifier import DependencyChangeClassifier

REPO = RepositoryIdentity(
    host="github.com", owner="acme", repo="widgets", repo_id="100"
)
SECRET = "SUPER-SECRET-DIFF-BODY"


def _candidate(*files: ChangedFileMetadata) -> CandidateEvidence:
    return CandidateEvidence(
        repository=REPO,
        source_delivery_id="d-1",
        normalized_pr_key="github:github.com/acme/widgets:42:mergesha",
        pr_number=42,
        pr_title="Update deps",
        changed_files=files,
        diff=DiffEvidence(
            diff_handle=f"github:pulls/42/files?token={SECRET}", summary=SECRET
        ),
        provider=SCMProviderName.GITHUB,
    )


def _is_safe(value: object) -> bool:
    if isinstance(value, str | int | float | bool):
        return True
    if isinstance(value, (tuple, list)):
        return all(_is_safe(v) for v in value)
    return False


def test_started_metadata_is_safe_and_links_repository() -> None:
    candidate = _candidate(
        ChangedFileMetadata(filename="package.json", status="modified", additions=2),
    )
    meta = started_metadata(candidate)
    assert meta["repository_key"] == REPO.key
    assert meta["normalized_pr_key"] == candidate.normalized_pr_key
    assert meta["changed_file_count"] == 1
    assert all(_is_safe(v) for v in meta.values())
    assert SECRET not in json.dumps(meta)


def test_completed_metadata_reports_counts_reasons_and_excludes_raw_content() -> None:
    candidate = _candidate(
        ChangedFileMetadata(filename="package.json", status="modified", additions=2),
        ChangedFileMetadata(
            filename="poetry.lock", status="modified", additions=30, deletions=4
        ),
    )
    result = DependencyChangeClassifier().classify(candidate)
    meta = completed_metadata(candidate, result)
    assert meta["repository_key"] == REPO.key
    assert meta["normalized_pr_key"] == candidate.normalized_pr_key
    assert meta["change_count"] == 1
    assert meta["draft_count"] == 1
    assert meta["no_adr_count"] == 1
    assert meta["evidence_count"] == 2
    assert "direct_manifest_add" in meta["reason_codes"]
    assert "lockfile_only_churn" in meta["reason_codes"]
    assert "package.json" in meta["source_paths"]
    assert isinstance(meta["max_confidence"], float)
    # Redaction: no raw diff handle/summary content leaks anywhere.
    assert all(_is_safe(v) for v in meta.values())
    assert SECRET not in json.dumps(meta)


def test_error_metadata_is_safe_metadata_only() -> None:
    candidate = _candidate(
        ChangedFileMetadata(filename="package.json", status="modified", additions=2),
    )
    meta = error_metadata(candidate, "ValueError")
    assert meta["repository_key"] == REPO.key
    assert meta["error_kind"] == "ValueError"
    assert all(_is_safe(v) for v in meta.values())
    assert SECRET not in json.dumps(meta)


def test_event_names_are_stable_constants() -> None:
    assert CLASSIFICATION_STARTED == "dependency_classification.started"
    assert CLASSIFICATION_COMPLETED == "dependency_classification.completed"
