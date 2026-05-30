"""Config loading + startup diagnostics (feature 002, slice 2).

Resolves the config path (explicit arg > ``LIVING_ADR_CONFIG`` env var > default
``living-adr.config.yaml`` in the current working directory), parses YAML once,
and validates it into a :class:`~living_adr.core.config.LivingADRConfig`.

All I/O, parse, and validation failures are wrapped in :class:`ConfigStartupError`
with operator-readable messages so both deployables can fail fast at startup
rather than serving traffic with partial or invalid configuration.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from living_adr.core.config import LivingADRConfig

CONFIG_ENV_VAR = "LIVING_ADR_CONFIG"
DEFAULT_CONFIG_FILENAME = "living-adr.config.yaml"


class ConfigStartupError(Exception):
    """Raised when configuration cannot be loaded or validated at startup.

    The message is operator-facing and includes the offending path plus the
    underlying parse or field-level validation detail.
    """


def resolve_config_path(explicit: Path | None = None) -> Path:
    """Resolve the config path: explicit arg, then env var, then default."""

    if explicit is not None:
        return Path(explicit)
    env_value = os.environ.get(CONFIG_ENV_VAR)
    if env_value:
        return Path(env_value)
    return Path.cwd() / DEFAULT_CONFIG_FILENAME


def _format_validation_error(path: Path, error: ValidationError) -> str:
    lines = [f"Invalid LivingADR configuration in {path}:"]
    for item in error.errors():
        location = ".".join(str(part) for part in item["loc"]) or "<root>"
        lines.append(f"  - {location}: {item['msg']}")
    return "\n".join(lines)


def load_living_adr_config(path: Path | None = None) -> LivingADRConfig:
    """Load, parse, and validate the LivingADR config into a typed snapshot.

    Raises :class:`ConfigStartupError` on any missing-file, YAML-parse, or
    model-validation failure.
    """

    resolved = resolve_config_path(path)

    try:
        raw_text = resolved.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigStartupError(
            f"Config file not found: {resolved}. Set {CONFIG_ENV_VAR} or create "
            f"{DEFAULT_CONFIG_FILENAME} (see living-adr.config.example.yaml)."
        ) from exc
    except OSError as exc:  # pragma: no cover - defensive
        raise ConfigStartupError(
            f"Could not read config file {resolved}: {exc}"
        ) from exc

    try:
        parsed = yaml.safe_load(raw_text)
    except yaml.YAMLError as exc:
        raise ConfigStartupError(
            f"Could not parse YAML config {resolved}: {exc}"
        ) from exc

    if not isinstance(parsed, dict):
        raise ConfigStartupError(
            f"Config file {resolved} must contain a top-level mapping with a "
            f"'repositories' list; got {type(parsed).__name__}."
        )

    try:
        return LivingADRConfig(**parsed)
    except ValidationError as exc:
        raise ConfigStartupError(_format_validation_error(resolved, exc)) from exc
    except TypeError as exc:
        raise ConfigStartupError(
            f"Config file {resolved} has unexpected top-level keys: {exc}"
        ) from exc


@dataclass(frozen=True)
class StartupResult:
    """Outcome of a startup config load: ready flag, snapshot, and error text."""

    ready: bool
    config: LivingADRConfig | None
    error: str | None


def evaluate_config_startup(path: Path | None = None) -> StartupResult:
    """Load config without raising, reporting readiness for startup checks.

    A deployable is *not ready* when configuration is missing or invalid.
    """

    try:
        config = load_living_adr_config(path)
    except ConfigStartupError as exc:
        return StartupResult(ready=False, config=None, error=str(exc))
    return StartupResult(ready=True, config=config, error=None)
