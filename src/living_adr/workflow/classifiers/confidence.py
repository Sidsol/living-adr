"""Confidence scoring, uncertainty penalties, and threshold routing (feature 005).

Implements the resolved ``semantic-change-default-v1`` policy (RD-005-1): a
conservative default threshold of ``0.70`` with per-repository overrides. The
scoring is explainable and bounded — a detection's ``base_confidence`` is reduced
by a fixed penalty per uncertainty reason, then routed to draft / no-ADR-needed.

Below-threshold and uncertain detections are *retained* (routed to
``no_adr_needed``), never dropped (FR-8). Feature 009 HITL review remains the
authoritative approval filter.

The shared vocabulary (:class:`Detection`, :class:`ConfidenceAssessment`,
:class:`UncertaintyReason`) lives in
:mod:`living_adr.workflow.classifiers.inputs` to avoid a circular import; this
module owns only the policy object and the scoring *algorithm*.
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

from living_adr.core.structural_change import ADRRecommendation, ReasonCode
from living_adr.workflow.classifiers.inputs import (
    ConfidenceAssessment,
    Detection,
)

POLICY_ID = "semantic-change-default-v1"
DEFAULT_THRESHOLD = 0.70
UNCERTAINTY_PENALTY = 0.15


def _clamp(value: float) -> float:
    return round(min(1.0, max(0.0, value)), 4)


class ConfidencePolicy(BaseModel):
    """Configurable, versioned threshold policy for schema/API routing.

    The default policy id and threshold are part of the contract recorded with
    every emitted record (evidence ``provenance``). ``repository_overrides`` maps
    a :class:`~living_adr.core.repository.RepositoryIdentity` ``key`` to a custom
    threshold so noisy or quiet repositories can be tuned without code changes.
    """

    model_config = ConfigDict(frozen=True)

    policy_id: str = POLICY_ID
    default_threshold: float = Field(default=DEFAULT_THRESHOLD, ge=0.0, le=1.0)
    uncertainty_penalty: float = Field(default=UNCERTAINTY_PENALTY, ge=0.0, le=1.0)
    repository_overrides: Mapping[str, float] = {}

    def threshold_for(self, repository_key: str) -> float:
        """Return the active threshold for a repository (override or default)."""

        return self.repository_overrides.get(repository_key, self.default_threshold)

    def score(self, detection: Detection) -> float:
        """Explainable, bounded confidence: base minus per-uncertainty penalty."""

        penalty = self.uncertainty_penalty * len(detection.uncertainty)
        return _clamp(detection.base_confidence - penalty)

    def assess(
        self, detection: Detection, repository_key: str
    ) -> ConfidenceAssessment:
        """Score and route a detection into a :class:`ConfidenceAssessment`."""

        threshold = self.threshold_for(repository_key)
        confidence = self.score(detection)

        if detection.forced_no_adr:
            reason = detection.no_adr_reason or ReasonCode.LOW_CONFIDENCE.value
            return ConfidenceAssessment(
                confidence=confidence,
                recommendation=ADRRecommendation.NO_ADR_NEEDED,
                threshold=threshold,
                reason_code=reason,
                policy_id=self.policy_id,
                uncertainty=detection.uncertainty,
            )

        uncertain = bool(detection.uncertainty)
        if confidence >= threshold:
            reason = (
                detection.uncertain_reason_code
                if uncertain and detection.uncertain_reason_code
                else detection.reason_code
            )
            recommendation = ADRRecommendation.DRAFT
        else:
            # Below threshold: retained, never dropped. Prefer an explicit
            # uncertainty reason code when one applies.
            reason = (
                detection.uncertain_reason_code
                if uncertain and detection.uncertain_reason_code
                else ReasonCode.LOW_CONFIDENCE.value
            )
            recommendation = ADRRecommendation.NO_ADR_NEEDED

        return ConfidenceAssessment(
            confidence=confidence,
            recommendation=recommendation,
            threshold=threshold,
            reason_code=reason,
            policy_id=self.policy_id,
            uncertainty=detection.uncertainty,
        )


__all__ = [
    "POLICY_ID",
    "DEFAULT_THRESHOLD",
    "UNCERTAINTY_PENALTY",
    "ConfidencePolicy",
]
