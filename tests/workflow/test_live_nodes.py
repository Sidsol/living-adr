"""Phase 3 tests: evidence-backed classifier node + concrete DraftInputResolver.

Verifies the live drafting bridge over persisted CandidateEvidence: the
composite producer merges classifier output, the real classifier node drives
adr-needed routing, and the (previously missing) concrete DraftInputResolver
produces DraftInputs the real ClaudeADRDraftNode can draft from — all without a
network call.
"""

from __future__ import annotations

from living_adr.core.config import LivingADRConfig, PublicationPolicy, RepositoryConfig
from living_adr.core.llm import FakeClaudeClient
from living_adr.core.models import RepositoryIdentity
from living_adr.core.scm import CandidateEvidence, ChangedFileMetadata, DiffEvidence
from living_adr.core.structural_change import (
    ADRRecommendation,
    ChangeEvidence,
    ChangeOperation,
    ChangeType,
    EvidenceKind,
    ObservedOperation,
    StructuralChange,
)
from living_adr.workflow.live_nodes import (
    CompositeStructuralChangeProducer,
    EvidenceBackedClassifierNode,
    EvidenceBackedDraftInputResolver,
)
from living_adr.workflow.nodes.adr_draft import ClaudeADRDraftNode
from living_adr.workflow.state import WorkflowState, WorkflowStatus
from living_adr.workflow.structural_change_producer import (
    StructuralChangeProducerResult,
)

_VALID_MARKDOWN = """# Adopt requests 2.x
Status: proposed (PROVISIONAL — not authoritative until human approval)

## Context
A direct dependency requests was added to pyproject.toml.

## Decision
Adopt requests 2.x as the standard HTTP client.

## Alternatives
Vendor httpx; keep urllib.

## Consequences
New transitive dependency surface.

## Citations
- ev-1
"""


def _repo() -> RepositoryIdentity:
    return RepositoryIdentity(
        host="github.com", owner="acme", repo="widgets", repo_id="r1"
    )


def _repo_config() -> RepositoryConfig:
    return RepositoryConfig(
        identity=_repo(),
        github_app_installation_id="inst-1",
        default_branch="main",
        adr_publication_policy=PublicationPolicy.LIVINGADR_ONLY,
        external_llm_allowed=True,
    )


def _config() -> LivingADRConfig:
    return LivingADRConfig(repositories=[_repo_config()])


def _change(
    *,
    change_id: str = "chg-1",
    recommendation: ADRRecommendation = ADRRecommendation.DRAFT,
    evidence_ids: tuple[str, ...] = ("ev-1",),
) -> StructuralChange:
    return StructuralChange(
        id=change_id,
        repository=_repo(),
        source_scm_event_id="evt-1",
        provider_delivery_id="del-1",
        normalized_pr_key="pr-1",
        change_type=ChangeType.DEPENDENCY,
        operation=ChangeOperation.ADDED,
        affected_dependency="requests",
        dependency_ecosystem="python",
        source_paths=("pyproject.toml",),
        evidence_ids=evidence_ids,
        confidence=0.9,
        reason_code="direct_manifest_add",
        adr_recommendation=recommendation,
        classifier_name="dependency-change",
        classifier_version="1.0.0",
    )


def _evidence(evidence_id: str = "ev-1") -> ChangeEvidence:
    return ChangeEvidence(
        id=evidence_id,
        repository=_repo(),
        source_scm_event_id="evt-1",
        provider_delivery_id="del-1",
        normalized_pr_key="pr-1",
        evidence_kind=EvidenceKind.DEPENDENCY_MANIFEST,
        source_path="pyproject.toml",
        after_value="requests==2.32.0",
        observed_operation=ObservedOperation.ADDED,
        parser="pyproject-parser",
        parser_version="1.0.0",
        immutable_hash="hash-1",
        summary="Added requests==2.32.0.",
    )


def _candidate() -> CandidateEvidence:
    return CandidateEvidence(
        repository=_repo(),
        source_delivery_id="del-1",
        normalized_pr_key="pr-1",
        pr_number=1,
        pr_title="Add requests",
        changed_files=(
            ChangedFileMetadata(
                filename="pyproject.toml", status="modified", additions=1, deletions=0
            ),
        ),
        diff=DiffEvidence(
            diff_handle="github:/repos/acme/widgets/pulls/1.diff",
            summary="1 file(s) changed",
            truncated=False,
            byte_size=10,
        ),
        provider="github",
    )


def _result(
    *, changes: tuple[StructuralChange, ...], evidence: tuple[ChangeEvidence, ...]
) -> StructuralChangeProducerResult:
    return StructuralChangeProducerResult(changes=changes, evidence=evidence)


class _FakeClassifier:
    def __init__(self, result: StructuralChangeProducerResult) -> None:
        self._result = result

    def classify(self, candidate: object) -> StructuralChangeProducerResult:
        return self._result


