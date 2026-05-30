"""Slice 2 tests: config + environment validation service (TASK-007..010).

Verifies the onboarding validator loads config through the feature 002 loader,
preserves ConfigStartupError diagnostics, reports missing env vars by their
canonical names, and emits restart-required lifecycle output. No YAML parsing
and no network here; the loader and env are injected.
"""

from __future__ import annotations

import pytest

from living_adr.core.config import (
    LivingADRConfig,
    PublicationPolicy,
    RepositoryConfig,
)
from living_adr.core.config_loader import ConfigStartupError
from living_adr.core.repository import RepositoryIdentity
from living_adr.onboarding.diagnostics import (
    DiagnosticCategory,
    DiagnosticSeverity,
)
from living_adr.onboarding.required_env import (
    REQUIRED_ENV_VARS,
    required_env_names,
)
from living_adr.onboarding.validation import OnboardingValidator

IDENTITY = RepositoryIdentity(
    host="github.com", owner="acme", repo="widgets", repo_id="100"
)
REPO_CONFIG = RepositoryConfig(
    identity=IDENTITY,
    github_app_installation_id="inst-555",
    default_branch="main",
    adr_publication_policy=PublicationPolicy.LIVINGADR_ONLY,
    external_llm_allowed=False,
)
VALID_CONFIG = LivingADRConfig(repositories=[REPO_CONFIG])


def _full_env() -> dict[str, str]:
    return {name: f"placeholder-{name.lower()}" for name in required_env_names()}


def _loader_ok(path=None):
    return VALID_CONFIG


def _loader_raising(message: str):
    def _loader(path=None):
        raise ConfigStartupError(message)

    return _loader


# --- TASK-007/008: config loading through feature 002 -----------------------


def test_validator_uses_injected_loader_and_passes_for_valid_setup() -> None:
    validator = OnboardingValidator(
        config_loader=_loader_ok,
        env=_full_env(),
    )
    result = validator.validate()
    assert result.passed is True
    assert result.exit_code == 0
    # Safe metadata reflects the configured repository.
    assert result.metadata["repository_key"] == "github.com/acme/widgets"
    assert result.metadata["installation_id"] == "inst-555"
    assert result.metadata["publication_policy"] == "livingadr_only"


def test_invalid_config_diagnostic_preserves_feature_002_error_text() -> None:
    message = (
        "Invalid LivingADR configuration in /etc/living-adr.config.yaml:\n"
        "  - repositories.0.default_branch: must not be empty or whitespace"
    )
    validator = OnboardingValidator(
        config_loader=_loader_raising(message),
        env=_full_env(),
    )
    result = validator.validate()
    assert result.passed is False
    config_diags = [
        d for d in result.diagnostics if d.category is DiagnosticCategory.CONFIG
    ]
    assert any(d.severity is DiagnosticSeverity.BLOCKING for d in config_diags)
    # Feature 002 field-path message is surfaced verbatim.
    assert any(
        "repositories.0.default_branch" in d.message for d in config_diags
    )


def test_validator_does_not_parse_yaml_itself() -> None:
    # The validator must depend only on the injected loader; it never imports
    # yaml. (Guards against re-parsing config — architecture #anti-patterns.)
    import inspect

    import living_adr.onboarding.validation as validation_module

    source = inspect.getsource(validation_module)
    assert "import yaml" not in source
    assert "yaml.safe_load" not in source


# --- TASK-009/010: environment validation -----------------------------------


def test_missing_required_env_var_is_blocking_and_named() -> None:
    env = _full_env()
    del env["GITHUB_APP_ID"]
    validator = OnboardingValidator(config_loader=_loader_ok, env=env)
    result = validator.validate()
    assert result.passed is False
    env_diags = [
        d
        for d in result.diagnostics
        if d.category is DiagnosticCategory.ENVIRONMENT
    ]
    assert any("GITHUB_APP_ID" in d.message for d in env_diags)
    assert all(d.severity is DiagnosticSeverity.BLOCKING for d in env_diags)


def test_empty_env_var_treated_as_missing() -> None:
    env = _full_env()
    env["ANTHROPIC_API_KEY"] = "   "
    validator = OnboardingValidator(config_loader=_loader_ok, env=env)
    result = validator.validate()
    assert any(
        "ANTHROPIC_API_KEY" in d.message
        for d in result.diagnostics
        if d.category is DiagnosticCategory.ENVIRONMENT
    )


def test_env_values_are_never_printed_only_presence() -> None:
    env = _full_env()
    env["GITHUB_WEBHOOK_SECRET"] = "whsec_realsecretvalue"
    # Drop one var so an env diagnostic is emitted, but the present secret value
    # must never appear in any diagnostic message/metadata.
    del env["LANGSMITH_API_KEY"]
    validator = OnboardingValidator(config_loader=_loader_ok, env=env)
    result = validator.validate()
    blob = "\n".join(
        d.message + str(dict(d.metadata)) for d in result.diagnostics
    )
    assert "whsec_realsecretvalue" not in blob


# --- TASK-016 (lifecycle, surfaced early in slice 2) ------------------------


def test_lifecycle_diagnostic_states_restart_required_for_both_deployables() -> None:
    validator = OnboardingValidator(config_loader=_loader_ok, env=_full_env())
    result = validator.validate()
    lifecycle = [
        d
        for d in result.diagnostics
        if d.category is DiagnosticCategory.LIFECYCLE
    ]
    assert lifecycle, "expected a lifecycle diagnostic"
    text = " ".join(d.message for d in lifecycle).lower()
    assert "living-adr-workflow" in text
    assert "living-adr-mcp" in text
    assert "restart" in text


def test_no_hot_reload_or_discovery_language_in_validation_module() -> None:
    import inspect

    import living_adr.onboarding.validation as validation_module

    source = inspect.getsource(validation_module).lower()
    # Forbid actual reload/watcher *behavior*, not the descriptive "no hot
    # reload" lifecycle message we intentionally emit.
    for forbidden in (
        "watchdog",
        "filesystemevent",
        ".watch(",
        "threading.timer",
        "while true",
        "schedule.every",
    ):
        assert forbidden not in source


# --- registry sanity --------------------------------------------------------


def test_required_env_registry_includes_expected_names() -> None:
    names = set(required_env_names())
    assert {
        "LIVING_ADR_CONFIG",
        "GITHUB_APP_ID",
        "GITHUB_APP_PRIVATE_KEY_PATH",
        "GITHUB_WEBHOOK_SECRET",
        "ANTHROPIC_API_KEY",
        "LANGSMITH_API_KEY",
        "LIVING_ADR_UI_TOKEN",
        "LIVING_ADR_STORAGE_PATH",
    } <= names


def test_required_env_vars_have_placeholders_and_descriptions() -> None:
    for var in REQUIRED_ENV_VARS:
        assert var.name and var.placeholder and var.description
        # Placeholders must not look like real secrets.
        assert "BEGIN PRIVATE KEY" not in var.placeholder


@pytest.mark.parametrize("var", REQUIRED_ENV_VARS, ids=lambda v: v.name)
def test_secret_vars_flagged(var) -> None:
    secret_names = {
        "GITHUB_WEBHOOK_SECRET",
        "ANTHROPIC_API_KEY",
        "LANGSMITH_API_KEY",
        "LIVING_ADR_UI_TOKEN",
    }
    if var.name in secret_names:
        assert var.secret is True
