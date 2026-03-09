"""Tool specialist sub-agent factory and lifecycle manager.

Creates dedicated AgentDefinition instances for individual MCP tools,
giving them deep context about the tool's capabilities. Manages
session-scoped specialist lifecycle with caching.
"""

from __future__ import annotations

import logging
from enum import StrEnum

from gpd.mcp.discovery.models import ToolEntry

logger = logging.getLogger(__name__)

SPECIALIST_PROMPT_TEMPLATE: str = """You are a specialist for the {mcp_name} MCP tool.

TOOL OVERVIEW:
{overview}

AVAILABLE TOOLS:
{tools_desc}

PHYSICS DOMAINS: {domains}

You have deep expertise in this tool's capabilities and quirks.
Make all tool calls yourself. Return structured results to the parent agent.
Optimize for efficiency -- batch operations when possible.
Always return results as JSON."""

SPECIALIST_TOOLS: list[str] = ["Read", "Grep", "Glob"]
"""Read-only tools for specialists. No Task, Write, or Bash."""


class AgentLifecycle(StrEnum):
    """Lifecycle type for specialist agents."""

    EPHEMERAL = "ephemeral"
    PERSISTENT = "persistent"


def analyze_tool_reuse(plan: object) -> dict[str, str]:
    """Analyze plan for tool reuse patterns to determine agent allocation.

    Tools used in >1 milestone get "persistent" agents (session-scoped).
    Tools used in exactly 1 milestone get "ephemeral" agents (single-use).

    Args:
        plan: ResearchPlan object with milestones attribute.

    Returns:
        Dict mapping tool_name -> "ephemeral" | "persistent".
    """
    tool_milestone_count: dict[str, int] = {}
    for milestone in getattr(plan, "milestones", []):
        for tool in getattr(milestone, "tools", []):
            tool_milestone_count[tool] = tool_milestone_count.get(tool, 0) + 1

    return {tool: "persistent" if count > 1 else "ephemeral" for tool, count in tool_milestone_count.items()}


def create_tool_specialist(tool: ToolEntry) -> object:
    """Create an AgentDefinition specialized for a specific MCP tool.

    The specialist gets a dynamically-generated system prompt with the tool's
    overview, tool list, and domain expertise. Read-only tools only.

    Returns an AgentDefinition (from claude_agent_sdk).

    Raises:
        RuntimeError: If claude-agent-sdk is not installed.
    """
    try:
        from claude_agent_sdk import AgentDefinition
    except ImportError:
        raise RuntimeError("claude-agent-sdk not installed. Run: pip install claude-agent-sdk") from None

    tools_desc = "\n".join(f"  - {t.get('name', 'unknown')}: {t.get('desc', 'no description')}" for t in tool.tools)
    domains = ", ".join(tool.domains[:5])

    description = (
        f"Specialist for the {tool.name} MCP tool. Use when research "
        f"requires deep interaction with {tool.name} ({domains})."
    )

    prompt = SPECIALIST_PROMPT_TEMPLATE.format(
        mcp_name=tool.name,
        overview=tool.overview or "No overview available.",
        tools_desc=tools_desc or "  No tools listed.",
        domains=domains or "general",
    )

    return AgentDefinition(
        description=description,
        prompt=prompt,
        tools=SPECIALIST_TOOLS,
        model="sonnet",
    )


class SpecialistManager:
    """Session-scoped lifecycle manager for tool specialist sub-agents.

    Caches AgentDefinitions by mcp_name. Not shared across sessions.
    """

    def __init__(self) -> None:
        self._specialists: dict[str, object] = {}
        self._active_count: int = 0
        self._lifecycles: dict[str, str] = {}

    def get_or_create(self, tool: ToolEntry) -> object:
        """Get cached specialist or create a new one."""
        if tool.name in self._specialists:
            return self._specialists[tool.name]

        definition = create_tool_specialist(tool)
        self._specialists[tool.name] = definition
        self._active_count += 1
        logger.info("Created specialist for %s (active: %d)", tool.name, self._active_count)
        return definition

    def get_all_specialists(self) -> dict[str, object]:
        """Return all active specialists for passing as agents parameter."""
        return dict(self._specialists)

    def set_lifecycle(self, mcp_name: str, lifecycle: str) -> None:
        """Store the lifecycle type for a specialist."""
        self._lifecycles[mcp_name] = lifecycle

    def get_lifecycle(self, mcp_name: str) -> str:
        """Return the lifecycle type for a specialist, defaulting to ephemeral."""
        return self._lifecycles.get(mcp_name, AgentLifecycle.EPHEMERAL)

    def remove(self, mcp_name: str) -> None:
        """Remove a specialist from the cache (only if ephemeral; persistent stays until clear())."""
        if mcp_name not in self._specialists:
            return
        if self.get_lifecycle(mcp_name) == AgentLifecycle.PERSISTENT:
            logger.debug("Skipping removal of persistent specialist %s", mcp_name)
            return
        del self._specialists[mcp_name]
        self._lifecycles.pop(mcp_name, None)
        self._active_count = max(0, self._active_count - 1)
        logger.info("Removed ephemeral specialist for %s (active: %d)", mcp_name, self._active_count)

    def remove_ephemeral(self, mcp_name: str) -> None:
        """Remove a specialist ONLY if its lifecycle is ephemeral."""
        if self.get_lifecycle(mcp_name) == AgentLifecycle.EPHEMERAL and mcp_name in self._specialists:
            del self._specialists[mcp_name]
            self._lifecycles.pop(mcp_name, None)
            self._active_count = max(0, self._active_count - 1)
            logger.info("Removed ephemeral specialist for %s (active: %d)", mcp_name, self._active_count)

    def clear(self) -> None:
        """Clear all specialists (session end)."""
        count = len(self._specialists)
        self._specialists.clear()
        self._lifecycles.clear()
        self._active_count = 0
        logger.info("Cleared %d specialists", count)

    @property
    def active_specialist_names(self) -> list[str]:
        """Return sorted list of active specialist mcp_names."""
        return sorted(self._specialists.keys())


def should_use_specialist(tool_call_count: int, threshold: int = 3) -> bool:
    """Heuristic: spawn a specialist if a tool has been called many times.

    When a tool is called more than threshold times in a research step,
    it's worth spawning a dedicated specialist for deeper expertise.
    """
    return tool_call_count > threshold
