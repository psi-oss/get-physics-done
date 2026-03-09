"""Physics category router, problem categorization, selection display, and milestone re-evaluation.

Maps physics problem descriptions to categories, gathers relevant tools from the catalog,
runs LLM-driven selection, and displays results with auto-proceed behavior.
"""

from __future__ import annotations

import logging
import time

from gpd.core.model_defaults import GPD_DEFAULT_MODEL
from gpd.mcp.discovery.catalog import ToolCatalog
from gpd.mcp.discovery.fallback import AutoSubstituteResult, find_substitute
from gpd.mcp.discovery.models import PHYSICS_CATEGORIES, ToolEntry
from gpd.mcp.discovery.selector import ToolSelection, ToolSelectionAgent

logger = logging.getLogger(__name__)

# Default auto-proceed delay in seconds; injectable for tests
AUTO_PROCEED_DELAY: float = 3.0


class PhysicsRouter:
    """Routes physics problems to relevant MCP tools via category detection + LLM selection."""

    def __init__(self, catalog: ToolCatalog, selector: ToolSelectionAgent | None = None) -> None:
        self._catalog = catalog
        self._selector = selector or ToolSelectionAgent()

    def detect_categories(self, problem_description: str) -> list[str]:
        """Heuristic pre-filter: scan problem description for physics category keywords.

        Returns matching category names sorted by keyword match count (most matches first).
        Case-insensitive. If no matches, returns all categories (let the LLM figure it out).
        """
        desc_lower = problem_description.lower()
        scored: dict[str, int] = {}

        for cat in PHYSICS_CATEGORIES:
            count = 0
            for keyword in cat.domain_keywords:
                if keyword.lower() in desc_lower:
                    count += 1
            if count > 0:
                scored[cat.name] = count

        if not scored:
            return [cat.name for cat in PHYSICS_CATEGORIES]

        return sorted(scored.keys(), key=lambda k: scored[k], reverse=True)

    async def route_and_select(self, problem_description: str) -> ToolSelection:
        """End-to-end routing: detect categories -> gather tools -> LLM selection.

        1. Detect physics categories from problem description
        2. Gather tools from catalog for detected categories (deduplicated)
        3. If no tools found, return empty selection
        4. Call selector for LLM-driven selection
        5. Return the selection
        """
        categories = self.detect_categories(problem_description)

        seen_names: set[str] = set()
        tools: list[ToolEntry] = []
        for cat in categories:
            for tool in self._catalog.get_tools_for_category(cat):
                if tool.name not in seen_names:
                    tools.append(tool)
                    seen_names.add(tool.name)

        if not tools:
            return ToolSelection(
                tools=[],
                reasoning="No tools available",
                physics_categories=categories,
                confidence=0.0,
            )

        return await self._selector.select(problem_description, tools)

    def handle_tool_failure(self, failed_tool: str, available_tools: list[ToolEntry]) -> AutoSubstituteResult:
        """Handle a tool failure by finding a substitute from the same physics category."""
        return find_substitute(failed_tool, available_tools)

    async def reevaluate_tools(
        self,
        problem_description: str,
        current_selection: ToolSelection,
        milestone_context: str = "",
    ) -> ToolSelection:
        """Re-evaluate tool selection at milestone boundaries.

        Invalidates category caches for all categories in the current selection,
        then re-runs route_and_select. Optionally augments the problem description
        with milestone context.
        """
        for cat in current_selection.physics_categories:
            self._catalog.invalidate_category(cat)

        augmented = problem_description
        if milestone_context:
            augmented = f"{problem_description}\n\nMilestone context: {milestone_context}"

        return await self.route_and_select(augmented)


