"""Tests: PullRequestPublisher opens a PR for an approved ADR (fake provider).

No network: a fake GitHub provider records branch/file/PR calls. Verifies the
rendered ADR path (number + slug), the per-decision branch, the embedded
decision marker, and policy gating (livingadr_only opens no PR).
"""

from __future__ import annotations

from types import SimpleNamespace

from living_adr.core.config import (
    LivingADRConfig,
    PublicationPolicy,
    RepositoryConfig,
)
from living_adr.core.models import RepositoryIdentity
from living_adr.core.scm import CommitResult
from living_adr.publication.pr_publisher import PullRequestPublisher
from living_adr.scm.github_provider import PullRequestHandle
from living_adr.workflow.state import DraftRef

REPO = RepositoryIdentity(
    host="github.com", owner="Sidsol", repo="living-adr", repo_id="1"
)
_MARKDOWN = "# Adopt httpx\n\n## Context\nA dependency was added.\n"


def _config(
    policy: PublicationPolicy = PublicationPolicy.PUBLISH_TO_GITHUB_AND_LIVINGADR,
) -> LivingADRConfig:
    return LivingADRConfig(
        repositories=[
            RepositoryConfig(
                identity=REPO,
                github_app_installation_id="1",
                default_branch="master",
                adr_publication_policy=policy,
                external_llm_allowed=True,
                adr_target_branch="master",
                adr_path_template="docs/adr/{number}-{slug}.md",
            )
        ]
    )


def _draft() -> DraftRef:
    return DraftRef(
        draft_id="draft-1",
        content_hash="h",
        preview=_MARKDOWN,
        citation_ids=("ev-1",),
        structural_change_id="chg-1",
    )


def _values() -> dict:
    return {
        "repository": REPO,
        "draft": _draft(),
        "approved_decision": SimpleNamespace(decision_id="dec-abc123def456"),
    }


class _FakeProvider:
    def __init__(self) -> None:
        self.branches: list[tuple[str, str]] = []
        self.files: list[tuple[str, str, str]] = []
        self.prs: list[dict] = []

    def list_directory(self, repository, branch, directory):
        return ()

    def get_branch_head_sha(self, repository, branch):
        return "basesha"

    def create_branch(self, repository, new_branch, base_sha):
        self.branches.append((new_branch, base_sha))
        return True

    def create_file(self, repository, branch, path, content, message, *, sha=None):
        self.files.append((branch, path, content))
        return CommitResult(commit_sha="c1", path=path, content_sha="s1", created=True)

    def open_pull_request(self, repository, *, title, head, base, body=""):
        self.prs.append({"title": title, "head": head, "base": base})
        return PullRequestHandle(
            number=42,
            html_url="https://github.com/Sidsol/living-adr/pull/42",
            head_ref=head,
            base_ref=base,
        )


def test_publish_completed_opens_pr_with_rendered_path() -> None:
    provider = _FakeProvider()
    pr = PullRequestPublisher(provider, _config()).publish_completed(_values())

    assert pr is not None
    assert pr.number == 42
    assert len(provider.branches) == 1
    branch, base_sha = provider.branches[0]
    assert branch == "livingadr/adr-dec-abc123de"
    assert base_sha == "basesha"

    _, path, content = provider.files[0]
    assert path == "docs/adr/0001-adopt-httpx.md"
    assert "dec-abc123def456" in content  # decision marker embedded for recovery

    assert provider.prs[0]["head"] == branch
    assert provider.prs[0]["base"] == "master"


def test_publish_skips_when_policy_is_livingadr_only() -> None:
    provider = _FakeProvider()
    result = PullRequestPublisher(
        provider, _config(policy=PublicationPolicy.LIVINGADR_ONLY)
    ).publish_completed(_values())

    assert result is None
    assert provider.prs == []


def test_publish_returns_none_without_approved_decision() -> None:
    provider = _FakeProvider()
    values = {"repository": REPO, "draft": _draft(), "approved_decision": None}

    assert PullRequestPublisher(provider, _config()).publish_completed(values) is None
    assert provider.branches == []
