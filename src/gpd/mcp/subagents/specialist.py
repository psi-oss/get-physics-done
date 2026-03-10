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

DEFAULT_SPECIALIST_THRESHOLD = 3

SPECIALIST_PROMPT_TEMPLATE: str = """You are a read-only specialist for the {mcp_name} MCP tool.

TOOL OVERVIEW:
{overview}

AVAILABLE OPERATIONS:
{tools_desc}

PHYSICS DOMAINS: {domains}

You do not execute the MCP tool directly. You only have Read, Grep, and Glob,
so reason from this metadata and any project files you inspect.
Help the parent agent decide when and how to use this MCP.
Always return results as JSON."""

SPECIALIST_TOOLS: list[str] = ["Read", "Grep", "Glob"]
"""Read-only tools for specialists. No Task, Write, or Bash."""


class SpecialistLifecycle(StrEnum):
    """Lifecycle type for specialist agents."""

    EPHEMERAL = "ephemeral"
    PERSISTENT = "persistent"


def _parse_lifecycle(lifecycle: SpecialistLifecycle | str) -> SpecialistLifecycle:
    """Normalize lifecycle inputs and reject unknown values."""
    return lifecycle if isinstance(lifecycle, SpecialistLifecycle) else SpecialistLifecycle(lifecycle)


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
    domains = ", ".join(tool.domains[:5]) or "general physics workflows"

    description = (
        f"Read-only specialist for planning use of the {tool.name} MCP. "
        f"Use when the parent agent needs focused guidance about {tool.name} in {domains}."
    )

    prompt = SPECIALIST_PROMPT_TEMPLATE.format(
        mcp_name=tool.name,
        overview=tool.overview or "No overview available.",
        tools_desc=tools_desc or "  No tools listed.",
        domains=domains,
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
        self._lifecycles: dict[str, SpecialistLifecycle] = {}

    def get_or_create(self, tool: ToolEntry) -> object:
        """Get cached specialist or create a new one."""
        if tool.name in self._specialists:
            return self._specialists[tool.name]

        definition = create_tool_specialist(tool)
        self._specialists[tool.name] = definition
        logger.info("Created specialist for %s (active: %d)", tool.name, self.active_count)
        return definition

    def get_all_specialists(self) -> dict[str, object]:
        """Return all active specialists for passing as agents parameter."""
        return dict(self._specialists)

    @property
    def active_count(self) -> int:
        """Return the current number of cached specialists."""
        return len(self._specialists)

    def set_lifecycle(self, mcp_name: str, lifecycle: SpecialistLifecycle | str) -> None:
        """Store the lifecycle type for a specialist."""
        self._lifecycles[mcp_name] = _parse_lifecycle(lifecycle)

    def get_lifecycle(self, mcp_name: str) -> SpecialistLifecycle:
        """Return the lifecycle type for a specialist, defaulting to ephemeral."""
        return self._lifecycles.get(mcp_name, SpecialistLifecycle.EPHEMERAL)

    def remove(self, mcp_name: str) -> bool:
        """Remove a specialist from the cache (only if ephemeral; persistent stays until clear())."""
        if mcp_name not in self._specialists:
            return False
        if self.get_lifecycle(mcp_name) == SpecialistLifecycle.PERSISTENT:
            logger.debug("Skipping removal of persistent specialist %s", mcp_name)
            return False
        del self._specialists[mcp_name]
        self._lifecycles.pop(mcp_name, None)
        logger.info("Removed ephemeral specialist for %s (active: %d)", mcp_name, self.active_count)
        return True

    def remove_ephemeral(self, mcp_name: str) -> bool:
        """Backward-compatible alias for ``remove()``."""
        return self.remove(mcp_name)

    def clear(self) -> None:
        """Clear all specialists (session end)."""
        count = len(self._specialists)
        self._specialists.clear()
        self._lifecycles.clear()
        logger.info("Cleared %d specialists", count)

    @property
    def active_specialist_names(self) -> list[str]:
        """Return sorted list of active specialist mcp_names."""
        return sorted(self._specialists.keys())


def should_use_specialist(tool_call_count: int, threshold: int = DEFAULT_SPECIALIST_THRESHOLD) -> bool:
    """Heuristic: spawn a specialist if a tool has been called many times.

    When a tool is called more than threshold times in a research step,
    it's worth spawning a dedicated specialist for deeper expertise.
    """
    if threshold < 0:
        msg = "threshold must be non-negative"
        raise ValueError(msg)
    return tool_call_count > threshold
