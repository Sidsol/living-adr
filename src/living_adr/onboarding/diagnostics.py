"""Secret-safe onboarding diagnostic models, redaction, and formatter (014).

This module is pure, deterministic, and dependency-free. It defines:

- :class:`DiagnosticSeverity` / :class:`DiagnosticCategory` — the closed
  vocabularies grouping operator diagnostics.
- :class:`OnboardingDiagnostic` — one categorized, severity-tagged finding with
  optional remediation, repository scope, and **safe** metadata.
- :class:`OnboardingValidationResult` — aggregation with pass/fail status and an
  exit-code mapping (0 pass, non-zero when any blocking diagnostic exists).
- redaction helpers + a safe-metadata allowlist enforcing the default-deny rule:
  diagnostics and success output never carry secrets, private keys, tokens, or
  raw payload/diff/prompt/draft/reviewer content (architecture #cross-cutting,
  #anti-patterns, FM-21).
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class DiagnosticSeverity(StrEnum):
    """How serious a diagnostic is. Only ``BLOCKING`` fails onboarding."""

    INFO = "info"
    WARNING = "warning"
    BLOCKING = "blocking"


class DiagnosticCategory(StrEnum):
    """Operator-facing grouping for onboarding diagnostics."""

    CONFIG = "config"
    ENVIRONMENT = "environment"
    GITHUB_APP = "github_app"
    PERMISSIONS = "permissions"
    WEBHOOK_OR_REPLAY = "webhook_or_replay"
    LIFECYCLE = "lifecycle"


#: Canonical, deterministic rendering order for grouped output.
CATEGORY_ORDER: tuple[DiagnosticCategory, ...] = (
    DiagnosticCategory.CONFIG,
    DiagnosticCategory.ENVIRONMENT,
    DiagnosticCategory.GITHUB_APP,
    DiagnosticCategory.PERMISSIONS,
    DiagnosticCategory.WEBHOOK_OR_REPLAY,
    DiagnosticCategory.LIFECYCLE,
)

#: Sentinel printed in place of any sensitive value.
REDACTED = "[REDACTED]"

# Substrings that mark a metadata *key* as sensitive (case-insensitive). Covers
# secrets/credentials plus known raw-content fields that must never be exported.
_SENSITIVE_KEY_TOKENS: tuple[str, ...] = (
    "secret",
    "private_key",
    "privatekey",
    "api_key",
    "apikey",
    "token",
    "webhook",
    "anthropic",
    "langsmith",
    "password",
    "credential",
    "payload",
    "diff",
    "prompt",
    "draft",
    "reviewer_comment",
)

# Substrings that mark a string *value* as a secret regardless of its key.
_SECRET_VALUE_SIGNATURES: tuple[str, ...] = (
    "-----BEGIN",
    "PRIVATE KEY",
    "ghp_",
    "ghs_",
    "github_pat_",
    "sk-ant-",
    "lsv2_",
    "whsec_",
)

#: Allowlist of metadata keys permitted in success/readiness output.
SAFE_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "repository_key",
        "config_path",
        "publication_policy",
        "installation_id",
        "default_branch",
        "repo_id",
        "required_permissions",
        "next_step",
        "poc_note",
    }
)

#: Preferred rendering order for safe success metadata.
SAFE_METADATA_ORDER: tuple[str, ...] = (
    "repository_key",
    "config_path",
    "default_branch",
    "publication_policy",
    "installation_id",
    "repo_id",
    "required_permissions",
    "next_step",
    "poc_note",
)


def is_sensitive_key(key: str) -> bool:
    """True when ``key`` names a secret or raw-content field."""

    lowered = key.lower()
    return any(token in lowered for token in _SENSITIVE_KEY_TOKENS)


def redact_value(value: object) -> object:
    """Mask a value that looks like a secret; pass non-secrets through.

    Only string values are scanned (for known secret signatures); other types
    are returned unchanged.
    """

    if isinstance(value, str):
        if any(sig in value for sig in _SECRET_VALUE_SIGNATURES):
            return REDACTED
        return value
    return value


def redact_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    """Return a copy of ``metadata`` with sensitive keys/values masked."""

    out: dict[str, object] = {}
    for key, value in metadata.items():
        if is_sensitive_key(key):
            out[key] = REDACTED
        else:
            out[key] = redact_value(value)
    return out


def safe_result_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    """Filter ``metadata`` to the safe allowlist, redacting any stray secret.

    Anything not on :data:`SAFE_METADATA_KEYS` is dropped entirely; allowlisted
    values are still scanned so an accidental secret cannot slip through a
    permitted key.
    """

    out: dict[str, object] = {}
    for key, value in metadata.items():
        if key not in SAFE_METADATA_KEYS:
            continue
        out[key] = redact_value(value)
    return out


class OnboardingDiagnostic(BaseModel):
    """One categorized, severity-tagged onboarding finding (secret-free)."""

    model_config = ConfigDict(frozen=True)

    category: DiagnosticCategory
    severity: DiagnosticSeverity
    message: str
    remediation: str | None = None
    repository_key: str | None = None
    metadata: Mapping[str, object] = Field(default_factory=dict)

    @property
    def is_blocking(self) -> bool:
        return self.severity is DiagnosticSeverity.BLOCKING

    def safe_metadata(self) -> dict[str, object]:
        """Redacted view of this diagnostic's metadata."""

        return redact_metadata(self.metadata)


