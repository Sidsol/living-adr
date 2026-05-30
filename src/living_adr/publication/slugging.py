"""Deterministic ADR title slugging (feature 011, FR-6).

Slugs are repository-portable filename fragments: lowercase ASCII, hyphen
separated, length-capped, and deterministic for the same title. Unicode is
transliterated to its closest ASCII form (accents dropped) so published ADR
filenames are stable across platforms and never carry non-ASCII bytes. A title
with no usable characters falls back to ``adr-<fallback_id>`` so a file name is
always producible.
"""

from __future__ import annotations

import re
import unicodedata

_NON_SLUG = re.compile(r"[^a-z0-9]+")

#: Default maximum slug length (FR-6).
DEFAULT_SLUG_MAX_LENGTH = 80


def slugify(
    title: str,
    *,
    fallback_id: str = "",
    max_length: int = DEFAULT_SLUG_MAX_LENGTH,
) -> str:
    """Return a deterministic lowercase-ASCII hyphenated slug for ``title``.

    Accents are stripped via NFKD normalisation, every run of non-alphanumeric
    characters becomes a single hyphen, the result is lower-cased and trimmed to
    ``max_length`` without a trailing hyphen. When nothing usable remains, the
    fallback ``adr-<fallback_id>`` (or ``adr``) is returned.
    """

    normalized = unicodedata.normalize("NFKD", title)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")
    slug = _NON_SLUG.sub("-", ascii_only.lower()).strip("-")
    if len(slug) > max_length:
        slug = slug[:max_length].rstrip("-")
    if slug:
        return slug
    return f"adr-{fallback_id}" if fallback_id else "adr"


__all__ = ["slugify", "DEFAULT_SLUG_MAX_LENGTH"]
