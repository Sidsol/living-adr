"""Slice 012-s02: read-only query wiring + safety guardrails.

The MCP app may be constructed with only the read-side query port, config, and
observability — never a write-side graph store, mutation service, SCM provider,
or LLM client (US-5, FR-3, FR-10, NFR-1). Shared request validation resolves a
configured ``RepositoryIdentity`` before any query runs and bounds untrusted
inputs (FR-7).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from living_adr.apps.mcp_context_server import dependencies as deps_mod
from living_adr.apps.mcp_context_server.dependencies import (
    ArchitectureContextQueryPort,
    McpServerDependencies,
    QueryLimits,
)
from living_adr.apps.mcp_context_server.validation import (
    McpValidationError,
    UnknownRepositoryError,
    clamp_limit,
    resolve_repository,
    validate_adr_id,
    validate_question,
    validate_repository_key,
    validate_status,
)
from living_adr.core.config import LivingADRConfig
from living_adr.core.config_loader import load_living_adr_config
from living_adr.core.graph.models import ADRRef, ProvenancedADR, WhyAnswer
from living_adr.core.observability import NoOpObservability
from living_adr.core.repository import RepositoryIdentity

TWO_REPO_YAML = """
repositories:
  - identity:
      host: github.com
      owner: org-a
      repo: repo-a
      repo_id: "111"
    github_app_installation_id: "1001"
    default_branch: main
    adr_publication_policy: livingadr_only
    external_llm_allowed: false
  - identity:
      host: github.com
      owner: org-b
      repo: repo-b
      repo_id: "222"
    github_app_installation_id: "2002"
    default_branch: main
    adr_publication_policy: livingadr_only
    external_llm_allowed: false
"""

# Forbidden write-side / credential symbols that must never cross into the
# read-only MCP dependency wiring (intent.md anti-patterns).
FORBIDDEN_IMPORT_TOKENS = (
    "ArchitectureGraphStore",
    "ApprovalBoundMutationService",
    "github_provider",
    "GithubProvider",
    "claude_adapter",
    "anthropic",
    "scm",
    "upsert",
    "supersede",
    "retract",
    "migrate",
)


class _FakeQuery:
    """Minimal read-only ArchitectureContextQuery-shaped fake."""

    def list_adrs(self, repository: RepositoryIdentity) -> tuple[ADRRef, ...]:
        return ()

    def fetch_adr(
        self, repository: RepositoryIdentity, adr_id: str
    ) -> ProvenancedADR | None:
        return None

    def answer_why(
        self,
        repository: RepositoryIdentity,
        question: str,
        code_area_id: str | None = None,
        snapshot: object | None = None,
        limit: int = 5,
    ) -> WhyAnswer:
        return WhyAnswer(
            repository=repository,
            question=question,
            answer="n/a",
            adr_id=None,
            citations=(),
            found=False,
        )


def _config(tmp_path: Path) -> LivingADRConfig:
    path = tmp_path / "living-adr.config.yaml"
    path.write_text(TWO_REPO_YAML, encoding="utf-8")
    return load_living_adr_config(path)


def _deps(tmp_path: Path) -> McpServerDependencies:
    return McpServerDependencies(
        config=_config(tmp_path),
        query=_FakeQuery(),
        observability=NoOpObservability(),
    )


def test_dependency_container_accepts_only_read_side_fields(tmp_path: Path) -> None:
    deps = _deps(tmp_path)
    assert set(deps.__dataclass_fields__) == {
        "config",
        "query",
        "observability",
        "limits",
    }
    assert isinstance(deps.limits, QueryLimits)
    assert isinstance(deps.query, ArchitectureContextQueryPort)


def test_query_port_exposes_no_mutation_methods() -> None:
    for forbidden in (
        "upsert_adr_node",
        "add_relationship",
        "supersede_adr",
        "retract_adr",
        "migrate_schema",
        "record_structural_change",
    ):
        assert not hasattr(ArchitectureContextQueryPort, forbidden)
    for allowed in ("list_adrs", "fetch_adr", "answer_why"):
        assert hasattr(ArchitectureContextQueryPort, allowed)


def test_dependencies_module_imports_no_write_side_symbols() -> None:
    source = Path(deps_mod.__file__).read_text(encoding="utf-8")
    for token in FORBIDDEN_IMPORT_TOKENS:
        assert token not in source, f"forbidden token {token!r} leaked into wiring"


def test_resolve_repository_returns_configured_identity(tmp_path: Path) -> None:
    config = _config(tmp_path)
    identity = resolve_repository(config, "github.com/org-a/repo-a")
    assert isinstance(identity, RepositoryIdentity)
    assert identity.repo == "repo-a"


def test_resolve_repository_rejects_unknown_repository(tmp_path: Path) -> None:
    config = _config(tmp_path)
    with pytest.raises(UnknownRepositoryError) as exc:
        resolve_repository(config, "github.com/evil/unknown")
    # Safe error must not leak the set of configured repository keys.
    assert "org-a" not in str(exc.value)
    assert "org-b" not in str(exc.value)


def test_validate_repository_key_bounds_input() -> None:
    assert validate_repository_key("  github.com/o/r  ") == "github.com/o/r"
    with pytest.raises(McpValidationError):
        validate_repository_key("")
    with pytest.raises(McpValidationError):
        validate_repository_key("x" * 1000)


def test_validate_adr_id_and_status_bounds() -> None:
    assert validate_adr_id(" adr-1 ") == "adr-1"
    with pytest.raises(McpValidationError):
        validate_adr_id("")
    assert validate_status(None) is None
    assert validate_status(" Approved ") == "approved"
    with pytest.raises(McpValidationError):
        validate_status("x" * 200)


def test_validate_question_and_clamp_limit() -> None:
    limits = QueryLimits()
    assert validate_question(" why? ", limits) == "why?"
    with pytest.raises(McpValidationError):
        validate_question("", limits)
    with pytest.raises(McpValidationError):
        validate_question("x" * (limits.max_question_length + 1), limits)
    assert clamp_limit(None, limits) == limits.default_limit
    assert clamp_limit(99, limits) == limits.max_limit
    assert clamp_limit(3, limits) == 3
    assert clamp_limit(0, limits) == limits.default_limit
