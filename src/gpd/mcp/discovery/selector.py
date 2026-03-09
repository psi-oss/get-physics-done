"""LLM-driven tool selection via PydanticAI Agent with structured output.

Uses a PydanticAI Agent() to select the most relevant MCP tools for a given
physics problem description, returning structured ToolSelection with per-tool
rationale and priority scoring.
"""

from __future__ import annotations

import asyncio
import logging
from itertools import groupby

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from gpd.core.model_defaults import GPD_DEFAULT_MODEL, resolve_model_and_settings
from gpd.mcp.discovery.models import OVERVIEW_PREVIEW_MAX_CHARS, ToolEntry

logger = logging.getLogger(__name__)

MAX_TOOLS = 15
"""Hard cap on tools per selection, per user decision."""


class SelectedTool(BaseModel):
    """A single tool selected for a physics problem with rationale."""

    mcp: str
    """MCP identifier."""

    reason: str
    """Why this tool was selected for this problem."""

    priority: int = Field(ge=1, le=3)
    """1=critical (must-have), 2=supporting (helpful), 3=optional (nice-to-have)."""


class ToolSelection(BaseModel):
    """Structured output from the tool selection agent."""

    tools: list[SelectedTool] = Field(max_length=MAX_TOOLS)
    """Selected tools, hard-capped at 15."""

    reasoning: str
    """Overall reasoning for the selection."""

    physics_categories: list[str]
    """Detected physics categories."""

    confidence: float = Field(ge=0.0, le=1.0)
    """Selection confidence."""


SELECTION_SYSTEM_PROMPT = (
    "You are a physics simulation tool router for the GPD+ research agent. "
    "Given a physics problem description and a catalog of available MCP simulation tools, "
    "select the most relevant tools. "
    "Select between 1 and 15 tools. Fewer is better -- only select tools that are genuinely needed. "
    "Priority 1 = critical for solving this problem. Priority 2 = supporting tool that adds value. "
    "Priority 3 = optional nice-to-have. "
    "Always explain WHY each tool is needed for this specific problem. "
    "Focus on tools that are marked as 'available'. Prefer available tools over unknown/stale ones."
)


def _build_tool_catalog_prompt(tools: list[ToolEntry]) -> str:
    """Build a compact catalog string for the LLM prompt.

    Groups tools by category and truncates overview to OVERVIEW_PREVIEW_MAX_CHARS to avoid
    context bloat (pitfall 3: use compact SKILLS_SUMMARY format).
    """
    if not tools:
        return "(no tools available)"

    # Group tools by first category
    def sort_key(t: ToolEntry) -> str:
        return t.categories[0] if t.categories else "uncategorized"

    sorted_tools = sorted(tools, key=sort_key)
    lines: list[str] = []

    for category, group in groupby(sorted_tools, key=sort_key):
        lines.append(f"\n### {category}")
        for tool in group:
            status = tool.status.value if tool.status else "unknown"
            domains_str = ", ".join(tool.domains[:3]) if tool.domains else "general"
            tool_names = ", ".join(t.get("name", "") for t in tool.tools[:5]) if tool.tools else "n/a"
            overview = tool.overview[:OVERVIEW_PREVIEW_MAX_CHARS] if tool.overview else tool.description[:OVERVIEW_PREVIEW_MAX_CHARS]
            lines.append(f"- {tool.name} [{status}] - {overview} | Domains: {domains_str} | Tools: {tool_names}")

    return "\n".join(lines)


def _build_selection_prompt(problem_description: str, tool_catalog: str) -> str:
    """Build the user prompt for the selection agent."""
    return (
        f"## Physics Problem\n{problem_description}\n\n"
        f"## Available MCP Tools\n{tool_catalog}\n\n"
        "Select the most relevant tools for this physics problem. Explain your reasoning."
    )


class ToolSelectionAgent:
    """PydanticAI-based agent for selecting MCP tools for a physics problem."""

    def __init__(self, model: str = GPD_DEFAULT_MODEL) -> None:
        base_model, self._model_settings = resolve_model_and_settings(model)
        self._agent: Agent[None, ToolSelection] = Agent(
            base_model,
            output_type=ToolSelection,
            system_prompt=SELECTION_SYSTEM_PROMPT,
            retries=2,
        )

    async def select(self, problem_description: str, available_tools: list[ToolEntry]) -> ToolSelection:
        """Select tools for a physics problem using LLM reasoning.

        If the LLM returns more than MAX_TOOLS, truncates to the top MAX_TOOLS
        by priority (priority 1 first, then 2, then 3).
        """
        catalog_prompt = _build_tool_catalog_prompt(available_tools)
        prompt = _build_selection_prompt(problem_description, catalog_prompt)

        result = await self._agent.run(prompt, model_settings=self._model_settings)
        selection = result.output

        if len(selection.tools) > MAX_TOOLS:
            selection.tools = sorted(selection.tools, key=lambda t: t.priority)[:MAX_TOOLS]

        return selection

    def select_sync(self, problem_description: str, available_tools: list[ToolEntry]) -> ToolSelection:
        """Synchronous wrapper for CLI contexts where async is not available."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.select(problem_description, available_tools))
                return future.result()
        return asyncio.run(self.select(problem_description, available_tools))


async def select_tools(
    problem_description: str,
    available_tools: list[ToolEntry],
    model: str = GPD_DEFAULT_MODEL,
) -> ToolSelection:
    """Module-level convenience function for one-shot tool selection.

    Creates a ToolSelectionAgent and calls select().
    """
    agent = ToolSelectionAgent(model=model)
    return await agent.select(problem_description, available_tools)
