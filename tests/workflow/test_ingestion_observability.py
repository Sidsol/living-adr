"""Slice 6 RED tests: metadata-only observability hygiene.

Drives the full ingestion + replay path through a recording Observability and
asserts every emitted event/counter/span carries only small non-sensitive
metadata (identifiers, counts, status enums, booleans) and never raw webhook
bodies, raw diffs, or secrets (architecture #cross-cutting, NFR-6, FM-21).
"""

from __future__ import annotations

import hashlib
import hmac
import json
from contextlib import contextmanager

from living_adr.apps.workflow_service.webhooks import GitHubWebhookHandler
from living_adr.core.config import (
    LivingADRConfig,
    PublicationPolicy,
    RepositoryConfig,
)
from living_adr.core.observability import ObservationSpan
from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import (
    ChangedFileMetadata,
    DiffEvidence,
    PullRequestMetadata,
)
from living_adr.persistence.ingestion_store import InMemoryIngestionStore
from living_adr.scm.github_webhook import (
    DELIVERY_HEADER,
    EVENT_HEADER,
    SIGNATURE_HEADER,
)
from living_adr.workflow.ingestion import IngestionPipeline
from living_adr.workflow.replay import ReplayService

SECRET = "obs-secret-value"
_ALLOWED_TYPES = (str, int, bool, type(None))


class RecordingObservability:
    """Captures every observation so hygiene can be asserted."""

    def __init__(self) -> None:
        self.events: list[tuple[str, dict]] = []

    def record_event(self, name, metadata=None) -> None:
        self.events.append((name, dict(metadata or {})))

    def increment_counter(self, name, value=1, metadata=None) -> None:
        self.events.append((name, dict(metadata or {})))

    @contextmanager
    def start_span(self, name, metadata=None):
        self.events.append((name, dict(metadata or {})))
        yield ObservationSpan(name, metadata)


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


def _headers(body, delivery_id):
    digest = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest()
    return {
        SIGNATURE_HEADER: f"sha256={digest}",
        DELIVERY_HEADER: delivery_id,
        EVENT_HEADER: "pull_request",
    }


class StaticProvider:
    def fetch_pull_request(self, repository, handle):
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

    def fetch_diff(self, repository, handle):
        return DiffEvidence(
            diff_handle="github:/repos/acme/widgets/pulls/42.diff",
            summary="1 file changed",
            byte_size=42,
        )


def _drive(obs: RecordingObservability) -> None:
    store = InMemoryIngestionStore()
    provider = StaticProvider()
    pipeline = IngestionPipeline(
        config=_config(), store=store, provider=provider, observability=obs
    )
    handler = GitHubWebhookHandler(
        secret=SECRET, pipeline=pipeline, observability=obs
    )
    body = _payload()
    handler.handle(body, _headers(body, "d-1"))  # accepted
    handler.handle(body, _headers(body, "d-1"))  # duplicate
    handler.handle(b"tampered", _headers(body, "d-2"))  # rejected (bad signature)
    ReplayService(
        store=store, provider=provider, observability=obs
    ).replay_delivery("d-1")


def test_lifecycle_is_observed() -> None:
    obs = RecordingObservability()
    _drive(obs)
    names = {name for name, _ in obs.events}
    assert "webhook.verified" in names
    assert "ingestion.accepted" in names
    assert "ingestion.duplicate" in names
    assert "webhook.rejected" in names
    assert any(n.startswith("ingestion.replay") for n in names)


def test_metadata_values_are_small_and_non_sensitive() -> None:
    obs = RecordingObservability()
    _drive(obs)
    for name, metadata in obs.events:
        for key, value in metadata.items():
            assert isinstance(value, _ALLOWED_TYPES), (
                f"{name}.{key} carries non-scalar metadata {type(value)!r}"
            )


def test_no_raw_body_diff_or_secret_leaks() -> None:
    obs = RecordingObservability()
    _drive(obs)
    blob = json.dumps(
        [(name, {k: str(v) for k, v in md.items()}) for name, md in obs.events]
    )
    assert SECRET not in blob
    assert "diff --git" not in blob
    assert "tampered" not in blob
    # No raw-payload field content (e.g. the PR title) leaks into metadata;
    # only small identifiers/counts/status enums are emitted.
    assert "Add httpx client" not in blob
    assert "octocat" not in blob
