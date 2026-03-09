"""Tests for ToolCatalog, hosted reconciliation, and lazy per-category discovery."""

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
from gpd.mcp.discovery.reconciler import check_deployment_status, reconcile_modal

# -- Test fixtures --


def _make_mock_mcps() -> dict:
    """Return a mock registry matching get_available_mcps() format."""
    return {
        "openfoam": {
            "description": "CFD toolkit",
            "tools": [{"name": "create_simulation", "desc": "Create a sim"}],
        },
        "su2": {
            "description": "CFD shape optimization",
            "tools": [{"name": "create_simulation", "desc": "Create a sim"}],
        },
        "rebound": {
            "description": "N-body orbital mechanics",
            "tools": [{"name": "create_simulation", "desc": "Create a sim"}],
        },
        "lammps": {
            "description": "Molecular dynamics",
            "tools": [{"name": "create_simulation", "desc": "Create a sim"}],
        },
        "calculix": {
            "description": "FEM solver",
            "tools": [{"name": "create_simulation", "desc": "Create a sim"}],
        },
    }


def _make_mock_skills() -> dict:
    """Return a mock skills summary matching get_skills_summary() format."""
    return {
        "openfoam": {
            "overview": "Computational fluid dynamics toolkit",
            "domains": ["Computational fluid dynamics", "turbulence modeling"],
        },
        "su2": {
            "overview": "Shape optimization CFD",
            "domains": ["CFD", "aerodynamics"],
        },
        "rebound": {
            "overview": "N-body simulator",
            "domains": ["N-body", "orbital mechanics"],
        },
        "lammps": {
            "overview": "Large-scale MD",
            "domains": ["Molecular dynamics", "materials science"],
        },
        "calculix": {
            "overview": "Finite element solver",
            "domains": ["Finite element", "structural mechanics"],
        },
    }


def _make_test_config() -> MCPSourcesConfig:
    """Return a test config that only has an explicitly configured hosted source."""
    return MCPSourcesConfig(
        sources={
            "hosted": SourceConfig(type="modal", app_name="physics-suite"),
        },
    )


# -- reconciler tests --


class TestCheckDeploymentStatus:
    def test_returns_empty_set_when_file_missing(self, tmp_path: Path) -> None:
        result = check_deployment_status(tmp_path / "nonexistent")
        assert result == set()

    def test_reads_passed_list(self, tmp_path: Path) -> None:
        import json

        status_path = tmp_path / "infra" / "mcp" / "deployment_status.json"
        status_path.parent.mkdir(parents=True)
        status_path.write_text(json.dumps({"passed": ["openfoam", "su2", "lammps"]}))
        result = check_deployment_status(tmp_path)
        assert result == {"openfoam", "su2", "lammps"}

    def test_handles_malformed_json(self, tmp_path: Path) -> None:
        status_path = tmp_path / "infra" / "mcp" / "deployment_status.json"
        status_path.parent.mkdir(parents=True)
        status_path.write_text("not valid json{{{")
        result = check_deployment_status(tmp_path)
        assert result == set()


