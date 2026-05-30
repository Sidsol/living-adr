"""Slice 7 (US-6/US-7) — package-level LlamaIndex containment.

Feature 007's swappable-seam guarantee is only real if the LlamaIndex backend
stays *inside* the adapter package. These tests walk the import graph with the
``ast`` module (no imports executed) and assert two things:

* every module under ``living_adr.core`` is free of LlamaIndex imports, and
* the LlamaIndex dependency is confined to ``living_adr.graph`` (the adapter
  package) — it never leaks into ``core`` or any other ``living_adr`` subpackage.

If a future change pulls ``llama_index`` into core (or some new top-level
package), this test fails loudly rather than silently coupling the domain to a
concrete persistence backend.
"""

from __future__ import annotations

import ast
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "src" / "living_adr"
CORE = SRC / "core"
ADAPTER_PKG = SRC / "graph"

LLAMA_ROOTS = frozenset({"llama_index", "llama_index_core"})


def _imported_roots(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                roots.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            roots.add(node.module.split(".")[0])
    return roots


def test_core_package_is_free_of_llamaindex() -> None:
    for path in sorted(CORE.rglob("*.py")):
        leaked = _imported_roots(path) & LLAMA_ROOTS
        rel = path.relative_to(SRC)
        assert not leaked, f"{rel} imports LlamaIndex: {sorted(leaked)}"


def test_llamaindex_is_confined_to_the_adapter_package() -> None:
    # Every llama-importing module must live under living_adr/graph.
    llama_modules = [
        path
        for path in sorted(SRC.rglob("*.py"))
        if _imported_roots(path) & LLAMA_ROOTS
    ]
    for path in llama_modules:
        assert ADAPTER_PKG in path.parents or path.parent == ADAPTER_PKG, (
            f"{path.relative_to(SRC)} imports LlamaIndex outside the adapter package"
        )
    # Positive containment: the adapter package really is the backend boundary.
    assert llama_modules, "expected at least one LlamaIndex-importing adapter module"
    assert all(
        str(path).startswith(str(ADAPTER_PKG)) for path in llama_modules
    )
