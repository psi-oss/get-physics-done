"""Tests for specialist sub-agent factory and lifecycle manager."""

from __future__ import annotations

from dataclasses import dataclass
from unittest.mock import patch

import pytest

from gpd.mcp.discovery.models import ToolEntry
from gpd.mcp.subagents.specialist import (
    SpecialistLifecycle,
    SpecialistManager,
    create_tool_specialist,
    should_use_specialist,
)


@dataclass
class FakeAgentDefinition:
    description: str
    prompt: str
    tools: list[str] | None = None
    model: str | None = None


def _make_tool(name: str = "openfoam", tools: list[dict[str, str]] | None = None) -> ToolEntry:
    """Create a ToolEntry for testing."""
    return ToolEntry(
        name=name,
        description=name,
        source="external",
        tools=tools or [{"name": "create_simulation"}],
    )


def _patched_create(tool: ToolEntry) -> FakeAgentDefinition:
    """Create specialist using fake AgentDefinition."""
    fake_module = type("M", (), {"AgentDefinition": FakeAgentDefinition})()
    with patch.dict("sys.modules", {"claude_agent_sdk": fake_module}):
        return create_tool_specialist(tool)


def test_create_specialist_has_tool_name_in_description():
    """Specialist description should contain the MCP tool name."""
    definition = _patched_create(_make_tool("openfoam"))
    assert "openfoam" in definition.description


def test_create_specialist_has_tool_list_in_prompt():
    """Specialist prompt should contain tool names from ToolEntry."""
    tool = _make_tool("openfoam", tools=[{"name": "create_simulation", "desc": "Create sim"}])
    definition = _patched_create(tool)
    assert "create_simulation" in definition.prompt


def test_create_specialist_prompt_matches_read_only_surface():
    """Prompt should describe the specialist's actual read-only role."""
    definition = _patched_create(_make_tool("openfoam"))
    assert "read-only specialist" in definition.prompt.lower()
    assert "do not execute the mcp tool directly" in definition.prompt.lower()


def test_create_specialist_no_task_tool():
    """Specialist should not have Task, Write, or Bash tools."""
    definition = _patched_create(_make_tool())
    assert "Task" not in definition.tools
    assert "Write" not in definition.tools
    assert "Bash" not in definition.tools


def test_specialist_manager_caches():
    """Creating same tool twice returns cached definition."""
    tool = _make_tool("openfoam")
    with patch.dict("sys.modules", {"claude_agent_sdk": type("M", (), {"AgentDefinition": FakeAgentDefinition})()}):
        manager = SpecialistManager()
        first = manager.get_or_create(tool)
        second = manager.get_or_create(tool)
    assert first is second
    assert manager.active_count == 1


def test_specialist_manager_multiple_tools():
    """Multiple tools create separate specialists."""
    with patch.dict("sys.modules", {"claude_agent_sdk": type("M", (), {"AgentDefinition": FakeAgentDefinition})()}):
        manager = SpecialistManager()
        manager.get_or_create(_make_tool("openfoam"))
        manager.get_or_create(_make_tool("lammps"))
    assert "openfoam" in manager.active_specialist_names
    assert "lammps" in manager.active_specialist_names
    assert len(manager.get_all_specialists()) == 2


def test_specialist_manager_remove():
    """Removing a specialist decrements count and removes from names."""
    with patch.dict("sys.modules", {"claude_agent_sdk": type("M", (), {"AgentDefinition": FakeAgentDefinition})()}):
        manager = SpecialistManager()
        manager.get_or_create(_make_tool("openfoam"))
        manager.remove("openfoam")
    assert manager.active_specialist_names == []
    assert manager.active_count == 0


def test_specialist_manager_keeps_persistent_specialists():
    """Persistent specialists stay cached until clear()."""
    with patch.dict("sys.modules", {"claude_agent_sdk": type("M", (), {"AgentDefinition": FakeAgentDefinition})()}):
        manager = SpecialistManager()
        manager.get_or_create(_make_tool("openfoam"))
        manager.set_lifecycle("openfoam", SpecialistLifecycle.PERSISTENT)
        removed = manager.remove("openfoam")
    assert removed is False
    assert manager.active_specialist_names == ["openfoam"]


def test_specialist_manager_clear():
    """Clearing removes all specialists and resets count."""
    with patch.dict("sys.modules", {"claude_agent_sdk": type("M", (), {"AgentDefinition": FakeAgentDefinition})()}):
        manager = SpecialistManager()
        manager.get_or_create(_make_tool("openfoam"))
        manager.get_or_create(_make_tool("lammps"))
        manager.get_or_create(_make_tool("su2"))
        manager.clear()
    assert manager.active_count == 0
    assert manager.active_specialist_names == []


def test_should_use_specialist_below_threshold():
    """Below default threshold of 3, should not use specialist."""
    assert should_use_specialist(2) is False


def test_should_use_specialist_above_threshold():
    """Above default threshold, should use specialist."""
    assert should_use_specialist(4) is True


def test_should_use_specialist_custom_threshold():
    """Custom threshold should be respected."""
    assert should_use_specialist(2, threshold=1) is True


def test_should_use_specialist_rejects_negative_threshold():
    """Threshold validation should reject nonsensical values."""
    with pytest.raises(ValueError, match="threshold must be non-negative"):
        should_use_specialist(1, threshold=-1)
