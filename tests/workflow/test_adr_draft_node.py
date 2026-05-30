"""S-006 RED tests: feature-015 ADR draft node seam (feature 008, US-6).

Exercises the real ``ClaudeADRDraftNode`` against a fake feature-015
``WorkflowState``, Feature 004 production change/evidence, a fake graph query, and
a fake Claude client. Covers the happy path plus every typed non-draft outcome
route (FR-9): no-ADR, policy denied, missing evidence, budget exceeded, provider
error, and invalid output — all without any real network call.
"""

from __future__ import annotations

from living_adr.core.config import (
    PublicationPolicy,
    RepositoryConfig,
)
from living_adr.core.graph.models import ADRPath, ADRRef, WhyAnswer
from living_adr.core.llm import ClaudeProviderError, FakeClaudeClient
from living_adr.core.models import RepositoryIdentity
from living_adr.core.structural_change import (
    ADRRecommendation,
    ChangeEvidence,
    ChangeOperation,
    ChangeType,
    EvidenceKind,
    ObservedOperation,
    StructuralChange,
)
from living_adr.workflow.nodes.adr_draft import (
    ClaudeADRDraftNode,
    DraftInputs,
)
from living_adr.workflow.nodes.protocols import ADRDraftNode
from living_adr.workflow.state import WorkflowState, WorkflowStatus

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
- adr-3
"""


def _repo() -> RepositoryIdentity:
    return RepositoryIdentity(
        host="github.com", owner="acme", repo="widgets", repo_id="r1"
    )


def _config(*, allowed: bool = True) -> RepositoryConfig:
    return RepositoryConfig(
        identity=_repo(),
        github_app_installation_id="inst-1",
        default_branch="main",
        adr_publication_policy=PublicationPolicy.LIVINGADR_ONLY,
        external_llm_allowed=allowed,
    )


def _change(
    recommendation: ADRRecommendation = ADRRecommendation.DRAFT,
) -> StructuralChange:
    return StructuralChange(
        id="chg-1",
        repository=_repo(),
        source_scm_event_id="evt-1",
        provider_delivery_id="del-1",
        normalized_pr_key="pr-1",
        change_type=ChangeType.DEPENDENCY,
        operation=ChangeOperation.ADDED,
        affected_dependency="requests",
        dependency_ecosystem="python",
        source_paths=("pyproject.toml",),
        evidence_ids=("ev-1",),
        confidence=0.9,
        reason_code="direct_manifest_add",
        adr_recommendation=recommendation,
        classifier_name="dependency-change",
        classifier_version="1.0.0",
    )


def _evidence() -> tuple[ChangeEvidence, ...]:
    return (
        ChangeEvidence(
            id="ev-1",
            repository=_repo(),
            source_scm_event_id="evt-1",
            provider_delivery_id="del-1",
            normalized_pr_key="pr-1",
            evidence_kind=EvidenceKind.DEPENDENCY_MANIFEST,
            source_path="pyproject.toml",
            before_value=None,
            after_value="requests==2.32.0",
            observed_operation=ObservedOperation.ADDED,
            parser="pyproject-parser",
            parser_version="1.0.0",
            immutable_hash="hash-1",
            summary="Added requests==2.32.0.",
        ),
    )


class _FakeQuery:
    def answer_why(
        self, repository, question, code_area_id=None, snapshot=None, limit=5
    ):
        return WhyAnswer(
            repository=repository,
            question=question,
            answer="Standardized on requests.",
            adr_id="adr-3",
            citations=("adr-3",),
            found=True,
        )

    def traverse_from_code_area(
        self,
        repository,
        code_area_id,
        relationship_types=None,
        max_depth=2,
        snapshot=None,
    ):
        ref = ADRRef(
            repository=repository, adr_id="adr-3", title="HTTP", status="approved"
        )
        return [ADRPath(repository=repository, code_area_id=code_area_id, adrs=(ref,))]


class _StaticResolver:
    def __init__(self, inputs: DraftInputs | None) -> None:
        self._inputs = inputs

    def resolve(self, state: WorkflowState) -> DraftInputs | None:
        return self._inputs


def _inputs(*, allowed: bool = True, evidence=None, change=None) -> DraftInputs:
    return DraftInputs(
        repository=_repo(),
        change=change or _change(),
        evidence=_evidence() if evidence is None else evidence,
        repository_config=_config(allowed=allowed),
    )


def _state() -> WorkflowState:
    return WorkflowState(repository=_repo(), status=WorkflowStatus.DRAFTING)


def _node(
    *, inputs: DraftInputs | None, client=None, query=None, budget=None
) -> ClaudeADRDraftNode:
    return ClaudeADRDraftNode(
        resolver=_StaticResolver(inputs),
        claude_client=client or FakeClaudeClient(response_text=_VALID_MARKDOWN),
        context_query=query if query is not None else _FakeQuery(),
        budget_config=budget,
    )


def test_node_satisfies_feature_015_seam() -> None:
    node = _node(inputs=_inputs())
    assert isinstance(node, ADRDraftNode)


def test_happy_path_produces_provisional_draft() -> None:
    client = FakeClaudeClient(response_text=_VALID_MARKDOWN)
    node = _node(inputs=_inputs(), client=client)
    update = node(_state())

    assert update["status"] is WorkflowStatus.DRAFTING
    draft = update["draft"]
    assert draft.provisional is True
    assert draft.content_hash
    assert draft.structural_change_id == "chg-1"
    assert "ev-1" in draft.citation_ids
    assert "adr-3" in draft.citation_ids
    assert len(client.calls) == 1


def test_no_adr_change_skips_claude() -> None:
    client = FakeClaudeClient(response_text=_VALID_MARKDOWN)
    node = _node(
        inputs=_inputs(change=_change(ADRRecommendation.NO_ADR_NEEDED)),
        client=client,
    )
    update = node(_state())
    assert update["status"] is WorkflowStatus.NO_ADR_NEEDED
    assert "draft" not in update
    assert client.calls == []


def test_unresolved_inputs_route_to_no_adr() -> None:
    client = FakeClaudeClient(response_text=_VALID_MARKDOWN)
    node = _node(inputs=None, client=client)
    update = node(_state())
    assert update["status"] is WorkflowStatus.NO_ADR_NEEDED
    assert client.calls == []


def test_policy_denied_skips_claude() -> None:
    client = FakeClaudeClient(response_text=_VALID_MARKDOWN)
    node = _node(inputs=_inputs(allowed=False), client=client)
    update = node(_state())
    assert update["status"] is WorkflowStatus.FAILED
    assert update["error"].category == "llm_policy_denied"
    assert client.calls == []


def test_missing_evidence_skips_claude() -> None:
    client = FakeClaudeClient(response_text=_VALID_MARKDOWN)
    node = _node(inputs=_inputs(evidence=()), client=client)
    update = node(_state())
    assert update["status"] is WorkflowStatus.FAILED
    assert update["error"].category == "missing_evidence"
    assert client.calls == []


def test_budget_exceeded_skips_claude() -> None:
    from living_adr.workflow.drafting.token_budget import BudgetConfig

    client = FakeClaudeClient(response_text=_VALID_MARKDOWN)
    node = _node(
        inputs=_inputs(), client=client, budget=BudgetConfig(max_prompt_tokens=1)
    )
    update = node(_state())
    assert update["status"] is WorkflowStatus.FAILED
    assert update["error"].category == "budget_exceeded"
    assert client.calls == []


def test_provider_error_is_routed() -> None:
    client = FakeClaudeClient(error=ClaudeProviderError("boom"))
    node = _node(inputs=_inputs(), client=client)
    update = node(_state())
    assert update["status"] is WorkflowStatus.FAILED
    assert update["error"].category == "provider_error"
    assert len(client.calls) == 1


def test_invalid_output_is_routed() -> None:
    client = FakeClaudeClient(response_text="not an adr at all")
    node = _node(inputs=_inputs(), client=client)
    update = node(_state())
    assert update["status"] is WorkflowStatus.FAILED
    assert update["error"].category == "invalid_output"
