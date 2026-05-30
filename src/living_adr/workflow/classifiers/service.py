"""Workflow-facing schema/API classifier service (feature 005, slice 6).

The single entry point feature 015 invokes and feature 008 consumes. It runs the
schema and API detectors over one feature 003 candidate-evidence bundle, merges
their outputs (de-duplicated by deterministic id, schema/API kept distinct),
records metadata-only telemetry, and converts unexpected detector failures into
typed diagnostics so a single bad PR never crashes the workflow (US-3, US-6).

It adapts the feature 005 detectors to the *same*
:class:`~living_adr.workflow.structural_change_producer.StructuralChangeProducer`
protocol the dependency producer (feature 004) implements, so downstream
orchestration never special-cases a classifier. Determinism is preserved
end-to-end: no clocks, no ordering hazards.
"""

from __future__ import annotations

from living_adr.core.observability import NoOpObservability, Observability
from living_adr.core.scm import CandidateEvidence
from living_adr.workflow.classifiers.api_contract import APIContractChangeDetector
from living_adr.workflow.classifiers.confidence import ConfidencePolicy
from living_adr.workflow.classifiers.inputs import (
    DetectorOutcome,
    build_classifier_input,
)
from living_adr.workflow.classifiers.schema import SchemaChangeDetector
from living_adr.workflow.structural_change_producer import (
    StructuralChangeProducerResult,
)

CLASSIFICATION_STARTED = "schema_api_classification.started"
CLASSIFICATION_COMPLETED = "schema_api_classification.completed"
CLASSIFICATION_ERROR = "schema_api_classification.error"


def _started_metadata(candidate: CandidateEvidence) -> dict[str, object]:
    return {
        "repository_key": candidate.repository.key,
        "normalized_pr_key": candidate.normalized_pr_key,
        "changed_file_count": len(candidate.changed_files),
    }


def _completed_metadata(
    candidate: CandidateEvidence,
    result: StructuralChangeProducerResult,
    policy_id: str,
) -> dict[str, object]:
    """Metadata-only completion telemetry (no raw diff/handle/content; FM-21)."""

    change_types = sorted(
        {c.change_type.value for c in result.changes}
        | {o.change_type.value for o in result.no_adr_outcomes}
    )
    reason_codes = sorted(
        {c.reason_code for c in result.changes}
        | {o.reason_code for o in result.no_adr_outcomes}
    )
    uncertainty: set[str] = set()
    for ev in result.evidence:
        token = ev.provenance.get("uncertainty", "none")
        if token and token != "none":
            uncertainty.update(token.split(","))
    confidences = [c.confidence for c in result.changes]
    confidences += [o.confidence for o in result.no_adr_outcomes]
    return {
        "repository_key": candidate.repository.key,
        "normalized_pr_key": candidate.normalized_pr_key,
        "policy_id": policy_id,
        "change_count": len(result.changes),
        "draft_count": len(result.draft_eligible_changes),
        "no_adr_count": len(result.no_adr_outcomes),
        "evidence_count": len(result.evidence),
        "change_types": tuple(change_types),
        "reason_codes": tuple(reason_codes),
        "uncertainty_reasons": tuple(sorted(uncertainty)),
        "max_confidence": max(confidences, default=0.0),
    }


def _error_metadata(
    candidate: CandidateEvidence, error_kind: str
) -> dict[str, object]:
    return {
        "repository_key": candidate.repository.key,
        "normalized_pr_key": candidate.normalized_pr_key,
        "error_kind": error_kind,
    }


class SchemaApiContractClassifier:
    """Concrete :class:`StructuralChangeProducer` for schema/API contract changes."""

    def __init__(
        self,
        policy: ConfidencePolicy | None = None,
        observability: Observability | None = None,
        schema_detector: object | None = None,
        api_detector: object | None = None,
    ) -> None:
        self.policy = policy or ConfidencePolicy()
        self.observability: Observability = observability or NoOpObservability()
        self.schema_detector = schema_detector or SchemaChangeDetector(self.policy)
        self.api_detector = api_detector or APIContractChangeDetector(self.policy)

    def produce(self, candidate: object) -> StructuralChangeProducerResult:
        assert isinstance(candidate, CandidateEvidence)
        self.observability.record_event(
            CLASSIFICATION_STARTED, _started_metadata(candidate)
        )

        try:
            inp = build_classifier_input(candidate)
            schema_outcome = self.schema_detector.detect(inp)
            api_outcome = self.api_detector.detect(inp)
        except Exception as exc:  # noqa: BLE001 - converted to typed diagnostics
            kind = type(exc).__name__
            self.observability.record_event(
                CLASSIFICATION_ERROR, _error_metadata(candidate, kind)
            )
            return StructuralChangeProducerResult(
                changes=(),
                no_adr_outcomes=(),
                evidence=(),
                diagnostics=(f"classification_error:{kind}",),
            )

        assert isinstance(schema_outcome, DetectorOutcome)
        assert isinstance(api_outcome, DetectorOutcome)
        result = self._merge(schema_outcome, api_outcome)
        self.observability.record_event(
            CLASSIFICATION_COMPLETED,
            _completed_metadata(candidate, result, self.policy.policy_id),
        )
        return result

    # Convenience alias mirroring the dependency classifier vocabulary.
    def classify(self, candidate: object) -> StructuralChangeProducerResult:
        return self.produce(candidate)

    @staticmethod
    def _merge(
        schema_outcome: DetectorOutcome, api_outcome: DetectorOutcome
    ) -> StructuralChangeProducerResult:
        changes = {c.id: c for c in schema_outcome.changes}
        changes.update({c.id: c for c in api_outcome.changes})
        outcomes = {o.id: o for o in schema_outcome.no_adr_outcomes}
        outcomes.update({o.id: o for o in api_outcome.no_adr_outcomes})
        evidence = {e.id: e for e in schema_outcome.evidence}
        evidence.update({e.id: e for e in api_outcome.evidence})
        return StructuralChangeProducerResult(
            changes=tuple(sorted(changes.values(), key=lambda c: c.id)),
            no_adr_outcomes=tuple(
                sorted(outcomes.values(), key=lambda o: (o.reason_code, o.id))
            ),
            evidence=tuple(sorted(evidence.values(), key=lambda e: e.id)),
            diagnostics=(),
        )


__all__ = [
    "SchemaApiContractClassifier",
    "CLASSIFICATION_STARTED",
    "CLASSIFICATION_COMPLETED",
    "CLASSIFICATION_ERROR",
]
