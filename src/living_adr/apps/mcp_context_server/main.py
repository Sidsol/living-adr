"""mcp-context-server smoke entrypoint: read-only ``answer_why`` wrapper.

This is a SMOKE STUB for the production MCP context server. It is read-only by
construction: it depends only on a read-side query port (``ArchitectureContext
Query``-shaped) exposing ``answer_why`` and imports no SCM, HITL, or write-side
graph code (architecture #service-boundaries; FM-15 MCP read-only trust;
FM-16 auth deferred). Transport (MCP stdio/SDK) is intentionally out of scope and
deferred to a later feature.
"""

from __future__ import annotations

from typing import Protocol

from living_adr.core.models import RepositoryIdentity, WhyAnswer


class AnswerWhyQuery(Protocol):
    """Read-side port surface the MCP server is allowed to depend on."""

    def answer_why(
        self,
        repository: RepositoryIdentity,
        question: str,
        code_area_id: str | None = None,
    ) -> WhyAnswer: ...


class SmokeMcpContextServer:
    """Read-only MCP-style context server over an approved-context query port."""

    def __init__(self, query: AnswerWhyQuery) -> None:
        self._query = query

    def answer_why_smoke(
        self,
        *,
        repository: RepositoryIdentity,
        question: str,
        code_area_id: str | None = None,
    ) -> WhyAnswer:
        """Answer a why-question using approved context only (read-only)."""

        return self._query.answer_why(repository, question, code_area_id)
