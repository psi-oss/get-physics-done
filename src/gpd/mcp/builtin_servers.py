"""Built-in MCP server definitions for GPD install, session launch, and release descriptors.

Provides the canonical registry of GPD's built-in MCP servers. Used by:
- Adapter install flow (_configure_runtime)
- Session launch (build_mcp_config_file)
- Public infra descriptor generation (infra/gpd-*.json)
"""

from __future__ import annotations

import logging
import os
import re
import subprocess
import sys
from copy import deepcopy

from gpd.mcp.verification_contract_policy import verification_server_description

logger = logging.getLogger(__name__)

_PYTHON_COMMAND_SENTINEL = "__GPD_PYTHON__"
_PUBLIC_PYTHON_PLACEHOLDER = "${GPD_PYTHON}"
_PYTHON_LAUNCH_NOTES = (
    f"Replace `{_PUBLIC_PYTHON_PLACEHOLDER}` with a Python >=3.11 interpreter that has GPD installed."
)

# Canonical definition of all GPD built-in MCP servers.
# Mirrors infra/*.json but lives inside the package so it ships with the wheel.
_ServerDef = dict[str, str | list[str] | dict[str, str] | bool]

_BUILTIN_SERVERS: dict[str, _ServerDef] = {
    "gpd-conventions": {
        "command": _PYTHON_COMMAND_SENTINEL,
        "args": ["-m", "gpd.mcp.servers.conventions_server"],
        "env": {"LOG_LEVEL": "${LOG_LEVEL:-WARNING}"},
    },
    "gpd-errors": {
        "command": _PYTHON_COMMAND_SENTINEL,
        "args": ["-m", "gpd.mcp.servers.errors_mcp"],
        "env": {"LOG_LEVEL": "${LOG_LEVEL:-WARNING}"},
    },
    "gpd-patterns": {
        "command": _PYTHON_COMMAND_SENTINEL,
        "args": ["-m", "gpd.mcp.servers.patterns_server"],
        "env": {"LOG_LEVEL": "${LOG_LEVEL:-WARNING}"},
    },
    "gpd-protocols": {
        "command": _PYTHON_COMMAND_SENTINEL,
        "args": ["-m", "gpd.mcp.servers.protocols_server"],
        "env": {"LOG_LEVEL": "${LOG_LEVEL:-WARNING}"},
    },
    "gpd-skills": {
        "command": _PYTHON_COMMAND_SENTINEL,
        "args": ["-m", "gpd.mcp.servers.skills_server"],
        "env": {"LOG_LEVEL": "${LOG_LEVEL:-WARNING}"},
    },
    "gpd-state": {
        "command": _PYTHON_COMMAND_SENTINEL,
        "args": ["-m", "gpd.mcp.servers.state_server"],
        "env": {"LOG_LEVEL": "${LOG_LEVEL:-WARNING}"},
    },
    "gpd-verification": {
        "command": _PYTHON_COMMAND_SENTINEL,
        "args": ["-m", "gpd.mcp.servers.verification_server"],
        "env": {"LOG_LEVEL": "${LOG_LEVEL:-WARNING}"},
    },
    "gpd-arxiv": {
        "command": _PYTHON_COMMAND_SENTINEL,
        "args": ["-m", "gpd.mcp.servers.arxiv_bridge"],
        "env": {},
        "optional": True,
        "module_check": "arxiv_mcp_server",
    },
}

_PUBLIC_BOOTSTRAP_PREREQUISITE = "Install GPD before enabling built-in MCP servers."
_ENTRY_POINT_NOTES = _PYTHON_LAUNCH_NOTES

