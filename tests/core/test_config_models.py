"""Slice 1: core repository config model validation.

Covers RepositoryIdentity (reused from feature 001's ``core.models`` and
re-exported via ``core.repository``) plus RepositoryConfig / LivingADRConfig
list validation, duplicate-identity rejection, N>=1 semantics, and the
no-secrets rule.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from living_adr.core.config import (
    LivingADRConfig,
    PublicationPolicy,
    RepositoryConfig,
)
from living_adr.core.models import RepositoryIdentity as ModelsRepositoryIdentity
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


# --- Behavior A: RepositoryIdentity value object -------------------------------


def test_repository_identity_reexport_is_the_canonical_model() -> None:
    # We reuse feature 001's identity rather than duplicating it.
    assert RepositoryIdentity is ModelsRepositoryIdentity


def test_repository_identity_canonical_key_is_host_owner_repo() -> None:
    identity = _identity()
    assert identity.key == "github.com/example-org/example-repo"
    # repo_id is retained separately from the canonical key.
    assert identity.repo_id == "100200300"


def test_repository_identity_missing_field_fails_with_field_detail() -> None:
    with pytest.raises(ValidationError) as exc:
        RepositoryIdentity(host="github.com", owner="o", repo="r")  # type: ignore[call-arg]
    assert "repo_id" in str(exc.value)


@pytest.mark.parametrize("field", ["host", "owner", "repo", "repo_id"])
def test_repository_identity_rejects_empty_or_whitespace(field: str) -> None:
    with pytest.raises(ValidationError) as exc:
        _identity(**{field: "   "})
    assert field in str(exc.value)


# --- Behavior B: RepositoryConfig + LivingADRConfig collection -----------------


def test_single_entry_repository_list_validates() -> None:
    config = LivingADRConfig(repositories=[_repo_config()])
    assert len(config.repositories) == 1


def test_empty_repository_list_is_rejected() -> None:
    with pytest.raises(ValidationError):
        LivingADRConfig(repositories=[])


def test_duplicate_canonical_identities_fail_validation() -> None:
    with pytest.raises(ValidationError) as exc:
        LivingADRConfig(repositories=[_repo_config(), _repo_config()])
    assert "duplicate" in str(exc.value).lower()


def test_distinct_identities_validate_through_list_path() -> None:
    other = _repo_config(identity=_identity(repo="second-repo", repo_id="999"))
    config = LivingADRConfig(repositories=[_repo_config(), other])
    assert len(config.repositories) == 2


def test_repository_config_exposes_canonical_key() -> None:
    assert _repo_config().canonical_key == "github.com/example-org/example-repo"


def test_lookup_by_canonical_key_returns_entry() -> None:
    config = LivingADRConfig(repositories=[_repo_config()])
    found = config.get("github.com/example-org/example-repo")
    assert found is not None
    assert found.identity.repo == "example-repo"
    assert config.get("github.com/none/none") is None


def test_external_llm_allowed_is_required_and_explicit() -> None:
    with pytest.raises(ValidationError) as exc:
        RepositoryConfig(
            identity=_identity(),
            github_app_installation_id="123",
            default_branch="main",
            adr_publication_policy=PublicationPolicy.LIVINGADR_ONLY,
        )  # type: ignore[call-arg]
    assert "external_llm_allowed" in str(exc.value)


@pytest.mark.parametrize("secret_field", ["token", "private_key", "api_key", "secret"])
def test_no_model_field_accepts_secret_values(secret_field: str) -> None:
    with pytest.raises(ValidationError):
        RepositoryConfig(
            identity=_identity(),
            github_app_installation_id="123",
            default_branch="main",
            adr_publication_policy=PublicationPolicy.LIVINGADR_ONLY,
            external_llm_allowed=False,
            **{secret_field: "leaked"},
        )  # type: ignore[arg-type]


def test_github_app_installation_id_must_be_non_empty() -> None:
    with pytest.raises(ValidationError):
        _repo_config(github_app_installation_id="   ")
