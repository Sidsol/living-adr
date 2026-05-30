"""Feature 005 schema/API contract change classifiers.

Stable workflow-facing surface for feature 015 (workflow orchestration) and
feature 008 (ADR drafting). Detector rule tables are intentionally *not* exported
— only the input adapter, the confidence policy, and (after slice 6) the service
facade are part of the contract.
"""

from __future__ import annotations

from living_adr.workflow.classifiers.api_contract import APIContractChangeDetector
from living_adr.workflow.classifiers.confidence import (
    DEFAULT_THRESHOLD,
    POLICY_ID,
    ConfidencePolicy,
)
from living_adr.workflow.classifiers.inputs import (
    ChangedFileEvidence,
    ClassifierInput,
    ClassifierInputError,
    UncertaintyReason,
    build_classifier_input,
)
from living_adr.workflow.classifiers.schema import SchemaChangeDetector
from living_adr.workflow.classifiers.service import SchemaApiContractClassifier

__all__ = [
    "ChangedFileEvidence",
    "ClassifierInput",
    "ClassifierInputError",
    "UncertaintyReason",
    "build_classifier_input",
    "ConfidencePolicy",
    "POLICY_ID",
    "DEFAULT_THRESHOLD",
    "SchemaChangeDetector",
    "APIContractChangeDetector",
    "SchemaApiContractClassifier",
]
