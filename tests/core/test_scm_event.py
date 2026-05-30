"""Slice 3 RED tests: provider-neutral SCM contracts in core.

Pins the cross-feature seam: the canonical ``SCMEvent`` (feature 001) is what
ingestion emits; the richer normalized PR key, provider-neutral fetch handles,
and the ``SCMProvider`` port live alongside it so downstream classifiers and a
future Azure DevOps adapter never traverse raw GitHub payloads.
"""

from __future__ import annotations

from datetime import UTC, datetime

from living_adr.core.models import SCMEvent
from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import (
    CandidateEvidence,
    ChangedFileMetadata,
    DiffEvidence,
    PullRequestMetadata,
    SCMEventEnvelope,
    SCMFetchHandle,
    SCMProvider,
    SCMProviderName,
    build_normalized_pr_key,
)

REPO = RepositoryIdentity(
    host="github.com", owner="acme", repo="widgets", repo_id="100"
)


def _handle() -> SCMFetchHandle:
    return SCMFetchHandle(
        installation_id="inst-555",
        pr_number=42,
        head_sha="headsha",
        head_ref="feature/x",
        base_ref="main",
        merge_commit_sha="mergesha",
    )


def _event() -> SCMEvent:
    return SCMEvent(
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


def test_normalized_pr_key_is_repository_scoped_and_stable() -> None:
    key = build_normalized_pr_key(
        SCMProviderName.GITHUB, REPO, 42, "mergesha"
    )
    assert key == "github:github.com/acme/widgets:42:mergesha"
    # Same inputs -> same key (deterministic); different repo -> different key.
    other = RepositoryIdentity(
        host="github.com", owner="acme", repo="other", repo_id="101"
    )
    assert build_normalized_pr_key(
        SCMProviderName.GITHUB, other, 42, "mergesha"
    ) != key


def test_normalized_pr_key_handles_missing_merge_sha() -> None:
    key = build_normalized_pr_key(SCMProviderName.GITHUB, REPO, 42, None)
    assert key.endswith(":42:unknown")


def test_envelope_wraps_canonical_event_with_neutral_fields() -> None:
    envelope = SCMEventEnvelope(
        event=_event(),
        provider=SCMProviderName.GITHUB,
        provider_event_type="pull_request.closed",
        normalized_pr_key=build_normalized_pr_key(
            SCMProviderName.GITHUB, REPO, 42, "mergesha"
        ),
        fetch_handle=_handle(),
        sender="octocat",
        provider_metadata={"github_node_id": "PR_xyz"},
    )
    # The canonical SCMEvent contract is preserved exactly (feature 001 seam).
    assert isinstance(envelope.event, SCMEvent)
    assert envelope.event.repository == REPO
    assert envelope.event.delivery_id == "d-1"
    assert envelope.fetch_handle.pr_number == 42
    assert envelope.fetch_handle.merge_commit_sha == "mergesha"
    # Provider-specific data is opaque metadata, not a workflow-facing field.
    assert envelope.provider_metadata["github_node_id"] == "PR_xyz"


def test_envelope_is_immutable() -> None:
    envelope = SCMEventEnvelope(
        event=_event(),
        provider=SCMProviderName.GITHUB,
        provider_event_type="pull_request.closed",
        normalized_pr_key="github:github.com/acme/widgets:42:mergesha",
        fetch_handle=_handle(),
    )
    import pytest

    with pytest.raises((TypeError, ValueError, AttributeError)):
        envelope.normalized_pr_key = "tampered"  # type: ignore[misc]


def test_candidate_evidence_links_event_and_is_immutable() -> None:
    evidence = CandidateEvidence(
        repository=REPO,
        source_delivery_id="d-1",
        normalized_pr_key="github:github.com/acme/widgets:42:mergesha",
        pr_number=42,
        pr_title="Add httpx client",
        changed_files=(
            ChangedFileMetadata(
                filename="pyproject.toml",
                status="modified",
                additions=2,
                deletions=0,
            ),
        ),
        diff=DiffEvidence(
            diff_handle="github:pulls/42/files",
            summary="1 file changed",
            truncated=False,
        ),
        provider=SCMProviderName.GITHUB,
    )
    assert evidence.source_delivery_id == "d-1"
    assert evidence.changed_files[0].filename == "pyproject.toml"
    assert evidence.is_complete is True
    import pytest

    with pytest.raises((TypeError, ValueError, AttributeError)):
        evidence.pr_number = 99  # type: ignore[misc]


def test_scm_provider_protocol_is_runtime_checkable() -> None:
    class FakeProvider:
        def fetch_pull_request(self, repository, handle):
            return PullRequestMetadata(
                number=handle.pr_number,
                title="t",
                body="",
                author="octocat",
                state="closed",
                merged=True,
                head_ref="f",
                base_ref="main",
                merge_commit_sha="m",
            )

        def fetch_changed_files(self, repository, handle):
            return ()

        def fetch_diff(self, repository, handle):
            return DiffEvidence(diff_handle="h", summary="s")

    assert isinstance(FakeProvider(), SCMProvider)


def test_azure_devops_maps_into_same_envelope_shape() -> None:
    # Documents the preserved seam: a future Azure DevOps adapter produces the
    # same workflow-facing envelope; only provider/metadata differ.
    azure_repo = RepositoryIdentity(
        host="dev.azure.com", owner="acme", repo="widgets", repo_id="ado-1"
    )
    event = _event().model_copy(
        update={
            "repository": azure_repo,
            "provider": SCMProviderName.AZURE_DEVOPS.value,
        }
    )
    envelope = SCMEventEnvelope(
        event=event,
        provider=SCMProviderName.AZURE_DEVOPS,
        provider_event_type="git.pullrequest.merged",
        normalized_pr_key=build_normalized_pr_key(
            SCMProviderName.AZURE_DEVOPS, azure_repo, 42, "mergesha"
        ),
        fetch_handle=SCMFetchHandle(
            installation_id="n/a", pr_number=42, merge_commit_sha="mergesha"
        ),
        provider_metadata={"ado_project": "Widgets"},
    )
    assert envelope.provider is SCMProviderName.AZURE_DEVOPS
    assert envelope.normalized_pr_key.startswith("azure_devops:")
    assert envelope.event.pr_number == 42
