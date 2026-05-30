"""Onboarding validation service (feature 014).

``OnboardingValidator`` is thin orchestration over established seams:

- config is loaded through the **injected** feature 002 loader
  (:func:`living_adr.core.config_loader.load_living_adr_config` by default); this
  module never parses YAML itself.
- environment presence is checked against the shared
  :mod:`living_adr.onboarding.required_env` registry, reporting only
  present/absent status — never values.
- a restart-required lifecycle diagnostic restates the no-hot-reload contract.

GitHub App installation/permission verification is layered on in slice 3 via an
injected verifier; config changes never trigger a reload here (architecture
#cross-cutting, #deployment, #anti-patterns).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from living_adr.core.config import LivingADRConfig, RepositoryConfig
from living_adr.core.config_loader import (
    ConfigStartupError,
    load_living_adr_config,
)
from living_adr.core.observability import NoOpObservability, Observability
from living_adr.onboarding.diagnostics import (
    DiagnosticCategory,
    DiagnosticSeverity,
    OnboardingDiagnostic,
    OnboardingValidationResult,
    safe_result_metadata,
)
from living_adr.onboarding.required_env import REQUIRED_ENV_VARS

ConfigLoader = Callable[..., LivingADRConfig]

_RESTART_MESSAGE = (
    "Configuration is read once at startup. After changing config or "
    "environment values, restart both living-adr-workflow and living-adr-mcp; "
    "there is no hot reload or automatic repository discovery."
)


class OnboardingValidator:
    """Validate that the configured PoC repository is ready to be tracked."""

    def __init__(
        self,
        *,
        config_loader: ConfigLoader = load_living_adr_config,
        env: Mapping[str, str] | None = None,
        config_path: object | None = None,
        observability: Observability | None = None,
    ) -> None:
        self._config_loader = config_loader
        self._env: Mapping[str, str] = env if env is not None else {}
        self._config_path = config_path
        self._obs: Observability = observability or NoOpObservability()

    def validate(self) -> OnboardingValidationResult:
        diagnostics: list[OnboardingDiagnostic] = []
        metadata: dict[str, object] = {}

        config = self._check_config(diagnostics, metadata)
        self._check_environment(diagnostics)
        self._add_lifecycle(diagnostics)
        # ``config`` is consumed by GitHub installation verification (slice 3).
        del config

        result = OnboardingValidationResult.from_diagnostics(
            diagnostics, metadata=safe_result_metadata(metadata)
        )
        self._obs.increment_counter(
            "onboarding.validation",
            metadata={"passed": result.passed},
        )
        return result

    # -- config ---------------------------------------------------------------

    def _check_config(
        self,
        diagnostics: list[OnboardingDiagnostic],
        metadata: dict[str, object],
    ) -> LivingADRConfig | None:
        try:
            config = self._config_loader(self._config_path)
        except ConfigStartupError as exc:
            diagnostics.append(
                OnboardingDiagnostic(
                    category=DiagnosticCategory.CONFIG,
                    severity=DiagnosticSeverity.BLOCKING,
                    message=str(exc),
                    remediation=(
                        "Fix the configuration reported above (see "
                        "living-adr.config.example.yaml) and re-run onboarding "
                        "validation."
                    ),
                )
            )
            return None

        if self._config_path is not None:
            metadata["config_path"] = str(self._config_path)

        repositories = config.repositories
        first = repositories[0]
        self._add_repository_metadata(metadata, first)

        diagnostics.append(
            OnboardingDiagnostic(
                category=DiagnosticCategory.CONFIG,
                severity=DiagnosticSeverity.INFO,
                message=(
                    f"Loaded configuration for {len(repositories)} "
                    f"repository(ies); validating "
                    f"{first.canonical_key!r}."
                ),
                repository_key=first.canonical_key,
            )
        )
        if len(repositories) > 1:
            diagnostics.append(
                OnboardingDiagnostic(
                    category=DiagnosticCategory.CONFIG,
                    severity=DiagnosticSeverity.INFO,
                    message=(
                        "PoC onboarding validation operationally supports a "
                        "single tracked repository; additional configured "
                        "repositories are validated uniformly but not part of "
                        "multi-repo governance automation."
                    ),
                    metadata={"poc_note": "single-repo PoC"},
                )
            )
            metadata["poc_note"] = "single-repo PoC"
        return config

    @staticmethod
    def _add_repository_metadata(
        metadata: dict[str, object], repo: RepositoryConfig
    ) -> None:
        metadata["repository_key"] = repo.canonical_key
        metadata["default_branch"] = repo.default_branch
        metadata["publication_policy"] = repo.adr_publication_policy.value
        metadata["installation_id"] = repo.github_app_installation_id

    # -- environment ----------------------------------------------------------

    def _check_environment(
        self, diagnostics: list[OnboardingDiagnostic]
    ) -> None:
        for var in REQUIRED_ENV_VARS:
            value = self._env.get(var.name)
            if value is None or not value.strip():
                diagnostics.append(
                    OnboardingDiagnostic(
                        category=DiagnosticCategory.ENVIRONMENT,
                        severity=DiagnosticSeverity.BLOCKING,
                        message=(
                            f"Required environment variable {var.name} is not "
                            f"set. ({var.description})"
                        ),
                        remediation=(
                            f"Set {var.name} (see .env.example) and restart the "
                            f"deployables."
                        ),
                    )
                )

    # -- lifecycle ------------------------------------------------------------

    @staticmethod
    def _add_lifecycle(diagnostics: list[OnboardingDiagnostic]) -> None:
        diagnostics.append(
            OnboardingDiagnostic(
                category=DiagnosticCategory.LIFECYCLE,
                severity=DiagnosticSeverity.INFO,
                message=_RESTART_MESSAGE,
            )
        )


__all__ = ["OnboardingValidator"]
