"""Slice S011-05 boundary + end-to-end contract for feature 011 publish-back.

Two guarantees are pinned here:

* **Read-side isolation** — the MCP context server (read path) never imports the
  ``publication`` package: publish-back is a write concern reached only after the
  approval boundary, never from a read tool (architecture #anti-patterns).
* **No SCM write without authorization** — a request whose decision was never
  consumed through feature 010's mutation boundary never reaches the committer.

The end-to-end test drives the real approval flow (mint → durable approval-bound
upsert → consumption) and then publishes the *same* approved record, proving the
full mint→consume→publish contract joins on ``decision_id`` with a single
``PUBLICATION_LINKED`` audit row and a committed file.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.approval._helpers import (
    DRAFT_HASH,
    DRAFT_MARKDOWN,
    FixedClock,
    SequentialIds,
    build_repo,
)
from tests.fakes.in_memory_graph_store import InMemoryGraphStore
from tests.publication._helpers import FakeSCMContents, build_config

from living_adr.approval.models import AuditEventType
from living_adr.approval.mutation_service import DurableApprovalBoundMutationService
from living_adr.approval.repository import InMemoryApprovalAuditRepository
from living_adr.apps.mcp_context_server import tools as mcp_tools
from living_adr.core.config import PublicationPolicy
from living_adr.publication import service as publication_service_mod
from living_adr.publication.models import (
    ADRPublicationRequest,
    PublicationNotAuthorizedError,
    PublicationStatus,
)
from living_adr.publication.repository import InMemoryPublicationRepository
from living_adr.publication.service import (
    ADRPublicationService,
    SCMContentsPublicationCommitter,
    resolve_publication_target,
)
from living_adr.workflow.approval_node import ApprovalMintingNode
from living_adr.workflow.nodes.stubs import StubMutationHandoffNode
from living_adr.workflow.state import (
    DraftRef,
    ReviewAction,
    ReviewResumeCommand,
    WorkflowState,
    WorkflowStatus,
)

# --- read-side isolation ---------------------------------------------------


def test_mcp_read_side_does_not_import_publication() -> None:
    package_dir = Path(mcp_tools.__file__).parent
    forbidden = ("living_adr.publication", "publication.service", "publish_to_github")
    for path in sorted(package_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for symbol in forbidden:
            assert symbol not in text, (
                f"{path.name} (MCP read side) must not reference {symbol!r}: "
                "publish-back is a write concern behind the approval boundary"
            )


# --- no SCM write without authorization ------------------------------------


class _FailIfCalledCommitter:
    def commit(self, request, target, authorization):  # noqa: ANN001
        raise AssertionError("committer reached without authorization")


def test_no_commit_when_decision_not_consumed() -> None:
    repo = build_repo()
    from tests.publication._helpers import build_adr, build_decision

    adr = build_adr(repo)
    decision = build_decision(repo, adr)
    service = ADRPublicationService(
        audit=InMemoryApprovalAuditRepository(),  # nothing consumed
        records=InMemoryPublicationRepository(),
        committer=_FailIfCalledCommitter(),
        clock=FixedClock(),
        id_provider=SequentialIds("pub-audit"),
    )
    request = ADRPublicationRequest(
        repository=repo,
        adr=adr,
        decision=decision,
        policy=PublicationPolicy.PUBLISH_TO_GITHUB,
        target=resolve_publication_target(build_config(repo)),
    )
    with pytest.raises(PublicationNotAuthorizedError):
        service.publish(request)


def test_publication_service_module_references_approval_validation() -> None:
    # The single publish entry point must route through feature 010's validation.
    text = Path(publication_service_mod.__file__).read_text(encoding="utf-8")
    assert "validate_for_mutation" in text


# --- full mint -> consume -> publish end-to-end ----------------------------


def test_mint_consume_publish_end_to_end() -> None:
    repo = build_repo()
    audit = InMemoryApprovalAuditRepository()
    store = InMemoryGraphStore()
    state = WorkflowState(
        repository=repo,
        normalized_event_key="github:acme/living-adr:7:delivery-1",
        draft=DraftRef(
            draft_id="draft-1",
            content_hash=DRAFT_HASH,
            preview=DRAFT_MARKDOWN,
            citation_ids=("ev-1",),
            structural_change_id="change-1",
        ),
        resume_command=ReviewResumeCommand(
            action=ReviewAction.APPROVE, reviewer_id="lead-1"
        ),
        status=WorkflowStatus.RESUMING,
    )
    # 1. mint the one-shot approved decision
    mint = ApprovalMintingNode(
        audit, clock=FixedClock(), id_provider=SequentialIds("mint")
    )
    decision = mint(state)["approved_decision"]
    authorised = state.model_copy(update={"approved_decision": decision})

    # 2. consume it through the durable approval-bound mutation boundary
    handoff = StubMutationHandoffNode(
        DurableApprovalBoundMutationService(
            store, audit, clock=FixedClock(), id_provider=SequentialIds("audit")
        )
    )
    handoff(authorised)
    adr = handoff.build_adr_record(authorised)

    # 3. publish the same approved record through the publication boundary
    contents = FakeSCMContents()
    publish = ADRPublicationService(
        audit=audit,
        records=InMemoryPublicationRepository(),
        committer=SCMContentsPublicationCommitter(contents),
        clock=FixedClock(),
        id_provider=SequentialIds("pub-audit"),
    )
    request = ADRPublicationRequest(
        repository=repo,
        adr=adr,
        decision=decision,
        policy=PublicationPolicy.PUBLISH_TO_GITHUB,
        target=resolve_publication_target(build_config(repo)),
    )
    result = publish.publish(request)

    assert result.status is PublicationStatus.COMMITTED
    assert result.decision_id == decision.decision_id
    # the file really landed in the fake repo
    assert contents.read_file(repo, "main", result.target_path) is not None
    # exactly one decision-linked publication audit row
    linked = [
        e
        for e in audit.list_audit_events(decision_id=decision.decision_id)
        if e.event_type is AuditEventType.PUBLICATION_LINKED
    ]
    assert len(linked) == 1
