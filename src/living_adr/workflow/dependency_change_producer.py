"""Dependency change producer facade (feature 004, slice S-005).

The workflow-facing entry point that Feature 015 invokes and Feature 008 consumes.
It adapts the deterministic :class:`DependencyChangeClassifier` to the generic
:class:`StructuralChangeProducer` protocol, instruments the run with metadata-only
telemetry, and converts unexpected classifier failures into typed diagnostics so a
single bad PR never crashes the workflow (US-4, US-5).

Determinism is preserved end-to-end: the facade adds no clocks or ordering, so
``produce`` is replay-stable for identical candidate evidence.
"""

from __future__ import annotations

from living_adr.core.observability import NoOpObservability, Observability
from living_adr.core.scm import CandidateEvidence
from living_adr.observability.classification_events import (
    CLASSIFICATION_COMPLETED,
    CLASSIFICATION_ERROR,
    CLASSIFICATION_STARTED,
    completed_metadata,
    error_metadata,
    started_metadata,
)
from living_adr.workflow.dependency_classifier import (
    DependencyChangeClassifier,
    DependencyClassificationResult,
)
from living_adr.workflow.structural_change_producer import (
    StructuralChangeProducerResult,
)


class DependencyChangeProducer:
    """First concrete :class:`StructuralChangeProducer`: dependency changes."""

    def __init__(
        self,
        classifier: object | None = None,
        observability: Observability | None = None,
    ) -> None:
        self.classifier = classifier or DependencyChangeClassifier()
        self.observability: Observability = observability or NoOpObservability()

    def produce(self, candidate: object) -> StructuralChangeProducerResult:
        assert isinstance(candidate, CandidateEvidence)
        self.observability.record_event(
            CLASSIFICATION_STARTED, started_metadata(candidate)
        )

        try:
            result = self.classifier.classify(candidate)
        except Exception as exc:  # noqa: BLE001 - converted to typed diagnostics
            kind = type(exc).__name__
            self.observability.record_event(
                CLASSIFICATION_ERROR, error_metadata(candidate, kind)
            )
            return StructuralChangeProducerResult(
                changes=(),
                no_adr_outcomes=(),
                evidence=(),
                diagnostics=(f"classification_error:{kind}",),
            )

        assert isinstance(result, DependencyClassificationResult)
        self.observability.record_event(
            CLASSIFICATION_COMPLETED, completed_metadata(candidate, result)
        )
        return StructuralChangeProducerResult(
            changes=result.changes,
            no_adr_outcomes=result.no_adr_outcomes,
            evidence=result.evidence,
            diagnostics=result.diagnostics,
        )


__all__ = ["DependencyChangeProducer"]
