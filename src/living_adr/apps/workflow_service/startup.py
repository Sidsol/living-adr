"""workflow-service startup config loading (feature 002).

Loads and validates the LivingADR configuration before the workflow service
becomes ready. Invalid config fails the process at startup rather than allowing
webhook ingestion or LangGraph orchestration to run against partial config.
"""

from __future__ import annotations

from living_adr.apps.startup_base import ConfigStartupBase


class WorkflowServiceStartup(ConfigStartupBase):
    """Validated config snapshot owned by the workflow-service entrypoint."""
