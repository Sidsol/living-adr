"""Slice 5 tests: confidence scoring, uncertainty, and threshold policy.

Pins the resolved RD-005-1 decision: a configurable ``semantic-change-default-v1``
policy with a conservative default threshold of ``0.70`` and per-repository
override support. Scoring is explainable and bounded; below-threshold and
uncertain detections are retained (routed to ``no_adr_needed``), never dropped
(US-4, US-5, FR-7, FR-8).
"""

from __future__ import annotations

import pytest

from living_adr.core.structural_change import (
    ADRRecommendation,
    ChangeOperation,
    ChangeType,
    EvidenceKind,
    ObservedOperation,
    ReasonCode,
)
from living_adr.workflow.classifiers.confidence import (
    DEFAULT_THRESHOLD,
    POLICY_ID,
    ConfidencePolicy,
)
from living_adr.workflow.classifiers.inputs import Detection, UncertaintyReason

REPO_KEY = "github.com/acme/widgets"


def _detection(
    *,
    base_confidence: float,
    uncertainty: tuple[UncertaintyReason, ...] = (),
    uncertain_reason_code: str | None = None,
    forced_no_adr: bool = False,
    no_adr_reason: str | None = None,
) -> Detection:
    return Detection(
        change_type=ChangeType.SCHEMA,
        subject="orders",
        source_path="db/migrations/0007.sql",
        evidence_kind=EvidenceKind.SCHEMA_MIGRATION,
        reason_code=ReasonCode.SCHEMA_MIGRATION.value,
        operation=ChangeOperation.ADDED,
        observed_operation=ObservedOperation.ADDED,
        base_confidence=base_confidence,
        parser="living-adr-schema-evidence",
        uncertainty=uncertainty,
        uncertain_reason_code=uncertain_reason_code,
        forced_no_adr=forced_no_adr,
        no_adr_reason=no_adr_reason,
    )


def test_policy_defaults_record_resolved_decision() -> None:
    policy = ConfidencePolicy()
    assert policy.policy_id == POLICY_ID == "semantic-change-default-v1"
    assert policy.default_threshold == DEFAULT_THRESHOLD == 0.70


def test_direct_evidence_is_draft_eligible() -> None:
    policy = ConfidencePolicy()
    assessment = policy.assess(_detection(base_confidence=0.85), REPO_KEY)
    assert assessment.confidence == 0.85
    assert assessment.recommendation is ADRRecommendation.DRAFT
    assert assessment.reason_code == ReasonCode.SCHEMA_MIGRATION
    assert assessment.threshold == 0.70
    assert assessment.policy_id == "semantic-change-default-v1"


def test_uncertainty_penalty_lowers_confidence() -> None:
    policy = ConfidencePolicy()
    one = policy.assess(
        _detection(
            base_confidence=0.85,
            uncertainty=(UncertaintyReason.GENERATED_ARTIFACT,),
            uncertain_reason_code=ReasonCode.SCHEMA_GENERATED_UNCERTAIN.value,
        ),
        REPO_KEY,
    )
    assert one.confidence == 0.70  # 0.85 - 0.15
    assert one.recommendation is ADRRecommendation.DRAFT
    assert one.reason_code == ReasonCode.SCHEMA_GENERATED_UNCERTAIN

    two = policy.assess(
        _detection(
            base_confidence=0.85,
            uncertainty=(
                UncertaintyReason.GENERATED_ARTIFACT,
                UncertaintyReason.RUNTIME_REFLECTION,
            ),
            uncertain_reason_code=ReasonCode.SCHEMA_GENERATED_UNCERTAIN.value,
        ),
        REPO_KEY,
    )
    assert two.confidence == 0.55  # 0.85 - 0.30
    assert two.recommendation is ADRRecommendation.NO_ADR_NEEDED


def test_below_threshold_without_uncertainty_is_low_confidence() -> None:
    policy = ConfidencePolicy()
    assessment = policy.assess(_detection(base_confidence=0.60), REPO_KEY)
    assert assessment.recommendation is ADRRecommendation.NO_ADR_NEEDED
    assert assessment.reason_code == ReasonCode.LOW_CONFIDENCE


def test_per_repository_override_changes_routing() -> None:
    policy = ConfidencePolicy(repository_overrides={REPO_KEY: 0.50})
    assert policy.threshold_for(REPO_KEY) == 0.50
    assert policy.threshold_for("other/repo") == 0.70
    assessment = policy.assess(_detection(base_confidence=0.60), REPO_KEY)
    assert assessment.recommendation is ADRRecommendation.DRAFT
    assert assessment.threshold == 0.50


def test_forced_no_adr_overrides_high_confidence() -> None:
    policy = ConfidencePolicy()
    assessment = policy.assess(
        _detection(
            base_confidence=0.90,
            forced_no_adr=True,
            no_adr_reason=ReasonCode.SEED_OR_TEST_ONLY.value,
        ),
        REPO_KEY,
    )
    assert assessment.recommendation is ADRRecommendation.NO_ADR_NEEDED
    assert assessment.reason_code == ReasonCode.SEED_OR_TEST_ONLY


def test_confidence_is_bounded_to_unit_interval() -> None:
    policy = ConfidencePolicy()
    assert policy.score(_detection(base_confidence=1.4)) == 1.0
    assert policy.score(
        _detection(
            base_confidence=0.10,
            uncertainty=(
                UncertaintyReason.GENERATED_ARTIFACT,
                UncertaintyReason.RUNTIME_REFLECTION,
            ),
        )
    ) == 0.0


def test_policy_threshold_is_validated() -> None:
    with pytest.raises(ValueError):
        ConfidencePolicy(default_threshold=1.5)
    with pytest.raises(ValueError):
        ConfidencePolicy(default_threshold=-0.1)


def test_policy_is_immutable() -> None:
    policy = ConfidencePolicy()
    with pytest.raises((TypeError, ValueError, AttributeError)):
        policy.default_threshold = 0.5  # type: ignore[misc]
