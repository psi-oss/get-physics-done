"""Integration tests for subagent spawning -- all SDK calls mocked."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gpd.mcp.discovery.fallback import (
    AutoSubstituteResult,
    MCPBuilderRequest,
    MCPBuilderResult,
    request_mcp_build,
)
from gpd.mcp.discovery.models import MCPStatus, ToolEntry
from gpd.mcp.subagents.models import SubagentResult, ToolCreateResult, ToolFixRequest
from gpd.mcp.subagents.orchestrator import SubagentOrchestrator
from gpd.mcp.subagents.specialist import SpecialistManager
from gpd.mcp.subagents.tool_spec import ToolSpec


@dataclass
class FakeAgentDefinition:
    description: str = "test"
    prompt: str = "test"
    tools: list[str] | None = None
    model: str | None = None


def _make_mock_sdk(result_json: str, success: bool = True) -> MagicMock:
    mock_sdk = MagicMock()
    mock_sdk.spawn = AsyncMock(
        return_value=SubagentResult(
            success=success,
            result_text=result_json,
            cost_usd=0.05,
            session_id="sess-test",
            duration_seconds=5.0,
        )
    )
    return mock_sdk


def _make_tool_entry(name: str, categories: list[str]) -> ToolEntry:
    return ToolEntry(
        name=name,
        description=f"{name} tool",
        source="modal",
        status=MCPStatus.available,
        categories=categories,
        domains=["computational fluid dynamics"],
        tools=[{"name": "create_simulation", "desc": "Create sim"}],
        overview="A simulation tool.",
    )


@pytest.mark.asyncio
async def test_request_mcp_build_delegates_to_orchestrator():
    """request_mcp_build should delegate to SubagentOrchestrator via spec drafter."""
    mock_catalog = MagicMock()
    mock_catalog.invalidate_all = MagicMock()

    mock_spec = ToolSpec(
        name="protein_folder",
        domain="bio",
        description="Protein folding",
        inputs=[{"name": "seq", "type": "str", "description": "Amino acid sequence"}],
        outputs=[{"name": "coords", "type": "dict", "description": "3D coords"}],
        expected_behavior="Folds proteins",
    )

    mock_create_result = ToolCreateResult(
        success=True,
        mcp_name="protein_folder",
        deploy_url="https://example.com",
        cost_usd=0.05,
    )

    mock_orchestrator_instance = MagicMock()
    mock_orchestrator_instance.create_new_tool = AsyncMock(return_value=mock_create_result)

    mock_drafter_instance = MagicMock()
    mock_drafter_instance.draft = AsyncMock(return_value=mock_spec)

    # Patch at the source module level (where `from ... import` resolves)
    with (
        patch("gpd.mcp.subagents.orchestrator.SubagentOrchestrator", return_value=mock_orchestrator_instance),
        patch("gpd.mcp.subagents.tool_spec.ToolSpecDrafter", return_value=mock_drafter_instance),
    ):
        result = await request_mcp_build(
            MCPBuilderRequest(capability_gap="protein folding", research_context="study"),
            catalog=mock_catalog,
        )

    assert isinstance(result, MCPBuilderResult)
    assert result.success is True
    assert result.mcp_name == "protein_folder"


@pytest.mark.asyncio
async def test_request_mcp_build_without_catalog_raises():
    """request_mcp_build without catalog should raise ValueError."""
    with pytest.raises(ValueError, match="ToolCatalog required"):
        await request_mcp_build(MCPBuilderRequest(capability_gap="test", research_context="test"))


@pytest.mark.asyncio
async def test_request_mcp_build_failure_propagates():
    """Build failure should propagate to MCPBuilderResult."""
    mock_catalog = MagicMock()

    mock_spec = ToolSpec(
        name="broken",
        domain="utility",
        description="broken tool",
        inputs=[],
        outputs=[],
        expected_behavior="fails",
    )

    mock_create_result = ToolCreateResult(
        success=False,
        error_message="build failed",
        cost_usd=0.01,
    )

    mock_orchestrator_instance = MagicMock()
    mock_orchestrator_instance.create_new_tool = AsyncMock(return_value=mock_create_result)

    mock_drafter_instance = MagicMock()
    mock_drafter_instance.draft = AsyncMock(return_value=mock_spec)

    with (
        patch("gpd.mcp.subagents.orchestrator.SubagentOrchestrator", return_value=mock_orchestrator_instance),
        patch("gpd.mcp.subagents.tool_spec.ToolSpecDrafter", return_value=mock_drafter_instance),
    ):
        result = await request_mcp_build(
            MCPBuilderRequest(capability_gap="broken thing", research_context="test"),
            catalog=mock_catalog,
        )

    assert isinstance(result, MCPBuilderResult)
    assert result.success is False


@pytest.mark.asyncio
async def test_full_fix_workflow():
    """Full fix workflow: orchestrator -> spawn -> parse -> hot-add."""
    mock_sdk = _make_mock_sdk('{"success": true, "mcp_name": "openfoam", "version_hash": "abc"}')
    mock_catalog = MagicMock()
    mock_catalog.invalidate_all = MagicMock()

    with patch("gpd.mcp.subagents.orchestrator.create_mcp_builder_definition", return_value=FakeAgentDefinition()):
        orchestrator = SubagentOrchestrator(catalog=mock_catalog, sdk=mock_sdk)
        result = await orchestrator.fix_broken_tool(
            ToolFixRequest(
                mcp_name="openfoam",
                error_id=1,
                error_summary="ImportError",
                error_type="ImportError",
                fix_complexity="simple",
                timeout_seconds=180,
            )
        )

    assert result.success is True
    mock_catalog.invalidate_all.assert_called_once()


@pytest.mark.asyncio
async def test_handle_failure_with_substitute_skips_spawn():
    """Moderate error with substitute should skip spawning and return substitute."""
    mock_sdk = _make_mock_sdk("{}")
    mock_catalog = MagicMock()

    available_tools = [
        _make_tool_entry("openfoam", ["cfd"]),
        _make_tool_entry("su2", ["cfd"]),
    ]

    with patch("gpd.mcp.subagents.orchestrator.create_mcp_builder_definition", return_value=FakeAgentDefinition()):
        orchestrator = SubagentOrchestrator(catalog=mock_catalog, sdk=mock_sdk)
        result = await orchestrator.handle_tool_failure(
            mcp_name="openfoam",
            error_type="RuntimeError",
            error_message="generic error",
            error_id=1,
            available_tools=available_tools,
        )

    assert isinstance(result, AutoSubstituteResult)
    mock_sdk.spawn.assert_not_called()


def test_specialist_integration_with_orchestrator():
    """Specialist definitions should be passable as agents parameter."""
    with patch.dict("sys.modules", {"claude_agent_sdk": type("M", (), {"AgentDefinition": FakeAgentDefinition})()}):
        manager = SpecialistManager()
        tool = _make_tool_entry("openfoam", ["cfd"])
        manager.get_or_create(tool)

        specialists = manager.get_all_specialists()
        assert "openfoam" in specialists
        assert isinstance(specialists["openfoam"], FakeAgentDefinition)
        assert "openfoam" in specialists["openfoam"].prompt
