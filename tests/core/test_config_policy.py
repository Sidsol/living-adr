"""Slice 3: publication policy + external-LLM egress policy parsing.

Governs GitHub publish-back targets and explicit Claude egress allow/deny.
These are security-sensitive decisions and must never be silently inferred.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from living_adr.core.config import (
    LivingADRConfig,
    PublicationPolicy,
    RepositoryConfig,
)
from living_adr.core.repository import RepositoryIdentity


def _identity(**overrides: str) -> RepositoryIdentity:
    fields = {
        "host": "github.com",
        "owner": "example-org",
        "repo": "example-repo",
        "repo_id": "100200300",
    }
    fields.update(overrides)
    return RepositoryIdentity(**fields)


def _repo_config(**overrides: object) -> RepositoryConfig:
    fields: dict[str, object] = {
        "identity": _identity(),
        "github_app_installation_id": "12345678",
        "default_branch": "main",
        "adr_publication_policy": PublicationPolicy.LIVINGADR_ONLY,
        "external_llm_allowed": False,
    }
    fields.update(overrides)
    return RepositoryConfig(**fields)


# --- Behavior A: publication policy enum parsing ------------------------------


@pytest.mark.parametrize(
    "raw",
    ["livingadr_only", "publish_to_github", "publish_to_github_and_livingadr"],
)
def test_all_three_publication_policies_parse(raw: str) -> None:
    cfg = _repo_config(
        adr_publication_policy=raw,
        adr_target_branch="main",
        adr_path_template="docs/adr/{number}-{slug}.md",
    )
    assert cfg.adr_publication_policy == PublicationPolicy(raw)


def test_unknown_publication_policy_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _repo_config(adr_publication_policy="email_it_to_me")


def test_publishes_to_github_helper() -> None:
    assert PublicationPolicy.LIVINGADR_ONLY.publishes_to_github is False
    assert PublicationPolicy.PUBLISH_TO_GITHUB.publishes_to_github is True
    assert PublicationPolicy.PUBLISH_TO_GITHUB_AND_LIVINGADR.publishes_to_github is True


# --- Behavior B: publish target branch / path requirements --------------------


def test_publish_to_github_requires_target_branch_and_path() -> None:
    with pytest.raises(ValidationError) as exc:
        _repo_config(adr_publication_policy=PublicationPolicy.PUBLISH_TO_GITHUB)
    message = str(exc.value).lower()
    assert "adr_target_branch" in message or "adr_path_template" in message


def test_publish_to_github_with_valid_target_validates() -> None:
    cfg = _repo_config(
        adr_publication_policy=PublicationPolicy.PUBLISH_TO_GITHUB,
        adr_target_branch="main",
        adr_path_template="docs/adr/{number}-{slug}.md",
    )
    assert cfg.adr_target_branch == "main"
    assert cfg.adr_path_template == "docs/adr/{number}-{slug}.md"


@pytest.mark.parametrize(
    "bad_path",
    ["/abs/docs/adr", "../escape/adr.md", "C:\\\\windows\\adr", "docs\\adr\\x.md"],
)
def test_publish_path_template_must_be_relative_and_safe(bad_path: str) -> None:
    with pytest.raises(ValidationError):
        _repo_config(
            adr_publication_policy=PublicationPolicy.PUBLISH_TO_GITHUB,
            adr_target_branch="main",
            adr_path_template=bad_path,
        )


def test_livingadr_only_does_not_require_publish_target() -> None:
    cfg = _repo_config(adr_publication_policy=PublicationPolicy.LIVINGADR_ONLY)
    assert cfg.adr_target_branch is None
    assert cfg.adr_path_template is None


# --- Behavior C: explicit external-LLM allow/deny -----------------------------


def test_external_llm_allow_is_explicit_true() -> None:
    cfg = _repo_config(external_llm_allowed=True)
    assert cfg.external_llm_allowed is True


def test_external_llm_deny_is_explicit_false() -> None:
    cfg = _repo_config(external_llm_allowed=False)
    assert cfg.external_llm_allowed is False


def test_allows_external_llm_lookup_by_identity_and_key() -> None:
    allowed = _repo_config(external_llm_allowed=True)
    denied = _repo_config(
        identity=_identity(repo="denied-repo", repo_id="222"),
        external_llm_allowed=False,
    )
    config = LivingADRConfig(repositories=[allowed, denied])

    assert config.allows_external_llm("github.com/example-org/example-repo") is True
    assert config.allows_external_llm(denied.identity) is False


def test_allows_external_llm_unknown_repository_denies_by_default() -> None:
    config = LivingADRConfig(repositories=[_repo_config(external_llm_allowed=True)])
    assert config.allows_external_llm("github.com/unknown/unknown") is False
