"""Auto-substitute logic for unavailable MCP tools."""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field

from gpd.mcp.discovery.models import PHYSICS_CATEGORIES, MCPStatus, ToolEntry

logger = logging.getLogger(__name__)

# Build preferred MCP lookup for confidence boosting
_PREFERRED_MCPS: dict[str, set[str]] = {}
for _cat in PHYSICS_CATEGORIES:
    _PREFERRED_MCPS[_cat.name] = set(_cat.preferred_mcps)


class AutoSubstituteResult(BaseModel):
    """Result of attempting to find a substitute for a failed tool."""

    original_tool: str
    """The tool that failed."""

    substitute_tool: str | None = None
    """Replacement tool (None if no substitute found)."""

    reason: str
    """Why this substitute was chosen (or why none was found)."""

    confidence: float = Field(ge=0.0, le=1.0, default=0.5)
    """How confident we are in the substitute."""


def find_substitute(
    failed_tool_name: str,
    available_tools: list[ToolEntry],
    exclude: set[str] | None = None,
) -> AutoSubstituteResult:
    """Find a same-category substitute for a failed tool.

    Scoring:
    1. Category overlap count (shared categories)
    2. Similar tool names (create_simulation/step_simulation pattern)
    3. Preferred-MCP list inclusion for matching categories

    Confidence: >2 shared categories = 0.8, 1 shared = 0.5, preferred list match = +0.1
    """
    exclude = exclude or set()

    # Find the failed tool's entry
    failed_entry: ToolEntry | None = None
    for tool in available_tools:
        if tool.name == failed_tool_name:
            failed_entry = tool
            break

    if failed_entry is None:
        return AutoSubstituteResult(
            original_tool=failed_tool_name,
            substitute_tool=None,
            reason=f"Failed tool '{failed_tool_name}' not found in available tools",
            confidence=0.0,
        )

    failed_categories = set(failed_entry.categories)
    failed_tool_names = {t.get("name", "") for t in failed_entry.tools}

    # Filter candidates: same-category, available, not excluded, not the failed tool
    candidates: list[tuple[ToolEntry, float]] = []
    for tool in available_tools:
        if tool.name == failed_tool_name:
            continue
        if tool.name in exclude:
            continue
        if tool.status != MCPStatus.available:
            continue

        tool_categories = set(tool.categories)
        overlap = failed_categories & tool_categories
        if not overlap:
            continue

        # Score the candidate
        score = float(len(overlap))

        # Bonus for similar tool names (standard physics MCP pattern)
        tool_names = {t.get("name", "") for t in tool.tools}
        shared_tools = failed_tool_names & tool_names
        if shared_tools:
            score += 0.5

        # Bonus for preferred MCP membership in overlapping categories
        for cat in overlap:
            if cat in _PREFERRED_MCPS and tool.name in _PREFERRED_MCPS[cat]:
                score += 0.3
                break

        candidates.append((tool, score))

    if not candidates:
        return AutoSubstituteResult(
            original_tool=failed_tool_name,
            substitute_tool=None,
            reason=f"No available same-category alternatives for '{failed_tool_name}'",
            confidence=0.0,
        )

    # Pick the highest-scoring candidate
    candidates.sort(key=lambda x: x[1], reverse=True)
    best_tool, best_score = candidates[0]

    # Confidence based on category overlap
    overlap_count = len(failed_categories & set(best_tool.categories))
    confidence = 0.8 if overlap_count > 1 else 0.5

    # Preferred list bonus
    for cat in failed_categories & set(best_tool.categories):
        if cat in _PREFERRED_MCPS and best_tool.name in _PREFERRED_MCPS[cat]:
            confidence = min(confidence + 0.1, 1.0)
            break

    return AutoSubstituteResult(
        original_tool=failed_tool_name,
        substitute_tool=best_tool.name,
        reason=f"'{best_tool.name}' shares {overlap_count} categories with '{failed_tool_name}' (score: {best_score:.1f})",
        confidence=confidence,
    )
