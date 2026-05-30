"""Slice 012-s03: list_adrs MCP surface.

``list_adrs`` is exposed over MCP through the read-only query port. It returns
repository-scoped ``ADRRef`` data (id, title, status), honours an optional status
filter, maps unsupported statuses to a safe error, and never leaks ADRs from
another repository (US-2, FR-4, FR-5, FR-6, FR-8).
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

KEY_A = "github.com/org-a/repo-a"
KEY_B = "github.com/org-b/repo-b"


class FakeQuery:
    """Read-only query fake keyed by repository canonical key."""

    def __init__(self, by_repo: dict[str, tuple[ADRRef, ...]]) -> None:
        self._by_repo = by_repo

    def list_adrs(self, repository: RepositoryIdentity) -> tuple[ADRRef, ...]:
        return self._by_repo.get(repository.key, ())

    def fetch_adr(
        self, repository: RepositoryIdentity, adr_id: str
    ) -> ProvenancedADR | None:  # pragma: no cover - unused in this slice
        return None

    def answer_why(  # pragma: no cover - unused in this slice
        self, *args: object, **kwargs: object
    ) -> WhyAnswer:
        raise NotImplementedError


def _config(tmp_path: Path) -> LivingADRConfig:
    path = tmp_path / "living-adr.config.yaml"
    path.write_text(TWO_REPO_YAML, encoding="utf-8")
    return load_living_adr_config(path)


def _ref(
    key: str, owner: str, repo: str, repo_id: str, adr_id: str, status: str
) -> ADRRef:
    return ADRRef(
        repository=RepositoryIdentity(
            host="github.com", owner=owner, repo=repo, repo_id=repo_id
        ),
        adr_id=adr_id,
        title=f"{adr_id} title",
        status=status,
    )


def _deps(tmp_path: Path, query: FakeQuery) -> McpServerDependencies:
    return McpServerDependencies(
        config=_config(tmp_path),
        query=query,
        observability=NoOpObservability(),
    )


def _dispatch(tmp_path: Path, query: FakeQuery):
    return make_dispatch(_deps(tmp_path, query))


def test_list_adrs_returns_scoped_serialized_refs(tmp_path: Path) -> None:
    query = FakeQuery(
        {
            KEY_A: (
                _ref(KEY_A, "org-a", "repo-a", "111", "adr-1", "approved"),
                _ref(KEY_A, "org-a", "repo-a", "111", "adr-2", "approved"),
            )
        }
    )
    result = _dispatch(tmp_path, query)("list_adrs", {"repository": KEY_A})
    assert result["repository"] == KEY_A
    assert result["count"] == 2
    ids = {a["adr_id"] for a in result["adrs"]}
    assert ids == {"adr-1", "adr-2"}
    first = result["adrs"][0]
    assert set(first) == {"repository", "adr_id", "title", "status"}


def test_list_adrs_filters_by_status(tmp_path: Path) -> None:
    query = FakeQuery(
        {
            KEY_A: (
                _ref(KEY_A, "org-a", "repo-a", "111", "adr-1", "approved"),
                _ref(KEY_A, "org-a", "repo-a", "111", "adr-9", "superseded"),
            )
        }
    )
    result = _dispatch(tmp_path, query)(
        "list_adrs", {"repository": KEY_A, "status": "approved"}
    )
    ids = {a["adr_id"] for a in result["adrs"]}
    assert ids == {"adr-1"}


def test_list_adrs_unsupported_status_is_safe_error(tmp_path: Path) -> None:
    query = FakeQuery({KEY_A: ()})
    result = _dispatch(tmp_path, query)(
        "list_adrs", {"repository": KEY_A, "status": "not-a-real-status"}
    )
    assert "error" in result
    assert result["error"]["type"] == "invalid_request"


def test_list_adrs_empty_repository(tmp_path: Path) -> None:
    query = FakeQuery({KEY_A: ()})
    result = _dispatch(tmp_path, query)("list_adrs", {"repository": KEY_A})
    assert result["count"] == 0
    assert result["adrs"] == []


def test_list_adrs_does_not_leak_other_repository(tmp_path: Path) -> None:
    query = FakeQuery(
        {
            KEY_A: (_ref(KEY_A, "org-a", "repo-a", "111", "adr-shared", "approved"),),
            KEY_B: (_ref(KEY_B, "org-b", "repo-b", "222", "adr-shared", "approved"),),
        }
    )
    result = _dispatch(tmp_path, query)("list_adrs", {"repository": KEY_A})
    assert result["count"] == 1
    assert result["adrs"][0]["repository"] == KEY_A


def test_list_adrs_unknown_repository_is_safe_error(tmp_path: Path) -> None:
    query = FakeQuery({})
    result = _dispatch(tmp_path, query)(
        "list_adrs", {"repository": "github.com/evil/unknown"}
    )
    assert result["error"]["type"] == "unknown_repository"
    assert "org-a" not in result["error"]["message"]


def test_list_adrs_tool_is_registered(tmp_path: Path) -> None:
    app = build_app(_deps(tmp_path, FakeQuery({})))
    assert "list_adrs" in app.tool_names
