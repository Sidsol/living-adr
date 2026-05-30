"""Canonical rendered-ADR content hashing for feature 010.

Approval binds to the *exact* reviewed ADR content via SHA-256. To keep that
binding stable across platforms and editors, the content is canonicalised to
UTF-8 with LF line endings before hashing (architecture #service-boundaries;
FR-5; assumption: UTF-8 with LF line endings).

Byte-compatibility: for content that is already LF/UTF-8, this digest is
identical to feature 008/009/015's rendered-draft hashing
(``living_adr.core.adr_draft.compute_draft_content_hash`` over the rendered body
and ``living_adr.hitl.hashing.compute_edited_draft_hash``), so a capability minted
by feature 010 verifies against the hash the reviewer approved. The only added
behaviour is CRLF/CR normalisation so a checkout with different line endings does
not produce a spurious :class:`DraftContentMismatchError`.

No provider/token metadata, clocks, or randomness ever enter the hash (NFR-3).
"""

from __future__ import annotations

import hashlib


def canonicalize_adr_content(content: str) -> str:
    """Normalise rendered ADR Markdown to canonical UTF-8/LF form (pre-hash)."""

    return content.replace("\r\n", "\n").replace("\r", "\n")


def canonical_adr_hash(content: str) -> str:
    """Return the SHA-256 hex digest of canonicalised rendered ADR content."""

    return hashlib.sha256(
        canonicalize_adr_content(content).encode("utf-8")
    ).hexdigest()


def content_matches_hash(content: str, expected_hash: str) -> bool:
    """True when ``content`` canonically hashes to ``expected_hash``."""

    return canonical_adr_hash(content) == expected_hash


__all__ = [
    "canonicalize_adr_content",
    "canonical_adr_hash",
    "content_matches_hash",
]
