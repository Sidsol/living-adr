"""Slice 012-s05: answer_why MCP surface.

``answer_why`` answers architecture rationale questions with citations through
the read-only query port. It bounds the question length, defaults/clamps the
limit, preserves citations and provenance, returns an explicit no-approved-
context result rather than hallucinating, and maps query failures to safe errors
(US-4, FR-4, FR-7, NFR-4).
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
        self, answer: WhyAnswer | None = None, *, raises: Exception | None = None
    ) -> None:
        self._answer = answer
        self._raises = raises
        self.last_limit: int | None = None
        self.last_question: str | None = None
        self.last_code_area: str | None = None

    def list_adrs(self, repository: RepositoryIdentity):  # pragma: no cover
        return ()

    def fetch_adr(  # pragma: no cover - unused in this slice
        self, repository: RepositoryIdentity, adr_id: str
    ):
        return None

    def answer_why(
        self,
        repository: RepositoryIdentity,
        question: str,
        code_area_id: str | None = None,
        snapshot: object | None = None,
        limit: int = 5,
    ) -> WhyAnswer:
        self.last_limit = limit
        self.last_question = question
        self.last_code_area = code_area_id
        if self._raises is not None:
            raise self._raises
        if self._answer is not None:
            return self._answer
        return WhyAnswer(
            repository=repository,
            question=question,
            answer="No approved ADR context is available for this repository.",
            adr_id=None,
            citations=(),
            found=False,
        )


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


def _cited_answer() -> WhyAnswer:
    prov = ProvenancedADR(
        repository=IDENTITY_A,
        adr=ADRRef(
            repository=IDENTITY_A,
            adr_id="adr-7",
            title="Adopt httpx",
            status="approved",
        ),
        citations=("adr:adr-7", "evidence:ev-7"),
    )
    return WhyAnswer(
        repository=IDENTITY_A,
        question="why httpx?",
        answer="Approved decision adr-7: Adopt httpx.",
        adr_id="adr-7",
        citations=("adr:adr-7",),
        found=True,
        provenance=(prov,),
    )


def test_answer_why_returns_cited_answer(tmp_path: Path) -> None:
    query = FakeQuery(_cited_answer())
    result = make_dispatch(_deps(tmp_path, query))(
        "answer_why", {"repository": KEY_A, "question": "why httpx?"}
    )
    assert result["found"] is True
    assert result["adr_id"] == "adr-7"
    assert result["citations"] == ["adr:adr-7"]
    assert result["provenance"][0]["adr"]["adr_id"] == "adr-7"


def test_answer_why_no_context_is_explicit(tmp_path: Path) -> None:
    query = FakeQuery(None)
    result = make_dispatch(_deps(tmp_path, query))(
        "answer_why", {"repository": KEY_A, "question": "why anything?"}
    )
    assert result["found"] is False
    assert result["adr_id"] is None
    assert "no approved adr context" in result["answer"].lower()


def test_answer_why_rejects_overlong_question(tmp_path: Path) -> None:
    query = FakeQuery(None)
    result = make_dispatch(_deps(tmp_path, query))(
        "answer_why", {"repository": KEY_A, "question": "x" * 5000}
    )
    assert result["error"]["type"] == "invalid_request"


def test_answer_why_clamps_limit(tmp_path: Path) -> None:
    query = FakeQuery(None)
    make_dispatch(_deps(tmp_path, query))(
        "answer_why", {"repository": KEY_A, "question": "why?", "limit": 99}
    )
    assert query.last_limit == 10


def test_answer_why_defaults_limit(tmp_path: Path) -> None:
    query = FakeQuery(None)
    make_dispatch(_deps(tmp_path, query))(
        "answer_why", {"repository": KEY_A, "question": "why?"}
    )
    assert query.last_limit == 5


def test_answer_why_passes_code_area(tmp_path: Path) -> None:
    query = FakeQuery(None)
    make_dispatch(_deps(tmp_path, query))(
        "answer_why",
        {"repository": KEY_A, "question": "why?", "code_area_id": "src/app.py"},
    )
    assert query.last_code_area == "src/app.py"


def test_answer_why_query_failure_is_safe_error(tmp_path: Path) -> None:
    query = FakeQuery(raises=RuntimeError("/secret/path stacktrace"))
    result = make_dispatch(_deps(tmp_path, query))(
        "answer_why", {"repository": KEY_A, "question": "why?"}
    )
    assert result["error"]["type"] == "query_failed"
    assert "secret" not in result["error"]["message"]


def test_answer_why_tool_is_registered(tmp_path: Path) -> None:
    app = build_app(_deps(tmp_path, FakeQuery(None)))
    assert "answer_why" in app.tool_names
