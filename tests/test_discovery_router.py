"""Tests for auto-substitute fallback, MCP Builder contract, and full module exports."""

from __future__ import annotations

import pytest

from gpd.mcp.discovery.fallback import (
    AutoSubstituteResult,
    MCPBuilderRequest,
    MCPBuilderResult,
    find_substitute,
    request_mcp_build,
    should_request_build,
)
from gpd.mcp.discovery.models import MCPStatus, ToolEntry

# -- Test fixtures --


def _make_tool(
    name: str,
    categories: list[str],
    status: MCPStatus = MCPStatus.available,
    tools: list[dict[str, str]] | None = None,
) -> ToolEntry:
    """Create a test ToolEntry."""
    return ToolEntry(
        name=name,
        description=f"{name} simulator",
        source="modal",
        status=status,
        categories=categories,
        domains=[f"{name} domain"],
        tools=tools or [{"name": "create_simulation", "desc": "Create a sim"}],
        overview=f"Overview of {name}",
    )


# -- find_substitute tests --


class TestFindSubstitute:
    def test_returns_same_category_tool(self) -> None:
        """Should find a substitute in the same physics category."""
        tools = [
            _make_tool("openfoam", ["cfd"]),
            _make_tool("su2", ["cfd"]),
        ]
        result = find_substitute("openfoam", tools)
        assert result.substitute_tool == "su2"
        assert result.confidence > 0

    def test_returns_none_when_no_alternatives(self) -> None:
        """Should return None when no same-category tools exist."""
        tools = [
            _make_tool("openfoam", ["cfd"]),
            _make_tool("qutip", ["quantum"]),
        ]
        result = find_substitute("openfoam", tools)
        assert result.substitute_tool is None
        assert result.confidence == 0.0

    def test_excludes_tools_in_exclude_set(self) -> None:
        """Tools in the exclude set should not be considered as substitutes."""
        tools = [
            _make_tool("openfoam", ["cfd"]),
            _make_tool("su2", ["cfd"]),
            _make_tool("dedalus", ["cfd"]),
        ]
        result = find_substitute("openfoam", tools, exclude={"su2"})
        assert result.substitute_tool == "dedalus"

    def test_prefers_more_category_overlap(self) -> None:
        """Tools with more shared categories should score higher."""
        tools = [
            _make_tool("openfoam", ["cfd", "multiphysics"]),
            _make_tool("su2", ["cfd"]),  # 1 overlap
            _make_tool("precice", ["cfd", "multiphysics"]),  # 2 overlaps
        ]
        result = find_substitute("openfoam", tools)
        assert result.substitute_tool == "precice"

    def test_prefers_preferred_mcps(self) -> None:
        """Tools on the preferred_mcps list should get a scoring bonus."""
        tools = [
            _make_tool("openfoam", ["cfd"]),
            _make_tool("su2", ["cfd"]),  # preferred for cfd
            _make_tool("custom_cfd", ["cfd"]),  # not preferred
        ]
        result = find_substitute("openfoam", tools)
        # su2 is on the preferred_mcps list for cfd, should be preferred
        assert result.substitute_tool == "su2"

    def test_confidence_higher_for_multi_category_match(self) -> None:
        """Multi-category overlap should yield higher confidence."""
        tools = [
            _make_tool("openfoam", ["cfd", "multiphysics"]),
            _make_tool("precice", ["cfd", "multiphysics"]),
        ]
        result = find_substitute("openfoam", tools)
        assert result.confidence >= 0.8

    def test_confidence_lower_for_single_category_match(self) -> None:
        """Single-category overlap should yield lower confidence."""
        tools = [
            _make_tool("openfoam", ["cfd"]),
            _make_tool("custom_cfd", ["cfd"]),
        ]
        result = find_substitute("openfoam", tools)
        assert result.confidence == 0.5

    def test_returns_not_found_for_missing_tool(self) -> None:
        """If the failed tool is not in available_tools, return no substitute."""
        tools = [_make_tool("su2", ["cfd"])]
        result = find_substitute("nonexistent", tools)
        assert result.substitute_tool is None
        assert "not found" in result.reason

    def test_skips_unavailable_tools(self) -> None:
        """Unavailable tools should not be considered as substitutes."""
        tools = [
            _make_tool("openfoam", ["cfd"]),
            _make_tool("su2", ["cfd"], status=MCPStatus.unavailable),
            _make_tool("dedalus", ["cfd"]),
        ]
        result = find_substitute("openfoam", tools)
        assert result.substitute_tool == "dedalus"


