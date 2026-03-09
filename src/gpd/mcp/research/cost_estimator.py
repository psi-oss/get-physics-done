"""Modal compute cost estimation for research milestones.

Computes per-milestone and total plan costs from Modal's published
per-second GPU rates, including cold start overhead, regional multipliers,
and non-preemptible pricing.
"""

from __future__ import annotations

import logging

from gpd.mcp.research.schemas import CostEstimate, ResearchMilestone, ResearchPlan, ToolCallCostEstimate

logger = logging.getLogger(__name__)

MODAL_RATES_USD_PER_SECOND: dict[str, float] = {
    "T4": 0.000164,
    "L4": 0.000222,
    "A10G": 0.000306,
    "L40S": 0.000542,
    "A100-40GB": 0.000389,
    "A100-80GB": 0.000450,
    "H100": 0.001380,
    "H200": 0.001780,
    "B200": 0.002780,
    "CPU": 0.0000131,
}
"""Modal per-second rates by GPU type (as of Mar 2026)."""

NON_PREEMPTIBLE_MULTIPLIER: float = 3.0
"""Multiplier for non-preemptible (production) workloads."""

REGIONAL_MULTIPLIER: float = 1.25
"""Regional multiplier for US-based workloads."""

COLD_START_OVERHEAD_SECONDS: float = 20.0
"""Typical container cold start overhead in seconds."""

CONFIDENCE_LEVELS = ("LOW", "MEDIUM", "HIGH")
"""Valid confidence levels, ordered from lowest to highest."""


def estimate_milestone_cost(
    milestone: ResearchMilestone,
    tool_metadata: dict[str, object],
) -> CostEstimate:
    """Estimate compute cost for a single milestone.

    Supports three metadata shapes:
    - a direct metadata mapping for the milestone
    - a registry keyed by tool name
    - a registry keyed by milestone_id, optionally with nested `tool_estimates`

    Args:
        milestone: The milestone to estimate cost for.
        tool_metadata: Metadata mapping or registry used to resolve costs.

    Returns:
        CostEstimate with computed values.
    """
    line_items = _resolve_milestone_line_items(milestone, tool_metadata)
    return _aggregate_cost_estimates(line_items)


def estimate_plan_cost(
    plan: ResearchPlan,
    tool_metadata_registry: dict[str, dict[str, object]],
) -> CostEstimate:
    """Estimate total compute cost for a research plan.

    Sums costs across all milestones. Confidence is set to the minimum
    confidence level across all milestone estimates.

    Args:
        plan: The research plan to estimate cost for.
        tool_metadata_registry: Mapping of milestone_id to tool metadata dicts.

    Returns:
        Aggregated CostEstimate for the entire plan.
    """
    plan_line_items: list[ToolCallCostEstimate] = []

    for milestone in plan.milestones:
        estimate = estimate_milestone_cost(milestone, tool_metadata_registry)
        milestone.cost_estimate = estimate
        plan_line_items.extend(estimate.tool_call_estimates)

    return _aggregate_cost_estimates(plan_line_items)


def format_cost_display(estimate: CostEstimate) -> str:
    """Format a cost estimate for terminal display.

    Returns a string like "$0.02-$0.05 (A10G, ~30s, MEDIUM confidence)".

    Args:
        estimate: The cost estimate to format.

    Returns:
        Formatted display string.
    """
    low, high = estimate.estimated_cost_range
    seconds_display = f"~{estimate.estimated_seconds:.0f}s"
    gpu_display = estimate.gpu_type or "CPU"
    return f"${low:.2f}-${high:.2f} ({gpu_display}, {seconds_display}, {estimate.confidence} confidence)"


def format_three_level_cost_display(plan: ResearchPlan) -> dict[str, object]:
    """Build three-level cost breakdown: per-tool-call, per-milestone, plan total.

    Returns a dict with:
      - "plan_total": overall cost summary
      - "milestones": list of per-milestone breakdowns, each with per-tool-call detail
    """
    milestone_breakdowns: list[dict[str, object]] = []
    plan_total_cost = 0.0
    plan_total_seconds = 0.0

    for milestone in plan.milestones:
        est = milestone.cost_estimate
        if est is None:
            continue

        tool_calls = [
            {
                "tool": line_item.tool_name,
                "est_seconds": line_item.estimated_seconds,
                "est_cost_usd": line_item.estimated_cost_usd,
                "gpu_type": line_item.gpu_type,
                "confidence": line_item.confidence,
            }
            for line_item in est.tool_call_estimates
        ]

        milestone_breakdowns.append(
            {
                "milestone_id": milestone.milestone_id,
                "description": milestone.description[:80],
                "subtotal_cost_usd": est.estimated_cost_usd,
                "subtotal_seconds": est.estimated_seconds,
                "confidence": est.confidence,
                "tool_calls": tool_calls,
            }
        )
        plan_total_cost += est.estimated_cost_usd
        plan_total_seconds += est.estimated_seconds

    low, high = CostEstimate(estimated_cost_usd=plan_total_cost).estimated_cost_range
    return {
        "plan_total": {
            "estimated_cost_usd": plan_total_cost,
            "cost_range": [low, high],
            "estimated_seconds": plan_total_seconds,
            "milestone_count": len(milestone_breakdowns),
        },
        "milestones": milestone_breakdowns,
    }


