"""Deterministic edited-draft hashing for the approve-after-edit path (feature 009).

When a reviewer edits a provisional draft and submits "approve after edit", the
UI computes a content hash over the exact edited Markdown so the downstream
feature 015 resume / feature 010 approval can bind to the precise reviewed bytes.

The hash convention matches feature 008/015's rendered-draft hashing: a plain
SHA-256 over the UTF-8 encoded content (see
``living_adr.core.adr_draft.compute_draft_content_hash`` and
``living_adr.hitl.stub_review`` which both hash the rendered Markdown the same
way). No provider/token metadata, clocks, or randomness enter the hash (NFR-3).
"""

from __future__ import annotations

import hashlib


def compute_edited_draft_hash(content: str) -> str:
    """Return the SHA-256 hex digest of the exact edited draft Markdown."""

    return hashlib.sha256(content.encode("utf-8")).hexdigest()


__all__ = ["compute_edited_draft_hash"]
