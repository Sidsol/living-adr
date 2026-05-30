"""Slice 4 RED tests: candidate evidence builder + cache reuse.

Evidence links the canonical event, PR metadata, changed files, and diff handle,
is immutable, repository-scoped, and reused from the cache on repeat/replay so the
provider is not called twice (NFR-3). Provider failures emit no partial evidence.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from living_adr.core.models import SCMEvent
from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import (
    ChangedFileMetadata,
    DiffEvidence,
    PullRequestMetadata,
    RateLimitError,
    SCMEventEnvelope,
    SCMFetchHandle,
    SCMProviderName,
    build_normalized_pr_key,
)
from living_adr.persistence.ingestion_store import InMemoryIngestionStore
from living_adr.workflow.ingestion import EvidenceBuilder

REPO = RepositoryIdentity(
    host="github.com", owner="acme", repo="widgets", repo_id="100"
)


def _envelope() -> SCMEventEnvelope:
    event = SCMEvent(
        repository=REPO,
        delivery_id="d-1",
        provider=SCMProviderName.GITHUB.value,
        event_type="merged_pr",
        pr_number=42,
        pr_title="Add httpx client",
        merged_at=datetime(2024, 6, 1, 10, 0, tzinfo=UTC),
        diff_summary="",
        changed_files=(),
    )
    return SCMEventEnvelope(
        event=event,
        provider=SCMProviderName.GITHUB,
        provider_event_type="pull_request.closed",
        normalized_pr_key=build_normalized_pr_key(
            SCMProviderName.GITHUB, REPO, 42, "mergesha"
        ),
        fetch_handle=SCMFetchHandle(
            installation_id="inst-555", pr_number=42, merge_commit_sha="mergesha"
        ),
    )


class CountingProvider:
    def __init__(self, error=None) -> None:
        self.pr_calls = 0
        self.file_calls = 0
        self.diff_calls = 0
        self._error = error

    def fetch_pull_request(self, repository, handle) -> PullRequestMetadata:
        self.pr_calls += 1
        if self._error is not None:
            raise self._error
        return PullRequestMetadata(
            number=42,
            title="Add httpx client",
            body="b",
            author="octocat",
            state="closed",
            merged=True,
            head_ref="f",
            base_ref="main",
            merge_commit_sha="mergesha",
        )

    def fetch_changed_files(self, repository, handle):
        self.file_calls += 1
        return (
            ChangedFileMetadata(filename="pyproject.toml", status="modified"),
        )

    def fetch_diff(self, repository, handle) -> DiffEvidence:
        self.diff_calls += 1
        return DiffEvidence(diff_handle="h", summary="1 file", byte_size=10)


def test_evidence_links_event_and_provider_data() -> None:
    store = InMemoryIngestionStore()
    provider = CountingProvider()
    builder = EvidenceBuilder(provider=provider, store=store)
    envelope = _envelope()
    evidence = builder.build(envelope)
    assert evidence.repository == REPO
    assert evidence.source_delivery_id == "d-1"
    assert evidence.normalized_pr_key == envelope.normalized_pr_key
    assert evidence.pr_number == 42
    assert evidence.pr_title == "Add httpx client"
    assert evidence.changed_files[0].filename == "pyproject.toml"
    assert evidence.diff.diff_handle == "h"
    assert evidence.provider is SCMProviderName.GITHUB
    assert evidence.is_complete is True


def test_evidence_is_cached_and_provider_not_called_twice() -> None:
    store = InMemoryIngestionStore()
    provider = CountingProvider()
    builder = EvidenceBuilder(provider=provider, store=store)
    envelope = _envelope()
    first = builder.build(envelope)
    second = builder.build(envelope)
    assert first == second
    assert provider.pr_calls == 1
    assert provider.file_calls == 1
    assert provider.diff_calls == 1
    assert store.get_evidence(envelope.normalized_pr_key) == first


def test_provider_failure_emits_no_partial_evidence() -> None:
    store = InMemoryIngestionStore()
    provider = CountingProvider(error=RateLimitError("rate limited"))
    builder = EvidenceBuilder(provider=provider, store=store)
    envelope = _envelope()
    with pytest.raises(RateLimitError):
        builder.build(envelope)
    assert store.get_evidence(envelope.normalized_pr_key) is None
