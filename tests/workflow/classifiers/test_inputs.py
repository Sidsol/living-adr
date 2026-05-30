"""Slice 2 RED tests: feature 003 evidence -> classifier input adapter.

The adapter turns an immutable feature 003 :class:`CandidateEvidence` bundle into
a normalized :class:`ClassifierInput` the detectors reason over. It must normalize
paths, preserve file status / line deltas / diff *handles* (never raw diff text),
reject cross-repository evidence, and tolerate empty evidence.
"""

from __future__ import annotations

import pytest

from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import (
    CandidateEvidence,
    ChangedFileMetadata,
    DiffEvidence,
    SCMProviderName,
)
from living_adr.workflow.classifiers.inputs import (
    ClassifierInput,
    ClassifierInputError,
    build_classifier_input,
)

REPO = RepositoryIdentity(
    host="github.com", owner="acme", repo="widgets", repo_id="100"
)
OTHER_REPO = RepositoryIdentity(
    host="github.com", owner="acme", repo="other", repo_id="200"
)


def _candidate(*files: ChangedFileMetadata) -> CandidateEvidence:
    return CandidateEvidence(
        repository=REPO,
        source_delivery_id="d-1",
        normalized_pr_key="github:github.com/acme/widgets:42:mergesha",
        pr_number=42,
        pr_title="Change",
        changed_files=files,
        diff=DiffEvidence(diff_handle="github:pulls/42/files", summary="changed"),
        provider=SCMProviderName.GITHUB,
    )


def test_adapter_builds_normalized_input() -> None:
    candidate = _candidate(
        ChangedFileMetadata(
            filename="db\\migrations\\0007.sql",
            status="modified",
            additions=10,
            deletions=2,
        ),
    )
    inp = build_classifier_input(candidate)
    assert isinstance(inp, ClassifierInput)
    assert inp.repository == REPO
    assert inp.normalized_pr_key.endswith(":42:mergesha")
    assert inp.diff_handle == "github:pulls/42/files"
    (file,) = inp.changed_files
    # Backslashes are normalized to forward slashes.
    assert file.path == "db/migrations/0007.sql"
    assert file.status == "modified"
    assert file.additions == 10
    assert file.deletions == 2
    # Diff ref is a handle reference, not raw diff content.
    assert file.diff_ref == "github:pulls/42/files#db/migrations/0007.sql"


def test_adapter_preserves_handles_without_raw_diff() -> None:
    candidate = _candidate(
        ChangedFileMetadata(filename="api/openapi.yaml", status="modified"),
    )
    inp = build_classifier_input(candidate)
    # No field carries newline-laden raw diff text.
    for file in inp.changed_files:
        assert "\n" not in file.diff_ref
    assert "\n" not in inp.diff_summary


def test_adapter_handles_empty_evidence() -> None:
    inp = build_classifier_input(_candidate())
    assert inp.changed_files == ()


def test_adapter_rejects_cross_repository_evidence() -> None:
    candidate = _candidate(
        ChangedFileMetadata(filename="api/openapi.yaml", status="modified"),
    )
    with pytest.raises(ClassifierInputError):
        build_classifier_input(candidate, expected_repository=OTHER_REPO)


def test_adapter_rejects_path_traversal() -> None:
    candidate = _candidate(
        ChangedFileMetadata(filename="../../etc/passwd", status="modified"),
    )
    with pytest.raises(ClassifierInputError):
        build_classifier_input(candidate)


def test_adapter_is_deterministic_and_sorted() -> None:
    candidate = _candidate(
        ChangedFileMetadata(filename="b/openapi.yaml", status="modified"),
        ChangedFileMetadata(filename="a/schema.sql", status="modified"),
    )
    inp = build_classifier_input(candidate)
    assert [f.path for f in inp.changed_files] == ["a/schema.sql", "b/openapi.yaml"]
    assert build_classifier_input(candidate) == inp