class TestReconcileModal:
    def test_marks_tools_in_passed_set_as_available(self) -> None:
        tools = [
            ToolEntry(name="openfoam", description="CFD", source="modal"),
            ToolEntry(name="su2", description="CFD", source="modal"),
        ]
        with (
            patch(
                "gpd.mcp.discovery.reconciler.check_deployment_status",
                return_value={"openfoam", "su2"},
            ),
            patch(
                "gpd.mcp.discovery.reconciler._check_modal_live",
                side_effect=[("openfoam", True), ("su2", True)],
            ),
        ):
            reconcile_modal(tools, app_name="physics-suite", max_workers=1)

        assert tools[0].status == MCPStatus.available
        assert tools[1].status == MCPStatus.available

    def test_marks_passed_but_not_live_tools_as_stale(self) -> None:
        tools = [
            ToolEntry(name="openfoam", description="CFD", source="modal"),
        ]
        with (
            patch(
                "gpd.mcp.discovery.reconciler.check_deployment_status",
                return_value={"openfoam"},
            ),
            patch(
                "gpd.mcp.discovery.reconciler._check_modal_live",
                return_value=("openfoam", False),
            ),
        ):
            reconcile_modal(tools, app_name="physics-suite", max_workers=1)

        assert tools[0].status == MCPStatus.stale

    def test_marks_tools_not_in_passed_as_unavailable(self) -> None:
        tools = [
            ToolEntry(name="missing_tool", description="Gone", source="modal"),
        ]
        with (
            patch(
                "gpd.mcp.discovery.reconciler.check_deployment_status",
                return_value=set(),
            ),
            patch(
                "gpd.mcp.discovery.reconciler._check_modal_live",
                return_value=("missing_tool", False),
            ),
        ):
            reconcile_modal(tools, app_name="physics-suite", max_workers=1)

        assert tools[0].status == MCPStatus.unavailable

    def test_skips_non_modal_tools(self) -> None:
        tools = [
            ToolEntry(name="sympy", description="Math", source="local", status=MCPStatus.available),
            ToolEntry(name="openfoam", description="CFD", source="modal"),
        ]
        with (
            patch(
                "gpd.mcp.discovery.reconciler.check_deployment_status",
                return_value={"openfoam"},
            ),
            patch(
                "gpd.mcp.discovery.reconciler._check_modal_live",
                return_value=("openfoam", True),
            ),
        ):
            reconcile_modal(tools, app_name="physics-suite")

        # Local tool status unchanged
        assert tools[0].status == MCPStatus.available
        assert tools[0].source == "local"
        # Modal tool reconciled
        assert tools[1].status == MCPStatus.available

    def test_live_check_marks_as_available(self) -> None:
        tools = [
            ToolEntry(name="new_tool", description="New", source="modal"),
        ]
        with (
            patch(
                "gpd.mcp.discovery.reconciler.check_deployment_status",
                return_value=set(),
            ),
            patch(
                "gpd.mcp.discovery.reconciler._check_modal_live",
                return_value=("new_tool", True),
            ),
        ):
            reconcile_modal(tools, app_name="physics-suite", max_workers=1)

        assert tools[0].status == MCPStatus.available


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
    @patch("gpd.mcp.discovery.catalog.ToolCatalog._load_modal_source")
    def test_loads_from_mocked_registry(self, mock_load: MagicMock) -> None:
        mock_load.return_value = {
            "openfoam": ToolEntry(name="openfoam", description="CFD", source="modal", categories=["cfd"]),
            "lammps": ToolEntry(name="lammps", description="MD", source="modal", categories=["md"]),
        }
        config = _make_test_config()
        catalog = ToolCatalog(config)
        all_tools = catalog.get_all_tools()
        assert "openfoam" in all_tools
        assert "lammps" in all_tools
        assert len(all_tools) == 2


