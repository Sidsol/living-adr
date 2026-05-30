"""Slice 6 (US-6) — feature 006 conformance suite against the LlamaIndex adapter.

This proves ``LlamaIndexPropertyGraphAdapter`` honours feature 006's executable
contract: repository scoping, approval-bound mutation (through
``ApprovalBoundMutationService``), read/write separation, domain-only query
returns, and the typed schema-migration hook.

How a future adapter opts in
----------------------------
Subclass ``GraphStoreConformanceSuite`` (named ``Test*`` so pytest collects the
inherited tests) and implement ``make_store()`` to return a *fresh, empty*
adapter that implements both ports. The suite is reused verbatim — never
weakened, skipped, or redefined to fit a particular backend. Here ``make_store``
hands each invocation an isolated temp ``var/graph`` root so the suite runs
fully offline and deterministically (no network, no embeddings).
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from tests.conformance.graph_store_conformance import GraphStoreConformanceSuite

from living_adr.graph import GraphPersistenceConfig, LlamaIndexPropertyGraphAdapter


class TestLlamaIndexConformance(GraphStoreConformanceSuite):
    """Run feature 006's reusable conformance suite against feature 007."""

    def setup_method(self) -> None:
        self._temp_dirs: list[str] = []

    def teardown_method(self) -> None:
        for path in self._temp_dirs:
            shutil.rmtree(path, ignore_errors=True)

    def make_store(self) -> LlamaIndexPropertyGraphAdapter:
        temp_dir = tempfile.mkdtemp(prefix="liadr-conformance-")
        self._temp_dirs.append(temp_dir)
        config = GraphPersistenceConfig(graph_root=Path(temp_dir) / "var" / "graph")
        return LlamaIndexPropertyGraphAdapter(config=config)
