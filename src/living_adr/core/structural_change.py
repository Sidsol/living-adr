"""Production structural-change contract (feature 004, slice S-001).

This module defines the **authoritative** ``StructuralChange`` and
``ChangeEvidence`` contract that downstream features bind to:

* Feature 008 (``claude-adr-drafting-capability``) consumes draft-eligible
  ``StructuralChange`` records plus their immutable ``ChangeEvidence`` to package
  prompts that cite concrete files (never raw GitHub payloads).
* Feature 005 (schema/API classifiers) reuses these same generic shapes so its
  changes flow through the identical workflow without dependency-specific leakage.

Relationship to the smoke-depth models in :mod:`living_adr.core.models`
-----------------------------------------------------------------------
Feature 001 established intentionally minimal ``StructuralChange`` /
``ChangeEvidence`` shapes for the walking skeleton. Those remain untouched for the
smoke pipeline. This module is the production-depth contract for the classifier
producers and lives in its own module so the two never collide.

Determinism (NFR-1)
-------------------
Stable ids and immutable hashes are derived purely from their inputs via SHA-256,
so replaying identical Feature 003 evidence yields byte-identical records. No
clocks, randomness, or ordering hazards are involved.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from living_adr.core.repository import RepositoryIdentity


class ChangeType(StrEnum):
    """Classifier-neutral structural-change family.

    Feature 004 emits :attr:`DEPENDENCY`. Feature 005 extends this enum with its
    own families (schema/API) without altering the dependency contract.
    """

    DEPENDENCY = "dependency"


class ChangeOperation(StrEnum):
    """The architecture-significant operation a structural change represents."""

    ADDED = "added"
    REMOVED = "removed"
    VERSION_CHANGED = "version_changed"
    MIXED = "mixed"


class ADRRecommendation(StrEnum):
    """Whether downstream drafting (Feature 008) should run for a record."""

    DRAFT = "draft"
    NO_ADR_NEEDED = "no_adr_needed"


class EvidenceKind(StrEnum):
    """The kind of immutable evidence a :class:`ChangeEvidence` record captures."""

    DEPENDENCY_MANIFEST = "dependency_manifest"
    DEPENDENCY_LOCKFILE = "dependency_lockfile"
    DEPENDENCY_DIFF_SUMMARY = "dependency_diff_summary"


class ObservedOperation(StrEnum):
    """The operation observed at the evidence (file) level.

    This is intentionally finer-grained than :class:`ChangeOperation`: lockfile
    churn is observable evidence but is not, on its own, an architecture-
    significant operation.
    """

    ADDED = "added"
    REMOVED = "removed"
    VERSION_CHANGED = "version_changed"
    LOCKFILE_CHURN = "lockfile_churn"
    UNKNOWN = "unknown"


class ReasonCode(StrEnum):
    """Stable, deterministic reason codes for changes and no-ADR outcomes.

    These are part of the contract: Feature 008 and observability key off them.
    Typed as a ``str`` field on the models so Feature 005 may introduce further
    codes without a breaking change to consumers.
    """

    # Draft-eligible (manifest-backed) reasons.
    DIRECT_MANIFEST_ADD = "direct_manifest_add"
    DIRECT_MANIFEST_REMOVE = "direct_manifest_remove"
    DIRECT_MANIFEST_VERSION_CHANGE = "direct_manifest_version_change"
    MANIFEST_LOCKFILE_PAIR = "manifest_lockfile_pair"
    MANIFEST_MIXED_OPERATIONS = "manifest_mixed_operations"
    # Below-threshold / suppressed (no-ADR) reasons.
    LOCKFILE_ONLY = "lockfile_only_churn"
    TRANSITIVE_ONLY = "transitive_only_churn"
    UNSUPPORTED_ECOSYSTEM = "unsupported_ecosystem"
    MALFORMED_EVIDENCE = "malformed_evidence"
    LOW_CONFIDENCE = "low_confidence"
    NO_DEPENDENCY_FILES = "no_dependency_files"


def _digest(*parts: object) -> str:
    """SHA-256 hex digest over a canonical, separator-joined component list."""

    canonical = "|".join("" if p is None else str(p) for p in parts)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_structural_change_id(
    *,
    repository: RepositoryIdentity,
    source_scm_event_id: str,
    change_type: ChangeType,
    operation: ChangeOperation,
    affected_dependency: str | None,
    source_paths: tuple[str, ...],
) -> str:
    """Deterministic id from repository/event/type/operation/package/paths."""

    return _digest(
        repository.key,
        source_scm_event_id,
        change_type.value,
        operation.value,
        affected_dependency,
        ":".join(sorted(source_paths)),
    )


def build_evidence_id(
    *,
    repository: RepositoryIdentity,
    source_scm_event_id: str,
    source_path: str,
    evidence_kind: EvidenceKind,
) -> str:
    """Deterministic evidence id from repository/event/path/kind."""

    return _digest(
        repository.key,
        source_scm_event_id,
        source_path,
        evidence_kind.value,
    )


def compute_evidence_hash(
    *,
    repository: RepositoryIdentity,
    source_scm_event_id: str,
    source_path: str,
    evidence_kind: EvidenceKind,
    before_value: str | None,
    after_value: str | None,
) -> str:
    """Immutable content hash binding the evidence identity to observed values."""

    return _digest(
        repository.key,
        source_scm_event_id,
        source_path,
        evidence_kind.value,
        before_value,
        after_value,
    )


def build_no_adr_outcome_id(
    *,
    repository: RepositoryIdentity,
    source_scm_event_id: str,
    change_type: ChangeType,
    reason_code: str,
    source_paths: tuple[str, ...],
) -> str:
    """Deterministic no-ADR outcome id from repository/event/reason/paths."""

    return _digest(
        repository.key,
        source_scm_event_id,
        change_type.value,
        reason_code,
        ":".join(sorted(source_paths)),
    )


class ChangeEvidence(BaseModel):
    """Immutable evidence record produced from Feature 003 candidate evidence.

    ``ChangeEvidence`` proves *what* changed; it is never approved rationale
    (architecture #anti-patterns FM-06). The ``summary`` is redaction-safe and the
    record never carries raw diff text or file contents — only handles/summaries.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    repository: RepositoryIdentity
    source_scm_event_id: str
    provider_delivery_id: str
    normalized_pr_key: str
    evidence_kind: EvidenceKind
    source_path: str
    diff_hunk_ref: str | None = None
    before_value: str | None = None
    after_value: str | None = None
    observed_operation: ObservedOperation
    parser: str
    parser_version: str
    immutable_hash: str
    summary: str
    provenance: Mapping[str, str] = {}


class StructuralChange(BaseModel):
    """A classified, repository-scoped, architecture-significant change.

    Feature 004 emits ``change_type == "dependency"`` records. The dependency-
    specific fields (``affected_dependency``, ``dependency_ecosystem``) are
    optional so Feature 005's non-dependency changes leave them ``None`` rather
    than forcing dependency semantics onto the generic contract (NFR-6).
    """

    model_config = ConfigDict(frozen=True)

    id: str
    repository: RepositoryIdentity
    source_scm_event_id: str
    provider_delivery_id: str
    normalized_pr_key: str
    change_type: ChangeType
    operation: ChangeOperation
    affected_dependency: str | None = None
    dependency_ecosystem: str | None = None
    source_paths: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    confidence: float = Field(ge=0.0, le=1.0)
    reason_code: str
    adr_recommendation: ADRRecommendation
    classifier_name: str
    classifier_version: str


class NoAdrOutcome(BaseModel):
    """A deterministic below-threshold / uncertain outcome.

    Recorded (never silently dropped, FM-03) when the dependency signal does not
    meet the draft threshold. It retains source paths and evidence ids so replay
    and observability can inspect *why* no ADR was created.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    repository: RepositoryIdentity
    source_scm_event_id: str
    provider_delivery_id: str
    normalized_pr_key: str
    change_type: ChangeType
    reason_code: str
    confidence: float = Field(ge=0.0, le=1.0)
    source_paths: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    adr_recommendation: ADRRecommendation = ADRRecommendation.NO_ADR_NEEDED


__all__ = [
    "ChangeType",
    "ChangeOperation",
    "ADRRecommendation",
    "EvidenceKind",
    "ObservedOperation",
    "ReasonCode",
    "build_structural_change_id",
    "build_evidence_id",
    "build_no_adr_outcome_id",
    "compute_evidence_hash",
    "ChangeEvidence",
    "StructuralChange",
    "NoAdrOutcome",
]
