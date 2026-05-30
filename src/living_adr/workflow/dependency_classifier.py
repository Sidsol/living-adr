"""Deterministic dependency change classifier (feature 004, slices S-003/S-004).

Turns Feature 003 candidate evidence into draft-eligible dependency
``StructuralChange`` records (slice S-003) and below-threshold / uncertain
``NoAdrOutcome`` records (slice S-004). The classifier is pure: no LLM calls, no
live SCM calls, no clocks. Identical inputs yield identical, sorted outputs so
replaying evidence reproduces the same decision (NFR-1, US-4).

Evidence here is metadata-only (filename/status/line deltas + diff handle), so a
specific affected package name cannot be derived; ``affected_dependency`` is left
``None`` and reserved for a future enrichment that has structured per-dependency
evidence. Detection therefore reasons at the manifest-file level.
"""

from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, ConfigDict

from living_adr.core.dependency_evidence import (
    Ecosystem,
    RecognizedDependencyFile,
    build_dependency_evidence,
    recognize_dependency_files,
)
from living_adr.core.scm import CandidateEvidence
from living_adr.core.structural_change import (
    ADRRecommendation,
    ChangeEvidence,
    ChangeOperation,
    ChangeType,
    EvidenceKind,
    NoAdrOutcome,
    ObservedOperation,
    ReasonCode,
    StructuralChange,
    build_no_adr_outcome_id,
    build_structural_change_id,
)

DEFAULT_DRAFT_THRESHOLD = 0.70
CLASSIFIER_NAME = "dependency-change"
CLASSIFIER_VERSION = "1.0.0"

# Confidence assigned to suppressed (no-ADR) signals.
_LOCKFILE_ONLY_CONFIDENCE = 0.30
_MALFORMED_CONFIDENCE = 0.40

# Confidence assigned to a determinable manifest-backed operation.
_OPERATION_CONFIDENCE: dict[ChangeOperation, float] = {
    ChangeOperation.ADDED: 0.80,
    ChangeOperation.REMOVED: 0.80,
    ChangeOperation.VERSION_CHANGED: 0.75,
    ChangeOperation.MIXED: 0.70,
}

_OBSERVED_TO_OPERATION: dict[ObservedOperation, ChangeOperation] = {
    ObservedOperation.ADDED: ChangeOperation.ADDED,
    ObservedOperation.REMOVED: ChangeOperation.REMOVED,
    ObservedOperation.VERSION_CHANGED: ChangeOperation.VERSION_CHANGED,
}


class DependencyClassificationResult(BaseModel):
    """Typed result holding draft-eligible changes and no-ADR outcomes (US-5)."""

    model_config = ConfigDict(frozen=True)

    changes: tuple[StructuralChange, ...] = ()
    no_adr_outcomes: tuple[NoAdrOutcome, ...] = ()
    evidence: tuple[ChangeEvidence, ...] = ()
    diagnostics: tuple[str, ...] = ()


def _aggregate_operation(
    manifests: list[RecognizedDependencyFile],
) -> ChangeOperation | None:
    """Aggregate manifest observed operations into one change operation.

    Returns ``None`` when any manifest operation is unknown/ambiguous, so the
    caller suppresses rather than guesses (S-003 checkpoint).
    """

    operations: set[ChangeOperation] = set()
    for manifest in manifests:
        mapped = _OBSERVED_TO_OPERATION.get(manifest.observed_operation)
        if mapped is None:
            return None
        operations.add(mapped)
    if not operations:
        return None
    if len(operations) == 1:
        return next(iter(operations))
    return ChangeOperation.MIXED


def _reason_code(operation: ChangeOperation, has_lockfile: bool) -> str:
    if has_lockfile:
        return ReasonCode.MANIFEST_LOCKFILE_PAIR
    return {
        ChangeOperation.ADDED: ReasonCode.DIRECT_MANIFEST_ADD,
        ChangeOperation.REMOVED: ReasonCode.DIRECT_MANIFEST_REMOVE,
        ChangeOperation.VERSION_CHANGED: ReasonCode.DIRECT_MANIFEST_VERSION_CHANGE,
        ChangeOperation.MIXED: ReasonCode.MANIFEST_MIXED_OPERATIONS,
    }[operation]


