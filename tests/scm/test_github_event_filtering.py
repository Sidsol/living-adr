"""Slice 2 RED tests: GitHub event filtering + repository resolution.

Only ``pull_request`` events with ``action=closed`` and ``merged=true`` for a
*configured* repository are accepted. Everything else is skipped or rejected with
a structured error category. Repository matching uses ``RepositoryIdentity`` /
canonical key, never hardcoded PoC repo values.
"""

from __future__ import annotations

import json

from living_adr.core.config import (
    LivingADRConfig,
    PublicationPolicy,
    RepositoryConfig,
)
from living_adr.core.ingestion import IngestionErrorCategory
from living_adr.core.repository import RepositoryIdentity
from living_adr.scm.github_webhook import FilterDecision, parse_and_filter


def _config(repo: str = "widgets", owner: str = "acme") -> LivingADRConfig:
    return LivingADRConfig(
        repositories=[
            RepositoryConfig(
                identity=RepositoryIdentity(
                    host="github.com", owner=owner, repo=repo, repo_id="100"
                ),
                github_app_installation_id="inst-555",
                default_branch="main",
                adr_publication_policy=PublicationPolicy.LIVINGADR_ONLY,
                external_llm_allowed=False,
            )
        ]
    )


def _merged_pr_payload(
    owner: str = "acme",
    repo: str = "widgets",
    action: str = "closed",
    merged: bool = True,
) -> bytes:
    payload = {
        "action": action,
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
            "body": "Introduces an outbound API client.",
            "merged": merged,
            "merged_at": "2024-06-01T10:00:00Z",
            "merge_commit_sha": "abc123def456",
            "head": {"ref": "feature/httpx", "sha": "headsha789"},
            "base": {"ref": "main"},
        },
        "sender": {"login": "octocat"},
        "installation": {"id": 555},
    }
    return json.dumps(payload).encode("utf-8")


def test_configured_merged_pr_is_accepted() -> None:
    result = parse_and_filter(_merged_pr_payload(), "pull_request", _config())
    assert result.decision is FilterDecision.ACCEPT
    assert result.error_category is IngestionErrorCategory.NONE
    assert result.repository is not None
    assert result.repository.key == "github.com/acme/widgets"
    assert result.payload is not None
    assert result.payload.pr_number == 42
    assert result.payload.merge_commit_sha == "abc123def456"
    assert result.repo_config is not None
    assert result.repo_config.github_app_installation_id == "inst-555"


def test_unconfigured_repository_is_rejected() -> None:
    payload = _merged_pr_payload(owner="evil", repo="spoof")
    result = parse_and_filter(payload, "pull_request", _config())
    assert result.decision is FilterDecision.REJECT
    assert result.error_category is IngestionErrorCategory.UNCONFIGURED_REPOSITORY
    assert result.payload is None


def test_non_pull_request_event_is_skipped() -> None:
    result = parse_and_filter(_merged_pr_payload(), "push", _config())
    assert result.decision is FilterDecision.SKIP
    assert result.error_category is IngestionErrorCategory.NOT_PULL_REQUEST


def test_closed_but_unmerged_pr_is_skipped() -> None:
    payload = _merged_pr_payload(merged=False)
    result = parse_and_filter(payload, "pull_request", _config())
    assert result.decision is FilterDecision.SKIP
    assert result.error_category is IngestionErrorCategory.NOT_MERGED


def test_opened_pr_is_skipped() -> None:
    payload = _merged_pr_payload(action="opened", merged=False)
    result = parse_and_filter(payload, "pull_request", _config())
    assert result.decision is FilterDecision.SKIP
    assert result.error_category is IngestionErrorCategory.NOT_MERGED


def test_malformed_payload_is_rejected() -> None:
    result = parse_and_filter(b"{not json", "pull_request", _config())
    assert result.decision is FilterDecision.REJECT
    assert result.error_category is IngestionErrorCategory.MALFORMED_PAYLOAD


def test_missing_pull_request_object_is_rejected() -> None:
    payload = json.dumps({"action": "closed"}).encode()
    result = parse_and_filter(payload, "pull_request", _config())
    assert result.decision is FilterDecision.REJECT
    assert result.error_category is IngestionErrorCategory.MALFORMED_PAYLOAD
