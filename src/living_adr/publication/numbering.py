"""ADR numbering, path rendering, and same-decision marker detection (feature 011).

These helpers are pure and provider-free: the publication committer feeds them
filenames/contents listed through the SCM port. They implement deterministic ADR
number allocation (FR-7), path rendering from the configured template/padding
(FR-5), and the ``livingadr_decision_id`` marker used to detect an already
published ADR for recovery/idempotency (FR-10).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

#: Numeric ADR filename prefix: leading digits followed by a separator or end.
_ADR_PREFIX = re.compile(r"^(\d+)(?:[-.]|$)")
_NUMBER_TOKEN = re.compile(r"N+")

#: Machine-readable marker embedded in published ADR Markdown so a retry can
#: detect the existing file even if the durable record is lost (FR-10).
DECISION_MARKER_LABEL = "livingadr_decision_id"


def parse_adr_number(filename: str) -> int | None:
    """Parse the leading numeric ADR prefix from ``filename`` (basename).

    Returns ``None`` for files that do not start with digits followed by a
    ``-``/``.`` separator (or end of string), so malformed names are ignored.
    """

    base = filename.rsplit("/", 1)[-1]
    match = _ADR_PREFIX.match(base)
    if match is None:
        return None
    return int(match.group(1))


def next_adr_number(filenames: Iterable[str]) -> int:
    """Highest existing ADR number + 1; ``1`` when no numbered ADR exists (FR-7)."""

    numbers = [n for n in (parse_adr_number(f) for f in filenames) if n is not None]
    return (max(numbers) + 1) if numbers else 1


def render_adr_path(
    template: str,
    number: int,
    slug: str,
    *,
    padding_width: int = 4,
) -> str:
    """Render the ADR path from ``template`` by filling number + slug tokens.

    The ``NNNN`` token (any run of ``N``) is replaced with the zero-padded
    number and ``<slug>`` with ``slug``. Padding width comes from the resolved
    target, not the literal token length, so config drives the width (FR-5).
    """

    rendered = _NUMBER_TOKEN.sub(str(number).zfill(padding_width), template, count=1)
    return rendered.replace("<slug>", slug)


def decision_marker(decision_id: str) -> str:
    """The HTML-comment marker line embedded in a published ADR (FR-10)."""

    return f"<!-- {DECISION_MARKER_LABEL}: {decision_id} -->"


def embed_decision_marker(markdown: str, decision_id: str) -> str:
    """Prepend the decision marker to ``markdown`` (idempotent if already present)."""

    marker = decision_marker(decision_id)
    if marker in markdown:
        return markdown
    return f"{marker}\n{markdown}"


def find_file_with_decision_marker(
    files: Mapping[str, str], decision_id: str
) -> str | None:
    """Return the path of the file whose content carries ``decision_id``'s marker."""

    needle = f"{DECISION_MARKER_LABEL}: {decision_id}"
    for path, content in files.items():
        if needle in content:
            return path
    return None


__all__ = [
    "DECISION_MARKER_LABEL",
    "parse_adr_number",
    "next_adr_number",
    "render_adr_path",
    "decision_marker",
    "embed_decision_marker",
    "find_file_with_decision_marker",
]
