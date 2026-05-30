"""Central registry of required environment variables (feature 014).

Single source of truth shared by the onboarding validator (presence checks) and
the ``.env.example`` drift test, so setup docs cannot drift from runtime
expectations (FR-8, US-3). This registry holds **names, descriptions, and
placeholders only** — never real secret values.

Names align with the seams already established:

- ``LIVING_ADR_CONFIG`` matches ``living_adr.core.config_loader.CONFIG_ENV_VAR``.
- ``LANGSMITH_API_KEY`` matches ``living_adr.observability.config``.

The remaining names follow the feature plan; if a later feature finalizes a
different exact name, update it here and both consumers stay aligned.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RequiredEnvVar:
    """One required environment variable: name, description, secret flag."""

    name: str
    description: str
    secret: bool
    placeholder: str


REQUIRED_ENV_VARS: tuple[RequiredEnvVar, ...] = (
    RequiredEnvVar(
        name="LIVING_ADR_CONFIG",
        description="Path to living-adr.config.yaml (feature 002 loader).",
        secret=False,
        placeholder="/etc/living-adr/living-adr.config.yaml",
    ),
    RequiredEnvVar(
        name="GITHUB_APP_ID",
        description="Numeric GitHub App id used for installation auth.",
        secret=False,
        placeholder="123456",
    ),
    RequiredEnvVar(
        name="GITHUB_APP_PRIVATE_KEY_PATH",
        description="Filesystem path to the GitHub App private key (.pem).",
        secret=False,
        placeholder="/run/secrets/github-app-private-key.pem",
    ),
    RequiredEnvVar(
        name="GITHUB_WEBHOOK_SECRET",
        description="HMAC secret for verifying GitHub webhook signatures.",
        secret=True,
        placeholder="replace-with-webhook-secret",
    ),
    RequiredEnvVar(
        name="ANTHROPIC_API_KEY",
        description="Anthropic API key for ADR drafting (later features).",
        secret=True,
        placeholder="replace-with-anthropic-api-key",
    ),
    RequiredEnvVar(
        name="LANGSMITH_API_KEY",
        description="LangSmith API key for observability export (feature 013).",
        secret=True,
        placeholder="replace-with-langsmith-api-key",
    ),
    RequiredEnvVar(
        name="LIVING_ADR_UI_TOKEN",
        description="Bearer token guarding the local review UI.",
        secret=True,
        placeholder="replace-with-ui-token",
    ),
    RequiredEnvVar(
        name="LIVING_ADR_STORAGE_PATH",
        description="Directory for local graph/ingestion persistence.",
        secret=False,
        placeholder="/var/lib/living-adr",
    ),
)


def required_env_names() -> tuple[str, ...]:
    """Return the ordered tuple of required environment variable names."""

    return tuple(var.name for var in REQUIRED_ENV_VARS)


__all__ = ["RequiredEnvVar", "REQUIRED_ENV_VARS", "required_env_names"]
