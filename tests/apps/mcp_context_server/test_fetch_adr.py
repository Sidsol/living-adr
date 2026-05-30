"""Slice 012-s04: fetch_adr MCP surface.

``fetch_adr`` returns one approved ADR with provenance/citations for a configured
repository, maps a missing or out-of-scope ADR to a safe not-found error,
validates an optional snapshot argument, and maps query failures to a safe
generic error without leaking internal types or stack traces
(US-3, FR-4, FR-6, FR-8).
"""

from __future__ import annotations

from pathlib import Path

from living_adr.apps.mcp_context_server.app import build_app
from living_adr.apps.mcp_context_server.dependencies import McpServerDependencies
from living_adr.apps.mcp_context_server.tools import make_dispatch
from living_adr.core.config import LivingADRConfig
from living_adr.core.config_loader import load_living_adr_config
from living_adr.core.graph.models import ADRRef, ProvenancedADR, WhyAnswer
from living_adr.core.observability import NoOpObservability
from living_adr.core.repository import RepositoryIdentity

ONE_REPO_YAML = """
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
"""

KEY_A = "github.com/org-a/repo-a"
IDENTITY_A = RepositoryIdentity(
    host="github.com", owner="org-a", repo="repo-a", repo_id="111"
)


class FakeQuery:
    def __init__(
        self, adr: ProvenancedADR | None = None, *, raises: Exception | None = None
    ) -> None:
        self._adr = adr
        self._raises = raises
        self.calls: list[tuple[str, str]] = []

    def list_adrs(  # pragma: no cover - unused in this slice
        self, repository: RepositoryIdentity
    ) -> tuple[ADRRef, ...]:
        return ()

    def fetch_adr(
        self, repository: RepositoryIdentity, adr_id: str
    ) -> ProvenancedADR | None:
        self.calls.append((repository.key, adr_id))
        if self._raises is not None:
            raise self._raises
        if self._adr is not None and self._adr.adr.adr_id == adr_id:
            return self._adr
        return None

    def answer_why(  # pragma: no cover - unused in this slice
        self, *args: object, **kwargs: object
    ) -> WhyAnswer:
        raise NotImplementedError


def _config(tmp_path: Path) -> LivingADRConfig:
    path = tmp_path / "living-adr.config.yaml"
    path.write_text(ONE_REPO_YAML, encoding="utf-8")
    return load_living_adr_config(path)


def _deps(tmp_path: Path, query: FakeQuery) -> McpServerDependencies:
    return McpServerDependencies(
        config=_config(tmp_path),
        query=query,
        observability=NoOpObservability(),
    )


def _provenanced(adr_id: str) -> ProvenancedADR:
    return ProvenancedADR(
        repository=IDENTITY_A,
        adr=ADRRef(
            repository=IDENTITY_A, adr_id=adr_id, title=f"{adr_id}", status="approved"
        ),
        citations=(f"adr:{adr_id}", "evidence:ev-1"),
    )


def test_fetch_adr_returns_provenanced_dto(tmp_path: Path) -> None:
    query = FakeQuery(_provenanced("adr-1"))
    result = make_dispatch(_deps(tmp_path, query))(
        "fetch_adr", {"repository": KEY_A, "adr_id": "adr-1"}
    )
    assert result["adr"]["adr"]["adr_id"] == "adr-1"
    assert result["adr"]["citations"] == ["adr:adr-1", "evidence:ev-1"]
    assert query.calls == [(KEY_A, "adr-1")]


def test_fetch_adr_missing_is_safe_not_found(tmp_path: Path) -> None:
    query = FakeQuery(None)
    result = make_dispatch(_deps(tmp_path, query))(
        "fetch_adr", {"repository": KEY_A, "adr_id": "does-not-exist"}
    )
    assert result["error"]["type"] == "not_found"


def test_fetch_adr_missing_adr_id_is_invalid_request(tmp_path: Path) -> None:
    query = FakeQuery(None)
    result = make_dispatch(_deps(tmp_path, query))(
        "fetch_adr", {"repository": KEY_A}
    )
    assert result["error"]["type"] == "invalid_request"


def test_fetch_adr_accepts_optional_snapshot(tmp_path: Path) -> None:
    query = FakeQuery(_provenanced("adr-1"))
    result = make_dispatch(_deps(tmp_path, query))(
        "fetch_adr",
        {"repository": KEY_A, "adr_id": "adr-1", "snapshot": "snap-123"},
    )
    assert result["adr"]["adr"]["adr_id"] == "adr-1"
    assert result["snapshot"] == "snap-123"
    assert query.calls == [(KEY_A, "adr-1")]


def test_fetch_adr_query_failure_is_safe_generic_error(tmp_path: Path) -> None:
    secret = "/etc/secret/path traceback boom"
    query = FakeQuery(raises=RuntimeError(secret))
    result = make_dispatch(_deps(tmp_path, query))(
        "fetch_adr", {"repository": KEY_A, "adr_id": "adr-1"}
    )
    assert result["error"]["type"] == "query_failed"
    assert secret not in result["error"]["message"]


def test_fetch_adr_tool_is_registered(tmp_path: Path) -> None:
    app = build_app(_deps(tmp_path, FakeQuery(None)))
    assert "fetch_adr" in app.tool_names