_PUBLIC_DESCRIPTOR_METADATA: dict[str, dict[str, object]] = {
    "gpd-conventions": {
        "description": (
            "GPD convention lock management. Tools for querying, setting, validating, and comparing "
            "physics conventions across research phases, including ASSERT_CONVENTION validation. "
            "Every derivation artifact must carry at least one ASSERT_CONVENTION header that matches "
            "the project convention lock."
        ),
        "capabilities": [
            "convention_lock_status",
            "convention_set",
            "convention_check",
            "convention_diff",
            "assert_convention_validate",
            "subfield_defaults",
        ],
        "registry_prefix": "gpd_conventions",
        "health_check": {
            "tool": "subfield_defaults",
            "input": {"domain": "qft"},
            "expect": "contains metric_signature",
        },
    },
    "gpd-errors": {
        "description": (
            "LLM physics error catalog and traceability matrix for GPD verification. "
            "104 error classes with detection strategies mapped to 8 verification check categories."
        ),
        "capabilities": [
            "get_error_class",
            "check_error_classes",
            "get_detection_strategy",
            "get_traceability",
            "list_error_classes",
        ],
        "registry_prefix": "gpd_errors",
        "health_check": {
            "tool": "list_error_classes",
            "input": {},
            "expect": "count >= 100 error classes loaded",
        },
    },
    "gpd-patterns": {
        "description": (
            "GPD cross-project pattern library. Tools for searching, adding, promoting, "
            "and seeding physics error patterns across research projects."
        ),
        "capabilities": [
            "lookup_pattern",
            "add_pattern",
            "promote_pattern",
            "seed_patterns",
            "list_domains",
        ],
        "registry_prefix": "gpd_patterns",
        "health_check": {
            "tool": "list_domains",
            "input": {},
            "expect": "contains qft",
        },
    },
    "gpd-protocols": {
        "description": (
            "Physics computation protocols for GPD research workflows. Provides step-by-step methodology, "
            "verification checkpoints, and auto-routing across the live protocol catalog. Use them as rigor-first "
            "procedural guidance; do not invent missing evidence, artifacts, or completion state."
        ),
        "capabilities": [
            "get_protocol",
            "list_protocols",
            "route_protocol",
            "get_protocol_checkpoints",
        ],
        "registry_prefix": "gpd_protocols",
        "health_check": {
            "tool": "list_protocols",
            "input": {},
            "expect": "count >= 40 protocols loaded",
        },
    },
    "gpd-skills": {
        "description": (
            "GPD skill discovery and routing. Tools for listing, retrieving, auto-routing, "
            "and indexing GPD workflow skills for agent prompt injection. Treat missing evidence or artifacts as "
            "missing, blocked, failed, or inconclusive; never fabricate fallback outputs."
        ),
        "capabilities": [
            "list_skills",
            "get_skill",
            "route_skill",
            "get_skill_index",
        ],
        "registry_prefix": "gpd_skills",
        "health_check": {
            "tool": "list_skills",
            "input": {},
            "expect": "contains gpd-execute-phase and gpd-research-phase",
        },
    },
    "gpd-state": {
        "description": (
            "GPD project state management. Tools for querying state, phase info, progress, "
            "validation, health checks, and configuration."
        ),
        "capabilities": [
            "get_state",
            "get_phase_info",
            "advance_plan",
            "get_progress",
            "validate_state",
            "run_health_check",
            "get_config",
        ],
        "registry_prefix": "gpd_state",
        "health_check": {
            "tool": "get_state",
            "input": {},
            "expect": "returns a stable validation error envelope for missing required project_dir",
        },
    },
    "gpd-verification": {
        "description": verification_server_description(),
        "capabilities": [
            "run_check",
            "run_contract_check",
            "suggest_contract_checks",
            "get_checklist",
            "get_bundle_checklist",
            "dimensional_check",
            "limiting_case_check",
            "symmetry_check",
            "get_verification_coverage",
        ],
        "registry_prefix": "gpd_verification",
        "health_check": {
            "tool": "get_checklist",
            "input": {"domain": "qft"},
            "expect": "contains Ward identities",
        },
    },
    "gpd-arxiv": {
        "description": (
            "Optional/conditional arXiv paper search, retrieval, and source-archive download via arxiv-mcp-server. "
            "Available only when the optional arxiv-mcp-server dependency is installed; "
            "search for physics papers, fetch abstracts, download full text, and download raw source archives."
        ),
        "capabilities": [
            "search_papers",
            "download_paper",
            "list_papers",
            "read_paper",
            "download_source",
        ],
        "registry_prefix": "gpd_arxiv",
        "health_check": {
            "tool": "search_papers",
            "input": {"query": "quantum field theory", "max_results": 1},
            "expect": "contains paper",
        },
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


def _is_module_available(module_name: str, *, python_path: str | None = None) -> bool:
    """Check if a Python module is importable in a specific interpreter."""
    interpreter = python_path or sys.executable
    try:
        return subprocess.run(
            [
                interpreter,
                "-c",
                "import importlib.util, sys; sys.exit(0 if importlib.util.find_spec(sys.argv[1]) is not None else 1)",
                module_name,
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        ).returncode == 0
    except (FileNotFoundError, ModuleNotFoundError, OSError, ValueError):
        return False


def _build_public_alternatives(name: str) -> dict[str, dict[str, object]] | None:
    """Build fallback launch alternatives for a public built-in server descriptor."""
    if not name.startswith("gpd-"):
        return None
    raw = _BUILTIN_SERVERS[name]
    args = list(raw.get("args", [])) if isinstance(raw.get("args"), list) else []
    return {
        "python_module": {
            "command": _PUBLIC_PYTHON_PLACEHOLDER,
            "args": args,
            "notes": _ENTRY_POINT_NOTES,
        }
    }


def build_public_descriptor(name: str) -> dict[str, object]:
    """Build the canonical public infra descriptor for a built-in MCP server."""
    raw = _BUILTIN_SERVERS[name]
    metadata = _PUBLIC_DESCRIPTOR_METADATA[name]
    default_args = list(raw.get("args", [])) if isinstance(raw.get("args"), list) else []
    env = dict(raw.get("env", {})) if isinstance(raw.get("env"), dict) else {}
    command = str(raw["command"])
    args = default_args
    if name.startswith("gpd-"):
        command = f"gpd-mcp-{name.removeprefix('gpd-')}"
        args = []
    elif command == _PYTHON_COMMAND_SENTINEL:
        command = _PUBLIC_PYTHON_PLACEHOLDER
    descriptor: dict[str, object] = {
        "name": name,
        "description": str(metadata["description"]),
        "transport": "stdio",
        "command": command,
        "args": args,
        "env": env,
        "capabilities": list(metadata["capabilities"]) if isinstance(metadata["capabilities"], list) else [],
        "registry_prefix": str(metadata["registry_prefix"]),
        "prerequisites": list(metadata.get("prerequisites", [_PUBLIC_BOOTSTRAP_PREREQUISITE])),
        "health_check": dict(metadata["health_check"]) if isinstance(metadata["health_check"], dict) else {},
    }
    alternatives = _build_public_alternatives(name)
    if alternatives:
        descriptor["alternatives"] = alternatives
    if raw.get("optional"):
        descriptor["optional"] = True
        descriptor["availability"] = "conditional"
        module_check = raw.get("module_check")
        if isinstance(module_check, str) and module_check:
            descriptor["availability_condition"] = (
                f"Available only when the optional Python module '{module_check}' is installed."
            )
    if command == _PUBLIC_PYTHON_PLACEHOLDER:
        descriptor["notes"] = _PYTHON_LAUNCH_NOTES
    return descriptor


def build_public_descriptors() -> dict[str, dict[str, object]]:
    """Build canonical public infra descriptors for all built-in MCP servers."""
    return {name: build_public_descriptor(name) for name in _BUILTIN_SERVERS}


def merge_managed_mcp_entry(
    existing_entry: object,
    managed_entry: dict[str, object],
    *,
    merge_mapping_keys: frozenset[str] = frozenset(),
) -> dict[str, object]:
    """Merge a managed MCP entry into an existing runtime config entry.

    Managed scalar fields overwrite the existing entry so reinstall can keep
    the runtime launch command current. Mapping fields like ``env`` can be
    merged instead, with existing values taking precedence so user overrides
    survive reinstalls.
    """

    merged: dict[str, object] = {}
    if isinstance(existing_entry, dict):
        merged = {str(key): deepcopy(value) for key, value in existing_entry.items()}

    for key, managed_value in managed_entry.items():
        if key in merge_mapping_keys and isinstance(managed_value, dict):
            existing_value = merged.get(key)
            merged_mapping = {str(subkey): deepcopy(subvalue) for subkey, subvalue in managed_value.items()}
            if isinstance(existing_value, dict):
                for subkey, subvalue in existing_value.items():
                    merged_mapping[str(subkey)] = deepcopy(subvalue)
            if merged_mapping:
                merged[key] = merged_mapping
            else:
                merged.pop(key, None)
            continue

        merged[key] = deepcopy(managed_value)

    return merged


def merge_managed_mcp_servers(
    existing_servers: object,
    managed_servers: dict[str, dict[str, object]],
    *,
    merge_mapping_keys: frozenset[str] = frozenset({"env"}),
) -> dict[str, dict[str, object]]:
    """Merge managed GPD MCP entries into a runtime config mapping."""

    existing_map = existing_servers if isinstance(existing_servers, dict) else {}
    merged_servers: dict[str, dict[str, object]] = {}

    for name, entry in existing_map.items():
        if isinstance(entry, dict):
            merged_servers[str(name)] = {str(key): deepcopy(value) for key, value in entry.items()}

    for name, managed_entry in managed_servers.items():
        merged_servers[name] = merge_managed_mcp_entry(
            existing_map.get(name) if isinstance(existing_map, dict) else None,
            managed_entry,
            merge_mapping_keys=merge_mapping_keys,
        )

    return merged_servers


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
            if not module_check or not _is_module_available(module_check, python_path=python_path):
                continue

        cmd = str(raw["command"])
        if cmd == _PYTHON_COMMAND_SENTINEL:
            cmd = python_path

        raw_args = raw.get("args", [])
        args_list: list[str] = list(raw_args) if isinstance(raw_args, list) else []
        resolved_args = [_resolve_env(str(a)) for a in args_list]
        if any(_UNRESOLVED_RE.search(a) for a in resolved_args):
            logger.debug("Skipping server %s: unresolved env vars in args", name)
            continue

        entry: dict[str, object] = {"command": cmd, "args": resolved_args}

        raw_env = raw.get("env", {})
        if isinstance(raw_env, dict) and raw_env:
            resolved_env = {k: _resolve_env(str(v)) for k, v in raw_env.items()}
            if any(_UNRESOLVED_RE.search(v) for v in resolved_env.values()):
                logger.debug("Skipping server %s: unresolved env vars in env", name)
                continue
            entry["env"] = resolved_env

        servers[name] = entry

    return servers