@dataclass(frozen=True)
class OnboardingValidationResult:
    """Aggregated onboarding outcome with status and exit-code mapping."""

    diagnostics: tuple[OnboardingDiagnostic, ...] = ()
    metadata: Mapping[str, object] = field(default_factory=dict)

    @classmethod
    def from_diagnostics(
        cls,
        diagnostics: Iterable[OnboardingDiagnostic],
        metadata: Mapping[str, object] | None = None,
    ) -> OnboardingValidationResult:
        return cls(
            diagnostics=tuple(diagnostics),
            metadata=dict(metadata or {}),
        )

    @property
    def passed(self) -> bool:
        """True when no blocking diagnostic is present."""

        return not any(d.is_blocking for d in self.diagnostics)

    @property
    def exit_code(self) -> int:
        """Process exit code: 0 on pass, 1 when any blocking diagnostic exists."""

        return 0 if self.passed else 1

    def blocking(self) -> list[OnboardingDiagnostic]:
        return [d for d in self.diagnostics if d.is_blocking]

    def by_category(self) -> dict[DiagnosticCategory, list[OnboardingDiagnostic]]:
        """Group diagnostics by category, preserving insertion order."""

        grouped: dict[DiagnosticCategory, list[OnboardingDiagnostic]] = {}
        for diag in self.diagnostics:
            grouped.setdefault(diag.category, []).append(diag)
        return grouped


def format_result(result: OnboardingValidationResult) -> str:
    """Render a deterministic, grouped, secret-safe operator report."""

    status = "PASS" if result.passed else "FAIL"
    lines: list[str] = [f"Onboarding validation: {status}"]

    safe_meta = safe_result_metadata(result.metadata)
    if safe_meta:
        lines.append("Repository readiness:")
        ordered_keys = [k for k in SAFE_METADATA_ORDER if k in safe_meta]
        ordered_keys += [k for k in safe_meta if k not in SAFE_METADATA_ORDER]
        for key in ordered_keys:
            lines.append(f"  {key}: {safe_meta[key]}")

    grouped = result.by_category()
    for category in CATEGORY_ORDER:
        diags = grouped.get(category)
        if not diags:
            continue
        lines.append(f"[{category.value}]")
        for diag in diags:
            lines.append(
                f"  - ({diag.severity.value}) {redact_value(diag.message)}"
            )
            if diag.remediation:
                lines.append(
                    f"    remediation: {redact_value(diag.remediation)}"
                )
    return "\n".join(lines)


__all__ = [
    "DiagnosticSeverity",
    "DiagnosticCategory",
    "CATEGORY_ORDER",
    "REDACTED",
    "SAFE_METADATA_KEYS",
    "SAFE_METADATA_ORDER",
    "is_sensitive_key",
    "redact_value",
    "redact_metadata",
    "safe_result_metadata",
    "OnboardingDiagnostic",
    "OnboardingValidationResult",
    "format_result",
]
