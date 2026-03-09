"""Modal compute cost estimation for research milestones.

Computes per-milestone and total plan costs from Modal's published
per-second GPU rates, including cold start overhead, regional multipliers,
and non-preemptible pricing.
"""

from __future__ import annotations

import logging

from gpd.mcp.research.schemas import CostEstimate, ResearchMilestone, ResearchPlan

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

    Computes cost from gpu_type and estimated_seconds in tool_metadata.
    Adds cold start overhead. Effective rate = base * regional * non-preemptible.
    Confidence is MEDIUM if gpu_type is in known rates, LOW otherwise.

    Args:
        milestone: The milestone to estimate cost for.
        tool_metadata: Dict with optional 'gpu_type' and 'estimated_seconds' keys.

    Returns:
        CostEstimate with computed values.
    """
    gpu_type = str(tool_metadata.get("gpu_type", "CPU"))
    base_rate = MODAL_RATES_USD_PER_SECOND.get(gpu_type, MODAL_RATES_USD_PER_SECOND["CPU"])

    effective_rate = base_rate * REGIONAL_MULTIPLIER * NON_PREEMPTIBLE_MULTIPLIER

    raw_seconds = float(tool_metadata.get("estimated_seconds", 30.0))
    estimated_seconds = raw_seconds + COLD_START_OVERHEAD_SECONDS

    confidence = "MEDIUM" if gpu_type in MODAL_RATES_USD_PER_SECOND else "LOW"

    return CostEstimate(
        gpu_type=gpu_type,
        estimated_seconds=estimated_seconds,
        rate_per_second=effective_rate,
        estimated_cost_usd=estimated_seconds * effective_rate,
        confidence=confidence,
    )


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
    total_cost = 0.0
    total_seconds = 0.0
    min_confidence_idx = len(CONFIDENCE_LEVELS) - 1  # Start at highest

    for milestone in plan.milestones:
        metadata = tool_metadata_registry.get(milestone.milestone_id, {})
        estimate = estimate_milestone_cost(milestone, metadata)
        milestone.cost_estimate = estimate
        total_cost += estimate.estimated_cost_usd
        total_seconds += estimate.estimated_seconds

        confidence_idx = CONFIDENCE_LEVELS.index(estimate.confidence) if estimate.confidence in CONFIDENCE_LEVELS else 0
        min_confidence_idx = min(min_confidence_idx, confidence_idx)

    min_confidence = CONFIDENCE_LEVELS[min_confidence_idx] if plan.milestones else "LOW"

    return CostEstimate(
        gpu_type="mixed"
        if len(plan.milestones) > 1
        else (plan.milestones[0].cost_estimate.gpu_type if plan.milestones else ""),
        estimated_seconds=total_seconds,
        rate_per_second=0.0,  # Not meaningful for aggregated estimate
        estimated_cost_usd=total_cost,
        confidence=min_confidence,
    )


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
        if milestone.cost_estimate is None:
            continue
        est = milestone.cost_estimate
        # Per-tool-call: divide milestone cost by number of tools
        tool_count = max(len(milestone.tools), 1)
        per_tool_cost = est.estimated_cost_usd / tool_count
        per_tool_seconds = est.estimated_seconds / tool_count

        tool_calls = [
            {
                "tool": tool_name,
                "est_seconds": per_tool_seconds,
                "est_cost_usd": per_tool_cost,
                "gpu_type": est.gpu_type,
            }
            for tool_name in milestone.tools
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

    low_mult = 0.5
    high_mult = 2.0
    return {
        "plan_total": {
            "estimated_cost_usd": plan_total_cost,
            "cost_range": [plan_total_cost * low_mult, plan_total_cost * high_mult],
            "estimated_seconds": plan_total_seconds,
            "milestone_count": len(milestone_breakdowns),
        },
        "milestones": milestone_breakdowns,
    }
