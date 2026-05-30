"""Classifier input adapter and shared classifier vocabulary (feature 005).

This module is the boundary between feature 003 evidence and the feature 005
schema/API detectors. It does three things:

1. Adapts an immutable :class:`~living_adr.core.scm.CandidateEvidence` bundle into
   a normalized :class:`ClassifierInput` (forward-slash paths, preserved status /
   line deltas / diff *handles* — never raw diff text).
2. Defines the shared detector vocabulary (:class:`Detection`,
   :class:`UncertaintyReason`, :class:`ConfidenceAssessment`) so the schema and
   API detectors and the confidence policy speak one language without a circular
   import (the policy/scoring *algorithm* lives in
   :mod:`living_adr.workflow.classifiers.confidence`).
3. Builds feature-004-compatible :class:`~living_adr.core.structural_change`
   records from a detection + its confidence assessment. Uncertainty/threshold
   metadata is recorded only in ``reason_code`` (change) and the evidence
   ``summary`` / ``provenance`` — never as new top-level fields.

Everything here is pure and deterministic: identical candidate evidence yields
byte-identical inputs and records (NFR-1).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import CandidateEvidence
from living_adr.core.structural_change import (
    ADRRecommendation,
    ChangeEvidence,
    ChangeOperation,
    ChangeType,
    EvidenceKind,
    NoAdrOutcome,
    ObservedOperation,
    StructuralChange,
    build_evidence_id,
    build_no_adr_outcome_id,
    build_structural_change_id,
    compute_evidence_hash,
)


class ClassifierInputError(ValueError):
    """Raised when candidate evidence cannot be safely adapted for classifiers."""


class UncertaintyReason(StrEnum):
    """Why static PR evidence cannot prove runtime / generated behavior (US-4).

    These are part of the explicit uncertainty taxonomy: a detection that carries
    any of these is flagged (lower confidence, uncertain ``reason_code``) rather
    than silently inflating certainty (FM-06, FM-07).
    """

    GENERATED_ARTIFACT = "generated_artifact"
    RUNTIME_REFLECTION = "runtime_reflection"
    FRAMEWORK_CONVENTION = "framework_convention"
    AMBIGUOUS_RENAME = "ambiguous_rename"
    DYNAMIC_ROUTING = "dynamic_routing"
    MISSING_CONTEXT = "missing_context"


def normalize_path(path: str) -> str:
    """Normalize a changed-file path to forward slashes, stripped of ``./``.

    Raises :class:`ClassifierInputError` for traversal paths (``..`` segments),
    which never appear in legitimate merged-PR evidence and would let a detector
    reason about content outside the repository scope (FM-18).
    """

    normalized = path.replace("\\", "/").strip()
    while normalized.startswith("./"):
        normalized = normalized[2:]
    segments = normalized.split("/")
    if ".." in segments:
        raise ClassifierInputError(f"path traversal not allowed: {path!r}")
    return normalized


class ChangedFileEvidence(BaseModel):
    """One normalized changed file: path, status, line deltas, and a diff handle."""

    model_config = ConfigDict(frozen=True)

    path: str
    status: str
    additions: int = 0
    deletions: int = 0
    diff_ref: str | None = None


class ClassifierInput(BaseModel):
    """Normalized, immutable classifier input adapted from feature 003 evidence."""

    model_config = ConfigDict(frozen=True)

    repository: RepositoryIdentity
    source_scm_event_id: str
    provider_delivery_id: str
    normalized_pr_key: str
    pr_number: int
    diff_handle: str
    diff_summary: str
    changed_files: tuple[ChangedFileEvidence, ...] = ()


def build_classifier_input(
    candidate: CandidateEvidence,
    *,
    expected_repository: RepositoryIdentity | None = None,
) -> ClassifierInput:
    """Adapt a feature 003 candidate-evidence bundle into a classifier input.

    ``expected_repository`` (when supplied) guards against cross-repository
    evidence: the candidate's repository key must match exactly, else
    :class:`ClassifierInputError` is raised (FM-18 minimal/scoped evidence).
    """

    if (
        expected_repository is not None
        and candidate.repository.key != expected_repository.key
    ):
        raise ClassifierInputError(
            "cross-repository evidence: "
            f"{candidate.repository.key!r} != {expected_repository.key!r}"
        )

    diff_handle = candidate.diff.diff_handle
    files = [
        ChangedFileEvidence(
            path=(path := normalize_path(changed.filename)),
            status=changed.status,
            additions=changed.additions,
            deletions=changed.deletions,
            diff_ref=f"{diff_handle}#{path}",
        )
        for changed in candidate.changed_files
    ]
    files.sort(key=lambda f: f.path)
    return ClassifierInput(
        repository=candidate.repository,
        source_scm_event_id=candidate.normalized_pr_key,
        provider_delivery_id=candidate.source_delivery_id,
        normalized_pr_key=candidate.normalized_pr_key,
        pr_number=candidate.pr_number,
        diff_handle=diff_handle,
        diff_summary=candidate.diff.summary,
        changed_files=tuple(files),
    )


@dataclass(frozen=True)
class Detection:
    """A single detector signal before confidence scoring/routing.

    Detectors emit detections; the confidence policy turns each into a
    :class:`ConfidenceAssessment`; :func:`make_structural_change` /
    :func:`make_no_adr` then build the feature-004-compatible records.
    """

    change_type: ChangeType
    subject: str
    source_path: str
    evidence_kind: EvidenceKind
    reason_code: str
    operation: ChangeOperation
    observed_operation: ObservedOperation
    base_confidence: float
    parser: str
    parser_version: str = "1.0.0"
    uncertainty: tuple[UncertaintyReason, ...] = ()
    uncertain_reason_code: str | None = None
    forced_no_adr: bool = False
    no_adr_reason: str | None = None
    note: str = ""


@dataclass(frozen=True)
class ConfidenceAssessment:
    """The scored routing decision for one :class:`Detection`."""

    confidence: float
    recommendation: ADRRecommendation
    threshold: float
    reason_code: str
    policy_id: str
    uncertainty: tuple[UncertaintyReason, ...] = field(default_factory=tuple)


CLASSIFIER_NAME = "schema-api-contract-change-detection"
CLASSIFIER_VERSION = "1.0.0"


def _evidence_summary(
    detection: Detection, assessment: ConfidenceAssessment
) -> str:
    reasons = (
        ",".join(u.value for u in assessment.uncertainty)
        if assessment.uncertainty
        else "none"
    )
    note = f"; {detection.note}" if detection.note else ""
    return (
        f"{detection.subject} {detection.change_type.value} "
        f"({assessment.reason_code}): operation={detection.operation.value}; "
        f"confidence={assessment.confidence}; uncertainty={reasons}{note}"
    )


def _provenance(
    inp: ClassifierInput, assessment: ConfidenceAssessment
) -> Mapping[str, str]:
    return {
        "source_delivery_id": inp.provider_delivery_id,
        "normalized_pr_key": inp.normalized_pr_key,
        "diff_handle": inp.diff_handle,
        "policy_id": assessment.policy_id,
        "threshold": str(assessment.threshold),
        "confidence": str(assessment.confidence),
        "uncertainty": (
            ",".join(u.value for u in assessment.uncertainty)
            if assessment.uncertainty
            else "none"
        ),
    }


def make_evidence(
    inp: ClassifierInput, detection: Detection, assessment: ConfidenceAssessment
) -> ChangeEvidence:
    """Build one immutable :class:`ChangeEvidence` for a detection (no raw diff)."""

    kind = detection.evidence_kind
    path = detection.source_path
    return ChangeEvidence(
        id=build_evidence_id(
            repository=inp.repository,
            source_scm_event_id=inp.source_scm_event_id,
            source_path=path,
            evidence_kind=kind,
        ),
        repository=inp.repository,
        source_scm_event_id=inp.source_scm_event_id,
        provider_delivery_id=inp.provider_delivery_id,
        normalized_pr_key=inp.normalized_pr_key,
        evidence_kind=kind,
        source_path=path,
        diff_hunk_ref=f"{inp.diff_handle}#{path}",
        before_value=None,
        after_value=None,
        observed_operation=detection.observed_operation,
        parser=detection.parser,
        parser_version=detection.parser_version,
        immutable_hash=compute_evidence_hash(
            repository=inp.repository,
            source_scm_event_id=inp.source_scm_event_id,
            source_path=path,
            evidence_kind=kind,
            before_value=None,
            after_value=None,
        ),
        summary=_evidence_summary(detection, assessment),
        provenance=_provenance(inp, assessment),
    )


def make_structural_change(
    inp: ClassifierInput,
    detection: Detection,
    evidence_id: str,
    assessment: ConfidenceAssessment,
) -> StructuralChange:
    """Build a draft-eligible feature-004-compatible :class:`StructuralChange`."""

    source_paths = (detection.source_path,)
    return StructuralChange(
        id=build_structural_change_id(
            repository=inp.repository,
            source_scm_event_id=inp.source_scm_event_id,
            change_type=detection.change_type,
            operation=detection.operation,
            affected_dependency=None,
            source_paths=source_paths,
        ),
        repository=inp.repository,
        source_scm_event_id=inp.source_scm_event_id,
        provider_delivery_id=inp.provider_delivery_id,
        normalized_pr_key=inp.normalized_pr_key,
        change_type=detection.change_type,
        operation=detection.operation,
        affected_dependency=None,
        dependency_ecosystem=None,
        source_paths=source_paths,
        evidence_ids=(evidence_id,),
        confidence=assessment.confidence,
        reason_code=assessment.reason_code,
        adr_recommendation=assessment.recommendation,
        classifier_name=CLASSIFIER_NAME,
        classifier_version=CLASSIFIER_VERSION,
    )


def make_no_adr(
    inp: ClassifierInput,
    detection: Detection,
    evidence_id: str,
    assessment: ConfidenceAssessment,
) -> NoAdrOutcome:
    """Build a retained below-threshold / uncertain :class:`NoAdrOutcome`."""

    source_paths = (detection.source_path,)
    return NoAdrOutcome(
        id=build_no_adr_outcome_id(
            repository=inp.repository,
            source_scm_event_id=inp.source_scm_event_id,
            change_type=detection.change_type,
            reason_code=assessment.reason_code,
            source_paths=source_paths,
        ),
        repository=inp.repository,
        source_scm_event_id=inp.source_scm_event_id,
        provider_delivery_id=inp.provider_delivery_id,
        normalized_pr_key=inp.normalized_pr_key,
        change_type=detection.change_type,
        reason_code=assessment.reason_code,
        confidence=assessment.confidence,
        source_paths=source_paths,
        evidence_ids=(evidence_id,),
    )


__all__ = [
    "ClassifierInputError",
    "UncertaintyReason",
    "normalize_path",
    "ChangedFileEvidence",
    "ClassifierInput",
    "build_classifier_input",
    "Detection",
    "ConfidenceAssessment",
    "CLASSIFIER_NAME",
    "CLASSIFIER_VERSION",
    "make_evidence",
    "make_structural_change",
    "make_no_adr",
]
