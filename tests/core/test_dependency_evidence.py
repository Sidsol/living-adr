"""Slice S-002 RED tests: manifest/lockfile recognition + evidence building.

Recognition is pure and deterministic: known dependency manifests and lockfiles
are mapped to an ecosystem and evidence kind, non-dependency files are ignored,
and evidence records are emitted in stable source-path order with immutable
hashes and redaction-safe summaries (never raw diff text).
"""

from __future__ import annotations

from living_adr.core.dependency_evidence import (
    Ecosystem,
    build_dependency_evidence,
    match_dependency_file,
)
from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import (
    CandidateEvidence,
    ChangedFileMetadata,
    DiffEvidence,
    SCMProviderName,
)
from living_adr.core.structural_change import EvidenceKind, ObservedOperation

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


def test_known_manifests_map_to_ecosystem_and_kind() -> None:
    cases = {
        "pyproject.toml": (Ecosystem.PYTHON, EvidenceKind.DEPENDENCY_MANIFEST),
        "requirements.txt": (Ecosystem.PYTHON, EvidenceKind.DEPENDENCY_MANIFEST),
        "requirements-dev.txt": (Ecosystem.PYTHON, EvidenceKind.DEPENDENCY_MANIFEST),
        "package.json": (Ecosystem.NPM, EvidenceKind.DEPENDENCY_MANIFEST),
        "go.mod": (Ecosystem.GO, EvidenceKind.DEPENDENCY_MANIFEST),
        "Cargo.toml": (Ecosystem.RUST, EvidenceKind.DEPENDENCY_MANIFEST),
        "pom.xml": (Ecosystem.JVM, EvidenceKind.DEPENDENCY_MANIFEST),
        "build.gradle": (Ecosystem.JVM, EvidenceKind.DEPENDENCY_MANIFEST),
        "Gemfile": (Ecosystem.RUBY, EvidenceKind.DEPENDENCY_MANIFEST),
        "MyApp.csproj": (Ecosystem.DOTNET, EvidenceKind.DEPENDENCY_MANIFEST),
    }
    for path, (ecosystem, kind) in cases.items():
        match = match_dependency_file(path)
        assert match is not None, path
        assert match.ecosystem is ecosystem, path
        assert match.evidence_kind is kind, path


def test_known_lockfiles_map_to_lockfile_kind() -> None:
    cases = {
        "poetry.lock": Ecosystem.PYTHON,
        "uv.lock": Ecosystem.PYTHON,
        "package-lock.json": Ecosystem.NPM,
        "pnpm-lock.yaml": Ecosystem.NPM,
        "yarn.lock": Ecosystem.NPM,
        "go.sum": Ecosystem.GO,
        "Cargo.lock": Ecosystem.RUST,
        "Gemfile.lock": Ecosystem.RUBY,
    }
    for path, ecosystem in cases.items():
        match = match_dependency_file(path)
        assert match is not None, path
        assert match.ecosystem is ecosystem, path
        assert match.evidence_kind is EvidenceKind.DEPENDENCY_LOCKFILE, path


def test_nested_paths_match_on_basename() -> None:
    match = match_dependency_file("services/api/package.json")
    assert match is not None
    assert match.ecosystem is Ecosystem.NPM
    assert match.evidence_kind is EvidenceKind.DEPENDENCY_MANIFEST


def test_non_dependency_files_are_ignored() -> None:
    for path in ("README.md", "src/app.py", "package.json.bak", "go.modules"):
        assert match_dependency_file(path) is None


def test_build_evidence_orders_by_source_path_and_is_deterministic() -> None:
    candidate = _candidate(
        ChangedFileMetadata(filename="package.json", status="modified", additions=2),
        ChangedFileMetadata(filename="README.md", status="modified", additions=9),
        ChangedFileMetadata(
            filename="package-lock.json", status="modified", additions=40
        ),
    )
    first = build_dependency_evidence(candidate)
    second = build_dependency_evidence(candidate)
    # README.md is ignored; only the two dependency files produce evidence.
    assert [e.source_path for e in first] == ["package-lock.json", "package.json"]
    assert first == second  # determinism / replay safety


def test_evidence_records_carry_provenance_hash_and_safe_summary() -> None:
    candidate = _candidate(
        ChangedFileMetadata(
            filename="pyproject.toml", status="modified", additions=1, deletions=0
        ),
    )
    (evidence,) = build_dependency_evidence(candidate)
    assert evidence.repository == REPO
    assert evidence.source_path == "pyproject.toml"
    assert evidence.evidence_kind is EvidenceKind.DEPENDENCY_MANIFEST
    assert evidence.observed_operation is ObservedOperation.ADDED
    assert evidence.provider_delivery_id == "d-1"
    assert evidence.normalized_pr_key == candidate.normalized_pr_key
    assert evidence.immutable_hash
    assert evidence.parser == "living-adr-dependency-evidence"
    assert evidence.parser_version
    assert evidence.provenance["source_delivery_id"] == "d-1"
    # Summary is redaction-safe metadata: it must not echo raw diff content.
    assert "pyproject.toml" in evidence.summary
    assert candidate.diff.diff_handle not in evidence.summary


def test_observed_operation_inference_from_line_deltas() -> None:
    candidate = _candidate(
        ChangedFileMetadata(
            filename="package.json", status="modified", additions=0, deletions=3
        ),
        ChangedFileMetadata(
            filename="go.mod", status="modified", additions=2, deletions=2
        ),
        ChangedFileMetadata(
            filename="Cargo.lock", status="modified", additions=88, deletions=88
        ),
    )
    by_path = {e.source_path: e for e in build_dependency_evidence(candidate)}
    assert by_path["package.json"].observed_operation is ObservedOperation.REMOVED
    assert by_path["go.mod"].observed_operation is ObservedOperation.VERSION_CHANGED
    # Lockfiles are always churn regardless of line deltas.
    assert (
        by_path["Cargo.lock"].observed_operation is ObservedOperation.LOCKFILE_CHURN
    )
