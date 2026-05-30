"""Slice S011-03 RED tests: deterministic slugging, numbering, path allocation.

Covers ASCII slug normalisation (unicode, punctuation, length cap, empty
fallback), numeric ADR prefix parsing that ignores malformed names, next-number
allocation (empty dir, gaps, highest), path rendering from the configured
template/padding, and same-decision marker embedding/detection.
"""

from __future__ import annotations

import pytest

from living_adr.publication.numbering import (
    decision_marker,
    embed_decision_marker,
    find_file_with_decision_marker,
    next_adr_number,
    parse_adr_number,
    render_adr_path,
)
from living_adr.publication.slugging import slugify

# --- slugging -------------------------------------------------------------


def test_simple_title_slug() -> None:
    assert slugify("Adopt Durable Approval Audit") == "adopt-durable-approval-audit"


def test_unicode_is_transliterated_to_ascii() -> None:
    assert slugify("Café déjà vu") == "cafe-deja-vu"


def test_punctuation_and_symbols_collapse_to_single_hyphen() -> None:
    assert slugify("Use   gRPC / HTTP-2!! (maybe?)") == "use-grpc-http-2-maybe"


def test_length_is_capped_without_trailing_hyphen() -> None:
    title = "word " * 40  # very long
    slug = slugify(title, max_length=80)
    assert len(slug) <= 80
    assert not slug.endswith("-")
    assert not slug.startswith("-")


def test_empty_or_unusable_title_uses_fallback_id() -> None:
    assert slugify("！！！", fallback_id="42") == "adr-42"
    assert slugify("", fallback_id="adr-7") == "adr-adr-7"


def test_unusable_title_without_fallback_is_stable() -> None:
    assert slugify("***") == "adr"


# --- numeric prefix parsing -----------------------------------------------


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("0001-adopt.md", 1),
        ("0007-foo.md", 7),
        ("12-bar.markdown", 12),
        ("0003.md", 3),
        ("readme.md", None),
        ("notes.txt", None),
        ("1abc-no-separator.md", None),
        ("draft-2-not-prefixed.md", None),
    ],
)
def test_parse_adr_number(filename: str, expected: int | None) -> None:
    assert parse_adr_number(filename) == expected


# --- next-number allocation -----------------------------------------------


def test_next_number_defaults_to_one_for_empty_directory() -> None:
    assert next_adr_number([]) == 1
    assert next_adr_number(["readme.md", "notes.txt"]) == 1


def test_next_number_is_highest_existing_plus_one_with_gaps() -> None:
    files = ["0001-a.md", "0003-b.md", "readme.md", "0002-c.md"]
    assert next_adr_number(files) == 4


# --- path rendering -------------------------------------------------------


def test_render_default_padding_and_slug() -> None:
    path = render_adr_path(
        "docs/adr/NNNN-<slug>.md", 1, "adopt-durable-approval-audit"
    )
    assert path == "docs/adr/0001-adopt-durable-approval-audit.md"


def test_render_respects_configured_padding_width() -> None:
    path = render_adr_path(
        "architecture/decisions/NNN-<slug>.markdown",
        42,
        "use-grpc",
        padding_width=3,
    )
    assert path == "architecture/decisions/042-use-grpc.markdown"


# --- same-decision marker -------------------------------------------------


def test_marker_embed_and_detect_roundtrip() -> None:
    body = "# Title\n\nSome ADR body.\n"
    marked = embed_decision_marker(body, "decision-xyz")
    assert "livingadr_decision_id: decision-xyz" in marked
    files = {"docs/adr/0001-x.md": marked, "docs/adr/0002-y.md": "no marker here"}
    assert find_file_with_decision_marker(files, "decision-xyz") == "docs/adr/0001-x.md"


def test_marker_detection_is_decision_specific() -> None:
    files = {"docs/adr/0001-x.md": decision_marker("decision-aaa")}
    assert find_file_with_decision_marker(files, "decision-bbb") is None
