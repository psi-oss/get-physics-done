"""Tests for LLM-driven tool selection, physics routing, and display formatting."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from gpd.mcp.discovery.models import (
    MCPStatus,
    ToolEntry,
)
from gpd.mcp.discovery.router import PhysicsRouter, display_selection
from gpd.mcp.discovery.selector import (
    MAX_TOOLS,
    SelectedTool,
    ToolSelection,
    ToolSelectionAgent,
    _build_selection_prompt,
    _build_tool_catalog_prompt,
)

# -- Test fixtures --


def _make_tool(name: str, categories: list[str], status: MCPStatus = MCPStatus.available) -> ToolEntry:
    """Create a test ToolEntry."""
    return ToolEntry(
        name=name,
        description=f"{name} simulator",
        source="modal",
        status=status,
        categories=categories,
        domains=[f"{name} domain"],
        tools=[{"name": "create_simulation", "desc": "Create a sim"}],
        overview=f"Overview of {name}",
    )


def _make_selection(n_tools: int = 3) -> ToolSelection:
    """Create a test ToolSelection with n_tools."""
    tools = [SelectedTool(mcp=f"tool_{i}", reason=f"Reason {i}", priority=(i % 3) + 1) for i in range(n_tools)]
    return ToolSelection(
        tools=tools,
        reasoning="Test reasoning",
        physics_categories=["cfd"],
        confidence=0.8,
    )


def _make_mock_catalog() -> MagicMock:
    """Create a mock ToolCatalog that returns test tools by category."""
    catalog = MagicMock()
    cfd_tools = [_make_tool("openfoam", ["cfd"]), _make_tool("su2", ["cfd"])]
    quantum_tools = [_make_tool("qutip", ["quantum"])]

    def get_tools_for_category(cat: str) -> list[ToolEntry]:
        if cat == "cfd":
            return cfd_tools
        if cat == "quantum":
            return quantum_tools
        return []

    catalog.get_tools_for_category = MagicMock(side_effect=get_tools_for_category)
    catalog.invalidate_category = MagicMock()
    return catalog


# -- ToolSelection model tests --


class TestToolSelectionModel:
    def test_validates_max_15_tools(self) -> None:
        """ToolSelection.tools max_length=15 should accept exactly 15."""
        tools = [SelectedTool(mcp=f"tool_{i}", reason=f"R{i}", priority=1) for i in range(15)]
        selection = ToolSelection(tools=tools, reasoning="ok", physics_categories=["cfd"], confidence=0.9)
        assert len(selection.tools) == 15

    def test_rejects_more_than_15_tools(self) -> None:
        """ToolSelection.tools max_length=15 should reject >15."""
        tools = [SelectedTool(mcp=f"tool_{i}", reason=f"R{i}", priority=1) for i in range(16)]
        with pytest.raises(ValidationError, match="List should have at most 15 items"):
            ToolSelection(tools=tools, reasoning="ok", physics_categories=["cfd"], confidence=0.9)

    def test_selected_tool_priority_range(self) -> None:
        """SelectedTool.priority must be 1-3."""
        SelectedTool(mcp="t", reason="r", priority=1)
        SelectedTool(mcp="t", reason="r", priority=3)

        with pytest.raises(ValidationError):
            SelectedTool(mcp="t", reason="r", priority=0)
        with pytest.raises(ValidationError):
            SelectedTool(mcp="t", reason="r", priority=4)


# -- Prompt building tests --


class TestBuildToolCatalogPrompt:
    def test_truncates_overview_to_200_chars(self) -> None:
        """Tool overview should be truncated to 200 chars in the prompt."""
        tool = ToolEntry(
            name="test_tool",
            description="Short desc",
            source="modal",
            categories=["cfd"],
            overview="A" * 300,
        )
        prompt = _build_tool_catalog_prompt([tool])
        # The overview part in the prompt should not have more than 200 A's
        assert "A" * 201 not in prompt
        assert "A" * 200 in prompt

    def test_groups_by_category(self) -> None:
        """Tools should be grouped by their first category."""
        tools = [
            _make_tool("openfoam", ["cfd"]),
            _make_tool("lammps", ["md"]),
            _make_tool("su2", ["cfd"]),
        ]
        prompt = _build_tool_catalog_prompt(tools)
        # Both category headers should appear
        assert "### cfd" in prompt
        assert "### md" in prompt

    def test_empty_tools_returns_placeholder(self) -> None:
        prompt = _build_tool_catalog_prompt([])
        assert "no tools available" in prompt


class TestBuildSelectionPrompt:
    def test_includes_problem_and_catalog(self) -> None:
        prompt = _build_selection_prompt("simulate airfoil", "tool_catalog_here")
        assert "simulate airfoil" in prompt
        assert "tool_catalog_here" in prompt
        assert "## Physics Problem" in prompt
        assert "## Available MCP Tools" in prompt


# -- ToolSelectionAgent tests --


class TestToolSelectionAgent:
    async def test_select_truncates_to_max_tools(self) -> None:
        """If LLM returns >MAX_TOOLS, agent should truncate to MAX_TOOLS by priority."""
        # Create a mock selection with 20 tools
        mock_tools = [SelectedTool(mcp=f"t{i}", reason=f"R{i}", priority=(i % 3) + 1) for i in range(20)]

        # Use model_construct to bypass validation (simulate >15 tools from LLM)
        raw_selection = ToolSelection.model_construct(
            tools=mock_tools,
            reasoning="too many",
            physics_categories=["cfd"],
            confidence=0.9,
        )
        mock_result = MagicMock()
        mock_result.output = raw_selection

        # Patch Agent constructor to avoid ANTHROPIC_API_KEY requirement
        with patch("gpd.mcp.discovery.selector.Agent"):
            agent = ToolSelectionAgent()

        with patch.object(agent._agent, "run", new_callable=AsyncMock, return_value=mock_result):
            result = await agent.select("test problem", [_make_tool("t", ["cfd"])])

        assert len(result.tools) <= MAX_TOOLS
        # Should be sorted by priority (1s first)
        priorities = [t.priority for t in result.tools]
        assert priorities == sorted(priorities)


# -- PhysicsRouter tests --


class TestPhysicsRouterDetectCategories:
    def test_detects_cfd_for_fluid_flow(self) -> None:
        catalog = _make_mock_catalog()
        router = PhysicsRouter(catalog, selector=MagicMock())
        cats = router.detect_categories("fluid flow around an airfoil with turbulence")
        assert "cfd" in cats

    def test_detects_quantum_for_dft(self) -> None:
        catalog = _make_mock_catalog()
        router = PhysicsRouter(catalog, selector=MagicMock())
        cats = router.detect_categories("DFT calculation of band structure using quantum methods")
        assert "quantum" in cats

    def test_returns_all_categories_for_ambiguous(self) -> None:
        catalog = _make_mock_catalog()
        router = PhysicsRouter(catalog, selector=MagicMock())
        cats = router.detect_categories("something completely unrelated to any physics category")
        # Should return all 12 categories since no keywords match
        assert len(cats) == 12


class TestPhysicsRouterRouteAndSelect:
    async def test_calls_catalog_for_detected_categories(self) -> None:
        """route_and_select should call catalog.get_tools_for_category for detected categories."""
        catalog = _make_mock_catalog()
        mock_selector = MagicMock()
        mock_selector.select = AsyncMock(return_value=_make_selection(2))

        router = PhysicsRouter(catalog, selector=mock_selector)
        await router.route_and_select("fluid flow around an airfoil with turbulence")

        # Should have called get_tools_for_category for at least 'cfd'
        called_cats = [call.args[0] for call in catalog.get_tools_for_category.call_args_list]
        assert "cfd" in called_cats

        # Should have called selector.select
        mock_selector.select.assert_called_once()

    async def test_returns_empty_selection_when_no_tools(self) -> None:
        """route_and_select returns empty selection when catalog has no tools."""
        catalog = MagicMock()
        catalog.get_tools_for_category = MagicMock(return_value=[])

        router = PhysicsRouter(catalog, selector=MagicMock())
        result = await router.route_and_select("anything")
        assert len(result.tools) == 0
        assert result.confidence == 0.0
        assert result.reasoning == "No tools available"


# -- display_selection tests --


class TestDisplaySelection:
    def test_formats_output_with_tools(self) -> None:
        selection = _make_selection(3)
        text = display_selection(selection, delay=0.0)
        assert "Selected 3 tools" in text
        assert "tool_0" in text
        assert "priority" in text

    def test_handles_empty_selection(self) -> None:
        selection = ToolSelection(tools=[], reasoning="No tools", physics_categories=[], confidence=0.0)
        text = display_selection(selection, delay=0.0)
        assert "No tools selected" in text


# -- reevaluate_tools tests --


class TestReevaluateTools:
    async def test_invalidates_caches_before_reselecting(self) -> None:
        """reevaluate_tools should invalidate category caches before re-running selection."""
        catalog = _make_mock_catalog()
        mock_selector = MagicMock()
        mock_selector.select = AsyncMock(return_value=_make_selection(2))

        router = PhysicsRouter(catalog, selector=mock_selector)
        current = ToolSelection(
            tools=[SelectedTool(mcp="openfoam", reason="CFD", priority=1)],
            reasoning="initial",
            physics_categories=["cfd", "fem"],
            confidence=0.9,
        )

        await router.reevaluate_tools("test problem", current, milestone_context="learned something")

        # Should have invalidated caches for both categories
        invalidate_calls = [call.args[0] for call in catalog.invalidate_category.call_args_list]
        assert "cfd" in invalidate_calls
        assert "fem" in invalidate_calls

        # Should have re-run selection
        mock_selector.select.assert_called_once()
