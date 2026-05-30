"""Metadata-only classification telemetry (feature 004, slice S-005).

Builds observability metadata for the dependency classifier that satisfies the
architecture default-deny raw-export contract (#cross-cutting, FM-21, NFR-4): only
identifiers, counts, reason codes, confidence, and source paths are emitted. Raw
diffs, diff handles, file contents, prompts, and secrets are never included.

These helpers return plain metadata mappings so they can be unit-tested in
isolation and then handed to any :class:`~living_adr.core.observability.Observability`
implementation by the producer facade.
"""

from __future__ import annotations

from living_adr.core.scm import CandidateEvidence
from living_adr.workflow.dependency_classifier import DependencyClassificationResult

CLASSIFICATION_STARTED = "dependency_classification.started"
CLASSIFICATION_COMPLETED = "dependency_classification.completed"
CLASSIFICATION_NO_ADR = "dependency_classification.no_adr"
CLASSIFICATION_ERROR = "dependency_classification.error"


def started_metadata(candidate: CandidateEvidence) -> dict[str, object]:
    """Safe metadata for a classification-started event."""

    return {
        "repository_key": candidate.repository.key,
        "normalized_pr_key": candidate.normalized_pr_key,
        "changed_file_count": len(candidate.changed_files),
    }


def completed_metadata(
    candidate: CandidateEvidence, result: DependencyClassificationResult
) -> dict[str, object]:
    """Safe metadata for a classification-completed event.

    Reports counts, distinct reason codes, the distinct source paths involved,
    and the maximum confidence. Confidence is a numeric bucket signal only; no
    raw evidence content is referenced.
    """

    draft_count = sum(
        1
        for change in result.changes
        if change.adr_recommendation.value == "draft"
    )
    reason_codes = sorted(
        {change.reason_code for change in result.changes}
        | {outcome.reason_code for outcome in result.no_adr_outcomes}
    )
    source_paths: set[str] = set()
    confidences: list[float] = []
    for change in result.changes:
        source_paths.update(change.source_paths)
        confidences.append(change.confidence)
    for outcome in result.no_adr_outcomes:
        source_paths.update(outcome.source_paths)
        confidences.append(outcome.confidence)

    return {
        "repository_key": candidate.repository.key,
        "normalized_pr_key": candidate.normalized_pr_key,
        "change_count": len(result.changes),
        "draft_count": draft_count,
        "no_adr_count": len(result.no_adr_outcomes),
        "evidence_count": len(result.evidence),
        "reason_codes": tuple(reason_codes),
        "source_paths": tuple(sorted(source_paths)),
        "max_confidence": max(confidences, default=0.0),
    }


def error_metadata(
    candidate: CandidateEvidence, error_kind: str
) -> dict[str, object]:
    """Safe metadata for a classification-error event (kind only, no payload)."""

    return {
        "repository_key": candidate.repository.key,
        "normalized_pr_key": candidate.normalized_pr_key,
        "error_kind": error_kind,
    }


__all__ = [
    "CLASSIFICATION_STARTED",
    "CLASSIFICATION_COMPLETED",
    "CLASSIFICATION_NO_ADR",
    "CLASSIFICATION_ERROR",
    "started_metadata",
    "completed_metadata",
    "error_metadata",
]
