"""MCP source config loader with env var resolution.

Loads MCP source configuration from YAML files, resolving ${VAR} and
${VAR:-default} environment variable references. Falls back to sensible
defaults when no config file exists.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

import yaml

from gpd.mcp.config import MCP_SOURCES_PATH
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


def _resolve_config_values(config: dict[str, object]) -> dict[str, object]:
    """Recursively walk a dict, applying resolve_env_vars to all string values.

    Returns a new dict (does not mutate the input).
    """
    resolved: dict[str, object] = {}
    for key, value in config.items():
        if isinstance(value, str):
            resolved[key] = resolve_env_vars(value)
        elif isinstance(value, dict):
            resolved[key] = _resolve_config_values(value)
        elif isinstance(value, list):
            resolved[key] = [
                _resolve_config_values(item)
                if isinstance(item, dict)
                else resolve_env_vars(item)
                if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            resolved[key] = value
    return resolved


def load_sources_config(config_path: Path | None = None) -> MCPSourcesConfig:
    """Load MCP sources configuration from YAML.

    Args:
        config_path: Path to YAML config file. Defaults to MCP_SOURCES_PATH.

    Returns:
        Parsed MCPSourcesConfig. Falls back to default config if the file
        does not exist or cannot be parsed.
    """
    path = config_path if config_path is not None else MCP_SOURCES_PATH

    if not path.exists():
        return get_default_config()

    try:
        with open(path) as f:
            raw = yaml.safe_load(f)
    except (OSError, yaml.YAMLError) as exc:
        logger.warning("Failed to parse MCP sources config at %s: %s", path, exc)
        return get_default_config()

    if not isinstance(raw, dict):
        logger.warning("MCP sources config at %s is not a dict, using defaults", path)
        return get_default_config()

    resolved = _resolve_config_values(raw)

    version = str(resolved.get("version", "1.0.0"))
    if not version.startswith("1."):
        logger.warning("Unsupported MCP sources config version %s (expected 1.x), using defaults", version)
        return get_default_config()

    return MCPSourcesConfig.model_validate(resolved)


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


def write_default_config(config_path: Path) -> None:
    """Write the default config as YAML to the given path.

    Includes comments explaining each section. Only called if the user
    explicitly requests config generation (not called automatically).
    """
    content = """\
# GPD+ MCP Sources Configuration
# Defines where GPD+ discovers MCP tools from.
#
# Environment variables: use ${VAR_NAME} or ${VAR_NAME:-default} syntax.
# Resolved from os.environ at load time.

version: "1.0.0"

sources:
  # Modal-deployed physics simulators (primary source, 100+ physics MCPs)
  gpd-modal:
    type: modal
    app_name: "gpd-mcp-servers"
    env: "${MCP_BUILDER_MODAL_ENV:-dev}"
    registry: "gpd-mcp-shared"
    reconcile: true  # Check Modal deployment status

  # External MCP endpoints (non-Modal services)
  external:
    type: external
    services_file: "${GPD_ROOT}/infra/mcp/registry/external_services.yaml"

  # Local MCP servers (stdio transport)
  local:
    type: local
    configs:
      - lean4
      - sympy
      - wolfram
      - paper-search
      - sagemath
      - code-execution
"""
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content)
