"""Shared startup config-snapshot base for both deployables (feature 002).

Both the workflow service and the MCP context server load the validated
:class:`~living_adr.core.config.LivingADRConfig` exactly once at startup and hold
it as an immutable snapshot. They fail fast (raise
:class:`~living_adr.core.config_loader.ConfigStartupError`) on invalid config so
neither process can become ready with partial configuration (US-1, US-4, FR-9).

Config is read once and injected; it is never re-parsed per request or per tool
call, which keeps lifecycle semantics restart-required (slice 4).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from living_adr.core.config import LivingADRConfig
from living_adr.core.config_loader import (
    ConfigStartupError,
    StartupResult,
    evaluate_config_startup,
)


@dataclass(frozen=True)
class ConfigStartupBase:
    """Immutable startup snapshot holding the validated config."""

    config: LivingADRConfig

    @property
    def ready(self) -> bool:
        """A constructed snapshot is, by definition, ready."""

        return True

    @classmethod
    def from_path(cls, path: Path | None = None) -> ConfigStartupBase:
        """Load + validate config, raising on failure (fail-fast startup)."""

        result = evaluate_config_startup(path)
        if not result.ready or result.config is None:
            raise ConfigStartupError(result.error or "configuration is invalid")
        return cls(config=result.config)

    @classmethod
    def evaluate(cls, path: Path | None = None) -> StartupResult:
        """Non-raising readiness probe over the config load."""

        return evaluate_config_startup(path)
