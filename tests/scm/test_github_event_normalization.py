"""Slice 3 RED tests: GitHub accepted payload -> canonical SCMEvent envelope.

The normalizer maps an accepted, filtered GitHub merged-PR into the provider-
neutral :class:`SCMEventEnvelope` (wrapping the canonical ``SCMEvent``). GitHub
taxonomy stays in the adapter; the workflow-facing event carries no GitHub-only
required fields.
"""

from __future__ import annotations

import json
from datetime import datetime

from living_adr.core.config import (
    LivingADRConfig,
    PublicationPolicy,
    RepositoryConfig,
)
from living_adr.core.models import SCMEvent
from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import SCMEventEnvelope, SCMProviderName
from living_adr.scm.github_webhook import normalize_to_scm_event, parse_and_filter


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
                "node_id": "R_repo",
            },
            "pull_request": {
                "number": 42,
                "title": "Add httpx client",
                "body": "Introduces outbound API client.",
                "merged": True,
                "merged_at": "2024-06-01T10:00:00Z",
                "merge_commit_sha": "abc123def",
                "head": {"ref": "feature/httpx", "sha": "headsha"},
                "base": {"ref": "main"},
                "node_id": "PR_xyz",
            },
            "sender": {"login": "octocat"},
            "installation": {"id": 555},
        }
    ).encode()


def _normalize() -> SCMEventEnvelope:
    result = parse_and_filter(_payload(), "pull_request", _config())
    assert result.payload is not None and result.repository is not None
    return normalize_to_scm_event("delivery-9", result.repository, result.payload)


def test_normalizes_into_canonical_scm_event() -> None:
    envelope = _normalize()
    assert isinstance(envelope.event, SCMEvent)
    event = envelope.event
    assert event.repository.key == "github.com/acme/widgets"
    assert event.delivery_id == "delivery-9"
    assert event.provider == SCMProviderName.GITHUB.value
    assert event.event_type == "merged_pr"
    assert event.pr_number == 42
    assert event.pr_title == "Add httpx client"
    assert event.merged_at == datetime.fromisoformat("2024-06-01T10:00:00+00:00")


def test_envelope_carries_normalized_key_and_fetch_handle() -> None:
    envelope = _normalize()
    assert envelope.provider is SCMProviderName.GITHUB
    assert envelope.normalized_pr_key == (
        "github:github.com/acme/widgets:42:abc123def"
    )
    handle = envelope.fetch_handle
    assert handle.installation_id == "inst-555"
    assert handle.pr_number == 42
    assert handle.merge_commit_sha == "abc123def"
    assert handle.base_ref == "main"
    assert envelope.sender == "octocat"


def test_changed_files_and_diff_are_not_on_the_event() -> None:
    # Changed files / diff are evidence (fetched in slice 4), not event fields.
    envelope = _normalize()
    assert envelope.event.changed_files == ()
    assert envelope.event.diff_summary == ""


def test_event_has_no_github_only_required_fields() -> None:
    # The workflow-facing event model field names are provider-neutral.
    envelope = _normalize()
    field_names = set(type(envelope.event).model_fields)
    for github_only in ("node_id", "html_url", "installation", "head", "base"):
        assert github_only not in field_names
