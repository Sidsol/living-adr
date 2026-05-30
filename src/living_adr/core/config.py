"""Typed repository configuration models (feature 002).

Defines the stable configuration seam consumed by every later feature:

- :class:`PublicationPolicy` — explicit, enumerated ADR publication modes.
- :class:`RepositoryConfig` — per-repository onboarding + policy record. Carries
  **no secrets**; secrets remain an environment/vault concern.
- :class:`LivingADRConfig` — top-level collection with ``repositories:
  list[RepositoryConfig]`` and canonical-key lookup helpers.

The PoC one-repository case is represented as a list of length one. There is no
``if single_repo:`` branch anywhere; ``N >= 1`` repositories are handled
uniformly (architecture #anti-patterns).
"""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from living_adr.core.repository import RepositoryIdentity


def _is_safe_relative_path(template: str) -> bool:
    """True when ``template`` is a relative, POSIX-style path with no traversal.

    Backslashes, drive letters (``C:``), leading slashes, and ``..`` segments are
    all rejected so a publish target can never escape the repository tree.
    """

    if "\\" in template or template.startswith("/"):
        return False
    if len(template) >= 2 and template[1] == ":":  # drive letter, e.g. C:
        return False
    segments = template.split("/")
    return ".." not in segments


class PublicationPolicy(StrEnum):
    """Where approved ADRs are published for a repository.

    Values are architecture-approved and exhaustive; unknown strings are
    rejected at validation time rather than silently defaulting.
    """

    LIVINGADR_ONLY = "livingadr_only"
    PUBLISH_TO_GITHUB = "publish_to_github"
    PUBLISH_TO_GITHUB_AND_LIVINGADR = "publish_to_github_and_livingadr"

    @property
    def publishes_to_github(self) -> bool:
        """True when this policy writes ADRs back to the GitHub repository."""

        return self in (
            PublicationPolicy.PUBLISH_TO_GITHUB,
            PublicationPolicy.PUBLISH_TO_GITHUB_AND_LIVINGADR,
        )


class RepositoryConfig(BaseModel):
    """Onboarding + policy record for one tracked repository.

    No field accepts a secret value: ``extra="forbid"`` rejects unknown keys
    (including secret-looking ones like ``token`` or ``private_key``) so secrets
    cannot leak into repository config (architecture #cross-cutting, FR-12).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    identity: RepositoryIdentity
    github_app_installation_id: str
    default_branch: str
    adr_publication_policy: PublicationPolicy
    external_llm_allowed: bool
    adr_target_branch: str | None = None
    adr_path_template: str | None = None

    @field_validator("github_app_installation_id", "default_branch")
    @classmethod
    def _non_empty(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("must not be empty or whitespace")
        return stripped

    @model_validator(mode="after")
    def _validate_publish_target(self) -> RepositoryConfig:
        """Publish-to-GitHub policies require a valid, relative ADR target."""

        if not self.adr_publication_policy.publishes_to_github:
            return self

        branch = (self.adr_target_branch or "").strip()
        if not branch:
            raise ValueError(
                "adr_target_branch is required when adr_publication_policy "
                "publishes to GitHub"
            )

        template = (self.adr_path_template or "").strip()
        if not template:
            raise ValueError(
                "adr_path_template is required when adr_publication_policy "
                "publishes to GitHub"
            )
        if not _is_safe_relative_path(template):
            raise ValueError(
                "adr_path_template must be a relative POSIX path without '..' "
                f"segments, drive letters, or backslashes: {template!r}"
            )
        return self

    @property
    def canonical_key(self) -> str:
        """Stable ``host/owner/repo`` key for this repository."""

        return self.identity.key


class LivingADRConfig(BaseModel):
    """Top-level configuration: a non-empty list of tracked repositories."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    repositories: list[RepositoryConfig]

    @field_validator("repositories")
    @classmethod
    def _at_least_one(
        cls, repositories: list[RepositoryConfig]
    ) -> list[RepositoryConfig]:
        if not repositories:
            raise ValueError("at least one repository must be configured (N >= 1)")
        return repositories

    @model_validator(mode="after")
    def _reject_duplicate_identities(self) -> LivingADRConfig:
        seen: set[str] = set()
        for entry in self.repositories:
            key = entry.canonical_key
            if key in seen:
                raise ValueError(
                    f"duplicate repository identity: {key!r} appears more than once"
                )
            seen.add(key)
        return self

    def get(self, canonical_key: str) -> RepositoryConfig | None:
        """Look up a repository by its canonical ``host/owner/repo`` key."""

        for entry in self.repositories:
            if entry.canonical_key == canonical_key:
                return entry
        return None

    def allows_external_llm(self, repository: RepositoryIdentity | str) -> bool:
        """Explicit external-LLM egress decision for ``repository``.

        Accepts a :class:`RepositoryIdentity` or a canonical key string. Unknown
        repositories are denied by default — external LLM egress is never
        inferred for a repository that is not configured (FM-14, NFR-2).
        """

        key = (
            repository.key
            if isinstance(repository, RepositoryIdentity)
            else repository
        )
        entry = self.get(key)
        if entry is None:
            return False
        return entry.external_llm_allowed
