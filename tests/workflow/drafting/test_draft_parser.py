"""S-005 RED tests: Markdown ADR output parser/validator (feature 008, US-1).

The parser turns a Claude Markdown completion into a validated
:class:`ParsedDraft`, requiring the ADR sections, at least one citation, and an
explicit provisional label. Missing structure raises :class:`DraftParseError` so
malformed output is never silently accepted as a draft.
"""

from __future__ import annotations

import pytest

from living_adr.workflow.drafting.parser import (
    DraftParseError,
    ParsedDraft,
    parse_adr_markdown,
)

_VALID = """# Adopt requests 2.x
Status: proposed (PROVISIONAL — not authoritative until human approval)

## Context
A direct dependency on requests was added to pyproject.toml.

## Decision
Adopt requests 2.x as the standard HTTP client.

## Alternatives
Vendor httpx; keep urllib.

## Consequences
New transitive dependency surface; revisit on CVE.

## Citations
- ev-1
- adr-3
"""


def test_parses_valid_adr_markdown() -> None:
    draft = parse_adr_markdown(_VALID)
    assert isinstance(draft, ParsedDraft)
    assert draft.title == "Adopt requests 2.x"
    assert "requests" in draft.context
    assert "Adopt" in draft.decision
    assert "Vendor" in draft.alternatives
    assert "transitive" in draft.consequences
    assert draft.provisional is True
    assert draft.citations == ("adr-3", "ev-1")
    assert draft.raw_markdown == _VALID


def test_missing_required_section_raises() -> None:
    without_decision = _VALID.replace(
        "## Decision\nAdopt requests 2.x as the standard HTTP client.\n\n", ""
    )
    with pytest.raises(DraftParseError) as exc:
        parse_adr_markdown(without_decision)
    assert "decision" in str(exc.value).lower()


def test_missing_title_raises() -> None:
    no_title = _VALID.replace("# Adopt requests 2.x\n", "")
    with pytest.raises(DraftParseError):
        parse_adr_markdown(no_title)


def test_missing_citations_raises() -> None:
    no_citations = _VALID.replace("## Citations\n- ev-1\n- adr-3\n", "## Citations\n")
    with pytest.raises(DraftParseError) as exc:
        parse_adr_markdown(no_citations)
    assert "citation" in str(exc.value).lower()


def test_missing_provisional_label_raises() -> None:
    not_provisional = _VALID.replace(
        "Status: proposed (PROVISIONAL — not authoritative until human approval)",
        "Status: proposed",
    )
    with pytest.raises(DraftParseError) as exc:
        parse_adr_markdown(not_provisional)
    assert "provisional" in str(exc.value).lower()
