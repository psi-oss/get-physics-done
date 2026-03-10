"""GPD agent definitions — delegates to gpd.registry for cached parsing."""

from __future__ import annotations

from gpd.registry import AGENTS_DIR, list_agents
from gpd.registry import get_agent as _get_agent


def get_agent(name: str) -> dict[str, object]:
    """Get an agent definition by name (dict form for backward compat)."""
    agent = _get_agent(name)
    return {
        "name": agent.name,
        "description": agent.description,
        "content": agent.system_prompt,
        "tools": agent.tools,
        "color": agent.color,
    }


__all__ = ["AGENTS_DIR", "list_agents", "get_agent"]