class _FakeProducer:
    def __init__(self, result: StructuralChangeProducerResult) -> None:
        self._result = result

    def produce(self, candidate: object) -> StructuralChangeProducerResult:
        return self._result


class _FakeSource:
    def __init__(self, candidate: CandidateEvidence | None) -> None:
        self._candidate = candidate

    def get_evidence(self, normalized_pr_key: str) -> CandidateEvidence | None:
        if self._candidate is not None and normalized_pr_key == "pr-1":
            return self._candidate
        return None


def _state(refs: tuple[str, ...] = ("pr-1",)) -> WorkflowState:
    return WorkflowState(
        repository=_repo(), status=WorkflowStatus.CLASSIFYING, evidence_refs=refs
    )


# --- CompositeStructuralChangeProducer -------------------------------------


def test_composite_merges_and_dedupes_by_id() -> None:
    shared = _change(change_id="chg-1")
    a = _FakeClassifier(_result(changes=(shared,), evidence=(_evidence("ev-1"),)))
    b = _FakeClassifier(
        _result(
            changes=(shared, _change(change_id="chg-2", evidence_ids=("ev-2",))),
            evidence=(_evidence("ev-2"),),
        )
    )
    composite = CompositeStructuralChangeProducer(classifiers=(a, b))

    result = composite.produce(_candidate())

    assert tuple(c.id for c in result.changes) == ("chg-1", "chg-2")
    assert tuple(e.id for e in result.evidence) == ("ev-1", "ev-2")


# --- EvidenceBackedClassifierNode ------------------------------------------


def test_classifier_node_flags_adr_needed_for_eligible_change() -> None:
    producer = _FakeProducer(_result(changes=(_change(),), evidence=(_evidence(),)))
    node = EvidenceBackedClassifierNode(
        source=_FakeSource(_candidate()), producer=producer
    )

    update = node(_state())

    classification = update["classification"]
    assert classification.adr_needed is True
    assert classification.confidence == 0.9
    assert classification.evidence_ids == ("ev-1",)
    assert update["status"] is WorkflowStatus.CLASSIFYING


def test_classifier_node_no_adr_when_no_eligible_change() -> None:
    producer = _FakeProducer(_result(changes=(), evidence=()))
    node = EvidenceBackedClassifierNode(
        source=_FakeSource(_candidate()), producer=producer
    )

    update = node(_state())

    assert update["classification"].adr_needed is False
    assert update["status"] is WorkflowStatus.NO_ADR_NEEDED


def test_classifier_node_no_adr_when_candidate_missing() -> None:
    producer = _FakeProducer(_result(changes=(_change(),), evidence=(_evidence(),)))
    node = EvidenceBackedClassifierNode(source=_FakeSource(None), producer=producer)

    update = node(_state())

    assert update["classification"].adr_needed is False


# --- EvidenceBackedDraftInputResolver --------------------------------------


def test_resolver_builds_draft_inputs_with_supporting_evidence() -> None:
    producer = _FakeProducer(
        _result(changes=(_change(),), evidence=(_evidence("ev-1"), _evidence("ev-9")))
    )
    resolver = EvidenceBackedDraftInputResolver(
        source=_FakeSource(_candidate()), config=_config(), producer=producer
    )

    inputs = resolver.resolve(_state())

    assert inputs is not None
    assert inputs.change.id == "chg-1"
    assert tuple(e.id for e in inputs.evidence) == ("ev-1",)
    assert inputs.repository_config.identity.repo == "widgets"


def test_resolver_returns_none_without_eligible_change() -> None:
    producer = _FakeProducer(_result(changes=(), evidence=()))
    resolver = EvidenceBackedDraftInputResolver(
        source=_FakeSource(_candidate()), config=_config(), producer=producer
    )

    assert resolver.resolve(_state()) is None


def test_resolver_returns_none_when_candidate_missing() -> None:
    producer = _FakeProducer(_result(changes=(_change(),), evidence=(_evidence(),)))
    resolver = EvidenceBackedDraftInputResolver(
        source=_FakeSource(None), config=_config(), producer=producer
    )

    assert resolver.resolve(_state()) is None


def test_resolver_output_drives_real_claude_draft_node() -> None:
    producer = _FakeProducer(_result(changes=(_change(),), evidence=(_evidence(),)))
    resolver = EvidenceBackedDraftInputResolver(
        source=_FakeSource(_candidate()), config=_config(), producer=producer
    )
    node = ClaudeADRDraftNode(
        resolver=resolver,
        claude_client=FakeClaudeClient(response_text=_VALID_MARKDOWN),
        context_query=None,
    )

    update = node(_state())

    assert update["status"] is WorkflowStatus.DRAFTING
    draft = update["draft"]
    assert draft.provisional is True
    assert draft.structural_change_id == "chg-1"
    assert "ev-1" in draft.citation_ids
