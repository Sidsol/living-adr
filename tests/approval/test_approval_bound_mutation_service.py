"""Slice S010-06: ApprovalBoundMutationService graph boundary.

Proves the durable mutation service is the *only* authorised path to the
``ArchitectureGraphStore`` write methods (FR-9): no store write occurs without a
valid capability, the boundary is delegated through domain ports (no concrete
graph adapter is imported by the approval package — adapter neutrality), and the
service is a structural drop-in for the workflow's narrow mutation seam so
workflow/MCP code never needs a raw store handle.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tests.approval._helpers import (
    FixedClock,
    SequentialIds,
    build_adr_record,
    build_command,
    build_context,
    build_repo,
)
from tests.fakes.in_memory_graph_store import InMemoryGraphStore

from living_adr.approval import mutation_service as mutation_service_mod
from living_adr.approval import repository as repository_mod
from living_adr.approval import validation as validation_mod
from living_adr.approval.minting import mint_approved_decision
from living_adr.approval.models import (
    ApprovalRequiredError,
    TargetMutationMismatchError,
)
from living_adr.approval.mutation_service import (
    AuthoritativeMutationService,
    DurableApprovalBoundMutationService,
)
from living_adr.approval.repository import InMemoryApprovalAuditRepository
from living_adr.core.graph.approval_bound_mutation import upsert_fingerprint
from living_adr.workflow.nodes.stubs import GraphMutationService
from living_adr.workflow.state import ReviewAction


def _service(store=None, audit=None):
    store = store or InMemoryGraphStore()
    audit = audit or InMemoryApprovalAuditRepository()
    service = DurableApprovalBoundMutationService(
        store, audit, clock=FixedClock(), id_provider=SequentialIds("audit")
    )
    return service, store, audit


def _valid_decision(audit, repo):
    record = build_adr_record(repo, decision_id="placeholder")
    expected_fp = upsert_fingerprint(repo, record)
    result = mint_approved_decision(
        repo,
        build_command(ReviewAction.APPROVE),
        build_context(repo),
        target_fingerprint=expected_fp,
        audit=audit,
        clock=FixedClock(),
        id_provider=SequentialIds("mint"),
    )
    return result.decision, build_adr_record(
        repo, decision_id=result.decision.decision_id
    )


# --- interface / drop-in seam (S6-001) -----------------------------------


def test_service_satisfies_authoritative_and_workflow_protocols() -> None:
    service, _store, _audit = _service()
    # The feature-010 authoritative boundary...
    assert isinstance(service, AuthoritativeMutationService)
    # ...and the narrow workflow mutation seam (feature 015 drop-in).
    assert isinstance(service, GraphMutationService)


# --- no store write without a valid capability (S6-002/S6-003) ------------


def test_missing_capability_never_touches_the_store() -> None:
    service, store, _audit = _service()
    repo = build_repo()
    record = build_adr_record(repo, decision_id="none")
    with pytest.raises(ApprovalRequiredError):
        service.authorize_and_upsert(repo, record, None)
    assert store.write_calls == 0


def test_wrong_target_capability_never_touches_the_store() -> None:
    service, store, audit = _service()
    repo = build_repo()
    decision, _record = _valid_decision(audit, repo)
    # Present the capability against a *different* mutation target.
    other = build_adr_record(repo, decision_id=decision.decision_id, adr_id="adr-2")
    with pytest.raises(TargetMutationMismatchError):
        service.authorize_and_upsert(repo, other, decision)
    assert store.write_calls == 0


def test_valid_capability_delegates_exactly_once() -> None:
    service, store, audit = _service()
    repo = build_repo()
    decision, record = _valid_decision(audit, repo)
    result = service.authorize_and_upsert(repo, record, decision)
    assert store.write_calls == 1
    assert result.node_id.value
    # The store is reached only through the feature 006 boundary the durable
    # service wraps — there is no second, unguarded store holder.
    assert service._core._store is store  # noqa: SLF001 - boundary assertion


# --- adapter neutrality (S6-004) -----------------------------------------

_FORBIDDEN_IMPORTS = (
    "living_adr.graph",  # concrete LlamaIndex/stub graph adapters
    "llama_index",
    "neo4j",
    "networkx",
    "anthropic",
    "Anthropic",
    "github",
    "GitHubProvider",
)


def test_approval_package_imports_no_concrete_adapter() -> None:
    package_dir = Path(mutation_service_mod.__file__).parent
    sources = sorted(package_dir.glob("*.py"))
    assert sources, "expected approval package sources to scan"
    for path in sources:
        text = path.read_text(encoding="utf-8")
        for forbidden in _FORBIDDEN_IMPORTS:
            assert forbidden not in text, (
                f"{path.name} must not reference {forbidden!r}: the approval "
                "boundary depends only on core domain ports (adapter neutrality)"
            )


def test_mutation_and_validation_depend_only_on_the_port_type() -> None:
    # The durable service is typed against the store *port*, not a concrete
    # adapter, and validation/repository likewise avoid concrete graph imports.
    for module in (mutation_service_mod, validation_mod, repository_mod):
        text = Path(module.__file__).read_text(encoding="utf-8")
        assert "living_adr.graph" not in text