class TestToolCatalogGetToolsForCategory:
    def _make_catalog_with_tools(self) -> ToolCatalog:
        """Create a catalog with pre-loaded tools, mocking reconciliation."""
        config = _make_test_config()
        catalog = ToolCatalog(config)
        catalog._full_catalog = {
            "openfoam": ToolEntry(name="openfoam", description="CFD", source="modal", categories=["cfd"]),
            "su2": ToolEntry(name="su2", description="CFD opt", source="modal", categories=["cfd"]),
            "rebound": ToolEntry(name="rebound", description="N-body", source="modal", categories=["nbody"]),
            "lammps": ToolEntry(name="lammps", description="MD", source="modal", categories=["md"]),
            "sympy": ToolEntry(name="sympy", description="Math", source="local", categories=["utility"]),
        }
        return catalog

    @patch("gpd.mcp.discovery.catalog.reconcile_modal", side_effect=lambda tools, **kw: tools)
    def test_returns_only_cfd_tools(self, mock_reconcile: MagicMock) -> None:
        catalog = self._make_catalog_with_tools()
        cfd_tools = catalog.get_tools_for_category("cfd")
        names = {t.name for t in cfd_tools}
        assert names == {"openfoam", "su2"}

    @patch("gpd.mcp.discovery.catalog.reconcile_modal", side_effect=lambda tools, **kw: tools)
    def test_lazy_reconcile_only_first_access(self, mock_reconcile: MagicMock) -> None:
        catalog = self._make_catalog_with_tools()

        # First access triggers reconcile
        catalog.get_tools_for_category("cfd")
        assert mock_reconcile.call_count == 1

        # Second access returns cached (no extra reconcile)
        catalog.get_tools_for_category("cfd")
        assert mock_reconcile.call_count == 1

    @patch("gpd.mcp.discovery.catalog.reconcile_modal", side_effect=lambda tools, **kw: tools)
    def test_caches_results(self, mock_reconcile: MagicMock) -> None:
        catalog = self._make_catalog_with_tools()
        first = catalog.get_tools_for_category("cfd")
        second = catalog.get_tools_for_category("cfd")
        assert first is second

    @patch("gpd.mcp.discovery.catalog.reconcile_modal", side_effect=lambda tools, **kw: tools)
    def test_invalidate_category_clears_cache(self, mock_reconcile: MagicMock) -> None:
        catalog = self._make_catalog_with_tools()

        catalog.get_tools_for_category("cfd")
        assert mock_reconcile.call_count == 1

        catalog.invalidate_category("cfd")

        catalog.get_tools_for_category("cfd")
        assert mock_reconcile.call_count == 2


class TestToolCatalogSnapshot:
    def test_snapshot_returns_correct_counts(self) -> None:
        config = _make_test_config()
        catalog = ToolCatalog(config)
        catalog._full_catalog = {
            "openfoam": ToolEntry(
                name="openfoam",
                description="CFD",
                source="modal",
                status=MCPStatus.available,
                categories=["cfd"],
            ),
            "su2": ToolEntry(
                name="su2",
                description="CFD",
                source="modal",
                status=MCPStatus.available,
                categories=["cfd"],
            ),
            "missing": ToolEntry(
                name="missing",
                description="Gone",
                source="modal",
                status=MCPStatus.unavailable,
                categories=["cfd"],
            ),
            "unknown_tool": ToolEntry(
                name="unknown_tool",
                description="?",
                source="modal",
                status=MCPStatus.unknown,
                categories=["quantum"],
            ),
        }
        catalog._reconciled_categories = {"cfd"}

        snapshot = catalog.get_snapshot()
        assert snapshot.total_tools == 4
        assert snapshot.available_tools == 2
        assert snapshot.stale_tools == 0
        assert "cfd" in snapshot.categories_discovered


class TestToolCatalogToolCount:
    @patch("gpd.mcp.discovery.catalog.ToolCatalog._load_full_catalog")
    def test_tool_count(self, mock_load: MagicMock) -> None:
        mock_load.return_value = {
            "a": ToolEntry(name="a", description="A", source="modal"),
            "b": ToolEntry(name="b", description="B", source="modal"),
            "c": ToolEntry(name="c", description="C", source="local"),
        }
        config = _make_test_config()
        catalog = ToolCatalog(config)
        assert catalog.tool_count == 3


class TestToolCatalogGracefulDegradation:
    def test_handles_missing_gpd_mcp_shared(self) -> None:
        """Catalog should return empty results if hosted registry metadata is unavailable."""
        config = _make_test_config()
        catalog = ToolCatalog(config)

        with patch(
            "gpd.mcp.discovery.catalog.ToolCatalog._load_modal_source",
            side_effect=ImportError("gpd-mcp-shared not installed"),
        ):
            # The _load_full_catalog catches the exception and continues
            all_tools = catalog.get_all_tools()
            assert isinstance(all_tools, dict)
