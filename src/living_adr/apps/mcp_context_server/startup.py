"""mcp-context-server startup config loading (feature 002).

Loads and validates the LivingADR configuration before the MCP context server
registers or serves any tools/resources. Invalid config fails startup so the
read-only context surface never serves traffic with partial configuration.
"""

from __future__ import annotations

from living_adr.apps.startup_base import ConfigStartupBase


class McpContextServerStartup(ConfigStartupBase):
    """Validated config snapshot owned by the mcp-context-server entrypoint."""
