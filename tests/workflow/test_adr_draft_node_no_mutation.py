"""S-006 RED tests: draft-node no-mutation boundary (feature 008, US-6/NFR-1).

These tests pin the invariant that the draft node is *inert*: it produces a
provisional draft and never performs (or even depends on) authoritative graph
mutation, approval minting, audit persistence, reviewer UI, or GitHub publish.
The node's state update touches only draft/status fields — never
``mutation_result`` or ``approved_decision``.
"""

from __future__ import annotations

import inspect

from living_adr.core.config import PublicationPolicy, RepositoryConfig
from living_adr.core.llm import FakeClaudeClient
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
from living_adr.workflow.nodes import adr_draft as adr_draft_module
from living_adr.workflow.nodes.adr_draft import ClaudeADRDraftNode, DraftInputs
from living_adr.workflow.state import WorkflowState, WorkflowStatus

_VALID_MARKDOWN = """# Adopt requests 2.x
Status: proposed (PROVISIONAL — not authoritative until human approval)

## Context
A direct dependency requests was added.

## Decision
Adopt requests 2.x.

## Alternatives
Vendor httpx.

## Consequences
New transitive surface.

## Citations
- ev-1
"""


def _repo() -> RepositoryIdentity:
    return RepositoryIdentity(
        host="github.com", owner="acme", repo="widgets", repo_id="r1"
    )


def _inputs() -> DraftInputs:
    change = StructuralChange(
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
        adr_recommendation=ADRRecommendation.DRAFT,
        classifier_name="dependency-change",
        classifier_version="1.0.0",
    )
    evidence = (
        ChangeEvidence(
            id="ev-1",
            repository=_repo(),
            source_scm_event_id="evt-1",
            provider_delivery_id="del-1",
            normalized_pr_key="pr-1",
            evidence_kind=EvidenceKind.DEPENDENCY_MANIFEST,
            source_path="pyproject.toml",
            after_value="requests==2.32.0",
            observed_operation=ObservedOperation.ADDED,
            parser="p",
            parser_version="1",
            immutable_hash="h",
            summary="Added requests==2.32.0.",
        ),
    )
    config = RepositoryConfig(
        identity=_repo(),
        github_app_installation_id="inst-1",
        default_branch="main",
        adr_publication_policy=PublicationPolicy.LIVINGADR_ONLY,
        external_llm_allowed=True,
    )
    return DraftInputs(
        repository=_repo(), change=change, evidence=evidence, repository_config=config
    )


class _Resolver:
    def resolve(self, state: WorkflowState) -> DraftInputs:
        return _inputs()


class _RecordingQuery:
    """Read-only fake that records every call (only read methods exist)."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def answer_why(
        self, repository, question, code_area_id=None, snapshot=None, limit=5
    ):
        from living_adr.core.graph.models import WhyAnswer

        self.calls.append("answer_why")
        return WhyAnswer(
            repository=repository,
            question=question,
            answer="",
            adr_id=None,
            citations=(),
            found=False,
        )

    def traverse_from_code_area(
        self,
        repository,
        code_area_id,
        relationship_types=None,
        max_depth=2,
        snapshot=None,
    ):
        self.calls.append("traverse_from_code_area")
        return []


def _run() -> dict:
    node = ClaudeADRDraftNode(
        resolver=_Resolver(),
        claude_client=FakeClaudeClient(response_text=_VALID_MARKDOWN),
        context_query=_RecordingQuery(),
    )
    return dict(node(WorkflowState(repository=_repo(), status=WorkflowStatus.DRAFTING)))


def test_state_update_touches_only_draft_fields() -> None:
    update = _run()
    assert set(update.keys()) <= {"draft", "status"}
    assert "mutation_result" not in update
    assert "approved_decision" not in update
    assert "review_request" not in update


def test_draft_is_provisional_and_non_authoritative() -> None:
    update = _run()
    assert update["draft"].provisional is True
    assert update["status"] is WorkflowStatus.DRAFTING


def test_query_used_read_only() -> None:
    query = _RecordingQuery()
    node = ClaudeADRDraftNode(
        resolver=_Resolver(),
        claude_client=FakeClaudeClient(response_text=_VALID_MARKDOWN),
        context_query=query,
    )
    node(WorkflowState(repository=_repo(), status=WorkflowStatus.DRAFTING))
    assert set(query.calls) <= {"answer_why", "traverse_from_code_area"}


def test_node_module_imports_no_mutation_or_approval_machinery() -> None:
    """The draft node must not depend on write/approval/publish components."""

    source = inspect.getsource(adr_draft_module)
    import_lines = [
        line
        for line in source.splitlines()
        if line.startswith(("import ", "from "))
    ]
    import_block = "\n".join(import_lines)
    forbidden = (
        "ArchitectureGraphStore",
        "ApprovalBoundMutationService",
        "ApprovedReviewDecision",
        "approval_bound_mutation",
        "github_provider",
        "github_webhook",
    )
    for symbol in forbidden:
        assert symbol not in import_block, f"draft node must not import {symbol}"