def display_selection(
    selection: ToolSelection,
    console: object | None = None,
    delay: float | None = None,
    catalog: ToolCatalog | None = None,
) -> str:
    """Display selected tools with rationale and auto-proceed after delay.

    Per user decision: "Show but auto-proceed". Prints tools with priority indicators
    and waits for the auto-proceed delay. If user presses Ctrl+C, returns with a note
    that user wants to modify.

    Args:
        selection: The tool selection to display.
        console: Optional rich Console for formatted output.
        delay: Override auto-proceed delay (defaults to AUTO_PROCEED_DELAY).
        catalog: Optional ToolCatalog for cost profile lookup.

    Returns:
        Formatted selection string.
    """
    if delay is None:
        delay = AUTO_PROCEED_DELAY

    if not selection.tools:
        msg = "No tools selected."
        if console is not None:
            _rich_print(console, msg)
        return msg

    # Build cost lookup from catalog if available
    cost_lookup: dict[str, float] = {}
    if catalog is not None:
        all_tools = catalog.get_all_tools()
        for entry in all_tools.values():
            cost_lookup[entry.name] = entry.cost_profile.cost_per_call_usd

    lines: list[str] = []
    lines.append(f"Selected {len(selection.tools)} tools (confidence: {selection.confidence:.0%}):")

    for tool in sorted(selection.tools, key=lambda t: t.priority):
        cost = cost_lookup.get(tool.mcp)
        cost_str = f" [${cost:.4f}/call]" if cost is not None else ""
        lines.append(f"  {tool.mcp:20s} - {tool.reason} [priority {tool.priority}]{cost_str}")

    lines.append(f"\n[auto-proceeding in {delay:.0f}s... press Ctrl+C to modify]")
    text = "\n".join(lines)

    if console is not None:
        _rich_print_selection(console, selection, delay, cost_lookup=cost_lookup)
    else:
        print(text)  # noqa: T201

    try:
        time.sleep(delay)
    except KeyboardInterrupt:
        return text + "\n(user interrupted -- awaiting modification)"

    return text


def _rich_print(console: object, message: str) -> None:
    """Print a plain message via rich Console."""
    console.print(message)  # type: ignore[union-attr]


def _rich_print_selection(
    console: object,
    selection: ToolSelection,
    delay: float,
    cost_lookup: dict[str, float] | None = None,
) -> None:
    """Print selection with rich formatting: priority 1 bold, priority 3 dim."""
    from rich.text import Text

    header = Text(f"Selected {len(selection.tools)} tools (confidence: {selection.confidence:.0%}):")
    console.print(header)  # type: ignore[union-attr]

    if cost_lookup is None:
        cost_lookup = {}

    for tool in sorted(selection.tools, key=lambda t: t.priority):
        line = Text()
        line.append("  ")
        name_part = f"{tool.mcp:20s}"
        cost = cost_lookup.get(tool.mcp)
        cost_str = f" [${cost:.4f}/call]" if cost is not None else ""
        reason_part = f" - {tool.reason} [priority {tool.priority}]{cost_str}"

        if tool.priority == 1:
            line.append(name_part, style="bold")
            line.append(reason_part, style="bold")
        elif tool.priority == 3:
            line.append(name_part, style="dim")
            line.append(reason_part, style="dim")
        else:
            line.append(name_part)
            line.append(reason_part)

        console.print(line)  # type: ignore[union-attr]

    footer = Text(f"\n[auto-proceeding in {delay:.0f}s... press Ctrl+C to modify]", style="dim")
    console.print(footer)  # type: ignore[union-attr]


async def route_and_select(
    problem_description: str,
    catalog: ToolCatalog,
    model: str = GPD_DEFAULT_MODEL,
) -> ToolSelection:
    """Module-level convenience function. Creates PhysicsRouter and calls route_and_select."""
    selector = ToolSelectionAgent(model=model)
    router = PhysicsRouter(catalog, selector=selector)
    return await router.route_and_select(problem_description)


async def reevaluate_tools(
    problem_description: str,
    current_selection: ToolSelection,
    catalog: ToolCatalog,
    milestone_context: str = "",
    model: str = GPD_DEFAULT_MODEL,
) -> ToolSelection:
    """Module-level convenience function for milestone re-evaluation."""
    selector = ToolSelectionAgent(model=model)
    router = PhysicsRouter(catalog, selector=selector)
    return await router.reevaluate_tools(problem_description, current_selection, milestone_context)