# -- AutoSubstituteResult model tests --


class TestAutoSubstituteResult:
    def test_model_fields(self) -> None:
        result = AutoSubstituteResult(
            original_tool="openfoam",
            substitute_tool="su2",
            reason="Same category",
            confidence=0.8,
        )
        assert result.original_tool == "openfoam"
        assert result.substitute_tool == "su2"
        assert result.reason == "Same category"
        assert result.confidence == 0.8

    def test_none_substitute_allowed(self) -> None:
        result = AutoSubstituteResult(
            original_tool="openfoam",
            reason="No substitute found",
            confidence=0.0,
        )
        assert result.substitute_tool is None


# -- MCP Builder contract tests --


class TestMCPBuilderModels:
    def test_request_creation(self) -> None:
        req = MCPBuilderRequest(
            capability_gap="protein folding simulation",
            research_context="Studying protein misfolding in Alzheimer's",
        )
        assert req.capability_gap == "protein folding simulation"
        assert req.priority == "normal"

    def test_request_urgent_priority(self) -> None:
        req = MCPBuilderRequest(
            capability_gap="missing solver",
            research_context="blocked",
            priority="urgent",
        )
        assert req.priority == "urgent"

    def test_result_success(self) -> None:
        result = MCPBuilderResult(
            success=True,
            mcp_name="protein_folding",
            deploy_url="https://modal.com/protein_folding",
        )
        assert result.success is True
        assert result.mcp_name == "protein_folding"

    def test_result_failure(self) -> None:
        result = MCPBuilderResult(
            success=False,
            error_message="Build failed: missing dependencies",
        )
        assert result.success is False
        assert result.mcp_name is None


class TestRequestMCPBuild:
    async def test_raises_without_catalog(self) -> None:
        """Phase 6: request_mcp_build raises ValueError without catalog."""
        req = MCPBuilderRequest(
            capability_gap="test",
            research_context="test",
        )
        with pytest.raises(ValueError, match="ToolCatalog required"):
            await request_mcp_build(req)


# -- should_request_build tests --


class TestShouldRequestBuild:
    def test_returns_true_when_no_substitute(self) -> None:
        result = AutoSubstituteResult(
            original_tool="missing_tool",
            substitute_tool=None,
            reason="No substitute",
            confidence=0.0,
        )
        assert should_request_build("missing_tool", result) is True

    def test_returns_false_when_substitute_exists(self) -> None:
        result = AutoSubstituteResult(
            original_tool="openfoam",
            substitute_tool="su2",
            reason="Found substitute",
            confidence=0.7,
        )
        assert should_request_build("openfoam", result) is False


# -- Full module export tests --


class TestFullModuleExports:
    def test_all_discovery_exports(self) -> None:
        """All symbols from both plans should be importable from gpd.mcp.discovery."""
        from gpd.mcp.discovery import (
            display_selection,
            find_substitute,
            reevaluate_tools,
            request_mcp_build,
            route_and_select,
            select_tools,
        )

        # Verify key types are actual classes/functions
        assert callable(find_substitute)
        assert callable(request_mcp_build)
        assert callable(select_tools)
        assert callable(display_selection)
        assert callable(route_and_select)
        assert callable(reevaluate_tools)
