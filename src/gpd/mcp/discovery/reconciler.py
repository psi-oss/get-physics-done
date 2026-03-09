"""Modal reconciliation for optional hosted MCP discovery.

deployment_status.json is treated as a stale hint only. Availability is only
confirmed by a live check via modal.Cls.from_name().
"""

from __future__ import annotations

import json
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

from gpd.mcp.discovery.models import MCPStatus, ToolEntry

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
    app_name: str = "",
    max_workers: int = 5,
) -> list[ToolEntry]:
    """Reconcile Modal tools against actual deployment status.

    Two-stage validation:
    1. Fast hint from deployment_status.json "passed" list
    2. Parallel live checks via modal.Cls.from_name() for every modal tool

    Only checks tools with source="modal". Non-modal tools are left unchanged.

    Args:
        tools: List of ToolEntry objects to reconcile (mutated in-place).
        app_name: Hosted deployment name to check against.
        max_workers: Maximum parallel live-check threads.

    Returns:
        The same list of tools with updated status fields.
    """
    passed_set = check_deployment_status()
    modal_tools = [tool for tool in tools if tool.source == "modal"]
    if not modal_tools or not app_name:
        return tools

    results: dict[str, bool] = {}
    ordered_modal_tools = sorted(modal_tools, key=lambda tool: tool.name not in passed_set)
    worker_count = max(1, min(max_workers, len(ordered_modal_tools)))
    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        futures = {executor.submit(_check_modal_live, tool.name, app_name): tool.name for tool in ordered_modal_tools}
        for future in as_completed(futures):
            name, deployed = future.result()
            results[name] = deployed

    for tool in modal_tools:
        if results.get(tool.name, False):
            tool.status = MCPStatus.available
        elif tool.name in passed_set:
            tool.status = MCPStatus.stale
        else:
            tool.status = MCPStatus.unavailable
        tool.last_checked = datetime.now(tz=UTC).isoformat()
        tool.staleness_seconds = 0.0

    return tools
