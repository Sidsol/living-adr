"""Slice S-001 RED tests: generic structural-change producer protocol/result.

The producer result is the typed handoff Feature 008 consumes and Feature 005
reuses. It must hold draft-eligible changes, no-ADR outcomes, and the supporting
immutable evidence together, without leaking dependency-specific coupling into the
generic protocol.
"""

from __future__ import annotations

from living_adr.core.repository import RepositoryIdentity
from living_adr.core.structural_change import (
    ADRRecommendation,
    ChangeOperation,
    ChangeType,
    ReasonCode,
    StructuralChange,
    build_structural_change_id,
)
from living_adr.workflow.structural_change_producer import (
    StructuralChangeProducer,
    StructuralChangeProducerResult,
)

REPO = RepositoryIdentity(
    host="github.com", owner="acme", repo="widgets", repo_id="100"
)


def _change() -> StructuralChange:
    return StructuralChange(
        id=build_structural_change_id(
            repository=REPO,
            source_scm_event_id="evt-1",
            change_type=ChangeType.DEPENDENCY,
            operation=ChangeOperation.ADDED,
            affected_dependency=None,
            source_paths=("package.json",),
        ),
        repository=REPO,
        source_scm_event_id="evt-1",
        provider_delivery_id="d-1",
        normalized_pr_key="evt-1",
        change_type=ChangeType.DEPENDENCY,
        operation=ChangeOperation.ADDED,
        affected_dependency=None,
        dependency_ecosystem="npm",
        source_paths=("package.json",),
        evidence_ids=("ev-1",),
        confidence=0.8,
        reason_code=ReasonCode.DIRECT_MANIFEST_ADD,
        adr_recommendation=ADRRecommendation.DRAFT,
        classifier_name="dependency-change",
        classifier_version="1.0.0",
    )


def test_result_holds_changes_outcomes_and_evidence() -> None:
    result = StructuralChangeProducerResult(
        changes=(_change(),),
        no_adr_outcomes=(),
        evidence=(),
        diagnostics=(),
    )
    assert result.changes[0].change_type is ChangeType.DEPENDENCY
    assert result.no_adr_outcomes == ()
    assert result.draft_eligible_changes == (result.changes[0],)


def test_result_defaults_are_empty_tuples() -> None:
    result = StructuralChangeProducerResult()
    assert result.changes == ()
    assert result.no_adr_outcomes == ()
    assert result.evidence == ()
    assert result.diagnostics == ()


def test_producer_protocol_is_runtime_checkable() -> None:
    class FakeProducer:
        def produce(self, candidate: object) -> StructuralChangeProducerResult:
            return StructuralChangeProducerResult()

    assert isinstance(FakeProducer(), StructuralChangeProducer)

    class NotAProducer:
        pass

    assert not isinstance(NotAProducer(), StructuralChangeProducer)
