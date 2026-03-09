"""ToolCatalog -- lazy per-category MCP tool discovery with Modal reconciliation.

Loads tools from multiple configured sources (Modal registry, external services,
local MCP servers, custom endpoints). Discovery is lazy: per-category tool
reconciliation against Modal only happens when a specific physics category
is requested.
"""

from __future__ import annotations

import logging
import threading

from gpd.mcp.discovery.models import (
    OVERVIEW_PREVIEW_MAX_CHARS,
    CostProfile,
    MCPSourcesConfig,
    MCPStatus,
    SourceConfig,
    ToolCatalogSnapshot,
    ToolEntry,
    categorize_tool,
)
from gpd.mcp.discovery.reconciler import reconcile_modal
from gpd.mcp.research.cost_estimator import MODAL_RATES_USD_PER_SECOND

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
    Per-category reconciliation against Modal only happens when
    get_tools_for_category() is called for a specific category.
    """

    def __init__(self, sources_config: MCPSourcesConfig) -> None:
        self._sources = sources_config
        self._full_catalog: dict[str, ToolEntry] | None = None
        self._category_cache: dict[str, list[ToolEntry]] = {}
        self._reconciled_categories: set[str] = set()

    def _load_full_catalog(self) -> dict[str, ToolEntry]:
        """Build the complete catalog from all configured sources.

        Loads from:
        1. Modal source: gpd-mcp-shared registry + SKILLS_SUMMARY
        2. External source: external_services.yaml
        3. Local source: known local MCP servers
        4. Custom source: inline endpoint definitions
        """
        catalog: dict[str, ToolEntry] = {}

        for source_name, source_config in self._sources.sources.items():
            try:
                if source_config.type == "modal":
                    catalog.update(self._load_modal_source(source_config))
                elif source_config.type == "external":
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

    def _load_modal_source(self, source_config: SourceConfig) -> dict[str, ToolEntry]:
        """Load tools from gpd-mcp-shared registry with SKILLS_SUMMARY metadata."""
        entries: dict[str, ToolEntry] = {}

        from gpd.utils.mcp_registry import get_available_mcps, get_skills_summary

        mcps = get_available_mcps()
        skills = get_skills_summary()

        gpu_domains = {
            "cfd",
            "molecular-dynamics",
            "particle-physics",
            "cosmology",
            "quantum-chemistry",
            "materials-science",
            "fluid-dynamics",
            "astrophysics",
            "nuclear-physics",
            "plasma-physics",
        }

        for name, info in mcps.items():
            skill_info = skills.get(name, {})
            domains = skill_info.get("domains", [])
            overview = skill_info.get("overview", "")
            description = info.get("description", f"{name} MCP")
            raw_tools = info.get("tools", [])
            tool_list = [{"name": t.get("name", ""), "desc": t.get("desc", "")} for t in raw_tools]

            source = info.get("source", "modal")
            categories = categorize_tool(name, domains)

            # Populate cost profile from domain heuristic
            uses_gpu = bool(set(domains) & gpu_domains)
            gpu_type = "A100-80GB" if uses_gpu else "CPU"
            est_seconds = 300.0 if uses_gpu else 30.0
            rate = MODAL_RATES_USD_PER_SECOND.get(gpu_type, MODAL_RATES_USD_PER_SECOND["CPU"])
            cost_per_call = est_seconds * rate * 1.25 * 3.0  # regional * non-preemptible

            entries[name] = ToolEntry(
                name=name,
                description=description,
                source=source,
                status=MCPStatus.unknown,
                categories=categories,
                domains=domains,
                tools=tool_list,
                overview=overview[:OVERVIEW_PREVIEW_MAX_CHARS] if overview else "",
                cost_profile=CostProfile(
                    gpu_type=gpu_type,
                    estimated_seconds=est_seconds,
                    cost_per_call_usd=cost_per_call,
                ),
                modal_app_name=source_config.app_name,
            )

        return entries

    def _load_external_source(self, source_config: SourceConfig) -> dict[str, ToolEntry]:
        """Load tools from external services YAML."""
        entries: dict[str, ToolEntry] = {}

        services_file = source_config.services_file
        if not services_file:
            return entries

        try:
            from infra.mcp.registry.loader import load_external_services

            services = load_external_services(services_file)
        except (ImportError, OSError):
            return entries

        for svc_id, svc in services.items():
            tools = [{"name": t.get("name", ""), "desc": t.get("description", "")} for t in svc.get("tools", [])]
            entries[svc_id] = ToolEntry(
                name=svc_id,
                description=svc.get("description", f"{svc_id} external service"),
                source="external",
                status=MCPStatus.available,
                categories=["uncategorized"],
                tools=tools,
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
        """Get tools for a physics category with lazy reconciliation.

        On first access per category:
        1. Loads the full catalog if not loaded
        2. Filters tools by category
        3. Reconciles Modal deployment status for matching tools
        4. Caches the result

        Subsequent calls return cached results without re-reconciling.
        """
        if category in self._category_cache and category in self._reconciled_categories:
            return self._category_cache[category]

        if self._full_catalog is None:
            self._full_catalog = self._load_full_catalog()

        matching = [t for t in self._full_catalog.values() if category in t.categories]

        if category not in self._reconciled_categories:
            # Find the modal app name from sources config
            app_name = "gpd-mcp-servers"
            for src in self._sources.sources.values():
                if src.type == "modal":
                    app_name = src.app_name
                    break

            reconcile_modal(matching, app_name=app_name)
            self._reconciled_categories.add(category)

        self._category_cache[category] = matching
        return matching

    def get_all_tools(self) -> dict[str, ToolEntry]:
        """Return the full catalog without reconciliation.

        For browsing and counting, not execution. Does not trigger
        Modal reconciliation.
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
                    "modal_app": entry.modal_app_name,
                    "source": entry.source,
                }
            )
        return rows

    def background_refresh(self) -> None:
        """Start a daemon thread that refreshes all tool statuses.

        Non-blocking -- UI shows cached data with staleness indicators.
        """

        def _refresh_worker() -> None:
            try:
                if self._full_catalog is None:
                    return
                app_name = "gpd-mcp-servers"
                for src in self._sources.sources.values():
                    if src.type == "modal":
                        app_name = src.app_name
                        break
                modal_tools = [t for t in self._full_catalog.values() if t.source == "modal"]
                if modal_tools:
                    reconcile_modal(modal_tools, app_name=app_name)
                logger.info("Background refresh complete: %d tools checked", len(modal_tools))
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
            categories_discovered=sorted(self._reconciled_categories),
            tools=tools,
        )

    def invalidate_category(self, category: str) -> None:
        """Clear cache for a specific category, forcing re-discovery.

        Used at milestone boundaries for re-evaluation.
        """
        self._category_cache.pop(category, None)
        self._reconciled_categories.discard(category)

    def invalidate_all(self) -> None:
        """Clear all caches, forcing complete re-discovery.

        Used when config changes.
        """
        self._full_catalog = None
        self._category_cache.clear()
        self._reconciled_categories.clear()

    @property
    def tool_count(self) -> int:
        """Return total tool count (loads lazily).

        For the startup MCP count display.
        """
        if self._full_catalog is None:
            self._full_catalog = self._load_full_catalog()
        return len(self._full_catalog)
