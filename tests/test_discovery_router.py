"""Tests for auto-substitute fallback and full module exports."""

from __future__ import annotations

from gpd.mcp.discovery.fallback import (
    AutoSubstituteResult,
    find_substitute,
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
        description=name,
        source="external",
        status=status,
        categories=categories,
        tools=tools or [{"name": "create_simulation"}],
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


# -- Full module export tests --


class TestFullModuleExports:
    def test_all_discovery_exports(self) -> None:
        """Remaining discovery helpers should be importable from gpd.mcp.discovery."""
        from gpd.mcp.discovery import (
            ToolCatalog,
            find_substitute,
            get_tool_catalog,
            load_sources_config,
        )

        # Verify key types are actual classes/functions
        assert ToolCatalog is not None
        assert callable(find_substitute)
        assert callable(get_tool_catalog)
        assert callable(load_sources_config)
