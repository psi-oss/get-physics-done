"""Research planning, execution, and orchestration engine for GPD+.

Public API for decomposing research questions into milestone DAGs,
estimating Modal compute costs, generating and evolving plans via
PydanticAI, executing milestones with error recovery and approval gates,
and displaying plan status with Rich terminal formatting.
"""

from __future__ import annotations

from gpd.mcp.research.cost_estimator import (
    MODAL_RATES_USD_PER_SECOND,
    estimate_milestone_cost,
    estimate_plan_cost,
    format_cost_display,
)
from gpd.mcp.research.error_recovery import (
    execute_milestone_with_recovery,
    find_substitute_tool,
    make_retry_decorator,
    simplify_milestone,
)
from gpd.mcp.research.planner import (
    ResearchPlanner,
    display_plan,
    display_plan_evolution,
    prompt_plan_approval,
)
from gpd.mcp.research.schemas import (
    ApprovalGate,
    CitationEntry,
    CostEstimate,
    MilestoneResult,
    MilestoneStatus,
    PlanEvolution,
    ResearchMilestone,
    ResearchPlan,
    RetryPolicy,
)

__all__ = [
    "ApprovalGate",
    "CitationEntry",
    "CostEstimate",
    "MODAL_RATES_USD_PER_SECOND",
    "MilestoneResult",
    "MilestoneStatus",
    "PlanEvolution",
    "ResearchMilestone",
    "ResearchPlan",
    "ResearchPlanner",
    "RetryPolicy",
    "display_plan",
    "display_plan_evolution",
    "estimate_milestone_cost",
    "estimate_plan_cost",
    "execute_milestone_with_recovery",
    "find_substitute_tool",
    "format_cost_display",
    "make_retry_decorator",
    "prompt_plan_approval",
    "simplify_milestone",
]
