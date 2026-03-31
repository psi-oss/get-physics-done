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
WOLFRAM_MCP_SERVICE_API_KEY_ENV_VAR = "WOLFRAM_MCP_SERVICE_API_KEY"
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
    api_key_env_aliases: tuple[str, ...] = ()

    def _env(self, env: Mapping[str, str] | None = None) -> Mapping[str, str]:
        return os.environ if env is None else env

    @property
    def api_key_env_vars(self) -> tuple[str, ...]:
        return (self.api_key_env_var, *self.api_key_env_aliases)

    def resolved_endpoint(self, env: Mapping[str, str] | None = None) -> str:
        raw_value = self._env(env).get(self.endpoint_env_var, "")
        cleaned = raw_value.strip() if isinstance(raw_value, str) else ""
        return cleaned or self.default_endpoint

    def resolve_api_key(self, env: Mapping[str, str] | None = None) -> str:
        source = self._env(env)
        for key in self.api_key_env_vars:
            raw_value = source.get(key, "")
            cleaned = raw_value.strip() if isinstance(raw_value, str) else ""
            if cleaned:
                return cleaned
        raise RuntimeError(
            "Wolfram MCP auth is not configured. Set "
            + " or ".join(self.api_key_env_vars)
            + "."
        )

    def api_key_present(self, env: Mapping[str, str] | None = None) -> bool:
        try:
            self.resolve_api_key(env)
        except RuntimeError:
            return False
        return True

    def is_configured(self, env: Mapping[str, str] | None = None) -> bool:
        return self.api_key_present(env)

    def projected_environment(self, env: Mapping[str, str] | None = None) -> dict[str, str]:
        endpoint = self.resolved_endpoint(env)
        if endpoint == self.default_endpoint:
            return {}
        return {self.endpoint_env_var: endpoint}

    def projected_server_entry(self, env: Mapping[str, str] | None = None) -> dict[str, object]:
        entry: dict[str, object] = {
            "command": self.bridge_command,
            "args": [],
        }
        projected_env = self.projected_environment(env)
        if projected_env:
            entry["env"] = projected_env
        return entry

    def config_summary(self, env: Mapping[str, str] | None = None) -> dict[str, object]:
        return {
            "integration_id": self.integration_id,
            "managed_server_key": self.managed_server_key,
            "bridge_command": self.bridge_command,
            "api_key_env_var": self.api_key_env_var,
            "api_key_env_vars": list(self.api_key_env_vars),
            "endpoint_env_var": self.endpoint_env_var,
            "endpoint": self.resolved_endpoint(env),
            "projected_environment": self.projected_environment(env),
            "configured": self.is_configured(env),
        }


WOLFRAM_MANAGED_INTEGRATION = ManagedIntegrationDescriptor(
    integration_id=WOLFRAM_INTEGRATION_ID,
    managed_server_key=WOLFRAM_MANAGED_SERVER_KEY,
    bridge_command=WOLFRAM_BRIDGE_COMMAND,
    api_key_env_var=WOLFRAM_MCP_API_KEY_ENV_VAR,
    endpoint_env_var=WOLFRAM_MCP_ENDPOINT_ENV_VAR,
    default_endpoint=WOLFRAM_MCP_DEFAULT_ENDPOINT,
    api_key_env_aliases=(WOLFRAM_MCP_SERVICE_API_KEY_ENV_VAR,),
    description=(
        "Optional shared Wolfram MCP integration, projected as a local stdio bridge "
        "and configured through environment variables."
    ),
)

MANAGED_INTEGRATIONS: dict[str, ManagedIntegrationDescriptor] = {
    WOLFRAM_MANAGED_INTEGRATION.integration_id: WOLFRAM_MANAGED_INTEGRATION,
}


def get_managed_integration(integration_id: object) -> ManagedIntegrationDescriptor | None:
    """Return a managed integration descriptor by canonical id."""

    if not isinstance(integration_id, str):
        return None
    normalized = integration_id.strip().lower()
    if not normalized:
        return None
    return MANAGED_INTEGRATIONS.get(normalized)


def list_managed_integrations() -> dict[str, ManagedIntegrationDescriptor]:
    """Return the canonical managed integration registry."""

    return dict(MANAGED_INTEGRATIONS)
