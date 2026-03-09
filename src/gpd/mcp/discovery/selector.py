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
    "You are a physics simulation tool router for the GPD research agent. "
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


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    """Return values without duplicates while preserving order."""
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def normalize_selection(
    selection: ToolSelection,
    available_tools: list[ToolEntry],
    detected_categories: list[str] | None = None,
) -> ToolSelection:
    """Validate and normalize selector output against the actual candidate tools."""
    candidate_names = {tool.name.lower(): tool.name for tool in available_tools}
    invalid_names: set[str] = set()
    seen_names: set[str] = set()
    normalized_tools: list[SelectedTool] = []

    for selected in sorted(selection.tools, key=lambda tool: tool.priority):
        canonical_name = candidate_names.get(selected.mcp.strip().lower())
        if canonical_name is None:
            invalid_names.add(selected.mcp)
            continue
        if canonical_name in seen_names:
            continue
        seen_names.add(canonical_name)
        if selected.mcp == canonical_name:
            normalized_tools.append(selected)
        else:
            normalized_tools.append(selected.model_copy(update={"mcp": canonical_name}))

    if invalid_names:
        logger.warning("Selector returned invalid tools outside the candidate set: %s", sorted(invalid_names))

    categories = (
        _dedupe_preserve_order(detected_categories)
        if detected_categories is not None
        else _dedupe_preserve_order(selection.physics_categories)
    )

    selection.tools = normalized_tools[:MAX_TOOLS]
    selection.physics_categories = categories
    if not selection.tools and invalid_names:
        selection.confidence = 0.0

    return selection


def _build_selection_prompt(
    problem_description: str,
    tool_catalog: str,
    detected_categories: list[str] | None = None,
) -> str:
    """Build the user prompt for the selection agent."""
    categories_block = ""
    if detected_categories:
        categories_block = f"## Detected Physics Categories\n{', '.join(detected_categories)}\n\n"
    return (
        f"## Physics Problem\n{problem_description}\n\n"
        f"{categories_block}"
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

    async def select(
        self,
        problem_description: str,
        available_tools: list[ToolEntry],
        detected_categories: list[str] | None = None,
    ) -> ToolSelection:
        """Select tools for a physics problem using LLM reasoning.

        If the LLM returns more than MAX_TOOLS, truncates to the top MAX_TOOLS
        by priority (priority 1 first, then 2, then 3).
        """
        catalog_prompt = _build_tool_catalog_prompt(available_tools)
        prompt = _build_selection_prompt(problem_description, catalog_prompt, detected_categories)

        result = await self._agent.run(prompt, model_settings=self._model_settings)
        return normalize_selection(result.output, available_tools, detected_categories)

    def select_sync(
        self,
        problem_description: str,
        available_tools: list[ToolEntry],
        detected_categories: list[str] | None = None,
    ) -> ToolSelection:
        """Synchronous wrapper for CLI contexts where async is not available."""
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop is not None and loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, self.select(problem_description, available_tools, detected_categories))
                return future.result()
        return asyncio.run(self.select(problem_description, available_tools, detected_categories))


async def select_tools(
    problem_description: str,
    available_tools: list[ToolEntry],
    model: str = GPD_DEFAULT_MODEL,
    detected_categories: list[str] | None = None,
) -> ToolSelection:
    """Module-level convenience function for one-shot tool selection.

    Creates a ToolSelectionAgent and calls select().
    """
    agent = ToolSelectionAgent(model=model)
    return await agent.select(problem_description, available_tools, detected_categories)
