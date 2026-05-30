"""Slice 3 RED tests: onboarding GitHub installation + permission diagnostics.

Covers TASK-011..015: permission mapping by publication policy, conversion of
installation verification results into onboarding diagnostics, and integration
into OnboardingValidator using a fake verifier (no network).
"""

from __future__ import annotations

import pytest

from living_adr.core.config import (
    LivingADRConfig,
    PublicationPolicy,
    RepositoryConfig,
)
from living_adr.core.repository import RepositoryIdentity
from living_adr.core.scm import (
    InstallationStatus,
    InstallationVerification,
    SCMProviderError,
)
from living_adr.onboarding.diagnostics import (
    DiagnosticCategory,
    DiagnosticSeverity,
)
from living_adr.onboarding.github_checks import (
    installation_diagnostics,
    permission_satisfied,
    required_permissions,
)
from living_adr.onboarding.required_env import required_env_names
from living_adr.onboarding.validation import OnboardingValidator

IDENTITY = RepositoryIdentity(
    host="github.com", owner="acme", repo="widgets", repo_id="100"
)


def _repo(policy=PublicationPolicy.LIVINGADR_ONLY, **extra) -> RepositoryConfig:
    kwargs = dict(
        identity=IDENTITY,
        github_app_installation_id="inst-555",
        default_branch="main",
        adr_publication_policy=policy,
        external_llm_allowed=False,
    )
    kwargs.update(extra)
    return RepositoryConfig(**kwargs)


_PUBLISH_REPO = _repo(
    policy=PublicationPolicy.PUBLISH_TO_GITHUB,
    adr_target_branch="main",
    adr_path_template="docs/adr",
)


def _verification(status, permissions, **extra) -> InstallationVerification:
    base = dict(
        repository_key=IDENTITY.key,
        expected_installation_id="inst-555",
        installation_id="inst-555",
        permissions=permissions,
        status=status,
    )
    base.update(extra)
    return InstallationVerification(**base)


def _full_env() -> dict[str, str]:
    return {name: f"placeholder-{name.lower()}" for name in required_env_names()}


# --- TASK-013: permission mapping -------------------------------------------


def test_required_permissions_livingadr_only_is_read_only() -> None:
    assert required_permissions(PublicationPolicy.LIVINGADR_ONLY) == (
        "contents:read",
    )


@pytest.mark.parametrize(
    "policy",
    [
        PublicationPolicy.PUBLISH_TO_GITHUB,
        PublicationPolicy.PUBLISH_TO_GITHUB_AND_LIVINGADR,
    ],
)
def test_publish_policies_require_contents_write(policy) -> None:
    perms = required_permissions(policy)
    assert "contents:read" in perms
    assert "contents:write" in perms


def test_permission_satisfied_semantics() -> None:
    assert permission_satisfied({"contents": "read"}, "contents:read") is True
    assert permission_satisfied({"contents": "read"}, "contents:write") is False
    assert permission_satisfied({"contents": "write"}, "contents:read") is True
    assert permission_satisfied({"contents": "write"}, "contents:write") is True
    assert permission_satisfied({}, "contents:read") is False


# --- TASK-012/014: installation_diagnostics ---------------------------------


def test_installed_read_only_policy_produces_no_blocking() -> None:
    diags = installation_diagnostics(
        _repo(),
        _verification(
            InstallationStatus.INSTALLED,
            {"contents": "read"},
            repo_id="100",
            default_branch="main",
        ),
    )
    assert not any(d.severity is DiagnosticSeverity.BLOCKING for d in diags)
    assert any(d.category is DiagnosticCategory.GITHUB_APP for d in diags)


def test_publish_policy_missing_write_is_blocking_permission() -> None:
    diags = installation_diagnostics(
        _PUBLISH_REPO,
        _verification(
            InstallationStatus.INSTALLED,
            {"contents": "read"},
            repo_id="100",
            default_branch="main",
        ),
    )
    blocking = [d for d in diags if d.severity is DiagnosticSeverity.BLOCKING]
    assert blocking
    assert all(d.category is DiagnosticCategory.PERMISSIONS for d in blocking)
    assert any("contents:write" in d.message for d in blocking)


