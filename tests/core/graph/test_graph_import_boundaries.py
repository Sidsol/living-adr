"""Slice 6 (US-6) tests: dependency isolation and signature purity.

The core graph/ADR/approval contract modules are the swap seam: they must not
import a concrete graph backend or runtime framework (LlamaIndex, LangSmith,
FastAPI, MCP, a database driver, or a concrete adapter module), and their public
port signatures must reference only LivingADR domain values and standard
scalar/collection/typing constructs. Otherwise downstream features (007, 010,
012, 015) would couple to persistence internals.
"""

from __future__ import annotations

import ast
import typing
from pathlib import Path

from living_adr.core.graph.ports import (
    ArchitectureContextQuery,
    ArchitectureGraphStore,
)

SRC = Path(__file__).resolve().parents[3] / "src" / "living_adr" / "core"

CONTRACT_MODULES = (
    SRC / "adr.py",
    SRC / "approval.py",
    SRC / "graph" / "models.py",
    SRC / "graph" / "ports.py",
    SRC / "graph" / "approval_bound_mutation.py",
    SRC / "graph" / "__init__.py",
)

FORBIDDEN_IMPORT_ROOTS = frozenset(
    {
        "llama_index",
        "llama_index_core",
        "langsmith",
        "langgraph",
        "fastapi",
        "uvicorn",
        "starlette",
        "mcp",
        "anthropic",
        "sqlite3",
        "sqlalchemy",
        "neo4j",
        "psycopg",
        "psycopg2",
    }
)

FORBIDDEN_TYPE_TOKENS = (
    "llama_index",
    "Session",
    "Connection",
    "Cursor",
    "Engine",
    "PropertyGraph",
    "Index",
    "Retriever",
)


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


def test_contract_modules_import_no_forbidden_backends() -> None:
    for path in CONTRACT_MODULES:
        roots = _imported_roots(path)
        leaked = roots & FORBIDDEN_IMPORT_ROOTS
        assert not leaked, f"{path.name} imports forbidden backend(s): {sorted(leaked)}"


def test_contract_modules_only_depend_on_living_adr_and_stdlib() -> None:
    # Positive framing: the only third-party root permitted is pydantic.
    allowed = {"living_adr", "pydantic", "__future__"}
    stdlib = {
        "typing",
        "collections",
        "contextlib",
        "datetime",
        "enum",
        "hashlib",
        "abc",
    }
    for path in CONTRACT_MODULES:
        roots = _imported_roots(path)
        unexpected = roots - allowed - stdlib
        assert not unexpected, (
            f"{path.name} has unexpected imports: {sorted(unexpected)}"
        )


def _hint_strings(func: object) -> list[str]:
    hints = typing.get_type_hints(func)
    return [str(v) for v in hints.values()]


def _hint_is_domain_or_standard(hint: str) -> bool:
    if "living_adr" in hint:
        return True
    prefixes = ("<class", "typing", "list", "set", "dict", "str", "int", "bool")
    return hint.startswith(prefixes)


def test_port_signatures_expose_only_domain_and_standard_types() -> None:
    write_methods = (
        "upsert_adr_node",
        "add_relationship",
        "record_structural_change",
        "supersede_adr",
        "retract_adr",
        "migrate_schema",
    )
    read_methods = ("traverse_from_code_area", "answer_why")
    for method in write_methods:
        for hint in _hint_strings(getattr(ArchitectureGraphStore, method)):
            for token in FORBIDDEN_TYPE_TOKENS:
                assert token not in hint, f"{method} signature leaks {token}: {hint}"
    for method in read_methods:
        for hint in _hint_strings(getattr(ArchitectureContextQuery, method)):
            assert _hint_is_domain_or_standard(hint), f"{method} leaks: {hint}"
