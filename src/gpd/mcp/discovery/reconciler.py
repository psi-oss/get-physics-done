"""Reconciliation helpers for MCP tool discovery.

Provides deployment status checks and tool reconciliation.  Modal-hosted
reconciliation is disabled (modal is not a dependency); the function
signature is preserved for compatibility with catalog.py.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from gpd.mcp.discovery.models import ToolEntry

logger = logging.getLogger(__name__)


def check_deployment_status(project_root: Path | None = None) -> set[str]:
    """Read the set of passing MCP names from deployment_status.json.

    Fast pre-filter: returns MCPs in the "passed" list. Treat this as a hint,
    not ground truth (the file may be stale).

    Args:
        project_root: Path to the project root. If None, attempts to infer
            from the current GPD checkout.

    Returns:
        Set of MCP names that appear in the "passed" list, or empty set
        if the file is not found or unreadable.
    """
    status_path = _resolve_deployment_status_path(project_root)
    if status_path is None or not status_path.exists():
        logger.warning("deployment_status.json not found, skipping fast pre-filter")
        return set()

    try:
        with open(status_path, encoding="utf-8") as f:
            data = json.load(f)
        passed = data.get("passed", [])
        return set(passed)
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        logger.warning("Failed to read deployment_status.json: %s", exc)
        return set()


def _resolve_deployment_status_path(project_root: Path | None) -> Path | None:
    """Resolve the path to deployment_status.json."""
    from gpd.mcp.discovery.sources import resolve_project_root

    resolved_root = resolve_project_root(project_root)
    if resolved_root is None:
        return None
    return resolved_root / "infra" / "mcp" / "deployment_status.json"


def reconcile_modal(
    tools: list[ToolEntry],
    app_name: str = "",
    max_workers: int = 5,
) -> list[ToolEntry]:
    """No-op: Modal reconciliation is disabled (modal is not a dependency).

    Returns the tools list unchanged.

    Args:
        tools: List of ToolEntry objects (returned as-is).
        app_name: Ignored (kept for API compatibility).
        max_workers: Ignored (kept for API compatibility).

    Returns:
        The same list of tools, unmodified.
    """
    logger.debug("reconcile_modal called but Modal is not a dependency; returning tools unchanged")
    return tools
