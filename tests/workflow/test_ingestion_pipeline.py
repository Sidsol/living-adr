"""Slice 2 RED tests: idempotent ingestion pipeline wiring.

The pipeline checks the delivery store *before* processing, persists first-seen
delivery state, and returns the prior outcome on duplicate delivery ids without
reprocessing. Filtering decisions map to accepted/skipped/rejected delivery state.
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
from living_adr.persistence.ingestion_store import InMemoryIngestionStore
from living_adr.scm.github_webhook import (
    DELIVERY_HEADER,
    EVENT_HEADER,
    SIGNATURE_HEADER,
)
from living_adr.workflow.ingestion import IngestionPipeline

SECRET = "pipeline-secret"


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


def _payload(owner: str = "acme", repo: str = "widgets", merged: bool = True) -> bytes:
    return json.dumps(
        {
            "action": "closed",
            "number": 42,
            "repository": {
                "id": 100,
                "name": repo,
                "full_name": f"{owner}/{repo}",
                "owner": {"login": owner},
                "html_url": f"https://github.com/{owner}/{repo}",
            },
            "pull_request": {
                "number": 42,
                "title": "Add httpx client",
                "merged": merged,
                "merged_at": "2024-06-01T10:00:00Z",
                "merge_commit_sha": "abc123",
                "head": {"ref": "f", "sha": "s"},
                "base": {"ref": "main"},
            },
            "sender": {"login": "octocat"},
            "installation": {"id": 555},
        }
    ).encode()


def _headers(body: bytes, delivery_id: str = "d-1") -> dict[str, str]:
    digest = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return {
        SIGNATURE_HEADER: f"sha256={digest}",
        DELIVERY_HEADER: delivery_id,
        EVENT_HEADER: "pull_request",
    }


def _handler(store: InMemoryIngestionStore) -> GitHubWebhookHandler:
    pipeline = IngestionPipeline(config=_config(), store=store)
    return GitHubWebhookHandler(secret=SECRET, pipeline=pipeline)


def test_accepted_merged_pr_persists_accepted_delivery() -> None:
    store = InMemoryIngestionStore()
    handler = _handler(store)
    body = _payload()
    response = handler.handle(body, _headers(body))
    assert response.status_code == 202
    stored = store.get_delivery("d-1")
    assert stored is not None
    assert stored.status is DeliveryStatus.ACCEPTED
    assert stored.repository_key == "github.com/acme/widgets"
    assert stored.pr_number == 42


def test_duplicate_delivery_returns_prior_without_reprocessing() -> None:
    store = InMemoryIngestionStore()
    handler = _handler(store)
    body = _payload()
    first = handler.handle(body, _headers(body))
    second = handler.handle(body, _headers(body))
    assert first.status_code == 202
    assert second.outcome == "duplicate"
    # Still exactly one stored delivery, unchanged.
    assert store.get_delivery("d-1").status is DeliveryStatus.ACCEPTED


def test_unconfigured_repository_persists_rejected() -> None:
    store = InMemoryIngestionStore()
    handler = _handler(store)
    body = _payload(owner="evil", repo="spoof")
    response = handler.handle(body, _headers(body))
    assert response.status_code == 422
    stored = store.get_delivery("d-1")
    assert stored.status is DeliveryStatus.REJECTED
    assert stored.error_category is IngestionErrorCategory.UNCONFIGURED_REPOSITORY


def test_unmerged_pr_persists_skipped() -> None:
    store = InMemoryIngestionStore()
    handler = _handler(store)
    body = _payload(merged=False)
    response = handler.handle(body, _headers(body))
    assert response.status_code == 200
    stored = store.get_delivery("d-1")
    assert stored.status is DeliveryStatus.SKIPPED
    assert stored.error_category is IngestionErrorCategory.NOT_MERGED
