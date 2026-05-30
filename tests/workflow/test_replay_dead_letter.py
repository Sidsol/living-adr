"""Slice 5 RED tests: replay + dead-letter recovery.

Covers retryable-then-recovered replay, poison (non-retryable) dead-letter,
idempotent replay of an already-accepted event (no provider refetch, no duplicate
evidence), and retry-budget exhaustion escalating to dead-letter.
"""

from __future__ import annotations

import hashlib
import hmac
import json

from living_adr.apps.workflow_service.webhooks import GitHubWebhookHandler
from living_adr.core.config import (
    LivingADRConfig,
    PublicationPolicy,
    RepositoryConfig,
)
from living_adr.core.ingestion import DeliveryStatus, IngestionErrorCategory
from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import (
    ChangedFileMetadata,
    DiffEvidence,
    ProviderPermissionError,
    PullRequestMetadata,
    RateLimitError,
)
from living_adr.persistence.ingestion_store import InMemoryIngestionStore
from living_adr.scm.github_webhook import (
    DELIVERY_HEADER,
    EVENT_HEADER,
    SIGNATURE_HEADER,
)
from living_adr.workflow.ingestion import IngestionPipeline
from living_adr.workflow.replay import ReplayService

SECRET = "replay-secret"


def _config() -> LivingADRConfig:
    return LivingADRConfig(
        repositories=[
            RepositoryConfig(
                identity=RepositoryIdentity(
                    host="github.com", owner="acme", repo="widgets", repo_id="100"
                ),
                github_app_installation_id="inst-555",
                default_branch="main",
                adr_publication_policy=PublicationPolicy.LIVINGADR_ONLY,
                external_llm_allowed=False,
            )
        ]
    )


def _payload() -> bytes:
    return json.dumps(
        {
            "action": "closed",
            "number": 42,
            "repository": {
                "id": 100,
                "name": "widgets",
                "full_name": "acme/widgets",
                "owner": {"login": "acme"},
                "html_url": "https://github.com/acme/widgets",
            },
            "pull_request": {
                "number": 42,
                "title": "Add httpx client",
                "merged": True,
                "merged_at": "2024-06-01T10:00:00Z",
                "merge_commit_sha": "mergesha",
                "head": {"ref": "f", "sha": "s"},
                "base": {"ref": "main"},
            },
            "sender": {"login": "octocat"},
            "installation": {"id": 555},
        }
    ).encode()


def _headers(body: bytes, delivery_id: str) -> dict[str, str]:
    digest = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return {
        SIGNATURE_HEADER: f"sha256={digest}",
        DELIVERY_HEADER: delivery_id,
        EVENT_HEADER: "pull_request",
    }


class FlakyProvider:
    """Fails for the first ``fail_times`` calls (or always), then succeeds."""

    def __init__(self, error=None, fail_times: int = 0) -> None:
        self._error = error
        self._fail_times = fail_times
        self.pr_calls = 0

    def _maybe_fail(self) -> None:
        if self._error is not None and self.pr_calls <= self._fail_times:
            raise self._error

    def fetch_pull_request(self, repository, handle) -> PullRequestMetadata:
        self.pr_calls += 1
        self._maybe_fail()
        return PullRequestMetadata(
            number=42,
            title="Add httpx client",
            body="",
            author="octocat",
            state="closed",
            merged=True,
            head_ref="f",
            base_ref="main",
            merge_commit_sha="mergesha",
        )

    def fetch_changed_files(self, repository, handle):
        return (ChangedFileMetadata(filename="pyproject.toml", status="modified"),)

    def fetch_diff(self, repository, handle) -> DiffEvidence:
        return DiffEvidence(diff_handle="h", summary="1 file", byte_size=10)


def _seed(store, provider, delivery_id="d-1"):
    pipeline = IngestionPipeline(config=_config(), store=store, provider=provider)
    handler = GitHubWebhookHandler(secret=SECRET, pipeline=pipeline)
    body = _payload()
    handler.handle(body, _headers(body, delivery_id))


def test_retryable_failure_then_recovered_replay_succeeds() -> None:
    store = InMemoryIngestionStore()
    # First fetch attempt rate-limits -> RETRYABLE, no evidence.
    provider = FlakyProvider(error=RateLimitError("limited"), fail_times=1)
    _seed(store, provider)
    seeded = store.get_delivery("d-1")
    assert seeded.status is DeliveryStatus.RETRYABLE
    assert store.get_evidence(seeded.normalized_pr_key) is None

    # Operator replays; provider has recovered (2nd call succeeds).
    result = ReplayService(store=store, provider=provider).replay_delivery("d-1")
    assert result.status is DeliveryStatus.REPLAYED
    assert result.evidence is not None
    assert result.reused is False
    assert store.get_delivery("d-1").status is DeliveryStatus.REPLAYED


def test_replay_of_accepted_event_is_idempotent_no_refetch() -> None:
    store = InMemoryIngestionStore()
    provider = FlakyProvider()  # always succeeds
    _seed(store, provider)
    accepted = store.get_delivery("d-1")
    assert accepted.status is DeliveryStatus.ACCEPTED
    calls_after_seed = provider.pr_calls

    result = ReplayService(store=store, provider=provider).replay_delivery("d-1")
    assert result.reused is True
    assert result.evidence is not None
    # No additional provider fetch on idempotent replay.
    assert provider.pr_calls == calls_after_seed
    # Duplicate replay remains idempotent.
    again = ReplayService(store=store, provider=provider).replay_delivery("d-1")
    assert again.reused is True
    assert provider.pr_calls == calls_after_seed


def test_poison_permission_failure_dead_letters() -> None:
    store = InMemoryIngestionStore()
    provider = FlakyProvider(error=ProviderPermissionError("no access"), fail_times=99)
    _seed(store, provider)
    seeded = store.get_delivery("d-1")
    # Non-retryable category -> straight to dead-letter.
    assert seeded.status is DeliveryStatus.DEAD_LETTER
    assert seeded.error_category is IngestionErrorCategory.PERMISSION_DENIED
    assert [d.delivery_id for d in store.list_dead_letters()] == ["d-1"]


def test_retry_budget_exhaustion_escalates_to_dead_letter() -> None:
    store = InMemoryIngestionStore()
    provider = FlakyProvider(error=RateLimitError("limited"), fail_times=99)
    _seed(store, provider)
    service = ReplayService(store=store, provider=provider, max_retries=2)
    # Seed left retry_count=0 RETRYABLE; replay until budget exhausts.
    r1 = service.replay_delivery("d-1")
    assert r1.status is DeliveryStatus.RETRYABLE
    r2 = service.replay_delivery("d-1")
    assert r2.status is DeliveryStatus.DEAD_LETTER
    assert store.get_delivery("d-1").status is DeliveryStatus.DEAD_LETTER


def test_replay_unknown_delivery_returns_none_result() -> None:
    store = InMemoryIngestionStore()
    result = ReplayService(
        store=store, provider=FlakyProvider()
    ).replay_delivery("missing")
    assert result.delivery is None
    assert result.evidence is None
