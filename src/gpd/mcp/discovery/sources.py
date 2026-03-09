"""MCP source config: hardcoded defaults.

Returns a sensible default MCPSourcesConfig. The previous YAML config-file
loader was dead code (no config file is ever created), so it has been removed.
"""

from __future__ import annotations

import logging
import os
import re

from gpd.mcp.discovery.models import MCPSourcesConfig, SourceConfig

logger = logging.getLogger(__name__)

_ENV_VAR_PATTERN = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")


def resolve_env_vars(value: str) -> str:
    """Replace ${VAR_NAME} and ${VAR_NAME:-default} patterns with env values.

    If VAR_NAME is not found and no default is provided, the placeholder
    is left as-is (tools may not need every env var at discovery time).
    """

    def _replace(match: re.Match[str]) -> str:
        var_name = match.group(1)
        default = match.group(2)
        env_val = os.environ.get(var_name)
        if env_val is not None:
            return env_val
        if default is not None:
            return default
        return match.group(0)

    return _ENV_VAR_PATTERN.sub(_replace, value)


def load_sources_config() -> MCPSourcesConfig:
    """Return the default MCP sources configuration."""
    return get_default_config()


def get_default_config() -> MCPSourcesConfig:
    """Return a sensible default MCPSourcesConfig with three sources.

    - gpd-modal: Modal-deployed physics simulators
    - external: External services from registry YAML
    - local: Local MCP servers (stdio transport)
    """
    return MCPSourcesConfig(
        version="1.0.0",
        sources={
            "gpd-modal": SourceConfig(
                type="modal",
                app_name="gpd-mcp-servers",
                reconcile=True,
            ),
            "external": SourceConfig(
                type="external",
                services_file="${GPD_ROOT}/infra/mcp/registry/external_services.yaml",
            ),
            "local": SourceConfig(
                type="local",
                configs=["lean4", "sympy", "wolfram", "paper-search", "sagemath", "code-execution"],
            ),
        },
    )
