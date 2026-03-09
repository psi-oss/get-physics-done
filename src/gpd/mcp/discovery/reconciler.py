"""Modal reconciliation for MCP tool discovery.

Two-stage validation: fast pre-filter from deployment_status.json,
then parallel live checks via modal.Cls.from_name() for unconfirmed tools.
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from gpd.mcp.discovery.models import MCPStatus, ToolEntry

logger = logging.getLogger(__name__)


def check_deployment_status(psi_root: Path | None = None) -> set[str]:
    """Read the set of passing MCP names from deployment_status.json.

    Fast pre-filter: returns MCPs in the "passed" list. Treat this as a hint,
    not ground truth (the file may be stale).

    Args:
        psi_root: Path to the PSI project root. If None, attempts to infer
            from psi_mcp_shared or PSI_ROOT env var.

    Returns:
        Set of MCP names that appear in the "passed" list, or empty set
        if the file is not found or unreadable.
    """
    status_path = _resolve_deployment_status_path(psi_root)
    if status_path is None or not status_path.exists():
        logger.warning("deployment_status.json not found, skipping fast pre-filter")
        return set()

    try:
        with open(status_path) as f:
            data = json.load(f)
        passed = data.get("passed", [])
        return set(passed)
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        logger.warning("Failed to read deployment_status.json: %s", exc)
        return set()


def _resolve_deployment_status_path(psi_root: Path | None) -> Path | None:
    """Resolve the path to deployment_status.json."""
    import os

    if psi_root is not None:
        return psi_root / "infra" / "modal" / "deployment_status.json"

    # Try PSI_ROOT env var
    env_root = os.environ.get("PSI_ROOT")
    if env_root:
        return Path(env_root) / "infra" / "modal" / "deployment_status.json"

    # Try to infer from GPD's path resolution
    from gpd.utils.paths import find_project_root

    project_root = find_project_root()
    if project_root is not None:
        return project_root / "infra" / "modal" / "deployment_status.json"

    return None


def _check_modal_live(name: str, app_name: str) -> tuple[str, bool]:
    """Check if an MCP is actually deployed on Modal via Cls.from_name().

    Returns (name, True) if the class reference can be created,
    (name, False) otherwise.
    """
    try:
        import modal
        import modal.exception

        class_name = name.replace("_", " ").title().replace(" ", "") + "Service"
        modal.Cls.from_name(app_name, class_name)
        return (name, True)
    except Exception as exc:
        # modal.exception.NotFoundError or any other error means not available
        logger.debug("Modal live check failed for %s: %s", name, exc)
        return (name, False)


def reconcile_modal(
    tools: list[ToolEntry],
    app_name: str = "psi-mcp-servers",
    max_workers: int = 5,
) -> list[ToolEntry]:
    """Reconcile Modal tools against actual deployment status.

    Two-stage validation:
    1. Fast pre-filter from deployment_status.json "passed" list
    2. Parallel live checks via modal.Cls.from_name() for candidates not in passed

    Only checks tools with source="modal". Non-modal tools are left unchanged.

    Args:
        tools: List of ToolEntry objects to reconcile (mutated in-place).
        app_name: Modal app name to check against.
        max_workers: Maximum parallel live-check threads.

    Returns:
        The same list of tools with updated status fields.
    """
    passed_set = check_deployment_status()

    candidates: list[ToolEntry] = []
    for tool in tools:
        if tool.source != "modal":
            continue
        if tool.name in passed_set:
            tool.status = MCPStatus.available
            tool.last_checked = datetime.now(tz=UTC).isoformat()
            tool.staleness_seconds = 0.0
        else:
            candidates.append(tool)

    if not candidates:
        return tools

    # Parallel live checks for candidates not in passed_set
    results: dict[str, bool] = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_check_modal_live, tool.name, app_name): tool.name for tool in candidates}
        for future in as_completed(futures):
            name, deployed = future.result()
            results[name] = deployed

    for tool in candidates:
        if results.get(tool.name, False):
            tool.status = MCPStatus.available
        else:
            tool.status = MCPStatus.unavailable
        tool.last_checked = datetime.now(tz=UTC).isoformat()
        tool.staleness_seconds = 0.0

    return tools
