"""Built-in MCP server definitions for GPD install and session launch.

Provides the canonical registry of GPD's built-in MCP servers. Used by:
- Adapter install flow (_configure_runtime)
- Session launch (build_mcp_config_file)
"""

from __future__ import annotations

import os
import re
import sys


# Canonical definition of all GPD built-in MCP servers.
# Mirrors infra/*.json but lives inside the package so it ships with the wheel.
_ServerDef = dict[str, str | list[str] | dict[str, str] | bool]

_BUILTIN_SERVERS: dict[str, _ServerDef] = {
    "gpd-conventions": {
        "command": "python",
        "args": ["-m", "gpd.mcp.servers.conventions_server"],
        "env": {"LOG_LEVEL": "${LOG_LEVEL:-WARNING}"},
    },
    "gpd-errors": {
        "command": "python",
        "args": ["-m", "gpd.mcp.servers.errors_mcp"],
        "env": {"LOG_LEVEL": "${LOG_LEVEL:-WARNING}"},
    },
    "gpd-patterns": {
        "command": "python",
        "args": ["-m", "gpd.mcp.servers.patterns_server"],
        "env": {"LOG_LEVEL": "${LOG_LEVEL:-WARNING}"},
    },
    "gpd-protocols": {
        "command": "python",
        "args": ["-m", "gpd.mcp.servers.protocols_server"],
        "env": {"LOG_LEVEL": "${LOG_LEVEL:-WARNING}"},
    },
    "gpd-skills": {
        "command": "python",
        "args": ["-m", "gpd.mcp.servers.skills_server"],
        "env": {"LOG_LEVEL": "${LOG_LEVEL:-WARNING}"},
    },
    "gpd-state": {
        "command": "python",
        "args": ["-m", "gpd.mcp.servers.state_server"],
        "env": {"LOG_LEVEL": "${LOG_LEVEL:-WARNING}"},
    },
    "gpd-verification": {
        "command": "python",
        "args": ["-m", "gpd.mcp.servers.verification_server"],
        "env": {"LOG_LEVEL": "${LOG_LEVEL:-WARNING}"},
    },
    "gpd-arxiv": {
        "command": "python",
        "args": ["-m", "arxiv_mcp_server"],
        "env": {},
        "optional": True,
        "module_check": "arxiv_mcp_server",
    },
}

_UNRESOLVED_RE = re.compile(r"\$\{[^}]+\}")
_ENV_VAR_PATTERN = re.compile(r"\$\{([^}:]+)(?::-([^}]*))?\}")

# Keys that are GPD-managed and should be removed on uninstall.
GPD_MCP_SERVER_KEYS = frozenset(_BUILTIN_SERVERS.keys())


def _resolve_env(value: str) -> str:
    """Resolve ${VAR:-default} patterns in a string."""
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


def _is_module_available(module_name: str) -> bool:
    """Check if a Python module is importable without loading it."""
    from importlib.util import find_spec

    try:
        return find_spec(module_name) is not None
    except (ModuleNotFoundError, ValueError):
        return False


def build_mcp_servers_dict(
    *,
    python_path: str | None = None,
) -> dict[str, dict[str, object]]:
    """Build resolved mcpServers dict for all available built-in servers.

    Args:
        python_path: Python interpreter path. Defaults to sys.executable.

    Returns:
        Dict mapping server name to {command, args, env} entries suitable
        for writing into a runtime's mcpServers config.
    """
    if python_path is None:
        python_path = sys.executable

    servers: dict[str, dict[str, object]] = {}
    for name, raw in _BUILTIN_SERVERS.items():
        # Skip optional servers if their dependencies aren't installed.
        if raw.get("optional"):
            module_check = str(raw.get("module_check", ""))
            if not module_check or not _is_module_available(module_check):
                continue

        cmd = str(raw["command"])
        if cmd == "python":
            cmd = python_path

        raw_args = raw.get("args", [])
        args_list: list[str] = list(raw_args) if isinstance(raw_args, list) else []
        resolved_args = [_resolve_env(str(a)) for a in args_list]
        if any(_UNRESOLVED_RE.search(a) for a in resolved_args):
            continue

        entry: dict[str, object] = {"command": cmd, "args": resolved_args}

        raw_env = raw.get("env", {})
        if isinstance(raw_env, dict) and raw_env:
            resolved_env = {k: _resolve_env(str(v)) for k, v in raw_env.items()}
            if any(_UNRESOLVED_RE.search(v) for v in resolved_env.values()):
                continue
            entry["env"] = resolved_env

        servers[name] = entry

    return servers
