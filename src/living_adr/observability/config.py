"""LangSmith observability settings (feature 013, slice 1).

Typed, secret-free configuration for the LangSmith-backed :class:`Observability`
adapter. Carries no API key in repository config — the key is read from the
process environment only. Defaults are **safe**: disabled, 100% PoC metadata
sampling, 30-day retention, and **no** raw export.

Architecture anchors: ``architecture.md#cross-cutting`` (structured logs,
metadata traces, default-deny raw export, 30-day retention, 100% PoC sampling)
and ``architecture.md#anti-patterns`` (secrets never live in ``RepositoryConfig``).
"""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, field_validator

# Architecture #cross-cutting: PoC retention ceiling. Configuring a longer
# window is an actionable validation error rather than a silent override.
MAX_RETENTION_DAYS = 30


def _as_bool(value: str | None) -> bool:
    if value is None:
        return False
    return value.strip().lower() in {"1", "true", "yes", "on"}


class LangSmithSettings(BaseModel):
    """Validated LangSmith adapter configuration. Secret-free except API key.

    The API key is accepted here only so it can be passed to the SDK client at
    construction time; it is never logged, never exported as metadata, and never
    persisted in :class:`RepositoryConfig`.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = False
    api_key: str | None = None
    project: str = "living-adr"
    endpoint: str | None = None
    sampling_rate: float = 1.0
    retention_days: int = MAX_RETENTION_DAYS
    raw_export_debug: bool = False
    sensitive_repositories: tuple[str, ...] = ()

    @field_validator("sampling_rate")
    @classmethod
    def _validate_sampling(cls, value: float) -> float:
        if not 0.0 <= value <= 1.0:
            raise ValueError("sampling_rate must be between 0.0 and 1.0")
        return value

    @field_validator("retention_days")
    @classmethod
    def _validate_retention(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("retention_days must be a positive number of days")
        if value > MAX_RETENTION_DAYS:
            raise ValueError(
                "retention_days exceeds the architecture ceiling of "
                f"{MAX_RETENTION_DAYS} days (architecture #cross-cutting); "
                "reduce retention or update the architecture requirement"
            )
        return value

    @property
    def should_enable(self) -> bool:
        """True only when explicitly enabled *and* an API key is present.

        Enabling without a key falls back to no-op behavior so a misconfigured
        deployment never silently drops to an unauthenticated client.
        """

        return self.enabled and bool(self.api_key)

    def is_sensitive(self, repository_key: str) -> bool:
        """True when ``repository_key`` is operator-marked as sensitive."""

        return repository_key in self.sensitive_repositories

    @classmethod
    def from_env(cls, env: Mapping[str, str]) -> LangSmithSettings:
        """Build settings from ``LANGSMITH_*`` environment variables.

        Unknown/absent variables fall back to safe defaults. Retention and
        sampling values that violate policy raise during validation so startup
        surfaces an actionable error (US-5).
        """

        values: dict[str, object] = {}
        if "LANGSMITH_ENABLED" in env:
            values["enabled"] = _as_bool(env.get("LANGSMITH_ENABLED"))
        if env.get("LANGSMITH_API_KEY"):
            values["api_key"] = env["LANGSMITH_API_KEY"]
        if env.get("LANGSMITH_PROJECT"):
            values["project"] = env["LANGSMITH_PROJECT"]
        if env.get("LANGSMITH_ENDPOINT"):
            values["endpoint"] = env["LANGSMITH_ENDPOINT"]
        if env.get("LANGSMITH_SAMPLING_RATE"):
            values["sampling_rate"] = float(env["LANGSMITH_SAMPLING_RATE"])
        if env.get("LANGSMITH_RETENTION_DAYS"):
            values["retention_days"] = int(env["LANGSMITH_RETENTION_DAYS"])
        if "LANGSMITH_RAW_EXPORT_DEBUG" in env:
            values["raw_export_debug"] = _as_bool(
                env.get("LANGSMITH_RAW_EXPORT_DEBUG")
            )
        sensitive = env.get("LANGSMITH_SENSITIVE_REPOSITORIES")
        if sensitive:
            values["sensitive_repositories"] = tuple(
                key.strip() for key in sensitive.split(",") if key.strip()
            )
        return cls(**values)


__all__ = ["LangSmithSettings", "MAX_RETENTION_DAYS"]
