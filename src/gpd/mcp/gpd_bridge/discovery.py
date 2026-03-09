"""GPD installation discovery and command/agent/workflow enumeration."""

from __future__ import annotations

import os
from pathlib import Path

GPD_COMMAND_DIR = "commands/gpd"
"""Relative path to GPD slash-command markdown files."""

GPD_AGENT_PREFIX = "gpd-"
"""Filename prefix for GPD agent profiles in the agents/ directory."""

GPD_CORE_DIR = "get-physics-done"
"""Core GPD directory containing package.json, workflows, and bin/."""


def find_gpd_install() -> Path | None:
    """Locate the GPD installation directory.

    Search order:
      1. Project-local: ``Path.cwd() / ".claude"``
      2. ``CLAUDE_CONFIG_DIR`` environment variable (if set)
      3. Global: ``Path.home() / ".claude"``

    Returns the first path where ``GPD_CORE_DIR/package.json`` exists,
    or ``None`` if GPD is not found.
    """
    candidates: list[Path] = [Path.cwd() / ".claude"]

    config_dir = os.environ.get("CLAUDE_CONFIG_DIR", "")
    if config_dir:
        candidates.append(Path(config_dir))

    candidates.append(Path.home() / ".claude")

    for candidate in candidates:
        pkg_json = candidate / GPD_CORE_DIR / "package.json"
        if pkg_json.exists():
            return candidate

    return None


def find_gpd_references_dir() -> Path | None:
    """Locate the GPD references directory (``get-physics-done/references/``).

    Uses :func:`find_gpd_install` to locate the ``.claude`` root, then
    returns the ``references/`` subdirectory if it exists.
    """
    gpd_dir = find_gpd_install()
    if gpd_dir is None:
        return None
    refs = gpd_dir / GPD_CORE_DIR / "references"
    return refs if refs.is_dir() else None


def discover_commands(gpd_dir: Path) -> list[Path]:
    """Return all ``.md`` files in the GPD commands directory.

    These are the GPD slash-command markdown files consumed by Claude Code.
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