def _coerce_seconds(raw_seconds: object) -> float:
    """Coerce estimated seconds from metadata, tolerating missing or bad values."""
    try:
        return float(raw_seconds)
    except (TypeError, ValueError):
        return 30.0


def _estimate_tool_call_cost(tool_name: str, tool_metadata: dict[str, object]) -> ToolCallCostEstimate:
    """Estimate cost for a single tool call or aggregate fallback entry."""
    gpu_type = str(tool_metadata.get("gpu_type", "CPU"))
    base_rate = MODAL_RATES_USD_PER_SECOND.get(gpu_type, MODAL_RATES_USD_PER_SECOND["CPU"])
    effective_rate = base_rate * REGIONAL_MULTIPLIER * NON_PREEMPTIBLE_MULTIPLIER
    raw_seconds = _coerce_seconds(
        tool_metadata.get("estimated_seconds", tool_metadata.get("estimated_gpu_seconds", 30.0))
    )
    estimated_seconds = raw_seconds + COLD_START_OVERHEAD_SECONDS
    confidence = "MEDIUM" if gpu_type in MODAL_RATES_USD_PER_SECOND else "LOW"

    return ToolCallCostEstimate(
        tool_name=tool_name,
        gpu_type=gpu_type,
        estimated_seconds=estimated_seconds,
        rate_per_second=effective_rate,
        estimated_cost_usd=estimated_seconds * effective_rate,
        confidence=confidence,
    )


def _aggregate_cost_estimates(line_items: list[ToolCallCostEstimate]) -> CostEstimate:
    """Aggregate tool-call estimates into a milestone or plan estimate."""
    if not line_items:
        return CostEstimate()

    total_seconds = sum(line_item.estimated_seconds for line_item in line_items)
    total_cost = sum(line_item.estimated_cost_usd for line_item in line_items)
    gpu_types = {line_item.gpu_type or "CPU" for line_item in line_items}
    min_confidence_idx = min(
        (
            CONFIDENCE_LEVELS.index(line_item.confidence)
            for line_item in line_items
            if line_item.confidence in CONFIDENCE_LEVELS
        ),
        default=0,
    )

    return CostEstimate(
        gpu_type=gpu_types.pop() if len(gpu_types) == 1 else "mixed",
        estimated_seconds=total_seconds,
        rate_per_second=(total_cost / total_seconds) if total_seconds > 0 else 0.0,
        estimated_cost_usd=total_cost,
        confidence=CONFIDENCE_LEVELS[min_confidence_idx],
        tool_call_estimates=line_items,
    )


def _resolve_milestone_line_items(
    milestone: ResearchMilestone,
    tool_metadata_registry: dict[str, object],
) -> list[ToolCallCostEstimate]:
    """Resolve cost metadata for a milestone.

    Supported registry shapes:
    - `{tool_name: {"gpu_type": ..., "estimated_seconds": ...}}`
    - `{milestone_id: {"gpu_type": ..., "estimated_seconds": ...}}`
    - `{milestone_id: {"tool_estimates": {tool_name: {...}}}}`
    """
    if _looks_like_cost_metadata(tool_metadata_registry):
        direct_metadata = tool_metadata_registry
        nested_tool_estimates = direct_metadata.get("tool_estimates")
        if isinstance(nested_tool_estimates, dict):
            tool_names = milestone.tools or [milestone.milestone_id]
            return [
                _estimate_tool_call_cost(tool_name, _get_tool_metadata(nested_tool_estimates.get(tool_name)))
                for tool_name in tool_names
            ]

        aggregate_label = (
            milestone.tools[0] if len(milestone.tools) == 1 else "+".join(milestone.tools) or milestone.milestone_id
        )
        return [_estimate_tool_call_cost(aggregate_label, direct_metadata)]

    milestone_entry = tool_metadata_registry.get(milestone.milestone_id)
    if isinstance(milestone_entry, dict):
        nested_tool_estimates = milestone_entry.get("tool_estimates")
        if isinstance(nested_tool_estimates, dict):
            tool_names = milestone.tools or [milestone.milestone_id]
            return [
                _estimate_tool_call_cost(tool_name, _get_tool_metadata(nested_tool_estimates.get(tool_name)))
                for tool_name in tool_names
            ]

    if any(tool_name in tool_metadata_registry for tool_name in milestone.tools):
        return [
            _estimate_tool_call_cost(tool_name, _get_tool_metadata(tool_metadata_registry.get(tool_name)))
            for tool_name in milestone.tools
        ]

    if isinstance(milestone_entry, dict):
        aggregate_label = (
            milestone.tools[0] if len(milestone.tools) == 1 else "+".join(milestone.tools) or milestone.milestone_id
        )
        return [_estimate_tool_call_cost(aggregate_label, milestone_entry)]

    if milestone.tools:
        return [_estimate_tool_call_cost(tool_name, {}) for tool_name in milestone.tools]

    return [_estimate_tool_call_cost(milestone.milestone_id, {})]


def _get_tool_metadata(raw_metadata: object) -> dict[str, object]:
    """Normalize a registry entry to a metadata mapping."""
    return raw_metadata if isinstance(raw_metadata, dict) else {}


def _looks_like_cost_metadata(raw_metadata: object) -> bool:
    """Return True when a mapping looks like a single cost metadata entry."""
    if not isinstance(raw_metadata, dict):
        return False

    return any(
        key in raw_metadata for key in ("gpu_type", "estimated_seconds", "estimated_gpu_seconds", "tool_estimates")
    )
