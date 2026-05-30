"""Slice 012-s06: metadata-only observability + read-only contract hardening.

Every MCP tool call emits metadata-only telemetry through the feature 002
``Observability`` port (US-6, FR-9): tool name, repository key, status, result
count, latency bucket, and error type — never raw questions, answers, ADR
content, or citations. Regression tests prove the surface stays read-only and
that no write-side/SCM/LLM symbol leaks into the app package.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from pathlib import Path

from living_adr.apps.mcp_context_server import (
    app as app_mod,
)
from living_adr.apps.mcp_context_server import (
    dependencies as deps_mod,
)
from living_adr.apps.mcp_context_server import (
    errors as errors_mod,
)
from living_adr.apps.mcp_context_server import (
    observability as obs_mod,
)
from living_adr.apps.mcp_context_server import (
    serializers as ser_mod,
)
from living_adr.apps.mcp_context_server import (
    tools as tools_mod,
)
from living_adr.apps.mcp_context_server import (
    validation as val_mod,
)
from living_adr.apps.mcp_context_server.dependencies import McpServerDependencies
from living_adr.apps.mcp_context_server.tools import (
    TOOL_DEFINITIONS,
    make_dispatch,
)
from living_adr.core.config_loader import load_living_adr_config
from living_adr.core.graph.models import ADRRef, ProvenancedADR, WhyAnswer
from living_adr.core.observability import ObservationSpan
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

DOCS_PATH = (
    Path(__file__).resolve().parents[3] / "docs" / "mcp-context-server.md"
)

# Precise write-side method / dependency names that must never appear in the
# read-only app package (avoids false positives on status strings).
FORBIDDEN_TOKENS = (
    "ArchitectureGraphStore",
    "ApprovalBoundMutationService",
    "upsert_adr_node",
    "add_relationship",
    "supersede_adr",
    "retract_adr",
    "migrate_schema",
    "record_structural_change",
    "GithubProvider",
    "github_provider",
    "claude_adapter",
    "anthropic",
)

PACKAGE_MODULES = (
    app_mod,
    deps_mod,
    errors_mod,
    obs_mod,
    ser_mod,
    tools_mod,
    val_mod,
)


class RecordingObservability:
    """Captures every metadata mapping handed to the Observability port."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, object]]] = []
        self.counters: list[tuple[str, int, dict[str, object]]] = []

    def record_event(
        self, name: str, metadata: Mapping[str, object] | None = None
    ) -> None:
        self.events.append((name, dict(metadata or {})))

    def increment_counter(
        self,
        name: str,
        value: int = 1,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        self.counters.append((name, value, dict(metadata or {})))

    @contextmanager
    def start_span(
        self, name: str, metadata: Mapping[str, object] | None = None
    ) -> Iterator[ObservationSpan]:
        yield ObservationSpan(name, metadata)

    def all_metadata_text(self) -> str:
        chunks: list[str] = []
        for _name, md in self.events:
            chunks.append(repr(md))
        for _name, _v, md in self.counters:
            chunks.append(repr(md))
        return " ".join(chunks)


class FakeQuery:
    def __init__(self, answer: WhyAnswer) -> None:
        self._answer = answer

    def list_adrs(self, repository: RepositoryIdentity) -> tuple[ADRRef, ...]:
        return (
            ADRRef(
                repository=repository,
                adr_id="adr-1",
                title="t",
                status="approved",
            ),
        )

    def fetch_adr(
        self, repository: RepositoryIdentity, adr_id: str
    ) -> ProvenancedADR | None:  # pragma: no cover - unused here
        return None

    def answer_why(self, *args: object, **kwargs: object) -> WhyAnswer:
        return self._answer


SECRET_QUESTION = "why did we adopt the SECRET_TOKEN_abc123 dependency?"


def _answer() -> WhyAnswer:
    return WhyAnswer(
        repository=IDENTITY_A,
        question=SECRET_QUESTION,
        answer="Approved decision adr-7: confidential rationale body.",
        adr_id="adr-7",
        citations=("adr:adr-7",),
        found=True,
    )


def _deps(tmp_path: Path, obs: RecordingObservability) -> McpServerDependencies:
    path = tmp_path / "living-adr.config.yaml"
    path.write_text(ONE_REPO_YAML, encoding="utf-8")
    return McpServerDependencies(
        config=load_living_adr_config(path),
        query=FakeQuery(_answer()),
        observability=obs,
    )


def test_tool_call_emits_metadata_only_event(tmp_path: Path) -> None:
    obs = RecordingObservability()
    make_dispatch(_deps(tmp_path, obs))(
        "answer_why", {"repository": KEY_A, "question": SECRET_QUESTION}
    )
    assert obs.events, "expected a metadata-only telemetry event"
    name, md = obs.events[0]
    assert md["tool"] == "answer_why"
    assert md["repository"] == KEY_A
    assert md["status"] == "ok"
    assert "latency_bucket" in md


def test_observability_excludes_raw_payloads(tmp_path: Path) -> None:
    obs = RecordingObservability()
    make_dispatch(_deps(tmp_path, obs))(
        "answer_why", {"repository": KEY_A, "question": SECRET_QUESTION}
    )
    blob = obs.all_metadata_text()
    assert "SECRET_TOKEN_abc123" not in blob
    assert "confidential rationale" not in blob
    assert "adr:adr-7" not in blob


def test_error_call_records_error_type(tmp_path: Path) -> None:
    obs = RecordingObservability()
    make_dispatch(_deps(tmp_path, obs))(
        "list_adrs", {"repository": "github.com/evil/unknown"}
    )
    _name, md = obs.events[0]
    assert md["status"] == "error"
    assert md["error_type"] == "unknown_repository"


def test_only_read_only_tools_are_exposed() -> None:
    names = {t.name for t in TOOL_DEFINITIONS}
    assert names == {"list_adrs", "fetch_adr", "answer_why"}
    forbidden = {
        "approve",
        "edit",
        "reject",
        "publish",
        "upsert",
        "migrate",
        "rebuild",
        "supersede",
        "retract",
    }
    assert names.isdisjoint(forbidden)


def test_app_package_imports_no_write_side_symbols() -> None:
    for module in PACKAGE_MODULES:
        source = Path(module.__file__).read_text(encoding="utf-8")
        for token in FORBIDDEN_TOKENS:
            assert token not in source, (
                f"forbidden token {token!r} found in {module.__name__}"
            )


def test_docs_describe_read_only_local_stdio_setup() -> None:
    assert DOCS_PATH.exists(), f"missing operator docs at {DOCS_PATH}"
    text = DOCS_PATH.read_text(encoding="utf-8").lower()
    assert "read-only" in text
    assert "stdio" in text
    assert "list_adrs" in text
    assert "fetch_adr" in text
    assert "answer_why" in text
    # No write credentials / secrets in MCP host configuration.
    assert "secret" in text  # must explicitly discuss not providing secrets
