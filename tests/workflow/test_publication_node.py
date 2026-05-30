"""Slice S011-05 RED tests: publication handoff node (post-mutation, no state add).

The node runs *after* the approval-bound mutation, reuses the deterministic ADR
record builder, looks up the repository's :class:`RepositoryConfig`, and routes
the approved ADR through :class:`ADRPublicationService`. It must NOT add fields to
the frozen ``extra="forbid"`` workflow state (handoff side-effect only), and must
not publish when no authoritative mutation occurred or the repo is unconfigured.
"""

from __future__ import annotations

from tests.publication._helpers import (
    build_adr,
    build_config,
    build_decision,
    build_repo,
)

from living_adr.core.approval import ApprovedReviewDecision
from living_adr.workflow.publication_node import PublicationHandoffNode
from living_adr.workflow.state import (
    DraftRef,
    MutationOutcome,
    MutationResult,
    WorkflowState,
    WorkflowStatus,
)


class SpyPublicationService:
    """Captures the publish request; returns a canned result object."""

    def __init__(self, result: object = "published") -> None:
        self.requests: list[object] = []
        self._result = result

    def publish(self, request):  # noqa: ANN001
        self.requests.append(request)
        return self._result


def _mutated_state(repo, decision: ApprovedReviewDecision) -> WorkflowState:
    return WorkflowState(
        repository=repo,
        normalized_event_key="github:acme/living-adr:7:delivery-1",
        draft=DraftRef(
            draft_id="adr-1",
            content_hash=decision.adr_draft_content_hash,
            preview="# draft\n",
            citation_ids=("ev-1",),
            structural_change_id="change-1",
        ),
        approved_decision=decision,
        mutation_result=MutationResult(
            outcome=MutationOutcome.MUTATED,
            detail="approval-bound mutation performed",
            node_id="node:adr-1",
            decision_id=decision.decision_id,
            service_called=True,
        ),
        status=WorkflowStatus.COMPLETED,
    )


def test_node_publishes_after_authoritative_mutation() -> None:
    repo = build_repo()
    adr = build_adr(repo)
    decision = build_decision(repo, adr)
    config = build_config(repo)
    service = SpyPublicationService()
    node = PublicationHandoffNode(
        service=service, config_provider=lambda _r: config
    )

    result = node.publish_for_state(_mutated_state(repo, decision))

    assert result == "published"
    assert len(service.requests) == 1
    request = service.requests[0]
    assert request.repository == repo
    assert request.decision is decision
    assert request.policy is config.adr_publication_policy


def test_node_call_adds_no_workflow_state_fields() -> None:
    repo = build_repo()
    adr = build_adr(repo)
    decision = build_decision(repo, adr)
    node = PublicationHandoffNode(
        service=SpyPublicationService(), config_provider=lambda _r: build_config(repo)
    )
    state = _mutated_state(repo, decision)

    update = node(state)

    # Side-effect-only handoff: the update must not introduce new state keys,
    # so merging it back into the frozen extra="forbid" state cannot fail.
    assert set(update).issubset(set(WorkflowState.model_fields))
    state.model_copy(update=update)


def test_node_does_not_publish_without_authoritative_mutation() -> None:
    repo = build_repo()
    adr = build_adr(repo)
    decision = build_decision(repo, adr)
    service = SpyPublicationService()
    node = PublicationHandoffNode(
        service=service, config_provider=lambda _r: build_config(repo)
    )
    state = _mutated_state(repo, decision).model_copy(
        update={
            "mutation_result": MutationResult(
                outcome=MutationOutcome.NO_MUTATION,
                detail="no mutation service configured",
            )
        }
    )

    assert node.publish_for_state(state) is None
    assert service.requests == []


def test_node_does_not_publish_for_unconfigured_repository() -> None:
    repo = build_repo()
    adr = build_adr(repo)
    decision = build_decision(repo, adr)
    service = SpyPublicationService()
    node = PublicationHandoffNode(service=service, config_provider=lambda _r: None)

    assert node.publish_for_state(_mutated_state(repo, decision)) is None
    assert service.requests == []
