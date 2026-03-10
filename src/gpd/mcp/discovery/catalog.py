"""ToolCatalog -- lazy per-category MCP tool discovery.

Loads tools from configured external services, local MCP servers, and
custom inline endpoints. The full catalog loads lazily on first access,
and per-category results are cached.
"""

from __future__ import annotations

import logging
import threading

from gpd.mcp.discovery.models import (
    OVERVIEW_PREVIEW_MAX_CHARS,
    MCPSourcesConfig,
    MCPStatus,
    SourceConfig,
    ToolCatalogSnapshot,
    ToolEntry,
    categorize_tool,
)
from gpd.mcp.discovery.sources import load_external_services_file

logger = logging.getLogger(__name__)

STALENESS_FRESH_THRESHOLD_SECONDS: float = 300.0
"""Tools checked within this many seconds are labelled 'fresh' in the catalog display."""

# Known category mappings for local MCPs (discovered at connection time,
# not pre-enumerated -- but we can assign categories for routing)
_LOCAL_MCP_CATEGORIES: dict[str, list[str]] = {
    "sympy": ["utility"],
    "lean4": ["utility"],
    "wolfram": ["utility"],
    "paper-search": ["databases"],
    "sagemath": ["utility"],
    "code-execution": ["utility"],
}


class ToolCatalog:
    """Lazy-loaded, category-cached MCP tool catalog.

    Loads the full catalog from all configured sources on first access.
    """

    def __init__(self, sources_config: MCPSourcesConfig) -> None:
        self._sources = sources_config
        self._full_catalog: dict[str, ToolEntry] | None = None
        self._category_cache: dict[str, list[ToolEntry]] = {}

    def _load_full_catalog(self) -> dict[str, ToolEntry]:
        """Build the complete catalog from all configured sources.

        Loads from:
        1. External source: external_services.yaml
        2. Local source: known local MCP servers
        3. Custom source: inline endpoint definitions
        """
        catalog: dict[str, ToolEntry] = {}

        for source_name, source_config in self._sources.sources.items():
            try:
                if source_config.type == "external":
                    catalog.update(self._load_external_source(source_config))
                elif source_config.type == "local":
                    catalog.update(self._load_local_source(source_config))
                elif source_config.type == "custom":
                    catalog.update(self._load_custom_source(source_config))
                else:
                    logger.warning("Unknown source type %r in %r", source_config.type, source_name)
            except (ImportError, OSError, ValueError) as exc:
                logger.warning("Failed to load source %r: %s", source_name, exc)

        return catalog

    def _load_external_source(self, source_config: SourceConfig) -> dict[str, ToolEntry]:
        """Load tools from external services YAML."""
        entries: dict[str, ToolEntry] = {}

        services_file = source_config.services_file
        if not services_file:
            return entries

        services = load_external_services_file(services_file)
        if not services:
            return entries

        for svc_id, svc in services.items():
            raw_tools = svc.get("tools", [])
            tools = (
                [{"name": str(t.get("name", "")), "desc": str(t.get("description", ""))} for t in raw_tools if isinstance(t, dict)]
                if isinstance(raw_tools, list)
                else []
            )
            raw_domains = svc.get("domains", [])
            domains = [str(domain) for domain in raw_domains] if isinstance(raw_domains, list) else []
            raw_categories = svc.get("categories", [])
            categories = (
                [str(category) for category in raw_categories]
                if isinstance(raw_categories, list) and raw_categories
                else categorize_tool(svc_id, domains)
            )
            overview = str(svc.get("overview", ""))[:OVERVIEW_PREVIEW_MAX_CHARS]
            entries[svc_id] = ToolEntry(
                name=svc_id,
                description=svc.get("description", f"{svc_id} external service"),
                source="external",
                status=MCPStatus.available,
                categories=categories,
                domains=domains,
                tools=tools,
                overview=overview,
            )

        return entries

    def _load_local_source(self, source_config: SourceConfig) -> dict[str, ToolEntry]:
        """Load local MCP server entries.

        Local MCP tools are discovered at connection time via MCP protocol,
        not pre-enumerated. We create placeholder entries with known categories.
        """
        entries: dict[str, ToolEntry] = {}

        for config_name in source_config.configs:
            categories = _LOCAL_MCP_CATEGORIES.get(config_name, ["uncategorized"])
            entries[config_name] = ToolEntry(
                name=config_name,
                description=f"{config_name} (local MCP server)",
                source="local",
                status=MCPStatus.available,
                categories=categories,
                tools=[],
            )

        return entries

    def _load_custom_source(self, source_config: SourceConfig) -> dict[str, ToolEntry]:
        """Load custom inline endpoint definitions."""
        entries: dict[str, ToolEntry] = {}

        for entry_def in source_config.custom_entries:
            name = str(entry_def.get("name", "custom"))
            description = str(entry_def.get("description", f"{name} custom MCP"))
            raw_domains = entry_def.get("domains", [])
            domains = [str(d) for d in raw_domains] if isinstance(raw_domains, list) else []
            categories = categorize_tool(name, domains)

            entries[name] = ToolEntry(
                name=name,
                description=description,
                source="custom",
                status=MCPStatus.available,
                categories=categories,
                domains=domains,
            )

        return entries

    def get_tools_for_category(self, category: str) -> list[ToolEntry]:
        """Get tools for a physics category with lazy caching.

        On first access per category, the catalog is loaded if needed,
        filtered by category, and the result is cached. Subsequent calls
        reuse the cached list until invalidated.
        """
        if category in self._category_cache:
            return self._category_cache[category]

        if self._full_catalog is None:
            self._full_catalog = self._load_full_catalog()

        matching = [t for t in self._full_catalog.values() if category in t.categories]
        self._category_cache[category] = matching
        return matching

    def get_all_tools(self) -> dict[str, ToolEntry]:
        """Return the full catalog without populating category cache.

        For browsing and counting, not execution.
        """
        if self._full_catalog is None:
            self._full_catalog = self._load_full_catalog()
        return self._full_catalog

    def get_full_catalog_display(self) -> list[dict[str, object]]:
        """Return all tools with full metadata for display as a sortable table."""
        if self._full_catalog is None:
            self._full_catalog = self._load_full_catalog()
        rows: list[dict[str, object]] = []
        for _name, entry in sorted(self._full_catalog.items()):
            staleness_label = (
                "fresh" if entry.staleness_seconds < STALENESS_FRESH_THRESHOLD_SECONDS else "stale" if entry.last_checked else "unchecked"
            )
            rows.append(
                {
                    "name": entry.name,
                    "status": entry.status.value,
                    "domains": entry.domains[:3],
                    "operations": [t.get("name", "") for t in entry.tools[:5]],
                    "gpu_type": entry.cost_profile.gpu_type,
                    "est_seconds": entry.cost_profile.estimated_seconds,
                    "cost_per_call": f"${entry.cost_profile.cost_per_call_usd:.4f}",
                    "last_checked": entry.last_checked or "never",
                    "staleness": staleness_label,
                    "source": entry.source,
                }
            )
        return rows

    def background_refresh(self) -> None:
        """Start a daemon thread that reloads the catalog from source.

        Non-blocking -- callers keep using the current cache until the
        background refresh completes.
        """

        def _refresh_worker() -> None:
            try:
                refreshed = self._load_full_catalog()
                self._full_catalog = refreshed
                self._category_cache.clear()
                logger.info("Background refresh complete: %d tools loaded", len(refreshed))
            except Exception as exc:
                logger.warning("Background refresh failed: %s", exc)

        thread = threading.Thread(target=_refresh_worker, daemon=True)
        thread.start()

    def get_snapshot(self) -> ToolCatalogSnapshot:
        """Build a point-in-time snapshot of the catalog state."""
        if self._full_catalog is None:
            self._full_catalog = self._load_full_catalog()

        tools = self._full_catalog
        available = sum(1 for t in tools.values() if t.status == MCPStatus.available)
        stale = sum(1 for t in tools.values() if t.status == MCPStatus.stale)

        return ToolCatalogSnapshot(
            total_tools=len(tools),
            available_tools=available,
            stale_tools=stale,
            categories_discovered=sorted(self._category_cache),
            tools=tools,
        )

    def invalidate_category(self, category: str) -> None:
        """Clear cache for a specific category, forcing re-discovery.

        Used at milestone boundaries for re-evaluation.
        """
        self._category_cache.pop(category, None)

    def invalidate_all(self) -> None:
        """Clear all caches, forcing complete re-discovery.

        Used when config changes.
        """
        self._full_catalog = None
        self._category_cache.clear()

    @property
    def tool_count(self) -> int:
        """Return total tool count (loads lazily).

        For the startup MCP count display.
        """
        if self._full_catalog is None:
            self._full_catalog = self._load_full_catalog()
        return len(self._full_catalog)
