"""Subagent spawning infrastructure for GPD+.

Provides SDK wrapper, MCP Builder agent definition, cost estimation,
specialist factory, and status display for subagent operations.
"""

from gpd.mcp.subagents.cost_estimator import FixEstimate, estimate_fix_cost
from gpd.mcp.subagents.models import (
    SubagentResult,
    SubagentStatus,
    ToolCreateRequest,
    ToolCreateResult,
    ToolFixRequest,
    ToolFixResult,
)
from gpd.mcp.subagents.orchestrator import SubagentOrchestrator
from gpd.mcp.subagents.sdk import SubagentSDK
from gpd.mcp.subagents.specialist import SpecialistManager, create_tool_specialist, should_use_specialist
from gpd.mcp.subagents.status_display import SubagentDisplay, run_with_status
from gpd.mcp.subagents.tool_spec import ToolSpec, ToolSpecDrafter

__all__ = [
    "FixEstimate",
    "SpecialistManager",
    "SubagentDisplay",
    "SubagentOrchestrator",
    "SubagentResult",
    "SubagentSDK",
    "SubagentStatus",
    "ToolCreateRequest",
    "ToolCreateResult",
    "ToolFixRequest",
    "ToolFixResult",
    "ToolSpec",
    "ToolSpecDrafter",
    "create_tool_specialist",
    "estimate_fix_cost",
    "run_with_status",
    "should_use_specialist",
]
