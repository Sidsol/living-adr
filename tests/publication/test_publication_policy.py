"""Slice S011-01 RED tests: publication policy, target resolution, fingerprint.

These tests pin the pure, provider-free behaviour of the publication target
models and resolution: enabled vs disabled policies, the default
``docs/adr/NNNN-<slug>.md`` template, branch fallback, repository-mismatch
rejection, and deterministic fingerprint stability/sensitivity.
"""

from __future__ import annotations

import pytest
from tests.publication._helpers import (
    build_adr,
    build_config,
    build_decision,
    build_repo,
)

from living_adr.core.config import PublicationPolicy
from living_adr.publication.models import (
    DEFAULT_ADR_PATH_TEMPLATE,
    ADRPublicationRequest,
    ADRPublicationTarget,
    PublicationRepositoryMismatchError,
    publication_fingerprint,
)
from living_adr.publication.service import resolve_publication_target

# --- target resolution ----------------------------------------------------


def test_default_template_and_directory_and_padding() -> None:
    target = resolve_publication_target(build_config())
    assert target.path_template == DEFAULT_ADR_PATH_TEMPLATE
    assert target.directory == "docs/adr"
    assert target.padding_width == 4
    assert target.publishes_to_github is True


def test_target_branch_overrides_default_branch() -> None:
    config = build_config(default_branch="main", adr_target_branch="adr-docs")
    target = resolve_publication_target(config)
    assert target.branch == "adr-docs"


def test_target_branch_falls_back_to_default_branch_for_livingadr_only() -> None:
    config = build_config(
        policy=PublicationPolicy.LIVINGADR_ONLY, default_branch="trunk"
    )
    target = resolve_publication_target(config)
    assert target.branch == "trunk"
    assert target.publishes_to_github is False


def test_custom_template_directory_and_padding_are_derived() -> None:
    config = build_config(
        adr_path_template="architecture/decisions/NNN-<slug>.markdown"
    )
    target = resolve_publication_target(config)
    assert target.directory == "architecture/decisions"
    assert target.padding_width == 3
    assert target.path_template == "architecture/decisions/NNN-<slug>.markdown"


# --- request validation ---------------------------------------------------


def test_request_rejects_repository_mismatch_between_adr_and_scope() -> None:
    repo = build_repo()
    other = build_repo("other-repo")
    adr = build_adr(other)
    target = resolve_publication_target(build_config(repo))
    with pytest.raises(PublicationRepositoryMismatchError):
        ADRPublicationRequest(
            repository=repo,
            adr=adr,
            decision=build_decision(other, adr),
            policy=PublicationPolicy.PUBLISH_TO_GITHUB,
            target=target,
        )


def test_request_accepts_consistent_repository_scope() -> None:
    repo = build_repo()
    adr = build_adr(repo)
    request = ADRPublicationRequest(
        repository=repo,
        adr=adr,
        decision=build_decision(repo, adr),
        policy=PublicationPolicy.PUBLISH_TO_GITHUB,
        target=resolve_publication_target(build_config(repo)),
    )
    assert request.repository == repo
    assert request.adr.adr_id == "adr-1"


# --- fingerprint ----------------------------------------------------------


def test_fingerprint_is_deterministic() -> None:
    repo = build_repo()
    adr = build_adr(repo)
    target = resolve_publication_target(build_config(repo))
    fp1 = publication_fingerprint(
        repo, adr, target, PublicationPolicy.PUBLISH_TO_GITHUB, "decision-1"
    )
    fp2 = publication_fingerprint(
        repo, adr, target, PublicationPolicy.PUBLISH_TO_GITHUB, "decision-1"
    )
    assert fp1 == fp2
    assert len(fp1) == 64  # sha256 hex


@pytest.mark.parametrize("mutate", ["content", "policy", "branch", "decision"])
def test_fingerprint_changes_with_each_input(mutate: str) -> None:
    repo = build_repo()
    adr = build_adr(repo)
    target = resolve_publication_target(build_config(repo))
    base = publication_fingerprint(
        repo, adr, target, PublicationPolicy.PUBLISH_TO_GITHUB, "decision-1"
    )

    if mutate == "content":
        other = publication_fingerprint(
            repo,
            build_adr(repo, content_hash="deadbeef"),
            target,
            PublicationPolicy.PUBLISH_TO_GITHUB,
            "decision-1",
        )
    elif mutate == "policy":
        other = publication_fingerprint(
            repo,
            adr,
            target,
            PublicationPolicy.PUBLISH_TO_GITHUB_AND_LIVINGADR,
            "decision-1",
        )
    elif mutate == "branch":
        other_target = ADRPublicationTarget(
            repository_key=target.repository_key,
            branch="different-branch",
            path_template=target.path_template,
            directory=target.directory,
            padding_width=target.padding_width,
            publishes_to_github=target.publishes_to_github,
        )
        other = publication_fingerprint(
            repo, adr, other_target, PublicationPolicy.PUBLISH_TO_GITHUB, "decision-1"
        )
    else:  # decision
        other = publication_fingerprint(
            repo, adr, target, PublicationPolicy.PUBLISH_TO_GITHUB, "decision-2"
        )

    assert other != base
