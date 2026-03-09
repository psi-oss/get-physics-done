"""Tests for MCP Builder agent definition and prompt construction."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from gpd.mcp.subagents.mcp_builder import (
    MCP_BUILDER_TOOLS,
    build_create_prompt,
    build_fix_prompt,
    create_mcp_builder_definition,
    get_mcp_builder_cwd,
    parse_subagent_result,
)
from gpd.mcp.subagents.models import (
    SubagentResult,
    ToolCreateRequest,
    ToolCreateResult,
    ToolFixRequest,
    ToolFixResult,
)


@dataclass
class FakeAgentDefinition:
    """Fake AgentDefinition for testing without claude-agent-sdk."""

    description: str
    prompt: str
    tools: list[str] | None = None
    model: str | None = None


def test_mcp_builder_definition_fields():
    """Verify AgentDefinition has correct description, tools, and model."""
    fake_module = MagicMock()
    fake_module.AgentDefinition = FakeAgentDefinition

    with patch.dict("sys.modules", {"claude_agent_sdk": fake_module}):
        definition = create_mcp_builder_definition()

    assert "MCP Builder specialist" in definition.description
    assert definition.model == "sonnet"
    assert "Read" in definition.tools
    assert "Write" in definition.tools
    assert "Bash" in definition.tools


def test_mcp_builder_tools_no_task():
    """Explicitly assert 'Task' not in MCP_BUILDER_TOOLS."""
    assert "Task" not in MCP_BUILDER_TOOLS


def test_build_fix_prompt_contains_error_info():
    """Verify fix prompt includes mcp_name, error_id, error_summary."""
    request = ToolFixRequest(
        mcp_name="openfoam",
        error_id=42,
        error_summary="ImportError: module not found",
        error_type="ImportError",
        fix_complexity="simple",
        timeout_seconds=180,
    )
    prompt = build_fix_prompt(request)
    assert "openfoam" in prompt
    assert "42" in prompt
    assert "ImportError: module not found" in prompt
    assert "ImportError" in prompt


def test_build_create_prompt_contains_spec():
    """Verify create prompt includes name, domain, inputs, outputs."""
    request = ToolCreateRequest(
        name="protein_folder",
        domain="bio",
        description="Protein folding simulator",
        inputs=[{"name": "sequence", "type": "str", "description": "Amino acid sequence"}],
        outputs=[{"name": "structure", "type": "dict", "description": "3D coordinates"}],
        similar_tools=["autodock_vina"],
        research_context="Studying protein folding kinetics",
    )
    prompt = build_create_prompt(request)
    assert "protein_folder" in prompt
    assert "bio" in prompt
    assert "sequence" in prompt
    assert "structure" in prompt
    assert "autodock_vina" in prompt


def test_parse_subagent_result_fix():
    """Verify JSON extraction from raw result text for ToolFixResult."""
    raw = SubagentResult(
        success=True,
        result_text='I fixed the tool. {"success": true, "mcp_name": "openfoam", "version_hash": "abc123"}',
        cost_usd=0.03,
    )
    result = parse_subagent_result(raw)
    assert isinstance(result, ToolFixResult)
    assert result.success is True
    assert result.mcp_name == "openfoam"
    assert result.version_hash == "abc123"


def test_parse_subagent_result_create():
    """Verify JSON extraction for ToolCreateResult."""
    raw = SubagentResult(
        success=True,
        result_text='Done. {"success": true, "mcp_name": "new_tool", "deploy_url": "https://example.com"}',
        cost_usd=0.10,
    )
    result = parse_subagent_result(raw)
    assert isinstance(result, ToolCreateResult)
    assert result.success is True
    assert result.mcp_name == "new_tool"
    assert result.deploy_url == "https://example.com"


def test_parse_subagent_result_invalid_json():
    """Verify graceful failure when JSON cannot be parsed."""
    raw = SubagentResult(
        success=False,
        result_text="Something went wrong, no JSON here",
        cost_usd=0.01,
    )
    result = parse_subagent_result(raw)
    assert isinstance(result, ToolFixResult)
    assert result.success is False
    assert "Could not parse" in (result.error_message or "")


def test_get_mcp_builder_cwd_resolves():
    """Verify the path resolution returns a valid directory under the project."""
    cwd = get_mcp_builder_cwd()
    assert isinstance(cwd, str)
    from pathlib import Path

    cwd_path = Path(cwd)
    assert cwd_path.is_dir(), f"get_mcp_builder_cwd() returned non-existent path: {cwd}"
    # Should resolve inside the project tree (contains pyproject.toml at some ancestor)
    found_project_root = any((p / "pyproject.toml").exists() for p in [cwd_path, *cwd_path.parents])
    assert found_project_root, f"cwd {cwd} is not inside the project tree"
