"""Regression tests for MCP skill tool list projection."""

from __future__ import annotations

import importlib
import sys
from unittest.mock import patch

import gpd.registry as registry_module
from gpd.registry import AgentDef, CommandDef, SkillDef


def test_get_skill_command_allowed_tools_are_defensive_copies() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    command_tools = ["file_read", "shell", "shell"]
    command = CommandDef(
        name="gpd:help",
        description="Help.",
        argument_hint="",
        agent=None,
        requires={},
        allowed_tools=command_tools,
        content="Command body.",
        path="/tmp/gpd-help.md",
        source="commands",
    )
    skill = SkillDef(
        name="gpd-help",
        description="Help.",
        content="Command body.",
        category="help",
        path="/tmp/gpd-help.md",
        source_kind="command",
        registry_name="help",
    )

    with (
        patch("gpd.mcp.servers.skills_server._resolve_skill", return_value=skill),
        patch("gpd.mcp.servers.skills_server.content_registry.get_command", return_value=command),
    ):
        result = get_skill("gpd-help")

    assert result["allowed_tools"] == ["file_read", "shell"]
    assert result["allowed_tools"] is not command.allowed_tools
    assert result["allowed_tools_surface"] == "command.allowed-tools"
    result["allowed_tools"].append("network")
    assert command.allowed_tools == ["file_read", "shell", "shell"]


def test_get_skill_command_surfaces_agent_metadata() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    command = CommandDef(
        name="gpd:plan-phase",
        description="Plan.",
        argument_hint="",
        agent="gpd-planner",
        requires={},
        allowed_tools=["file_read"],
        content="## Command Requirements\n\n```yaml\ncontext_mode: project-required\nproject_reentry_capable: false\nagent: gpd-planner\nallowed_tools:\n  - file_read\n```\n\nBody.",
        path="/tmp/gpd-plan-phase.md",
        source="commands",
    )
    skill = SkillDef(
        name="gpd-plan-phase",
        description="Plan.",
        content=command.content,
        category="planning",
        path="/tmp/gpd-plan-phase.md",
        source_kind="command",
        registry_name="plan-phase",
    )

    with (
        patch("gpd.mcp.servers.skills_server._resolve_skill", return_value=skill),
        patch("gpd.mcp.servers.skills_server.content_registry.get_command", return_value=command),
    ):
        result = get_skill("gpd-plan-phase")

    assert result["agent"] == "gpd-planner"
    assert result["allowed_tools_surface"] == "command.allowed-tools"
    assert result["structured_metadata_authority"]["agent"] == "mirrored"
    assert "agent: gpd-planner" in result["content"]


def test_get_skill_agent_surfaces_allowed_tools() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    agent_tools = ["shell", "file_read", "shell"]
    agent = AgentDef(
        name="gpd-debugger",
        description="Debugger.",
        system_prompt="Agent body.",
        tools=agent_tools,
        color="blue",
        path="/tmp/gpd-debugger.md",
        source="agents",
    )
    skill = SkillDef(
        name="gpd-debugger",
        description="Debugger.",
        content="Agent body.",
        category="debugging",
        path="/tmp/gpd-debugger.md",
        source_kind="agent",
        registry_name="gpd-debugger",
    )

    with (
        patch("gpd.mcp.servers.skills_server._resolve_skill", return_value=skill),
        patch("gpd.mcp.servers.skills_server.content_registry.get_agent", return_value=agent),
    ):
        result = get_skill("gpd-debugger")

    assert result["allowed_tools"] == ["shell", "file_read"]
    assert result["allowed_tools"] is not agent.tools
    assert result["allowed_tools_surface"] == "agent.tools"
    assert result["structured_metadata_authority"] == {
        "content": "canonical",
        "allowed_tools": "mirrored",
        "agent_policy": "mirrored",
    }
    result["allowed_tools"].append("network")
    assert agent.tools == ["shell", "file_read", "shell"]


def test_skills_server_import_is_resilient_to_registry_index_failure(monkeypatch) -> None:
    monkeypatch.setattr(
        registry_module,
        "list_skills",
        lambda: (_ for _ in ()).throw(ValueError("boom")),
    )
    sys.modules.pop("gpd.mcp.servers.skills_server", None)

    module = importlib.import_module("gpd.mcp.servers.skills_server")

    assert hasattr(module, "list_skills")
    assert hasattr(module, "get_skill")
