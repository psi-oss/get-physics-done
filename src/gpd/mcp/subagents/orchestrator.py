"""Subagent spawn orchestrator for fix and create workflows.

Ties together SDK spawning, MCP Builder definition, and cost estimation
into high-level async functions that handle the full lifecycle: estimate cost,
decide fix-vs-substitute, spawn MCP Builder, parse results, and hot-add.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from gpd.mcp.discovery.fallback import AutoSubstituteResult, find_substitute
from gpd.mcp.discovery.models import ToolEntry
from gpd.mcp.subagents.cost_estimator import estimate_fix_cost
from gpd.mcp.subagents.mcp_builder import (
    MCP_BUILDER_TOOLS,
    build_create_prompt,
    build_fix_prompt,
    create_mcp_builder_definition,
    get_mcp_builder_cwd,
    parse_subagent_result,
)
from gpd.mcp.subagents.models import (
    SubagentStatus,
    ToolCreateContext,
    ToolCreateRequest,
    ToolCreateResult,
    ToolFixRequest,
    ToolFixResult,
)
from gpd.mcp.subagents.sdk import SubagentSDK

logger = logging.getLogger(__name__)


class SubagentOrchestrator:
    """High-level orchestrator for subagent spawning.

    Ties together SDK, cost estimator, and MCP Builder definition.
    Provides fix_broken_tool(), create_new_tool(), and handle_tool_failure().
    """

    def __init__(self, catalog: object, sdk: SubagentSDK | None = None) -> None:
        self._catalog = catalog
        self._sdk = sdk or SubagentSDK()
        self._mcp_builder_def: object | None = None
        self._specialist_manager: object | None = None
        self._repair_attempts: dict[str, int] = {}
        self._tool_creation_cost_usd: float = 0.0
        self._tool_creation_budget_usd: float = 50.0

    def _get_mcp_builder_definition(self) -> object:
        """Lazy-create MCP Builder AgentDefinition on first use."""
        if self._mcp_builder_def is None:
            self._mcp_builder_def = create_mcp_builder_definition()
        return self._mcp_builder_def

    async def fix_broken_tool(
        self,
        request: ToolFixRequest,
        on_status: Callable[[SubagentStatus], None] | None = None,
    ) -> ToolFixResult:
        """Spawn MCP Builder to fix a broken tool.

        Builds the fix prompt, spawns the subagent, parses the result,
        and hot-adds the fixed tool back to the catalog on success.
        """
        fix_prompt = build_fix_prompt(request)
        definition = self._get_mcp_builder_definition()
        cwd = get_mcp_builder_cwd()

        raw = await self._sdk.spawn(
            prompt=fix_prompt,
            agents={"mcp-builder": definition},
            allowed_tools=MCP_BUILDER_TOOLS,
            cwd=cwd,
            max_turns=50,
            timeout_seconds=request.timeout_seconds,
            on_status=on_status,
        )

        result = parse_subagent_result(raw)
        if not isinstance(result, ToolFixResult):
            result = ToolFixResult(
                success=False,
                mcp_name=request.mcp_name,
                error_message="Unexpected result type from subagent",
                cost_usd=raw.cost_usd,
            )

        if result.success:
            self._hot_add(request.mcp_name)

        return result

    async def create_new_tool(
        self,
        request: ToolCreateRequest,
        on_status: Callable[[SubagentStatus], None] | None = None,
        context: ToolCreateContext | None = None,
    ) -> ToolCreateResult:
        """Spawn MCP Builder to create a new tool.

        Builds the create prompt, spawns the subagent, parses the result,
        hot-adds the new tool, tracks soft budget, and re-validates catalog.

        Args:
            request: Tool creation specification.
            on_status: Optional status callback.
            context: Optional structured context for richer MCP Builder input.
        """
        import time as _time

        # If context passed externally, attach to request for prompt building
        if context is not None:
            request = request.model_copy(update={"context": context})

        create_prompt = build_create_prompt(request)
        definition = self._get_mcp_builder_definition()
        cwd = get_mcp_builder_cwd()

        creation_start = _time.monotonic()
        raw = await self._sdk.spawn(
            prompt=create_prompt,
            agents={"mcp-builder": definition},
            allowed_tools=MCP_BUILDER_TOOLS,
            cwd=cwd,
            max_turns=80,
            max_budget_usd=5.0,
            timeout_seconds=600,
            on_status=on_status,
        )
        creation_elapsed = _time.monotonic() - creation_start

        result = parse_subagent_result(raw)
        if not isinstance(result, ToolCreateResult):
            result = ToolCreateResult(
                success=False,
                error_message="Unexpected result type from subagent",
                cost_usd=raw.cost_usd,
            )

        if result.success:
            self._hot_add(result.mcp_name)

        # Soft budget tracking (per locked decision Area 4 Decision 4)
        creation_cost_estimate = raw.cost_usd if raw.cost_usd > 0 else creation_elapsed * 0.01
        self._tool_creation_cost_usd += creation_cost_estimate
        if self._tool_creation_cost_usd > self._tool_creation_budget_usd:
            logger.warning(
                "Tool creation soft budget exceeded: $%.2f spent of $%.2f budget. Continuing per policy.",
                self._tool_creation_cost_usd,
                self._tool_creation_budget_usd,
            )

        # Post-creation re-validation (per locked decision Area 4 Decision 3)
        if result.success:
            catalog = self._catalog
            if hasattr(catalog, "refresh"):
                catalog.refresh()
            elif hasattr(catalog, "_full_catalog"):
                catalog._full_catalog = None  # Force reload on next access

            updated_tools = catalog.get_all_tools() if hasattr(catalog, "get_all_tools") else {}
            if result.mcp_name not in updated_tools:
                logger.warning(
                    "New tool %s not found in refreshed catalog -- creation may have failed",
                    result.mcp_name,
                )
            else:
                logger.info("Post-creation re-validation passed: %s is in the catalog", result.mcp_name)

        return result

    async def handle_tool_failure(
        self,
        mcp_name: str,
        error_type: str,
        error_message: str,
        error_id: int,
        available_tools: list[ToolEntry],
        on_status: Callable[[SubagentStatus], None] | None = None,
    ) -> ToolFixResult | AutoSubstituteResult:
        """Main entry point for handling tool failures during research.

        Decides whether to fix or substitute based on cost estimation,
        then executes the chosen action.
        """
        # Step 1: Check for substitute
        substitute = find_substitute(mcp_name, available_tools)

        # Step 2: Estimate fix cost
        estimate = estimate_fix_cost(
            error_type=error_type,
            error_message=error_message,
            mcp_name=mcp_name,
            has_substitute=substitute.substitute_tool is not None,
        )

        logger.info(
            "Tool failure decision for %s: %s (fix=%s min, sub=%s min)",
            mcp_name,
            estimate.recommendation,
            estimate.fix_minutes,
            estimate.substitute_minutes,
        )

        # Step 3: Act on recommendation
        if estimate.recommendation == "substitute" and substitute.substitute_tool is not None:
            return substitute

        if estimate.recommendation == "fix":
            request = ToolFixRequest(
                mcp_name=mcp_name,
                error_id=error_id,
                error_summary=error_message,
                error_type=error_type,
                fix_complexity=str(estimate.fix_complexity),
                timeout_seconds=estimate.timeout_seconds,
            )
            return await self.fix_broken_tool(request, on_status=on_status)

        # Skip: too expensive, no substitute
        return ToolFixResult(
            success=False,
            mcp_name=mcp_name,
            error_message="Skipped: too expensive to fix, no substitute available",
        )

    def _hot_add(self, mcp_name: str | None) -> None:
        """Invalidate catalog caches so newly fixed/created tools are discovered."""
        if mcp_name is None:
            return

        if hasattr(self._catalog, "invalidate_all"):
            self._catalog.invalidate_all()
            logger.info("Hot-added %s to session -- catalog will re-discover on next access", mcp_name)

    def analyze_and_allocate(
        self,
        plan: object,
        catalog: object,
    ) -> dict[str, str]:
        """Run plan-time allocation analysis and pre-create persistent specialists.

        Called after plan approval, before execution begins.
        Scans the plan for tool reuse, decides ephemeral vs persistent,
        and pre-creates AgentDefinitions for persistent tools.

        Returns:
            Dict mapping tool_name -> "ephemeral" | "persistent".
        """
        from gpd.mcp.subagents.specialist import SpecialistManager, analyze_tool_reuse

        allocation = analyze_tool_reuse(plan)
        logger.info("Tool allocation: %s", allocation)

        # Pre-create specialists for persistent tools
        all_tools = catalog.get_all_tools() if hasattr(catalog, "get_all_tools") else {}
        specialist_mgr = self._specialist_manager
        if specialist_mgr is None or not isinstance(specialist_mgr, SpecialistManager):
            specialist_mgr = SpecialistManager()
            self._specialist_manager = specialist_mgr

        for tool_name, lifecycle in allocation.items():
            specialist_mgr.set_lifecycle(tool_name, lifecycle)
            if lifecycle == "persistent" and tool_name in all_tools:
                specialist_mgr.get_or_create(all_tools[tool_name])
                logger.info("Pre-created persistent specialist for %s", tool_name)

        return allocation

    async def repair_down_tool(
        self,
        tool_name: str,
        on_status: Callable[[SubagentStatus], None] | None = None,
    ) -> bool:
        """Attempt to repair a down tool via MCP Builder. Returns True if repair succeeds.

        Guards against infinite loops: at most 1 repair attempt per tool per session.
        """
        if self._repair_attempts.get(tool_name, 0) >= 1:
            logger.warning(
                "Skipping repair for %s: already attempted %d time(s) this session",
                tool_name,
                self._repair_attempts[tool_name],
            )
            return False

        self._repair_attempts[tool_name] = self._repair_attempts.get(tool_name, 0) + 1
        logger.info("Attempting self-healing repair for down tool: %s", tool_name)

        request = ToolFixRequest(
            mcp_name=tool_name,
            error_id=0,
            error_summary=f"Tool {tool_name} is down/unavailable",
            error_type="deployment",
            fix_complexity="medium",
            timeout_seconds=300,
        )
        result = await self.fix_broken_tool(request, on_status=on_status)
        return result.success

    async def _dispatch_down_tool_repairs(
        self,
        plan: object,
        on_status: Callable[[SubagentStatus], None] | None = None,
    ) -> list[str]:
        """Read plan.down_tools_needing_repair and attempt repair for each.

        Called after plan generation (Plan 02 stores the list) and after
        analyze_and_allocate() at plan-time. Per locked decision Area 2 Decision 4:
        "Launch the MCP Builder agent to diagnose and fix the tool. Automated self-healing."

        Returns list of tool names that were successfully repaired.
        """
        down_tools = getattr(plan, "down_tools_needing_repair", [])
        if not down_tools:
            return []

        logger.info("Found %d down tool(s) needing repair: %s", len(down_tools), down_tools)
        repaired: list[str] = []
        for tool_name in down_tools:
            success = await self.repair_down_tool(tool_name, on_status=on_status)
            if success:
                repaired.append(tool_name)
                logger.info("Successfully repaired down tool: %s", tool_name)
            else:
                logger.warning("Failed to repair down tool: %s -- escalating to user", tool_name)

        return repaired

    async def _handle_circuit_trip(
        self,
        tool_name: str,
        circuit_breaker: object,
        plan: object,
        executor: object,
    ) -> None:
        """When a circuit breaker trips, dispatch error recovery for ALL affected milestones.

        Per locked decision: circuit breaker triggers error recovery for ALL pending
        milestones using that tool, not just the current one.

        Args:
            tool_name: The degraded tool name.
            circuit_breaker: CircuitBreaker instance from error_recovery.
            plan: ResearchPlan with milestones.
            executor: ResearchExecutor (or object with enqueue_error_recovery method).
        """
        from gpd.mcp.research.error_recovery import CircuitBreaker

        if not isinstance(circuit_breaker, CircuitBreaker):
            return

        affected_ids = circuit_breaker.get_affected_milestones(tool_name, plan)
        if not affected_ids:
            return

        logger.warning(
            "Circuit breaker tripped for %s -- dispatching error recovery for %d milestones: %s",
            tool_name,
            len(affected_ids),
            affected_ids,
        )
        for milestone_id in affected_ids:
            if hasattr(executor, "enqueue_error_recovery"):
                executor.enqueue_error_recovery(milestone_id, tool_name)
            else:
                logger.info(
                    "Marking milestone %s for error recovery due to degraded tool %s",
                    milestone_id,
                    tool_name,
                )