@pytest.mark.parametrize(
    "status",
    [
        InstallationStatus.NOT_INSTALLED,
        InstallationStatus.SUSPENDED,
        InstallationStatus.MISMATCHED,
        InstallationStatus.ACCESS_DENIED,
        InstallationStatus.RATE_LIMITED,
    ],
)
def test_bad_installation_states_block_with_repo_scoped_remediation(status) -> None:
    diags = installation_diagnostics(
        _repo(), _verification(status, {}, installation_id=None)
    )
    blocking = [
        d
        for d in diags
        if d.severity is DiagnosticSeverity.BLOCKING
        and d.category is DiagnosticCategory.GITHUB_APP
    ]
    assert blocking
    joined = " ".join((d.message + (d.remediation or "")) for d in blocking)
    # Repository key and installation id named; private key material never.
    assert "github.com/acme/widgets" in joined
    assert "inst-555" in joined
    assert "PRIVATE KEY" not in joined


def test_repo_id_mismatch_is_warning_not_blocking() -> None:
    diags = installation_diagnostics(
        _repo(),
        _verification(
            InstallationStatus.INSTALLED,
            {"contents": "read"},
            repo_id="999",
            default_branch="main",
        ),
    )
    warnings = [d for d in diags if d.severity is DiagnosticSeverity.WARNING]
    assert any("repo" in d.message.lower() for d in warnings)
    assert not any(d.severity is DiagnosticSeverity.BLOCKING for d in diags)


# --- TASK-015: validator integration ----------------------------------------


class _FakeVerifier:
    def __init__(self, result=None, error=None) -> None:
        self._result = result
        self._error = error
        self.calls: list[tuple[str, str]] = []

    def verify_installation(self, repository, installation_id):
        self.calls.append((repository.key, installation_id))
        if self._error is not None:
            raise self._error
        return self._result


def _loader(config):
    def _load(path=None):
        return config

    return _load


def test_validator_passes_with_good_installation_and_permissions() -> None:
    config = LivingADRConfig(repositories=[_repo()])
    verifier = _FakeVerifier(
        result=_verification(
            InstallationStatus.INSTALLED,
            {"contents": "read"},
            repo_id="100",
            default_branch="main",
        )
    )
    validator = OnboardingValidator(
        config_loader=_loader(config),
        env=_full_env(),
        installation_verifier=verifier,
    )
    result = validator.validate()
    assert result.passed is True
    assert verifier.calls == [("github.com/acme/widgets", "inst-555")]
    assert "required_permissions" in result.metadata


def test_validator_fails_when_installation_missing() -> None:
    config = LivingADRConfig(repositories=[_repo()])
    verifier = _FakeVerifier(
        result=_verification(
            InstallationStatus.NOT_INSTALLED, {}, installation_id=None
        )
    )
    validator = OnboardingValidator(
        config_loader=_loader(config),
        env=_full_env(),
        installation_verifier=verifier,
    )
    result = validator.validate()
    assert result.passed is False
    assert any(
        d.category is DiagnosticCategory.GITHUB_APP
        and d.severity is DiagnosticSeverity.BLOCKING
        for d in result.diagnostics
    )


def test_validator_handles_provider_error_without_leaking() -> None:
    config = LivingADRConfig(repositories=[_repo()])
    verifier = _FakeVerifier(error=SCMProviderError("boom token=ghp_secret"))
    validator = OnboardingValidator(
        config_loader=_loader(config),
        env=_full_env(),
        installation_verifier=verifier,
    )
    result = validator.validate()
    assert result.passed is False
    blob = "\n".join(d.message + (d.remediation or "") for d in result.diagnostics)
    assert "ghp_secret" not in blob


def test_validator_without_verifier_warns_but_does_not_block() -> None:
    config = LivingADRConfig(repositories=[_repo()])
    validator = OnboardingValidator(
        config_loader=_loader(config),
        env=_full_env(),
        installation_verifier=None,
    )
    result = validator.validate()
    # Skipping live verification is a warning, not a blocking failure.
    assert result.passed is True
    assert any(
        d.category is DiagnosticCategory.GITHUB_APP
        and d.severity is DiagnosticSeverity.WARNING
        for d in result.diagnostics
    )
