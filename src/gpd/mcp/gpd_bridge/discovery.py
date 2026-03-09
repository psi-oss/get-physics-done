"""GPD installation discovery and command/agent/workflow enumeration."""

from __future__ import annotations

import os
from pathlib import Path

GPD_COMMAND_DIR = "commands/gpd"
"""Relative path to GPD slash-command markdown files."""

GPD_AGENT_PREFIX = "gpd-"
"""Filename prefix for GPD agent profiles in the agents/ directory."""

GPD_CORE_DIR = "get-physics-done"
"""Core GPD directory containing version metadata, references, and workflows."""


def _has_gpd_install_marker(config_dir: Path) -> bool:
    """Return True when *config_dir* looks like a GPD runtime install root."""
    core_dir = config_dir / GPD_CORE_DIR
    if not core_dir.is_dir():
        return False

    if (core_dir / "VERSION").is_file():
        return True

    if (core_dir / "package.json").is_file():
        return True

    # Older or partially migrated installs may still be recognizable by content layout.
    return (core_dir / "references").is_dir() and (core_dir / "workflows").is_dir()


def find_gpd_install() -> Path | None:
    """Locate the GPD installation directory.

    Search order (for each runtime config dir: .claude, .codex, .gemini, .config/opencode):
      1. Project-local: ``Path.cwd() / <config_dir>``
      2. Runtime-specific env var (``CLAUDE_CONFIG_DIR``, etc.) if set
      3. Global: ``Path.home() / <config_dir>``

    Returns the first path where ``get-physics-done/`` has a supported
    install marker (``VERSION`` preferred, ``package.json`` fallback),
    or ``None`` if GPD is not found.
    """
    from gpd.hooks.runtime_detect import RUNTIME_DIR_NAMES

    # Collect candidates across all supported runtimes
    candidates: list[Path] = []
    for dir_name in RUNTIME_DIR_NAMES.values():
        candidates.append(Path.cwd() / dir_name)

    # Check runtime-specific config dir env vars
    for env_var in ("CLAUDE_CONFIG_DIR", "CODEX_CONFIG_DIR", "GEMINI_CONFIG_DIR", "OPENCODE_CONFIG_DIR"):
        config_dir = os.environ.get(env_var, "")
        if config_dir:
            candidates.append(Path(config_dir))

    for dir_name in RUNTIME_DIR_NAMES.values():
        candidates.append(Path.home() / dir_name)

    for candidate in candidates:
        if _has_gpd_install_marker(candidate):
            return candidate

    return None


def find_gpd_references_dir() -> Path | None:
    """Locate the GPD references directory (``get-physics-done/references/``).

    Uses :func:`find_gpd_install` to locate the runtime config root, then
    returns the ``references/`` subdirectory if it exists.
    """
    gpd_dir = find_gpd_install()
    if gpd_dir is None:
        return None
    refs = gpd_dir / GPD_CORE_DIR / "references"
    return refs if refs.is_dir() else None


def discover_commands(gpd_dir: Path) -> list[Path]:
    """Return all ``.md`` files in the GPD commands directory.

    These are the GPD slash-command markdown files consumed by the hosting runtime.
    """
    cmd_dir = gpd_dir / GPD_COMMAND_DIR
    if not cmd_dir.is_dir():
        return []
    return sorted(cmd_dir.glob("*.md"))


def discover_agents(gpd_dir: Path) -> list[Path]:
    """Return all ``.md`` files matching the ``gpd-*.md`` prefix in agents/.

    These are GPD agent profile files. Non-GPD agents (without the
    ``gpd-`` prefix) are excluded.
    """
    agents_dir = gpd_dir / "agents"
    if not agents_dir.is_dir():
        return []
    return sorted(agents_dir.glob(f"{GPD_AGENT_PREFIX}*.md"))


def discover_workflows(gpd_dir: Path) -> list[Path]:
    """Return all ``.md`` files in the GPD workflows directory."""
    workflows_dir = gpd_dir / GPD_CORE_DIR / "workflows"
    if not workflows_dir.is_dir():
        return []
    return sorted(workflows_dir.glob("*.md"))
