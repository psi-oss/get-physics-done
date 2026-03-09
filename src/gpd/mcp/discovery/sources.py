"""MCP source config: hardcoded defaults.

Returns a sensible default MCPSourcesConfig. The previous YAML config-file
loader was dead code (no config file is ever created), so it has been removed.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

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


def resolve_project_root(project_root: Path | None = None) -> Path | None:
    """Resolve the project root from explicit input, env, or nearby manifests."""
    if project_root is not None:
        return project_root

    env_root = os.environ.get("GPD_ROOT")
    if env_root:
        return Path(env_root).expanduser()

    from gpd.utils.paths import find_project_root

    inferred_root = find_project_root()
    if inferred_root is not None:
        return inferred_root

    for start in (Path.cwd(), Path(__file__).resolve()):
        for parent in (start, *start.parents):
            if (parent / "pyproject.toml").exists() or (parent / ".git").exists():
                return parent

    return None


def resolve_source_path(path_value: str, project_root: Path | None = None) -> Path | None:
    """Resolve a configured source path with env substitution and project-root fallback."""
    resolved = resolve_env_vars(path_value).strip()
    if not resolved:
        return None
    if "${" in resolved:
        logger.warning("Skipping source path with unresolved env vars: %s", path_value)
        return None

    path = Path(resolved).expanduser()
    if not path.is_absolute():
        root = resolve_project_root(project_root)
        if root is None:
            logger.warning("Could not resolve project root for source path: %s", path_value)
            return None
        path = root / path

    return path.resolve()


def load_external_services_file(path_value: str, project_root: Path | None = None) -> dict[str, dict[str, object]]:
    """Load external services YAML from a resolved path or return an empty mapping."""
    path = resolve_source_path(path_value, project_root=project_root)
    if path is None:
        return {}
    if not path.exists():
        logger.info("External services file not found: %s", path)
        return {}

    import yaml

    try:
        raw_data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as exc:
        logger.warning("Failed to load external services file %s: %s", path, exc)
        return {}

    if not isinstance(raw_data, dict):
        logger.warning("External services file %s must contain a mapping", path)
        return {}

    services = raw_data.get("services", raw_data)
    if not isinstance(services, dict):
        logger.warning("External services file %s has non-mapping 'services' content", path)
        return {}

    normalized: dict[str, dict[str, object]] = {}
    for service_name, payload in services.items():
        if not isinstance(payload, dict):
            logger.warning("Skipping malformed external service entry %r in %s", service_name, path)
            continue
        normalized[str(service_name)] = payload
    return normalized


def get_default_config() -> MCPSourcesConfig:
    """Return the public default MCP sources configuration.

    The public release ships with local and external discovery enabled by
    default. Hosted Modal-backed sources remain opt-in via explicit config.
    """
    return MCPSourcesConfig(
        version="1.0.0",
        sources={
            "external": SourceConfig(
                type="external",
                services_file="${GPD_ROOT:-.}/infra/mcp/registry/external_services.yaml",
            ),
            "local": SourceConfig(
                type="local",
                configs=["lean4", "sympy", "wolfram", "paper-search", "sagemath", "code-execution"],
            ),
        },
    )
