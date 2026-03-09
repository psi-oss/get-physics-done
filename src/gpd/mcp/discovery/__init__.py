"""MCP tool discovery layer for GPD+.

Public API for discovering available MCP tools from configured sources
(Modal deployments, local servers, external endpoints, custom configs),
LLM-driven tool selection, physics category routing, auto-substitute
fallback, and MCP Builder subagent contract.
"""

from __future__ import annotations

from gpd.mcp.discovery.catalog import ToolCatalog
from gpd.mcp.discovery.fallback import (
    AutoSubstituteResult,
    MCPBuilderRequest,
    MCPBuilderResult,
    find_substitute,
    request_mcp_build,
)
from gpd.mcp.discovery.models import (
    PHYSICS_CATEGORIES,
    MCPSourcesConfig,
    MCPStatus,
    PhysicsCategory,
    ToolCatalogSnapshot,
    ToolEntry,
)
from gpd.mcp.discovery.router import (
    PhysicsRouter,
    display_selection,
    reevaluate_tools,
    route_and_select,
)
from gpd.mcp.discovery.selector import (
    SelectedTool,
    ToolSelection,
    ToolSelectionAgent,
    select_tools,
)
from gpd.mcp.discovery.sources import get_default_config, load_sources_config

__all__ = [
    "AutoSubstituteResult",
    "MCPBuilderRequest",
    "MCPBuilderResult",
    "MCPSourcesConfig",
    "MCPStatus",
    "PHYSICS_CATEGORIES",
    "PhysicsCategory",
    "PhysicsRouter",
    "SelectedTool",
    "ToolCatalog",
    "ToolCatalogSnapshot",
    "ToolEntry",
    "ToolSelection",
    "ToolSelectionAgent",
    "display_selection",
    "find_substitute",
    "get_default_config",
    "load_sources_config",
    "reevaluate_tools",
    "request_mcp_build",
    "route_and_select",
    "select_tools",
]


def get_tool_catalog() -> ToolCatalog:
    """Load sources config and create a ToolCatalog instance.

    Returns:
        A ToolCatalog ready for lazy per-category discovery.
    """
    config = load_sources_config()
    return ToolCatalog(config)


def discover_tools(
    catalog: ToolCatalog,
    categories: list[str] | None = None,
) -> ToolCatalogSnapshot:
    """Discover tools for the specified categories.

    If categories is None, discovers all categories. Otherwise, discovers
    only the specified categories. Returns a snapshot of the current catalog state.

    Args:
        catalog: ToolCatalog instance.
        categories: List of category names to discover, or None for all.

    Returns:
        Snapshot of the catalog after discovery.
    """
    if categories is None:
        categories = [cat.name for cat in PHYSICS_CATEGORIES]

    for category in categories:
        catalog.get_tools_for_category(category)

    return catalog.get_snapshot()
