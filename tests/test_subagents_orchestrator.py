"""Tests for subagent spawn orchestrator."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from gpd.mcp.discovery.fallback import AutoSubstituteResult
from gpd.mcp.discovery.models import MCPStatus, ToolEntry
from gpd.mcp.subagents.models import (
    SubagentResult,
    ToolCreateRequest,
    ToolCreateResult,
    ToolFixRequest,
    ToolFixResult,
)
from gpd.mcp.subagents.orchestrator import SubagentOrchestrator
from gpd.mcp.subagents.tool_spec import ToolSpec, spec_to_create_request


@dataclass
class FakeAgentDefinition:
    description: str = "test"
    prompt: str = "test"
    tools: list[str] | None = None
    model: str | None = None


def _make_mock_sdk(result_json: str, success: bool = True) -> MagicMock:
    """Create a mock SubagentSDK that returns a canned result."""
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


def _make_mock_catalog() -> MagicMock:
    """Create a mock ToolCatalog."""
    catalog = MagicMock()
    catalog.invalidate_all = MagicMock()
    return catalog


def _make_tool_entry(name: str, categories: list[str], status: MCPStatus = MCPStatus.available) -> ToolEntry:
    """Create a ToolEntry for testing."""
    return ToolEntry(
        name=name,
        description=f"{name} tool",
        source="modal",
        status=status,
        categories=categories,
        domains=[],
        tools=[],
    )


@pytest.mark.asyncio
async def test_fix_broken_tool_success():
    """Mock spawn to return success, verify ToolFixResult."""
    mock_sdk = _make_mock_sdk('{"success": true, "mcp_name": "openfoam", "version_hash": "abc123"}')
    mock_catalog = _make_mock_catalog()

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

    assert isinstance(result, ToolFixResult)
    assert result.success is True
    assert result.mcp_name == "openfoam"
    mock_catalog.invalidate_all.assert_called_once()


@pytest.mark.asyncio
async def test_fix_broken_tool_failure():
    """Mock spawn to return failure, verify ToolFixResult.success == False."""
    mock_sdk = _make_mock_sdk('{"success": false, "mcp_name": "openfoam", "error_message": "build failed"}')
    mock_catalog = _make_mock_catalog()

    with patch("gpd.mcp.subagents.orchestrator.create_mcp_builder_definition", return_value=FakeAgentDefinition()):
        orchestrator = SubagentOrchestrator(catalog=mock_catalog, sdk=mock_sdk)
        result = await orchestrator.fix_broken_tool(
            ToolFixRequest(
                mcp_name="openfoam",
                error_id=1,
                error_summary="build error",
                error_type="BuildError",
                fix_complexity="complex",
                timeout_seconds=900,
            )
        )

    assert isinstance(result, ToolFixResult)
    assert result.success is False


@pytest.mark.asyncio
async def test_create_new_tool_success():
    """Mock spawn to return success with deploy_url."""
    mock_sdk = _make_mock_sdk('{"success": true, "mcp_name": "new_tool", "deploy_url": "https://example.com"}')
    mock_catalog = _make_mock_catalog()

    with patch("gpd.mcp.subagents.orchestrator.create_mcp_builder_definition", return_value=FakeAgentDefinition()):
        orchestrator = SubagentOrchestrator(catalog=mock_catalog, sdk=mock_sdk)
        result = await orchestrator.create_new_tool(
            ToolCreateRequest(
                name="new_tool",
                domain="bio",
                description="A new tool",
                inputs=[{"name": "x", "type": "float", "description": "input"}],
                outputs=[{"name": "y", "type": "float", "description": "output"}],
                research_context="testing",
            )
        )

    assert isinstance(result, ToolCreateResult)
    assert result.success is True
    assert result.mcp_name == "new_tool"


@pytest.mark.asyncio
async def test_handle_tool_failure_substitutes():
    """With same-category substitute and moderate error, should return AutoSubstituteResult."""
    mock_sdk = _make_mock_sdk("{}")  # Should not be called
    mock_catalog = _make_mock_catalog()

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
    assert result.substitute_tool == "su2"
    mock_sdk.spawn.assert_not_called()


@pytest.mark.asyncio
async def test_handle_tool_failure_fixes():
    """No substitute available, simple error -> should spawn MCP Builder."""
    mock_sdk = _make_mock_sdk('{"success": true, "mcp_name": "unique_tool", "version_hash": "abc"}')
    mock_catalog = _make_mock_catalog()

    available_tools = [
        _make_tool_entry("unique_tool", ["quantum"]),
    ]

    with patch("gpd.mcp.subagents.orchestrator.create_mcp_builder_definition", return_value=FakeAgentDefinition()):
        orchestrator = SubagentOrchestrator(catalog=mock_catalog, sdk=mock_sdk)
        result = await orchestrator.handle_tool_failure(
            mcp_name="unique_tool",
            error_type="ImportError",
            error_message="module not found",
            error_id=2,
            available_tools=available_tools,
        )

    assert isinstance(result, ToolFixResult)
    assert result.success is True
    mock_sdk.spawn.assert_called_once()


@pytest.mark.asyncio
async def test_handle_tool_failure_no_available_fix():
    """Complex error, no substitute, but fix is still attempted."""
    mock_sdk = _make_mock_sdk('{"success": true, "mcp_name": "broken_tool", "version_hash": "def"}')
    mock_catalog = _make_mock_catalog()

    available_tools = [
        _make_tool_entry("broken_tool", ["geophysics"]),
    ]

    with patch("gpd.mcp.subagents.orchestrator.create_mcp_builder_definition", return_value=FakeAgentDefinition()):
        orchestrator = SubagentOrchestrator(catalog=mock_catalog, sdk=mock_sdk)
        result = await orchestrator.handle_tool_failure(
            mcp_name="broken_tool",
            error_type="TimeoutError",
            error_message="request timed out",
            error_id=3,
            available_tools=available_tools,
        )

    assert isinstance(result, ToolFixResult)
    assert result.success is True


@pytest.mark.asyncio
async def test_hot_add_invalidates_catalog():
    """Verify catalog.invalidate_all() called after successful fix."""
    mock_sdk = _make_mock_sdk('{"success": true, "mcp_name": "openfoam", "version_hash": "xyz"}')
    mock_catalog = _make_mock_catalog()

    with patch("gpd.mcp.subagents.orchestrator.create_mcp_builder_definition", return_value=FakeAgentDefinition()):
        orchestrator = SubagentOrchestrator(catalog=mock_catalog, sdk=mock_sdk)
        await orchestrator.fix_broken_tool(
            ToolFixRequest(
                mcp_name="openfoam",
                error_id=1,
                error_summary="err",
                error_type="ImportError",
                fix_complexity="simple",
                timeout_seconds=180,
            )
        )

    mock_catalog.invalidate_all.assert_called_once()


def test_spec_to_create_request_conversion():
    """Verify ToolSpec -> ToolCreateRequest conversion."""
    spec = ToolSpec(
        name="protein_folder",
        domain="bio",
        description="Protein folding",
        inputs=[{"name": "seq", "type": "str", "description": "Amino acid sequence"}],
        outputs=[{"name": "coords", "type": "dict", "description": "3D coordinates"}],
        expected_behavior="Folds proteins",
        similar_tools=["autodock_vina"],
        constraints=["must run on Modal"],
    )
    request = spec_to_create_request(spec, research_context="study")
    assert request.name == "protein_folder"
    assert request.domain == "bio"
    assert len(request.inputs) == 1
    assert request.similar_tools == ["autodock_vina"]
    assert request.research_context == "study"
