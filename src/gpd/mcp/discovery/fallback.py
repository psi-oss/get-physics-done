"""Auto-substitute logic and MCP Builder subagent spawn interface (Phase 6 contract).

Handles tool failure by finding same-category replacements with confidence scoring.
Defines the MCPBuilderRequest/MCPBuilderResult contract for Phase 6 implementation.
"""

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


# -- MCP Builder Subagent Interface (Phase 6 contract) --


class MCPBuilderRequest(BaseModel):
    """Request to spawn MCP Builder as a subagent to build a missing tool."""

    capability_gap: str
    """What's missing (e.g., 'protein folding simulation')."""

    research_context: str
    """Current research question for context."""

    priority: str = "normal"
    """'urgent' (blocks research) or 'normal' (background)."""


class MCPBuilderResult(BaseModel):
    """Result from MCP Builder subagent after building a tool."""

    success: bool
    mcp_name: str | None = None
    """Name of the newly built MCP."""

    deploy_url: str | None = None
    error_message: str | None = None


async def request_mcp_build(
    request: MCPBuilderRequest,
    catalog: object | None = None,
) -> MCPBuilderResult:
    """Spawn MCP Builder subagent to build a missing tool.

    Drafts a tool specification from the capability gap, then spawns MCP Builder
    to build and deploy the tool. Requires a ToolCatalog for hot-add on success.

    Args:
        request: The build request with capability gap and research context.
        catalog: ToolCatalog instance for hot-add on success. Required.

    Raises:
        ValueError: If catalog is not provided.
    """
    from gpd.mcp.subagents.orchestrator import SubagentOrchestrator
    from gpd.mcp.subagents.status_display import SubagentDisplay
    from gpd.mcp.subagents.tool_spec import ToolSpecDrafter, spec_to_create_request

    if catalog is None:
        raise ValueError("ToolCatalog required for MCP Builder spawning. Pass catalog= parameter.")

    display = SubagentDisplay()
    orchestrator = SubagentOrchestrator(catalog)

    # Draft tool spec from capability gap
    drafter = ToolSpecDrafter()
    spec = await drafter.draft(
        capability_gap=request.capability_gap,
        research_context=request.research_context,
        available_tools=[],
    )

    # Convert to create request and spawn
    create_request = spec_to_create_request(spec, request.research_context)
    result = await orchestrator.create_new_tool(create_request, on_status=display.on_status)

    return MCPBuilderResult(
        success=result.success,
        mcp_name=result.mcp_name,
        deploy_url=result.deploy_url,
        error_message=result.error_message,
    )


def should_request_build(failed_tool: str, substitute_result: AutoSubstituteResult) -> bool:
    """Heuristic for when to suggest spawning MCP Builder.

    Returns True if no substitute was found (the capability is completely missing).
    The actual decision to spawn happens at a higher level in the router.
    """
    return substitute_result.substitute_tool is None
