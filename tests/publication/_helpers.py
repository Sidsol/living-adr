"""Shared builders for feature 011 publication tests.

These helpers construct repository-scoped domain values (identities, repository
config, ADR records, approved decisions) and a fake SCM contents provider so each
test stays focused on publish-back behaviour rather than fixture boilerplate. No
concrete graph adapter, LLM, or network seam is imported.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from living_adr.core.adr import ADRRecord, ADRStatus
from living_adr.core.approval import ApprovedReviewDecision
from living_adr.core.config import PublicationPolicy, RepositoryConfig
from living_adr.core.graph.approval_bound_mutation import upsert_fingerprint
from living_adr.core.models import RepositoryIdentity


def build_repo(repo: str = "living-adr") -> RepositoryIdentity:
    return RepositoryIdentity(
        host="github.com", owner="acme", repo=repo, repo_id=f"id-{repo}"
    )


def sha256_lf(content: str) -> str:
    normalised = content.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(normalised.encode("utf-8")).hexdigest()


ADR_MARKDOWN = (
    "# Title: Adopt durable approval audit\n"
    "## Status\nApproved\n"
    "## Context\nWe need durable approval capability.\n"
    "## Decision\nMint one-shot capabilities.\n"
    "## Consequences\nStronger SM-05 evidence.\n"
)
ADR_HASH = sha256_lf(ADR_MARKDOWN)


def build_config(
    repository: RepositoryIdentity | None = None,
    *,
    policy: PublicationPolicy = PublicationPolicy.PUBLISH_TO_GITHUB,
    default_branch: str = "main",
    adr_target_branch: str | None = "main",
    adr_path_template: str | None = "docs/adr/NNNN-<slug>.md",
    external_llm_allowed: bool = False,
) -> RepositoryConfig:
    repository = repository or build_repo()
    # livingadr_only does not require branch/template; null them out so the
    # model validator does not demand a publish target it never uses.
    if not policy.publishes_to_github:
        adr_target_branch = None
        adr_path_template = None
    return RepositoryConfig(
        identity=repository,
        github_app_installation_id="inst-1",
        default_branch=default_branch,
        adr_publication_policy=policy,
        external_llm_allowed=external_llm_allowed,
        adr_target_branch=adr_target_branch,
        adr_path_template=adr_path_template,
    )


def build_adr(
    repository: RepositoryIdentity | None = None,
    *,
    adr_id: str = "adr-1",
    title: str = "Adopt durable approval audit",
    decision_id: str = "decision-1",
    content_hash: str = ADR_HASH,
    markdown: str = ADR_MARKDOWN,
    structural_change_id: str | None = "change-1",
) -> ADRRecord:
    return ADRRecord(
        repository=repository or build_repo(),
        adr_id=adr_id,
        title=title,
        status=ADRStatus.APPROVED,
        content_hash=content_hash,
        decision_id=decision_id,
        structural_change_id=structural_change_id,
        markdown=markdown,
    )


def build_decision(
    repository: RepositoryIdentity | None = None,
    adr: ADRRecord | None = None,
    *,
    decision_id: str = "decision-1",
    reviewer_id: str = "lead-1",
    minted_at: datetime | None = None,
    approved: bool = True,
) -> ApprovedReviewDecision:
    repository = repository or build_repo()
    adr = adr or build_adr(repository, decision_id=decision_id)
    return ApprovedReviewDecision(
        repository=repository,
        decision_id=decision_id,
        reviewer_id=reviewer_id,
        adr_draft_id=adr.adr_id,
        adr_draft_content_hash=adr.content_hash,
        structural_change_event_id=adr.structural_change_id,
        target_fingerprint=upsert_fingerprint(repository, adr),
        minted_at=minted_at or datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC),
        approved=approved,
    )


class FixedClock:
    def __init__(self, start: datetime | None = None) -> None:
        self._now = start or datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self._now

    def advance(self, delta: timedelta) -> None:
        self._now = self._now + delta


class SequentialIds:
    def __init__(self, prefix: str) -> None:
        self._prefix = prefix
        self._n = 0

    def __call__(self) -> str:
        self._n += 1
        return f"{self._prefix}-{self._n}"
