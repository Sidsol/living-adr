"""Slice S010-07: feature-011 publish-back consumption contract.

Feature 011 (GitHub publish-back) is *not* implemented here. This contract test
pins the clean seam feature 010 leaves for it, so a later feature can publish an
approved ADR without reaching past the approval boundary:

* the :class:`ApprovedReviewDecision` capability exposes exactly the fields a
  publisher needs to correlate a published artefact to its authorising decision;
* a consumed decision yields a durable ``decision_id → graph node`` link plus a
  ``MUTATION_PERFORMED`` audit row feature 011 can publish from;
* ``PUBLICATION_LINKED`` is a *reserved* audit type — feature 010 never emits it
  (no GitHub publish happens here), proving the seam is documented but unbuilt;
* the approval package references no GitHub publication provider.
"""

from __future__ import annotations

from pathlib import Path

from tests.approval._helpers import (
    DRAFT_HASH,
    DRAFT_MARKDOWN,
    FixedClock,
    SequentialIds,
    build_repo,
)
from tests.fakes.in_memory_graph_store import InMemoryGraphStore

from living_adr.approval import mutation_service as mutation_service_mod
from living_adr.approval.audit_queries import (
    build_decision_audit_trail,
    decision_mutation_links,
)
from living_adr.approval.models import ApprovedReviewDecision, AuditEventType
from living_adr.approval.mutation_service import DurableApprovalBoundMutationService
from living_adr.approval.repository import InMemoryApprovalAuditRepository
from living_adr.workflow.approval_node import ApprovalMintingNode
from living_adr.workflow.nodes.stubs import StubMutationHandoffNode
from living_adr.workflow.state import (
    DraftRef,
    ReviewAction,
    ReviewResumeCommand,
    WorkflowState,
    WorkflowStatus,
)

# Fields a downstream publisher (feature 011) correlates a published ADR against.
_REQUIRED_DECISION_FIELDS = frozenset(
    {
        "repository",
        "decision_id",
        "reviewer_id",
        "adr_draft_id",
        "adr_draft_content_hash",
        "target_fingerprint",
        "decision_version",
        "minted_at",
        "consumed_at",
        "approved",
    }
)


def _run_approved_flow():
    audit = InMemoryApprovalAuditRepository()
    store = InMemoryGraphStore()
    state = WorkflowState(
        repository=build_repo(),
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
    node = ApprovalMintingNode(
        audit, clock=FixedClock(), id_provider=SequentialIds("mint")
    )
    decision = node(state)["approved_decision"]
    authorised = state.model_copy(update={"approved_decision": decision})
    service = DurableApprovalBoundMutationService(
        store, audit, clock=FixedClock(), id_provider=SequentialIds("audit")
    )
    result = StubMutationHandoffNode(service)(authorised)["mutation_result"]
    return audit, decision, result


# --- capability field contract -------------------------------------------


def test_approved_decision_exposes_publish_correlation_fields() -> None:
    fields = set(ApprovedReviewDecision.model_fields)
    missing = _REQUIRED_DECISION_FIELDS - fields
    assert not missing, f"capability missing publish-correlation fields: {missing}"


# --- decision → node linkage feature 011 publishes from ------------------


def test_consumed_decision_yields_publishable_node_link() -> None:
    audit, decision, result = _run_approved_flow()

    links = decision_mutation_links(audit)
    assert len(links) == 1
    link = links[0]
    assert link.decision_id == decision.decision_id
    assert link.node_id == result.node_id
    assert link.reviewer_id == "lead-1"


# --- publication seam reserved but unbuilt -------------------------------


def test_publication_linked_is_reserved_and_unemitted() -> None:
    # The taxonomy slot exists for feature 011...
    assert AuditEventType.PUBLICATION_LINKED == "publication_linked"

    # ...but feature 010 never publishes, so no such audit row is produced.
    audit, decision, _result = _run_approved_flow()
    trail = build_decision_audit_trail(audit, decision.decision_id)
    assert AuditEventType.PUBLICATION_LINKED not in trail.event_types


def test_approval_package_imports_no_github_publisher() -> None:
    package_dir = Path(mutation_service_mod.__file__).parent
    forbidden = ("github", "GitHubProvider", "publish_to_github", "PyGithub")
    for path in sorted(package_dir.glob("*.py")):
        text = path.read_text(encoding="utf-8")
        for symbol in forbidden:
            assert symbol not in text, (
                f"{path.name} must not reference {symbol!r}: feature 011 publish "
                "is downstream and must not be reached from the approval boundary"
            )
