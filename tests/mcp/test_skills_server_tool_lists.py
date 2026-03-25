"""Regression tests for MCP skill tool list projection."""

from __future__ import annotations

from unittest.mock import patch

from gpd.registry import AgentDef, CommandDef, SkillDef


def test_get_skill_command_allowed_tools_are_defensive_copies() -> None:
    from gpd.mcp.servers.skills_server import get_skill

    command_tools = ["file_read", "shell", "shell"]
    command = CommandDef(
        name="gpd:help",
        description="Help.",
        argument_hint="",
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
    result["allowed_tools"].append("network")
    assert agent.tools == ["shell", "file_read", "shell"]
