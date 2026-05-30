"""Markdown ADR output parser and validator (feature 008, slice S-005, US-1).

Claude output is **never** trusted blindly: this parser validates that a draft
contains the required ADR sections, at least one citation, and an explicit
provisional label before the node accepts it as a draft. Anything malformed
raises :class:`DraftParseError`, which the node maps to the ``INVALID_OUTPUT``
outcome (FR-9) — never a silent or partial draft.
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict

_TITLE_RE = re.compile(r"^#\s+(?P<title>.+?)\s*$", re.MULTILINE)
_HEADING_RE = re.compile(r"^##\s+(?P<name>.+?)\s*$", re.MULTILINE)
_STATUS_RE = re.compile(r"^Status:\s*(?P<status>.+?)\s*$", re.MULTILINE)
_CITATION_TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")

_REQUIRED_SECTIONS = ("context", "decision", "alternatives", "consequences")
_PROVISIONAL_MARKER = "provisional"


class DraftParseError(ValueError):
    """Raised when a Claude completion is not a valid provisional ADR draft."""


class ParsedDraft(BaseModel):
    """A validated ADR parsed from Claude Markdown output."""

    model_config = ConfigDict(frozen=True)

    title: str
    status: str
    context: str
    decision: str
    alternatives: str
    consequences: str
    citations: tuple[str, ...]
    provisional: bool
    raw_markdown: str


def _split_sections(markdown: str) -> dict[str, str]:
    """Map lower-cased ``## Heading`` names to their body text."""

    sections: dict[str, str] = {}
    matches = list(_HEADING_RE.finditer(markdown))
    for index, match in enumerate(matches):
        name = match.group("name").strip().lower()
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        sections[name] = markdown[start:end].strip()
    return sections


def _extract_citations(body: str) -> tuple[str, ...]:
    tokens: list[str] = []
    for line in body.splitlines():
        stripped = line.strip().lstrip("-*").strip()
        if not stripped:
            continue
        for token in _CITATION_TOKEN_RE.findall(stripped):
            tokens.append(token)
    # Deterministic, de-duplicated order.
    return tuple(sorted(set(tokens)))


def parse_adr_markdown(markdown: str) -> ParsedDraft:
    """Validate and parse a Markdown ADR completion into a :class:`ParsedDraft`."""

    title_match = _TITLE_RE.search(markdown)
    if title_match is None:
        raise DraftParseError("ADR is missing a '# Title' heading")
    title = title_match.group("title").strip()

    status_match = _STATUS_RE.search(markdown)
    if status_match is None:
        raise DraftParseError("ADR is missing a 'Status:' line")
    status = status_match.group("status").strip()

    if _PROVISIONAL_MARKER not in status.lower():
        raise DraftParseError(
            "ADR status must carry an explicit provisional label"
        )

    sections = _split_sections(markdown)
    for required in _REQUIRED_SECTIONS:
        if not sections.get(required):
            raise DraftParseError(f"ADR is missing required section: {required}")

    citations = _extract_citations(sections.get("citations", ""))
    if not citations:
        raise DraftParseError(
            "ADR must include at least one citation (evidence or ADR id)"
        )

    return ParsedDraft(
        title=title,
        status=status,
        context=sections["context"],
        decision=sections["decision"],
        alternatives=sections["alternatives"],
        consequences=sections["consequences"],
        citations=citations,
        provisional=True,
        raw_markdown=markdown,
    )


__all__ = [
    "DraftParseError",
    "ParsedDraft",
    "parse_adr_markdown",
]
