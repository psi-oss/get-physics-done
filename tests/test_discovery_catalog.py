"""Tests for ToolCatalog and lazy per-category discovery."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from gpd.mcp.discovery.catalog import ToolCatalog
from gpd.mcp.discovery.models import (
    MCPSourcesConfig,
    MCPStatus,
    SourceConfig,
    ToolEntry,
)

# -- Test fixtures --

def _make_test_config() -> MCPSourcesConfig:
    """Return a test config with a single inline custom source."""
    return MCPSourcesConfig(
        sources={
            "custom": SourceConfig(type="custom"),
        },
    )


class TestToolCatalogExternalSource:
    def test_loads_external_services_from_resolved_env_path(self, monkeypatch, tmp_path: Path) -> None:
        services_path = tmp_path / "external_services.yaml"
        services_path.write_text(
            """
services:
  ext_solver:
    description: External FEM solver
    overview: Runs external finite-element jobs
    domains:
      - Finite element
    tools:
      - name: solve
        description: Solve a model
""".strip(),
            encoding="utf-8",
        )
        monkeypatch.setenv("TEST_EXTERNAL_ROOT", str(tmp_path))

        config = MCPSourcesConfig(
            sources={
                "external": SourceConfig(
                    type="external",
                    services_file="${TEST_EXTERNAL_ROOT}/external_services.yaml",
                )
            }
        )

        catalog = ToolCatalog(config)
        all_tools = catalog.get_all_tools()

        assert "ext_solver" in all_tools
        assert all_tools["ext_solver"].categories == ["fem"]
        assert all_tools["ext_solver"].tools[0]["name"] == "solve"


# -- ToolCatalog tests --


class TestToolCatalogLoadFullCatalog:
    @patch("gpd.mcp.discovery.catalog.ToolCatalog._load_custom_source")
    def test_loads_from_mocked_custom_source(self, mock_load: MagicMock) -> None:
        mock_load.return_value = {
            "openfoam": ToolEntry(name="openfoam", description="CFD", source="custom", categories=["cfd"]),
            "lammps": ToolEntry(name="lammps", description="MD", source="custom", categories=["md"]),
        }
        config = _make_test_config()
        catalog = ToolCatalog(config)
        all_tools = catalog.get_all_tools()
        assert "openfoam" in all_tools
        assert "lammps" in all_tools
        assert len(all_tools) == 2


class TestToolCatalogGetToolsForCategory:
    def _make_catalog_with_tools(self) -> ToolCatalog:
        """Create a catalog with pre-loaded tools."""
        config = _make_test_config()
        catalog = ToolCatalog(config)
        catalog._full_catalog = {
            "openfoam": ToolEntry(name="openfoam", description="CFD", source="external", categories=["cfd"]),
            "su2": ToolEntry(name="su2", description="CFD opt", source="external", categories=["cfd"]),
            "rebound": ToolEntry(name="rebound", description="N-body", source="external", categories=["nbody"]),
            "lammps": ToolEntry(name="lammps", description="MD", source="external", categories=["md"]),
            "sympy": ToolEntry(name="sympy", description="Math", source="local", categories=["utility"]),
        }
        return catalog

    def test_returns_only_cfd_tools(self) -> None:
        catalog = self._make_catalog_with_tools()
        cfd_tools = catalog.get_tools_for_category("cfd")
        names = {t.name for t in cfd_tools}
        assert names == {"openfoam", "su2"}

    def test_caches_results(self) -> None:
        catalog = self._make_catalog_with_tools()
        first = catalog.get_tools_for_category("cfd")
        second = catalog.get_tools_for_category("cfd")
        assert first is second

    def test_invalidate_category_clears_cache(self) -> None:
        catalog = self._make_catalog_with_tools()
        first = catalog.get_tools_for_category("cfd")
        catalog.invalidate_category("cfd")
        second = catalog.get_tools_for_category("cfd")
        assert first == second
        assert first is not second

    def test_snapshot_tracks_discovered_categories(self) -> None:
        catalog = self._make_catalog_with_tools()
        catalog.get_tools_for_category("cfd")
        snapshot = catalog.get_snapshot()
        assert snapshot.categories_discovered == ["cfd"]


class TestToolCatalogSnapshot:
    def test_snapshot_returns_correct_counts(self) -> None:
        config = _make_test_config()
        catalog = ToolCatalog(config)
        catalog._full_catalog = {
            "openfoam": ToolEntry(
                name="openfoam",
                description="CFD",
                source="external",
                status=MCPStatus.available,
                categories=["cfd"],
            ),
            "su2": ToolEntry(
                name="su2",
                description="CFD",
                source="external",
                status=MCPStatus.available,
                categories=["cfd"],
            ),
            "missing": ToolEntry(
                name="missing",
                description="Gone",
                source="external",
                status=MCPStatus.unavailable,
                categories=["cfd"],
            ),
            "unknown_tool": ToolEntry(
                name="unknown_tool",
                description="?",
                source="external",
                status=MCPStatus.unknown,
                categories=["quantum"],
            ),
        }
        catalog.get_tools_for_category("cfd")

        snapshot = catalog.get_snapshot()
        assert snapshot.total_tools == 4
        assert snapshot.available_tools == 2
        assert snapshot.stale_tools == 0
        assert "cfd" in snapshot.categories_discovered


class TestToolCatalogToolCount:
    @patch("gpd.mcp.discovery.catalog.ToolCatalog._load_full_catalog")
    def test_tool_count(self, mock_load: MagicMock) -> None:
        mock_load.return_value = {
            "a": ToolEntry(name="a", description="A", source="external"),
            "b": ToolEntry(name="b", description="B", source="custom"),
            "c": ToolEntry(name="c", description="C", source="local"),
        }
        config = _make_test_config()
        catalog = ToolCatalog(config)
        assert catalog.tool_count == 3


class TestToolCatalogGracefulDegradation:
    def test_handles_failing_custom_source_loader(self) -> None:
        """Catalog should return empty results if one source loader fails."""
        config = _make_test_config()
        catalog = ToolCatalog(config)

        with patch(
            "gpd.mcp.discovery.catalog.ToolCatalog._load_custom_source",
            side_effect=ImportError("custom loader unavailable"),
        ):
            all_tools = catalog.get_all_tools()
            assert isinstance(all_tools, dict)
