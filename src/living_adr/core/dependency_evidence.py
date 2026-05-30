"""Dependency manifest/lockfile recognition and evidence building (S-002).

Pure, deterministic functions that turn Feature 003 :class:`CandidateEvidence`
into immutable dependency :class:`ChangeEvidence`. Recognition is by *basename*
(so nested monorepo paths still match) and uses a static registry of well-known
manifests and lockfiles across Python, JS/TS, Go, Rust, JVM, Ruby, and .NET.

No raw diff text or file contents are ever read: the only inputs are the changed-
file metadata (filename/status/line deltas) and the redaction-safe diff handle.
Evidence is emitted in stable source-path order so replaying identical evidence
yields byte-identical records (NFR-1).
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from living_adr.core.scm import CandidateEvidence, ChangedFileMetadata
from living_adr.core.structural_change import (
    ChangeEvidence,
    EvidenceKind,
    ObservedOperation,
    build_evidence_id,
    compute_evidence_hash,
)

PARSER_NAME = "living-adr-dependency-evidence"
PARSER_VERSION = "1.0.0"


class Ecosystem(StrEnum):
    """Dependency ecosystem a recognized file belongs to."""

    PYTHON = "python"
    NPM = "npm"
    GO = "go"
    RUST = "rust"
    JVM = "jvm"
    RUBY = "ruby"
    DOTNET = "dotnet"
    UNKNOWN = "unknown"


class DependencyFileMatch(BaseModel):
    """Result of recognizing a changed file as a dependency manifest/lockfile."""

    model_config = ConfigDict(frozen=True)

    ecosystem: Ecosystem
    evidence_kind: EvidenceKind


# Exact-basename registries. Manifests declare *direct* dependencies; lockfiles
# pin the resolved/transitive graph.
_MANIFESTS: dict[str, Ecosystem] = {
    "pyproject.toml": Ecosystem.PYTHON,
    "setup.py": Ecosystem.PYTHON,
    "setup.cfg": Ecosystem.PYTHON,
    "Pipfile": Ecosystem.PYTHON,
    "package.json": Ecosystem.NPM,
    "go.mod": Ecosystem.GO,
    "Cargo.toml": Ecosystem.RUST,
    "pom.xml": Ecosystem.JVM,
    "build.gradle": Ecosystem.JVM,
    "build.gradle.kts": Ecosystem.JVM,
    "Gemfile": Ecosystem.RUBY,
}
_LOCKFILES: dict[str, Ecosystem] = {
    "poetry.lock": Ecosystem.PYTHON,
    "uv.lock": Ecosystem.PYTHON,
    "Pipfile.lock": Ecosystem.PYTHON,
    "package-lock.json": Ecosystem.NPM,
    "pnpm-lock.yaml": Ecosystem.NPM,
    "yarn.lock": Ecosystem.NPM,
    "go.sum": Ecosystem.GO,
    "Cargo.lock": Ecosystem.RUST,
    "gradle.lockfile": Ecosystem.JVM,
    "Gemfile.lock": Ecosystem.RUBY,
    "packages.lock.json": Ecosystem.DOTNET,
}


def _basename(path: str) -> str:
    # Normalize both separators so Windows- and POSIX-style paths match.
    return path.replace("\\", "/").rsplit("/", 1)[-1]


def match_dependency_file(path: str) -> DependencyFileMatch | None:
    """Recognize ``path`` as a dependency manifest/lockfile, or ``None``.

    Matching is by basename against the static registry, plus two pattern rules:
    ``requirements*.txt`` (Python manifests) and ``*.csproj`` (.NET manifests).
    """

    name = _basename(path)
    if name in _MANIFESTS:
        return DependencyFileMatch(
            ecosystem=_MANIFESTS[name],
            evidence_kind=EvidenceKind.DEPENDENCY_MANIFEST,
        )
    if name in _LOCKFILES:
        return DependencyFileMatch(
            ecosystem=_LOCKFILES[name],
            evidence_kind=EvidenceKind.DEPENDENCY_LOCKFILE,
        )
    if name.startswith("requirements") and name.endswith(".txt"):
        return DependencyFileMatch(
            ecosystem=Ecosystem.PYTHON,
            evidence_kind=EvidenceKind.DEPENDENCY_MANIFEST,
        )
    if name.endswith(".csproj"):
        return DependencyFileMatch(
            ecosystem=Ecosystem.DOTNET,
            evidence_kind=EvidenceKind.DEPENDENCY_MANIFEST,
        )
    return None


def infer_observed_operation(
    match: DependencyFileMatch, changed_file: ChangedFileMetadata
) -> ObservedOperation:
    """Infer the file-level observed operation from status and line deltas.

    Lockfiles are always :attr:`ObservedOperation.LOCKFILE_CHURN`. Manifests use
    status plus additions/deletions: additions-only is an add, deletions-only a
    removal, both a version change.
    """

    if match.evidence_kind is EvidenceKind.DEPENDENCY_LOCKFILE:
        return ObservedOperation.LOCKFILE_CHURN

    status = changed_file.status.lower()
    if status == "added":
        return ObservedOperation.ADDED
    if status in ("removed", "deleted"):
        return ObservedOperation.REMOVED

    adds, dels = changed_file.additions, changed_file.deletions
    if adds > 0 and dels == 0:
        return ObservedOperation.ADDED
    if dels > 0 and adds == 0:
        return ObservedOperation.REMOVED
    if adds > 0 and dels > 0:
        return ObservedOperation.VERSION_CHANGED
    return ObservedOperation.UNKNOWN


class RecognizedDependencyFile(BaseModel):
    """A matched changed file paired with its recognition + observed operation."""

    model_config = ConfigDict(frozen=True)

    source_path: str
    match: DependencyFileMatch
    observed_operation: ObservedOperation
    additions: int
    deletions: int


def recognize_dependency_files(
    candidate: CandidateEvidence,
) -> tuple[RecognizedDependencyFile, ...]:
    """Return recognized dependency files, sorted by source path (deterministic)."""

    recognized: list[RecognizedDependencyFile] = []
    for changed in candidate.changed_files:
        match = match_dependency_file(changed.filename)
        if match is None:
            continue
        recognized.append(
            RecognizedDependencyFile(
                source_path=changed.filename,
                match=match,
                observed_operation=infer_observed_operation(match, changed),
                additions=changed.additions,
                deletions=changed.deletions,
            )
        )
    return tuple(sorted(recognized, key=lambda r: r.source_path))


def _summary(recognized: RecognizedDependencyFile) -> str:
    kind = recognized.match.evidence_kind.value
    return (
        f"{recognized.source_path} ({recognized.match.ecosystem.value} {kind}): "
        f"+{recognized.additions}/-{recognized.deletions}, "
        f"observed={recognized.observed_operation.value}"
    )


def build_dependency_evidence(
    candidate: CandidateEvidence,
) -> tuple[ChangeEvidence, ...]:
    """Build immutable dependency evidence from candidate evidence.

    One :class:`ChangeEvidence` is emitted per recognized dependency file, in
    stable source-path order. ``source_scm_event_id`` is the repository-scoped
    normalized PR key; ``provider_delivery_id`` is the provider's raw delivery id.
    """

    source_scm_event_id = candidate.normalized_pr_key
    provenance: Mapping[str, str] = {
        "source_delivery_id": candidate.source_delivery_id,
        "normalized_pr_key": candidate.normalized_pr_key,
        "diff_handle": candidate.diff.diff_handle,
    }

    evidence: list[ChangeEvidence] = []
    for recognized in recognize_dependency_files(candidate):
        kind = recognized.match.evidence_kind
        path = recognized.source_path
        immutable_hash = compute_evidence_hash(
            repository=candidate.repository,
            source_scm_event_id=source_scm_event_id,
            source_path=path,
            evidence_kind=kind,
            before_value=None,
            after_value=None,
        )
        evidence.append(
            ChangeEvidence(
                id=build_evidence_id(
                    repository=candidate.repository,
                    source_scm_event_id=source_scm_event_id,
                    source_path=path,
                    evidence_kind=kind,
                ),
                repository=candidate.repository,
                source_scm_event_id=source_scm_event_id,
                provider_delivery_id=candidate.source_delivery_id,
                normalized_pr_key=candidate.normalized_pr_key,
                evidence_kind=kind,
                source_path=path,
                diff_hunk_ref=f"{candidate.diff.diff_handle}#{path}",
                before_value=None,
                after_value=None,
                observed_operation=recognized.observed_operation,
                parser=PARSER_NAME,
                parser_version=PARSER_VERSION,
                immutable_hash=immutable_hash,
                summary=_summary(recognized),
                provenance=provenance,
            )
        )
    return tuple(evidence)


__all__ = [
    "Ecosystem",
    "DependencyFileMatch",
    "RecognizedDependencyFile",
    "match_dependency_file",
    "infer_observed_operation",
    "recognize_dependency_files",
    "build_dependency_evidence",
    "PARSER_NAME",
    "PARSER_VERSION",
]
