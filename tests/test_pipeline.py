"""Tests for MCP pipeline discover/plan JSON contracts."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from gpd.mcp.discovery.models import CostProfile, MCPStatus, ToolEntry
from gpd.mcp.discovery.selector import SelectedTool, ToolSelection
from gpd.mcp.pipeline import app
from gpd.mcp.research.schemas import CostEstimate, ResearchMilestone, ResearchPlan

runner = CliRunner()


class FakeCatalog:
    """Minimal catalog stub for pipeline discover tests."""

    def __init__(self, _config: object) -> None:
        self._entry = ToolEntry(
            name="openfoam",
            description="CFD solver",
            source="modal",
            status=MCPStatus.available,
            categories=["cfd"],
            domains=["Computational fluid dynamics"],
            tools=[{"name": "create_simulation", "desc": "Create a sim"}],
            overview="CFD workflows for airfoils",
            cost_profile=CostProfile(
                gpu_type="A10G",
                estimated_seconds=45.0,
                cost_per_call_usd=0.22,
            ),
        )

    def get_all_tools(self) -> dict[str, ToolEntry]:
        return {"openfoam": self._entry}

    def get_full_catalog_display(self) -> list[dict[str, object]]:
        return [{"name": "openfoam", "status": "available"}]

    def background_refresh(self) -> None:
        return None


class FakeRouter:
    """Minimal router stub for pipeline discover tests."""

    def __init__(self, catalog: FakeCatalog, selector: object | None = None) -> None:
        self._catalog = catalog
        self._selector = selector

    async def route_and_select(self, _query: str) -> ToolSelection:
        return ToolSelection(
            tools=[SelectedTool(mcp="openfoam", reason="Best CFD match", priority=1)],
            reasoning="CFD query",
            physics_categories=["cfd"],
            confidence=0.95,
        )


def _make_plan() -> ResearchPlan:
    milestone = ResearchMilestone(
        milestone_id="m1",
        description="Run the main simulation",
        tools=["openfoam"],
        cost_estimate=CostEstimate(
            gpu_type="A10G",
            estimated_seconds=65.0,
            rate_per_second=0.001,
            estimated_cost_usd=0.065,
            confidence="MEDIUM",
        ),
    )
    return ResearchPlan(
        plan_id="plan-123456",
        query="Airfoil lift study",
        milestones=[milestone],
        reasoning="Single-step plan for test coverage.",
        total_cost_estimate=CostEstimate(
            gpu_type="A10G",
            estimated_seconds=65.0,
            rate_per_second=0.001,
            estimated_cost_usd=0.065,
            confidence="MEDIUM",
        ),
    )


def test_discover_emits_cost_profile_and_categories() -> None:
    with (
        patch("gpd.mcp.discovery.sources.load_sources_config", return_value=MagicMock()),
        patch("gpd.mcp.discovery.catalog.ToolCatalog", FakeCatalog),
        patch("gpd.mcp.discovery.selector.ToolSelectionAgent", return_value=MagicMock()),
        patch("gpd.mcp.discovery.router.PhysicsRouter", FakeRouter),
    ):
        result = runner.invoke(app, ["discover", "simulate flow over an airfoil"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["physics_categories"] == ["cfd"]
    assert payload["tools"][0]["categories"] == ["cfd"]
    assert payload["tools"][0]["cost_profile"]["gpu_type"] == "A10G"
    assert payload["tools"][0]["estimated_seconds"] == 45.0
    assert payload["tools"][0]["cost_per_call_usd"] == 0.22


def test_plan_uses_nested_cost_profile_metadata(tmp_path: Path) -> None:
    captured_registry: dict[str, dict[str, object]] = {}

    class FakePlanner:
        async def generate_plan(
            self,
            query: str,
            available_tools: list[dict[str, object]],
            tool_metadata_registry: dict[str, dict[str, object]],
        ) -> ResearchPlan:
            assert query == "Airfoil lift study"
            assert available_tools[0]["name"] == "openfoam"
            captured_registry.update(tool_metadata_registry)
            return _make_plan()

    tools_file = tmp_path / "tools.json"
    tools_file.write_text(
        json.dumps(
            {
                "tools": [
                    {
                        "name": "openfoam",
                        "domains": ["Computational fluid dynamics"],
                        "cost_profile": {
                            "gpu_type": "A10G",
                            "estimated_seconds": 45.0,
                            "cost_per_call_usd": 0.22,
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with patch("gpd.mcp.research.planner.ResearchPlanner", FakePlanner):
        result = runner.invoke(
            app,
            [
                "plan",
                "--query",
                "Airfoil lift study",
                "--tools-file",
                str(tools_file),
                "--work-dir",
                str(tmp_path / "work"),
            ],
        )

    assert result.exit_code == 0
    assert captured_registry["openfoam"]["gpu_type"] == "A10G"
    assert captured_registry["openfoam"]["estimated_seconds"] == 45.0
    assert captured_registry["openfoam"]["cost_per_call_usd"] == 0.22
