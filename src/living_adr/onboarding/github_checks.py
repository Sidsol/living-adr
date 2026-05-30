"""Onboarding GitHub App permission mapping + diagnostic conversion (014).

Keeps onboarding-specific policy logic thin: GitHub API details live in the
provider seam (:mod:`living_adr.scm.github_provider`); this module only maps a
publication policy to required permissions and converts a safe
:class:`~living_adr.core.scm.InstallationVerification` into onboarding
diagnostics. No GitHub HTTP, no secrets.
"""

from __future__ import annotations

from collections.abc import Mapping

from living_adr.core.config import PublicationPolicy, RepositoryConfig
from living_adr.core.scm import InstallationStatus, InstallationVerification
from living_adr.onboarding.diagnostics import (
    DiagnosticCategory,
    DiagnosticSeverity,
    OnboardingDiagnostic,
)


def required_permissions(policy: PublicationPolicy) -> tuple[str, ...]:
    """Required GitHub App permissions for a publication policy.

    ``contents:read`` is always required; ``contents:write`` is added only when
    the policy publishes ADRs back to GitHub (US-2, FR-5).
    """

    perms = ["contents:read"]
    if policy.publishes_to_github:
        perms.append("contents:write")
    return tuple(perms)


def permission_satisfied(granted: Mapping[str, str], required: str) -> bool:
    """True when ``granted`` permissions satisfy the ``scope:level`` requirement."""

    scope, _, level = required.partition(":")
    have = granted.get(scope)
    if have is None:
        return False
    if level == "read":
        return have in ("read", "write", "admin")
    if level == "write":
        return have in ("write", "admin")
    return False


# Operator-facing remediation for each non-installed status. None of these ever
# reference private key material — only the repository key and installation id.
_STATUS_REMEDIATION: dict[InstallationStatus, str] = {
    InstallationStatus.NOT_INSTALLED: (
        "Install the GitHub App on {key} and set the configured installation "
        "id {inst}."
    ),
    InstallationStatus.SUSPENDED: (
        "The GitHub App installation {inst} for {key} is suspended; unsuspend "
        "it in the repository/org settings."
    ),
    InstallationStatus.MISMATCHED: (
        "Configured installation id {inst} does not match the installation "
        "found for {key}; update github_app_installation_id."
    ),
    InstallationStatus.ACCESS_DENIED: (
        "GitHub denied access verifying installation {inst} for {key}; check "
        "the App credentials and repository access."
    ),
    InstallationStatus.RATE_LIMITED: (
        "GitHub rate-limited the installation check for {key} (installation "
        "{inst}); retry later."
    ),
    InstallationStatus.ERROR: (
        "Could not verify installation {inst} for {key}; inspect the App "
        "configuration and retry."
    ),
}


def installation_diagnostics(
    repo: RepositoryConfig, verification: InstallationVerification
) -> list[OnboardingDiagnostic]:
    """Convert an installation verification into onboarding diagnostics."""

    key = repo.canonical_key
    inst = repo.github_app_installation_id
    diagnostics: list[OnboardingDiagnostic] = []

    if verification.status is not InstallationStatus.INSTALLED:
        template = _STATUS_REMEDIATION.get(
            verification.status, _STATUS_REMEDIATION[InstallationStatus.ERROR]
        )
        diagnostics.append(
            OnboardingDiagnostic(
                category=DiagnosticCategory.GITHUB_APP,
                severity=DiagnosticSeverity.BLOCKING,
                message=(
                    f"GitHub App installation check failed for {key} "
                    f"(installation {inst}): {verification.status.value}."
                ),
                remediation=template.format(key=key, inst=inst),
                repository_key=key,
                metadata={"installation_status": verification.status.value},
            )
        )
        return diagnostics

    # Installed: confirm, then check permissions and metadata consistency.
    diagnostics.append(
        OnboardingDiagnostic(
            category=DiagnosticCategory.GITHUB_APP,
            severity=DiagnosticSeverity.INFO,
            message=(
                f"GitHub App installation {inst} verified for {key}."
            ),
            repository_key=key,
            metadata={"installation_id": inst},
        )
    )

    required = required_permissions(repo.adr_publication_policy)
    missing = [
        perm
        for perm in required
        if not permission_satisfied(verification.permissions, perm)
    ]
    if missing:
        diagnostics.append(
            OnboardingDiagnostic(
                category=DiagnosticCategory.PERMISSIONS,
                severity=DiagnosticSeverity.BLOCKING,
                message=(
                    f"Installation for {key} is missing required permission(s): "
                    f"{', '.join(missing)} (policy "
                    f"{repo.adr_publication_policy.value})."
                ),
                remediation=(
                    "Grant the listed GitHub App permission(s) for "
                    f"{key} and re-run onboarding validation."
                ),
                repository_key=key,
            )
        )
    else:
        diagnostics.append(
            OnboardingDiagnostic(
                category=DiagnosticCategory.PERMISSIONS,
                severity=DiagnosticSeverity.INFO,
                message=(
                    f"Required permission(s) satisfied for {key}: "
                    f"{', '.join(required)}."
                ),
                repository_key=key,
            )
        )

    if (
        verification.repo_id is not None
        and verification.repo_id != repo.identity.repo_id
    ):
        diagnostics.append(
            OnboardingDiagnostic(
                category=DiagnosticCategory.GITHUB_APP,
                severity=DiagnosticSeverity.WARNING,
                message=(
                    f"Configured repo id {repo.identity.repo_id} for {key} "
                    f"differs from GitHub repo id {verification.repo_id}."
                ),
                remediation=(
                    "Confirm the configured repository identity matches GitHub."
                ),
                repository_key=key,
            )
        )

    if (
        verification.default_branch is not None
        and verification.default_branch != repo.default_branch
    ):
        diagnostics.append(
            OnboardingDiagnostic(
                category=DiagnosticCategory.GITHUB_APP,
                severity=DiagnosticSeverity.WARNING,
                message=(
                    f"Configured default branch {repo.default_branch!r} for "
                    f"{key} differs from GitHub default branch "
                    f"{verification.default_branch!r}."
                ),
                remediation="Align default_branch in config with GitHub.",
                repository_key=key,
            )
        )

    return diagnostics


__all__ = [
    "required_permissions",
    "permission_satisfied",
    "installation_diagnostics",
]
