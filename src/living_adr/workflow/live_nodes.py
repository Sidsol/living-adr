"""Evidence-backed real workflow nodes for the live drafting path (Phase 3).

Bridges persisted ingestion evidence to the real classifier and draft seams so a
merged PR produces a genuine, classifier-grounded ADR draft instead of the
walking-skeleton smoke fixture. It provides:

* :class:`CompositeStructuralChangeProducer` — runs the schema/API and dependency
  classifiers over the same :class:`CandidateEvidence` and merges their typed
  output (deduplicated by id), so a PR touching dependencies and/or API/schema
  both yield draft-eligible changes;
* :class:`EvidenceBackedClassifierNode` — the real ``StructuralClassifierNode``:
  loads the ``CandidateEvidence`` referenced by the workflow state and writes a
  :class:`ClassificationResult` that drives the adr-needed routing;
* :class:`EvidenceBackedDraftInputResolver` — the (previously missing) concrete
  ``DraftInputResolver``: turns the workflow state + persisted evidence into the
  :class:`DraftInputs` the ``ClaudeADRDraftNode`` drafts from.

All classification is pure over ``CandidateEvidence`` (no network, no raw diff
text): the classifiers consume only changed-file metadata and diff handles.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from living_adr.workflow.classifiers.service import SchemaApiContractClassifier
from living_adr.workflow.dependency_classifier import DependencyChangeClassifier
from living_adr.workflow.nodes.adr_draft import DraftInputs
from living_adr.workflow.state import (
    ClassificationResult,
    WorkflowState,
    WorkflowStatus,
)
from living_adr.workflow.structural_change_producer import (
    StructuralChangeProducerResult,
)

if TYPE_CHECKING:
    from collections.abc import Mapping, Sequence
    from typing import Any

    from living_adr.core.config import LivingADRConfig
    from living_adr.core.scm import CandidateEvidence

    StateUpdate = Mapping[str, Any]


class EvidenceSource(Protocol):
    """Read port over the ingestion store used to load candidate evidence."""

    def get_evidence(self, normalized_pr_key: str) -> CandidateEvidence | None: ...


class StructuralChangeProducer(Protocol):
    """A producer turning candidate evidence into a typed structural-change bundle."""

    def produce(self, candidate: object) -> StructuralChangeProducerResult: ...


class CompositeStructuralChangeProducer:
    """Runs several classifiers over one candidate and merges their results.

    Each classifier is pure over ``CandidateEvidence`` and exposes ``classify``
    (the schema/API and dependency classifiers both do). Changes, evidence, and
    no-ADR outcomes are de-duplicated by id and returned in deterministic id
    order, so injecting this producer keeps the workflow classifier-agnostic.
    """

    def __init__(self, classifiers: Sequence[object] | None = None) -> None:
        self._classifiers: tuple[object, ...] = (
            tuple(classifiers)
            if classifiers is not None
            else (SchemaApiContractClassifier(), DependencyChangeClassifier())
        )

    def produce(self, candidate: object) -> StructuralChangeProducerResult:
        changes: dict[str, object] = {}
        outcomes: dict[str, object] = {}
        evidence: dict[str, object] = {}
        diagnostics: list[str] = []
        for classifier in self._classifiers:
            result = classifier.classify(candidate)
            for change in result.changes:
                changes[change.id] = change
            for outcome in result.no_adr_outcomes:
                outcomes[outcome.id] = outcome
            for item in result.evidence:
                evidence[item.id] = item
            diagnostics.extend(result.diagnostics)
        return StructuralChangeProducerResult(
            changes=tuple(sorted(changes.values(), key=lambda c: c.id)),
            no_adr_outcomes=tuple(sorted(outcomes.values(), key=lambda o: o.id)),
            evidence=tuple(sorted(evidence.values(), key=lambda e: e.id)),
            diagnostics=tuple(diagnostics),
        )


def load_candidate(
    state: WorkflowState, source: EvidenceSource
) -> CandidateEvidence | None:
    """Load the candidate evidence the workflow state references, if present."""

    for ref in state.evidence_refs:
        candidate = source.get_evidence(ref)
        if candidate is not None:
            return candidate
    return None


class EvidenceBackedClassifierNode:
    """Real ``StructuralClassifierNode`` over persisted candidate evidence."""

    def __init__(
        self,
        *,
        source: EvidenceSource,
        producer: StructuralChangeProducer | None = None,
    ) -> None:
        self._source = source
        self._producer = producer or CompositeStructuralChangeProducer()

    def __call__(self, state: WorkflowState) -> StateUpdate:
        candidate = load_candidate(state, self._source)
        if candidate is None:
            return self._no_adr("no candidate evidence available for classification")

        result = self._producer.produce(candidate)
        eligible = result.draft_eligible_changes
        if not eligible:
            return self._no_adr("no architecture-significant change detected")

        evidence_ids = tuple(
            sorted({eid for change in eligible for eid in change.evidence_ids})
        )
        confidence = max(change.confidence for change in eligible)
        # ClassificationResult.changes uses the orchestration smoke
        # `core.models.StructuralChange`; the production
        # `core.structural_change.StructuralChange` flows to drafting via the
        # resolver. Here we carry only the routing signal (adr-needed + the
        # supporting evidence ids/confidence), leaving `changes` empty.
        return {
            "classification": ClassificationResult(
                adr_needed=True,
                confidence=confidence,
                evidence_ids=evidence_ids,
            ),
            "status": WorkflowStatus.CLASSIFYING,
        }

    @staticmethod
    def _no_adr(reason: str) -> StateUpdate:
        return {
            "classification": ClassificationResult(
                adr_needed=False, no_adr_reason=reason
            ),
            "status": WorkflowStatus.NO_ADR_NEEDED,
        }


class EvidenceBackedDraftInputResolver:
    """Concrete ``DraftInputResolver``: workflow state + evidence -> DraftInputs."""

    def __init__(
        self,
        *,
        source: EvidenceSource,
        config: LivingADRConfig,
        producer: StructuralChangeProducer | None = None,
    ) -> None:
        self._source = source
        self._config = config
        self._producer = producer or CompositeStructuralChangeProducer()

    def resolve(self, state: WorkflowState) -> DraftInputs | None:
        candidate = load_candidate(state, self._source)
        if candidate is None:
            return None

        result = self._producer.produce(candidate)
        eligible = result.draft_eligible_changes
        if not eligible:
            return None

        repository_config = self._config.get(candidate.repository.key)
        if repository_config is None:
            return None

        change = eligible[0]
        wanted = set(change.evidence_ids)
        supporting = tuple(item for item in result.evidence if item.id in wanted)
        return DraftInputs(
            repository=candidate.repository,
            change=change,
            evidence=supporting or result.evidence,
            repository_config=repository_config,
        )


__all__ = [
    "EvidenceSource",
    "StructuralChangeProducer",
    "CompositeStructuralChangeProducer",
    "EvidenceBackedClassifierNode",
    "EvidenceBackedDraftInputResolver",
    "load_candidate",
]
