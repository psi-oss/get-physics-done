"""Shared managed optional MCP integrations.

The registry is intentionally small in v1: a single logical `wolfram`
integration that can be projected into runtime-specific MCP config later
without exposing runtime-specific fields at the capability layer.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass

WOLFRAM_INTEGRATION_ID = "wolfram"
WOLFRAM_MANAGED_SERVER_KEY = "gpd-wolfram"
WOLFRAM_BRIDGE_COMMAND = "gpd-mcp-wolfram"
WOLFRAM_MCP_API_KEY_ENV_VAR = "GPD_WOLFRAM_MCP_API_KEY"
WOLFRAM_MCP_ENDPOINT_ENV_VAR = "GPD_WOLFRAM_MCP_ENDPOINT"
WOLFRAM_MCP_DEFAULT_ENDPOINT = "https://services.wolfram.com/api/mcp"


@dataclass(frozen=True, slots=True)
class ManagedIntegrationDescriptor:
    """Descriptor for one shared optional integration."""

    integration_id: str
    managed_server_key: str
    bridge_command: str
    api_key_env_var: str
    endpoint_env_var: str
    default_endpoint: str
    description: str

    def _env(self, env: Mapping[str, str] | None = None) -> Mapping[str, str]:
        return os.environ if env is None else env

    def resolved_endpoint(self, env: Mapping[str, str] | None = None) -> str:
        raw_value = self._env(env).get(self.endpoint_env_var, "")
        cleaned = raw_value.strip() if isinstance(raw_value, str) else ""
        return cleaned or self.default_endpoint

    def api_key_present(self, env: Mapping[str, str] | None = None) -> bool:
        raw_value = self._env(env).get(self.api_key_env_var, "")
        return bool(raw_value and str(raw_value).strip())

    def is_configured(self, env: Mapping[str, str] | None = None) -> bool:
        return self.api_key_present(env)

    def config_summary(self, env: Mapping[str, str] | None = None) -> dict[str, object]:
        return {
            "integration_id": self.integration_id,
            "managed_server_key": self.managed_server_key,
            "bridge_command": self.bridge_command,
            "api_key_env_var": self.api_key_env_var,
            "endpoint_env_var": self.endpoint_env_var,
            "endpoint": self.resolved_endpoint(env),
            "configured": self.is_configured(env),
        }


WOLFRAM_MANAGED_INTEGRATION = ManagedIntegrationDescriptor(
    integration_id=WOLFRAM_INTEGRATION_ID,
    managed_server_key=WOLFRAM_MANAGED_SERVER_KEY,
    bridge_command=WOLFRAM_BRIDGE_COMMAND,
    api_key_env_var=WOLFRAM_MCP_API_KEY_ENV_VAR,
    endpoint_env_var=WOLFRAM_MCP_ENDPOINT_ENV_VAR,
    default_endpoint=WOLFRAM_MCP_DEFAULT_ENDPOINT,
    description=(
        "Optional shared Wolfram MCP integration, projected as a local stdio bridge "
        "and configured through environment variables."
    ),
)

MANAGED_INTEGRATIONS: dict[str, ManagedIntegrationDescriptor] = {
    WOLFRAM_MANAGED_INTEGRATION.integration_id: WOLFRAM_MANAGED_INTEGRATION,
}


def get_managed_integration(integration_id: str) -> ManagedIntegrationDescriptor | None:
    """Return a managed integration descriptor by canonical id."""

    normalized = integration_id.strip().lower()
    return MANAGED_INTEGRATIONS.get(normalized)


def list_managed_integrations() -> dict[str, ManagedIntegrationDescriptor]:
    """Return the canonical managed integration registry."""

    return dict(MANAGED_INTEGRATIONS)