class DependencyChangeClassifier:
    """Deterministic, fakeable classifier. The first structural-change producer."""

    def __init__(self, draft_threshold: float = DEFAULT_DRAFT_THRESHOLD) -> None:
        self.draft_threshold = draft_threshold

    def classify(
        self, candidate: CandidateEvidence
    ) -> DependencyClassificationResult:
        evidence = build_dependency_evidence(candidate)
        evidence_by_path = {e.source_path: e for e in evidence}
        recognized = recognize_dependency_files(candidate)

        groups: dict[Ecosystem, list[RecognizedDependencyFile]] = defaultdict(list)
        for item in recognized:
            groups[item.match.ecosystem].append(item)

        changes: list[StructuralChange] = []
        outcomes: list[NoAdrOutcome] = []
        source_scm_event_id = candidate.normalized_pr_key

        def _outcome(
            ecosystem_files: list[RecognizedDependencyFile],
            reason_code: str,
            confidence: float,
        ) -> NoAdrOutcome:
            source_paths = tuple(sorted(f.source_path for f in ecosystem_files))
            evidence_ids = tuple(
                evidence_by_path[path].id
                for path in source_paths
                if path in evidence_by_path
            )
            return NoAdrOutcome(
                id=build_no_adr_outcome_id(
                    repository=candidate.repository,
                    source_scm_event_id=source_scm_event_id,
                    change_type=ChangeType.DEPENDENCY,
                    reason_code=reason_code,
                    source_paths=source_paths,
                ),
                repository=candidate.repository,
                source_scm_event_id=source_scm_event_id,
                provider_delivery_id=candidate.source_delivery_id,
                normalized_pr_key=candidate.normalized_pr_key,
                change_type=ChangeType.DEPENDENCY,
                reason_code=reason_code,
                confidence=confidence,
                source_paths=source_paths,
                evidence_ids=evidence_ids,
            )

        for ecosystem in sorted(groups, key=lambda e: e.value):
            files = groups[ecosystem]
            manifests = [
                f
                for f in files
                if f.match.evidence_kind is EvidenceKind.DEPENDENCY_MANIFEST
            ]
            has_lockfile = any(
                f.match.evidence_kind is EvidenceKind.DEPENDENCY_LOCKFILE
                for f in files
            )
            if not manifests:
                # Lockfile-only / transitive-only churn: suppressed (FM-03).
                outcomes.append(
                    _outcome(files, ReasonCode.LOCKFILE_ONLY, _LOCKFILE_ONLY_CONFIDENCE)
                )
                continue

            operation = _aggregate_operation(manifests)
            if operation is None:
                # Recognized manifest but no inferable operation: uncertain.
                outcomes.append(
                    _outcome(
                        files,
                        ReasonCode.MALFORMED_EVIDENCE,
                        _MALFORMED_CONFIDENCE,
                    )
                )
                continue

            confidence = _OPERATION_CONFIDENCE[operation]
            if confidence < self.draft_threshold:
                outcomes.append(
                    _outcome(files, ReasonCode.LOW_CONFIDENCE, confidence)
                )
                continue

            source_paths = tuple(sorted(f.source_path for f in files))
            evidence_ids = tuple(
                evidence_by_path[path].id
                for path in source_paths
                if path in evidence_by_path
            )
            changes.append(
                StructuralChange(
                    id=build_structural_change_id(
                        repository=candidate.repository,
                        source_scm_event_id=source_scm_event_id,
                        change_type=ChangeType.DEPENDENCY,
                        operation=operation,
                        affected_dependency=None,
                        source_paths=source_paths,
                    ),
                    repository=candidate.repository,
                    source_scm_event_id=source_scm_event_id,
                    provider_delivery_id=candidate.source_delivery_id,
                    normalized_pr_key=candidate.normalized_pr_key,
                    change_type=ChangeType.DEPENDENCY,
                    operation=operation,
                    affected_dependency=None,
                    dependency_ecosystem=ecosystem.value,
                    source_paths=source_paths,
                    evidence_ids=evidence_ids,
                    confidence=confidence,
                    reason_code=_reason_code(operation, has_lockfile),
                    adr_recommendation=ADRRecommendation.DRAFT,
                    classifier_name=CLASSIFIER_NAME,
                    classifier_version=CLASSIFIER_VERSION,
                )
            )

        changes.sort(key=lambda c: (c.dependency_ecosystem or "", c.id))
        outcomes.sort(key=lambda o: (o.reason_code, o.id))
        return DependencyClassificationResult(
            changes=tuple(changes),
            no_adr_outcomes=tuple(outcomes),
            evidence=evidence,
            diagnostics=(),
        )


__all__ = [
    "DEFAULT_DRAFT_THRESHOLD",
    "CLASSIFIER_NAME",
    "CLASSIFIER_VERSION",
    "DependencyClassificationResult",
    "DependencyChangeClassifier",
]
