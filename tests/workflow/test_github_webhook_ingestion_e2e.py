"""Slice 6 RED tests: end-to-end GitHub webhook ingestion.

Exercises the full verified path through the real ``GitHubWebhookHandler`` ->
``IngestionPipeline`` -> ``GitHubProvider`` (behind a fake, network-free GitHub
client) and asserts the externally observable contract: a valid signed merged-PR
delivery yields exactly one canonical ``SCMEvent`` plus one ``CandidateEvidence``,
and a duplicate delivery returns the prior outcome without any provider refetch
(FR-1, FR-9, NFR idempotency; no real network).
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
from living_adr.core.models import SCMEvent
from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import CandidateEvidence
from living_adr.persistence.ingestion_store import InMemoryIngestionStore
from living_adr.scm.github_provider import GitHubProvider
from living_adr.scm.github_webhook import (
    DELIVERY_HEADER,
    EVENT_HEADER,
    SIGNATURE_HEADER,
)
from living_adr.workflow.ingestion import IngestionPipeline

SECRET = "e2e-secret"

_PR_JSON = {
    "number": 42,
    "title": "Add httpx client",
    "body": "Introduces outbound API client.",
    "state": "closed",
    "merged": True,
    "user": {"login": "octocat"},
    "head": {"ref": "feature/httpx"},
    "base": {"ref": "main"},
    "merge_commit_sha": "mergesha",
}
_FILES_JSON = [
    {
        "filename": "pyproject.toml",
        "status": "modified",
        "additions": 2,
        "deletions": 0,
    },
]
_DIFF_TEXT = "diff --git a/pyproject.toml b/pyproject.toml\n+httpx>=0.27\n"


class CountingGitHubClient:
    """Network-free GitHub client that records every call for refetch checks."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_json(self, path: str):
        self.calls.append(path)
        for suffix, value in (
            ("/pulls/42/files", _FILES_JSON),
            ("/pulls/42", _PR_JSON),
        ):
            if path.endswith(suffix):
                return value
        raise AssertionError(f"unexpected path {path}")

    def get_diff(self, path: str) -> str:
        self.calls.append(path + "#diff")
        return _DIFF_TEXT


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
                "head": {"ref": "feature/httpx", "sha": "headsha"},
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


def _build():
    store = InMemoryIngestionStore()
    client = CountingGitHubClient()
    provider = GitHubProvider(client)
    pipeline = IngestionPipeline(config=_config(), store=store, provider=provider)
    handler = GitHubWebhookHandler(secret=SECRET, pipeline=pipeline)
    return store, client, handler


def test_valid_merged_pr_yields_one_event_and_one_evidence() -> None:
    store, client, handler = _build()
    body = _payload()

    response = handler.handle(body, _headers(body, "delivery-1"))
    assert response.status_code == 202

    envelope = store.get_envelope("delivery-1")
    assert envelope is not None
    assert isinstance(envelope.event, SCMEvent)
    assert envelope.event.delivery_id == "delivery-1"
    assert envelope.event.pr_number == 42
    key = envelope.normalized_pr_key

    evidence = store.get_evidence(key)
    assert isinstance(evidence, CandidateEvidence)
    assert client.calls, "provider should have fetched evidence once"


def test_duplicate_delivery_returns_prior_without_refetch() -> None:
    store, client, handler = _build()
    body = _payload()

    first = handler.handle(body, _headers(body, "delivery-1"))
    assert first.status_code == 202
    calls_after_first = list(client.calls)

    second = handler.handle(body, _headers(body, "delivery-1"))
    # Duplicate is acknowledged (2xx) and must not re-run the provider.
    assert 200 <= second.status_code < 300
    assert client.calls == calls_after_first, "duplicate must not refetch"

    # Still exactly one stored event + one evidence record.
    envelope = store.get_envelope("delivery-1")
    assert envelope is not None
    assert store.get_evidence(envelope.normalized_pr_key) is not None
