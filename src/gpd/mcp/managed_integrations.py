"""Shared managed optional MCP integrations.

The registry is intentionally small in v1: a single logical `wolfram`
integration that can be projected into runtime-specific MCP config later
without exposing runtime-specific fields at the capability layer.
"""

from __future__ import annotations

import json
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from gpd.core.constants import ProjectLayout
from gpd.core.root_resolution import resolve_project_root

WOLFRAM_INTEGRATION_ID = "wolfram"
WOLFRAM_MANAGED_SERVER_KEY = "gpd-wolfram"
WOLFRAM_BRIDGE_COMMAND = "gpd-mcp-wolfram"
WOLFRAM_MCP_API_KEY_ENV_VAR = "GPD_WOLFRAM_MCP_API_KEY"
WOLFRAM_MCP_ENDPOINT_ENV_VAR = "GPD_WOLFRAM_MCP_ENDPOINT"
WOLFRAM_MCP_DEFAULT_ENDPOINT = "https://services.wolfram.com/api/mcp"
INTEGRATIONS_CONFIG_FILENAME = "integrations.json"


def _project_integrations_config_path(cwd: Path) -> Path:
    workspace_cwd = cwd.expanduser().resolve(strict=False)
    project_root = resolve_project_root(workspace_cwd, require_layout=True)
    return ProjectLayout(project_root or workspace_cwd).gpd / INTEGRATIONS_CONFIG_FILENAME


def _strict_unknown_keys_error(*, section: str, unknown_keys: list[str], supported_keys: list[str]) -> RuntimeError:
    joined_unknown = ", ".join(unknown_keys)
    joined_supported = ", ".join(supported_keys)
    return RuntimeError(f"{section} contains unsupported keys: {joined_unknown}; supported keys are {joined_supported}")


def _load_project_integrations_payload(cwd: Path) -> dict[str, object]:
    config_path = _project_integrations_config_path(cwd)
    try:
        raw_text = config_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except OSError as exc:
        raise RuntimeError(f"Cannot read integrations config: {exc}") from exc

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Malformed integrations config: {exc}. Fix or delete {config_path.name}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("integrations config must be a JSON object")
    unknown_keys = sorted(str(key) for key in payload if str(key) not in MANAGED_INTEGRATIONS)
    if unknown_keys:
        raise _strict_unknown_keys_error(
            section="integrations config",
            unknown_keys=unknown_keys,
            supported_keys=sorted(MANAGED_INTEGRATIONS),
        )
    return payload


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

    @property
    def api_key_env_vars(self) -> tuple[str, ...]:
        return (self.api_key_env_var,)

    def project_config_path(self, cwd: Path) -> Path:
        return _project_integrations_config_path(cwd)

    def project_payload(self, cwd: Path | None = None) -> dict[str, object]:
        if cwd is None:
            return {}
        return _load_project_integrations_payload(cwd)

    def project_record(self, cwd: Path | None = None, *, strict: bool = False) -> dict[str, object] | None:
        if cwd is None:
            return None
        payload = self.project_payload(cwd)
        raw = payload.get(self.integration_id)
        if raw is None:
            return None
        if not isinstance(raw, dict):
            raise RuntimeError(f"integrations.{self.integration_id} must be a JSON object")
        unknown_keys = sorted(str(key) for key in raw if str(key) not in {"enabled", "endpoint"})
        if unknown_keys:
            raise _strict_unknown_keys_error(
                section=f"integrations.{self.integration_id}",
                unknown_keys=unknown_keys,
                supported_keys=["enabled", "endpoint"],
            )

        record: dict[str, object] = {}
        if "enabled" in raw:
            enabled = raw.get("enabled")
            if not isinstance(enabled, bool):
                raise RuntimeError(f"integrations.{self.integration_id}.enabled must be a boolean")
            record["enabled"] = enabled
        if "endpoint" in raw:
            endpoint = raw.get("endpoint")
            if not isinstance(endpoint, str) or not endpoint.strip():
                raise RuntimeError(f"integrations.{self.integration_id}.endpoint must be a non-empty string")
            record["endpoint"] = endpoint.strip()
        return record

    def project_enabled(self, cwd: Path | None = None, *, strict: bool = False) -> bool:
        record = self.project_record(cwd, strict=strict)
        if record is None:
            return True
        enabled = record.get("enabled")
        return enabled if isinstance(enabled, bool) else True

    def resolved_endpoint(
        self,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
        *,
        strict: bool = False,
    ) -> str:
        record = self.project_record(cwd, strict=strict)
        if record is not None:
            endpoint = record.get("endpoint")
            if isinstance(endpoint, str) and endpoint:
                return endpoint
        env_source = self._env(env)
        if self.endpoint_env_var in env_source:
            raw_value = env_source.get(self.endpoint_env_var, "")
            cleaned = raw_value.strip() if isinstance(raw_value, str) else ""
            if not cleaned:
                raise RuntimeError(f"{self.endpoint_env_var} is set but empty")
            return cleaned
        return self.default_endpoint

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

    def is_configured(
        self,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
        *,
        strict: bool = False,
    ) -> bool:
        if not self.project_enabled(cwd, strict=strict):
            return False
        return self.api_key_present(env)

    def projected_environment(
        self,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
        *,
        strict: bool = False,
    ) -> dict[str, str]:
        endpoint = self.resolved_endpoint(env, cwd=cwd, strict=strict)
        if endpoint == self.default_endpoint:
            return {}
        return {self.endpoint_env_var: endpoint}

    def projected_server_entry(
        self,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
        *,
        strict: bool = False,
    ) -> dict[str, object]:
        entry: dict[str, object] = {
            "command": self.bridge_command,
            "args": [],
        }
        projected_env = self.projected_environment(env, cwd=cwd, strict=strict)
        if projected_env:
            entry["env"] = projected_env
        return entry

    def config_summary(
        self,
        env: Mapping[str, str] | None = None,
        cwd: Path | None = None,
        *,
        strict: bool = False,
    ) -> dict[str, object]:
        record = self.project_record(cwd, strict=strict)
        return {
            "integration_id": self.integration_id,
            "managed_server_key": self.managed_server_key,
            "bridge_command": self.bridge_command,
            "api_key_env_var": self.api_key_env_var,
            "api_key_env_vars": list(self.api_key_env_vars),
            "endpoint_env_var": self.endpoint_env_var,
            "endpoint": self.resolved_endpoint(env, cwd=cwd, strict=strict),
            "projected_environment": self.projected_environment(env, cwd=cwd, strict=strict),
            "project_configured": record is not None,
            "enabled": self.project_enabled(cwd, strict=strict),
            "configured": self.is_configured(env, cwd=cwd, strict=strict),
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


def projected_managed_optional_mcp_servers(
    env: Mapping[str, str] | None = None,
    *,
    cwd: Path | None = None,
    strict: bool = False,
) -> dict[str, dict[str, object]]:
    """Project all configured optional managed integrations into MCP server entries."""

    managed_servers: dict[str, dict[str, object]] = {}
    for integration in MANAGED_INTEGRATIONS.values():
        if not integration.is_configured(env, cwd=cwd, strict=strict):
            continue
        managed_servers[integration.managed_server_key] = integration.projected_server_entry(
            env,
            cwd=cwd,
            strict=strict,
        )
    return managed_servers


def managed_optional_mcp_server_keys() -> frozenset[str]:
    """Return the registry-backed optional managed MCP server keys."""

    return frozenset(integration.managed_server_key for integration in MANAGED_INTEGRATIONS.values())
