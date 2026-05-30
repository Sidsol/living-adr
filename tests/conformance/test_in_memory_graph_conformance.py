"""Slice 5 (US-5): run the conformance suite against the in-memory adapter and
prove the suite catches non-conforming adapters.

The first class opts the reference :class:`InMemoryGraphStore` into the reusable
:class:`GraphStoreConformanceSuite` exactly as feature 007's LlamaIndex adapter
will. The remaining tests deliberately feed *broken* adapters to the reusable
assertions to prove the suite fails them with a named contract violation
(``AssertionError``), rather than passing silently.
"""

from __future__ import annotations

import pytest
from tests.conformance.graph_store_conformance import (
    GraphStoreConformanceSuite,
    assert_query_returns_domain_values,
    assert_repository_scoping,
)
from tests.fakes.in_memory_graph_store import InMemoryGraphStore

from living_adr.core.graph.models import WhyAnswer


class TestInMemoryGraphStoreConformance(GraphStoreConformanceSuite):
    """The reference adapter must pass the full conformance contract."""

    def make_store(self) -> InMemoryGraphStore:
        return InMemoryGraphStore()


# ----------------------------------------------- negative examples (TASK-017)


class _RepositoryIgnoringStore(InMemoryGraphStore):
    """Broken adapter: ignores repository scope by funnelling all repos to one key."""

    def _bucket(self, repository) -> str:  # noqa: ANN001
        return "GLOBAL"

    def upsert_adr_node(self, repository, adr, decision):  # noqa: ANN001
        node = super().upsert_adr_node(repository, adr, decision)
        # Re-file under a single global bucket so other repos can see it.
        self._nodes.setdefault("GLOBAL", {})[node.value] = adr
        return node

    def answer_why(
        self, repository, question, code_area_id=None, snapshot=None, limit=5
    ):  # noqa: ANN001
        records = list(self._nodes.get("GLOBAL", {}).values())
        if not records:
            return super().answer_why(repository, question)
        rec = records[0]
        return WhyAnswer(
            repository=repository,
            question=question,
            answer="leaked across scope",
            adr_id=rec.adr_id,
            citations=(f"adr:{rec.adr_id}",),
            found=True,
        )


class _LeakyQueryStore(InMemoryGraphStore):
    """Broken adapter: returns a raw backend object (dict) from the read port."""

    def answer_why(
        self, repository, question, code_area_id=None, snapshot=None, limit=5
    ):  # noqa: ANN001
        return {"answer": "raw backend object", "found": True}  # type: ignore[return-value]


def test_suite_fails_adapter_that_ignores_repository_scope() -> None:
    with pytest.raises(AssertionError):
        assert_repository_scoping(_RepositoryIgnoringStore)


def test_suite_fails_adapter_that_leaks_backend_objects() -> None:
    with pytest.raises(AssertionError):
        assert_query_returns_domain_values(_LeakyQueryStore)
