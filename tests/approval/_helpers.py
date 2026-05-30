"""Shared builders for feature 010 approval/audit tests.

These helpers construct repository-scoped domain values (identities, review
contexts, resume commands, ADR records) without importing any concrete graph
adapter, LLM, or network seam. They keep each test focused on approval/audit
behaviour rather than fixture boilerplate.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from living_adr.approval.minting import ReviewContext
from living_adr.core.adr import ADRRecord, ADRStatus
from living_adr.core.models import RepositoryIdentity
from living_adr.workflow.state import ReviewAction, ReviewResumeCommand


def build_repo(repo: str = "living-adr") -> RepositoryIdentity:
    """A deterministic repository identity for approval tests."""

    return RepositoryIdentity(
        host="github.com", owner="acme", repo=repo, repo_id=f"id-{repo}"
    )


def sha256_lf(content: str) -> str:
    """Plain SHA-256 over LF-normalised UTF-8 (matches feature 008/009 hashing)."""

    normalised = content.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


DRAFT_MARKDOWN = (
    "# Title: Adopt durable approval audit\n"
    "## Status\nProposed\n"
    "## Context\nWe need durable approval capability.\n"
    "## Decision\nMint one-shot capabilities.\n"
    "## Consequences\nStronger SM-05 evidence.\n"
)
DRAFT_HASH = sha256_lf(DRAFT_MARKDOWN)


def build_context(
    repository: RepositoryIdentity | None = None,
    *,
    draft_id: str = "draft-1",
    content_hash: str = DRAFT_HASH,
    structural_change_event_id: str | None = "change-1",
    adr_record_id: str = "adr-1",
    decision_version: int = 1,
    thread_id: str = "wf-thread-1",
    normalized_event_key: str = "github:acme/living-adr:7:delivery-1",
) -> ReviewContext:
    return ReviewContext(
        repository=repository or build_repo(),
        workflow_thread_id=thread_id,
        normalized_event_key=normalized_event_key,
        adr_draft_id=draft_id,
        adr_draft_content_hash=content_hash,
        structural_change_event_id=structural_change_event_id,
        adr_record_id=adr_record_id,
        decision_version=decision_version,
    )


def build_command(
    action: ReviewAction = ReviewAction.APPROVE,
    *,
    reviewer_id: str = "lead-1",
    edited_content: str | None = None,
    edited_content_hash: str | None = None,
) -> ReviewResumeCommand:
    return ReviewResumeCommand(
        action=action,
        reviewer_id=reviewer_id,
        edited_content=edited_content,
        edited_content_hash=edited_content_hash,
    )


def build_adr_record(
    repository: RepositoryIdentity,
    *,
    decision_id: str,
    adr_id: str = "adr-1",
    content_hash: str = DRAFT_HASH,
    markdown: str = DRAFT_MARKDOWN,
    structural_change_id: str | None = "change-1",
) -> ADRRecord:
    return ADRRecord(
        repository=repository,
        adr_id=adr_id,
        title="Adopt durable approval audit",
        status=ADRStatus.APPROVED,
        content_hash=content_hash,
        decision_id=decision_id,
        structural_change_id=structural_change_id,
        markdown=markdown,
    )


class FixedClock:
    """A controllable monotonic-ish clock for TTL/expiry tests."""

    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now = self._now + delta


class SequentialIds:
    """Deterministic id provider so audit ids are stable in assertions."""

    def __init__(self, prefix: str) -> None:
        self._prefix = prefix
        self._n = 0

    def __call__(self) -> str:
        self._n += 1
        return f"{self._prefix}-{self._n}"
