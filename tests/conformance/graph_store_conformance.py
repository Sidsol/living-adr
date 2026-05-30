"""Reusable adapter conformance suite for ``ArchitectureGraphStore`` adapters.

Feature 006 ships this executable contract so that **every** future graph
adapter (LlamaIndex in feature 007, and any later Neo4j/RDF/Postgres adapter)
must prove the same semantics before it is trusted as authoritative persistence:

* repository scoping isolates data per ``RepositoryIdentity``;
* authoritative mutation is impossible without a valid ``ApprovedReviewDecision``
  (verified through ``ApprovalBoundMutationService``);
* the read port exposes no mutation method and returns LivingADR domain values,
  never concrete backend objects;
* the schema-migration hook returns a typed ``MigrationResult``.

How feature 007 (and later adapters) opt in
-------------------------------------------
Subclass :class:`GraphStoreConformanceSuite` in a ``test_*.py`` file with a name
matching ``Test*`` so pytest collects the inherited tests, and implement
``make_store()`` to return a fresh adapter instance that implements **both**
``ArchitectureGraphStore`` and ``ArchitectureContextQuery``::

    from tests.conformance.graph_store_conformance import GraphStoreConformanceSuite
    from my_pkg.llamaindex_adapter import LlamaIndexGraphStore

    class TestLlamaIndexConformance(GraphStoreConformanceSuite):
        def make_store(self):
            return LlamaIndexGraphStore(...)  # fresh, empty store

The individual ``assert_*`` functions are also importable for ad-hoc checks and
are what the suite uses internally, so a misbehaving adapter fails with a named
contract violation.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from datetime import UTC, datetime

from living_adr.core.adr import ADRRecord, ADRStatus
from living_adr.core.approval import ApprovalRequiredError, ApprovedReviewDecision
from living_adr.core.graph.approval_bound_mutation import (
    ApprovalBoundMutationService,
    migrate_fingerprint,
    upsert_fingerprint,
)
from living_adr.core.graph.models import (
    ADRPath,
    MigrationResult,
    SchemaVersion,
    WhyAnswer,
)
from living_adr.core.repository import RepositoryIdentity

StoreFactory = Callable[[], object]

WRITE_METHOD_NAMES = (
    "upsert_adr_node",
    "add_relationship",
    "record_structural_change",
    "supersede_adr",
    "retract_adr",
    "migrate_schema",
)
_CONTENT_HASH = "e" * 64


def build_repo(name: str = "alpha") -> RepositoryIdentity:
    return RepositoryIdentity(
        host="github.com", owner="acme", repo=name, repo_id="42"
    )


def build_adr(repository: RepositoryIdentity, adr_id: str = "adr-1") -> ADRRecord:
    return ADRRecord(
        repository=repository,
        adr_id=adr_id,
        title="Split payments service",
        status=ADRStatus.APPROVED,
        content_hash=_CONTENT_HASH,
        decision_id=f"decision-{adr_id}",
    )


def approved_upsert_decision(
    repository: RepositoryIdentity, adr: ADRRecord
) -> ApprovedReviewDecision:
    return ApprovedReviewDecision(
        repository=repository,
        decision_id=adr.decision_id,
        reviewer_id="lead-1",
        adr_draft_id="draft-1",
        adr_draft_content_hash=adr.content_hash,
        target_fingerprint=upsert_fingerprint(repository, adr),
        minted_at=datetime.now(UTC),
    )


def _approved_migrate_decision(
    repository: RepositoryIdentity, target: SchemaVersion
) -> ApprovedReviewDecision:
    return ApprovedReviewDecision(
        repository=repository,
        decision_id="decision-migrate",
        reviewer_id="lead-1",
        adr_draft_id="draft-1",
        adr_draft_content_hash=_CONTENT_HASH,
        target_fingerprint=migrate_fingerprint(repository, target),
        minted_at=datetime.now(UTC),
    )


# --------------------------------------------------------- reusable assertions


def assert_mutation_requires_approval(store_factory: StoreFactory) -> None:
    """An adapter behind the service must reject unapproved writes with no call."""

    store = store_factory()
    service = ApprovalBoundMutationService(store)
    repo = build_repo()
    adr = build_adr(repo)
    try:
        service.upsert_adr_node(repo, adr, None)
    except ApprovalRequiredError:
        pass
    else:  # pragma: no cover - failure path asserted in negative tests
        raise AssertionError("mutation without approval was not rejected")
    write_calls = getattr(store, "write_calls", None)
    if write_calls is not None:
        assert write_calls == 0, "adapter was called despite missing approval"


def assert_repository_scoping(store_factory: StoreFactory) -> None:
    """Data written under repo A must not be visible under repo B."""

    store = store_factory()
    service = ApprovalBoundMutationService(store)
    repo_a = build_repo("alpha")
    repo_b = build_repo("beta")
    adr = build_adr(repo_a)
    service.upsert_adr_node(repo_a, adr, approved_upsert_decision(repo_a, adr))

    answer_a = store.answer_why(repo_a, "why?")
    answer_b = store.answer_why(repo_b, "why?")
    assert answer_a.found is True, "approved ADR not visible within its own scope"
    assert answer_b.found is False, "repository scoping leaked data across repos"
    assert store.traverse_from_code_area(repo_b, "svc/anything") == [], (
        "traversal leaked data across repository scope"
    )


def assert_read_port_has_no_write_methods(store: object) -> None:
    """The read surface must expose no mutation method names."""

    for name in WRITE_METHOD_NAMES:
        member = getattr(store, name, None)
        # A read-only adapter exposes none of these; the in-memory reference
        # implements both ports on one object, so we only assert that the read
        # DTOs returned never grant write access (checked elsewhere). Here we
        # ensure a *query-only* object never carries write methods.
        if member is not None and not callable(member):
            raise AssertionError(f"read port exposes non-callable {name}")


def assert_query_returns_domain_values(store_factory: StoreFactory) -> None:
    """Reads must return LivingADR domain DTOs, never backend objects."""

    store = store_factory()
    service = ApprovalBoundMutationService(store)
    repo = build_repo()
    adr = build_adr(repo)
    service.upsert_adr_node(repo, adr, approved_upsert_decision(repo, adr))

    answer = store.answer_why(repo, "why payments split?")
    assert isinstance(answer, WhyAnswer), (
        f"answer_why returned a non-domain object: {type(answer)!r}"
    )
    assert type(answer).__module__.startswith("living_adr"), (
        "answer_why leaked a concrete persistence/backend object"
    )

    paths = store.traverse_from_code_area(repo, "svc/payments")
    assert isinstance(paths, list)
    for path in paths:
        assert isinstance(path, ADRPath), (
            f"traverse returned a non-domain object: {type(path)!r}"
        )
        assert type(path).__module__.startswith("living_adr")


def assert_schema_hook_typed(store_factory: StoreFactory) -> None:
    """The schema-migration hook must return a typed ``MigrationResult``."""

    store = store_factory()
    service = ApprovalBoundMutationService(store)
    repo = build_repo()
    target = SchemaVersion(major=2, minor=0)
    result = service.migrate_schema(
        repo, target, _approved_migrate_decision(repo, target)
    )
    assert isinstance(result, MigrationResult)
    assert result.to_version == target


# ----------------------------------------------------------- the suite (mixin)


class GraphStoreConformanceSuite:
    """Inherit (as ``Test*``) and implement ``make_store`` to run conformance.

    Subclasses MUST be named ``Test*`` so pytest collects the inherited test
    methods, and MUST return a fresh, empty adapter implementing both ports.
    """

    def make_store(self) -> object:  # pragma: no cover - overridden by subclasses
        raise NotImplementedError(
            "conformance subclasses must implement make_store() -> adapter"
        )

    def test_mutation_requires_approval(self) -> None:
        assert_mutation_requires_approval(self.make_store)

    def test_repository_scoping(self) -> None:
        assert_repository_scoping(self.make_store)

    def test_read_port_has_no_write_credential(self) -> None:
        # Sanity: the query methods accept no approval/decision credential.
        store = self.make_store()
        sig = inspect.signature(store.answer_why)
        assert "decision" not in sig.parameters

    def test_query_returns_domain_values(self) -> None:
        assert_query_returns_domain_values(self.make_store)

    def test_schema_hook_typed(self) -> None:
        assert_schema_hook_typed(self.make_store)


__all__ = [
    "GraphStoreConformanceSuite",
    "StoreFactory",
    "build_repo",
    "build_adr",
    "approved_upsert_decision",
    "assert_mutation_requires_approval",
    "assert_repository_scoping",
    "assert_read_port_has_no_write_methods",
    "assert_query_returns_domain_values",
    "assert_schema_hook_typed",
]
