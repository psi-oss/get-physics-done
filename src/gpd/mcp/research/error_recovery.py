"""Four-tier error recovery chain for milestone execution.

Implements retry -> simplify -> substitute -> skip fallback chain
per the locked decision "Both fallback strategies in sequence".
Uses tenacity for exponential backoff with jitter on retries,
and PydanticAI agents for simplification and substitution.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from pydantic_ai import Agent
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from gpd.core.model_defaults import GPD_DEFAULT_MODEL, resolve_model_and_settings
from gpd.mcp.research.schemas import (
    MilestoneResult,
    ResearchMilestone,
    RetryPolicy,
)

logger = logging.getLogger(__name__)


class CircuitBreaker:
    """Per-tool failure tracking with configurable threshold.

    After N consecutive failures on a tool, marks it as degraded
    and identifies all pending milestones affected, triggering
    the error recovery chain for each.

    Default threshold=3 per locked decision.
    """

    def __init__(self, threshold: int = 3) -> None:
        self._threshold = threshold
        self._failure_counts: dict[str, int] = {}
        self._degraded_tools: set[str] = set()

    def record_failure(self, tool_name: str) -> bool:
        """Record a failure. Returns True if circuit just tripped (newly degraded)."""
        self._failure_counts[tool_name] = self._failure_counts.get(tool_name, 0) + 1
        if self._failure_counts[tool_name] >= self._threshold:
            if tool_name not in self._degraded_tools:
                self._degraded_tools.add(tool_name)
                logger.warning(
                    "Circuit breaker tripped for %s after %d consecutive failures",
                    tool_name,
                    self._failure_counts[tool_name],
                )
                return True
        return False

    def record_success(self, tool_name: str) -> None:
        """Reset failure count on success."""
        self._failure_counts.pop(tool_name, None)
        self._degraded_tools.discard(tool_name)

    def is_degraded(self, tool_name: str) -> bool:
        """Check if a tool is currently marked degraded."""
        return tool_name in self._degraded_tools

    def get_affected_milestones(
        self,
        tool_name: str,
        plan: object,
    ) -> list[str]:
        """Find all pending milestones that use a degraded tool.

        Args:
            tool_name: The degraded tool name.
            plan: ResearchPlan object with milestones attribute.

        Returns:
            List of milestone_ids for pending milestones using this tool.
        """
        affected = []
        for milestone in getattr(plan, "milestones", []):
            if tool_name in getattr(milestone, "tools", []) and getattr(milestone, "status", "") in (
                "pending",
                "approved",
            ):
                affected.append(milestone.milestone_id)
        return affected

    @property
    def degraded_tools(self) -> set[str]:
        """Return the set of currently degraded tool names."""
        return set(self._degraded_tools)

    @property
    def failure_counts(self) -> dict[str, int]:
        """Return current failure counts for all tracked tools."""
        return dict(self._failure_counts)


def make_retry_decorator(policy: RetryPolicy) -> Callable:
    """Build a tenacity retry decorator from a milestone's RetryPolicy.

    Args:
        policy: Retry configuration with max_retries, backoff_base,
            backoff_max, and jitter settings.

    Returns:
        A tenacity retry decorator configured per the policy.
    """
    return retry(
        stop=stop_after_attempt(policy.max_retries + 1),
        wait=wait_exponential_jitter(
            initial=1,
            max=policy.backoff_max,
            exp_base=policy.backoff_base,
            jitter=5 if policy.jitter else 0,
        ),
        retry=retry_if_exception_type((TimeoutError, ConnectionError, RuntimeError)),
        reraise=True,
    )


async def execute_tool_call(
    tool_name: str,
    arguments: dict,
    tool_router: Callable | None,
) -> dict:
    """Execute a single MCP tool call via the tool_router.

    The tool_router is a callable (from Phase 3) that takes
    (tool_name, arguments) and returns a result dict. When tool_router
    is None, returns a "skipped" result indicating Claude Code should
    call the tool directly.

    Args:
        tool_name: Name of the MCP tool to call.
        arguments: Arguments dict to pass to the tool.
        tool_router: Callable that routes to the appropriate MCP server,
            or None to delegate tool calls to Claude Code.

    Returns:
        Result dict from the tool execution, or a skipped-result dict
        when tool_router is None.
    """
    if tool_router is None:
        return {
            "status": "skipped",
            "tool_name": tool_name,
            "reason": "No tool_router provided -- tools will be called by Claude Code directly",
            "arguments": arguments,
        }
    result = await tool_router(tool_name, arguments)
    return result


async def simplify_milestone(
    milestone: ResearchMilestone,
    planner_agent: Agent | None = None,
    model: str = GPD_DEFAULT_MODEL,
) -> ResearchMilestone | None:
    """Use PydanticAI Agent to generate a simplified version of a milestone.

    Simplification means: coarser mesh, fewer parameters, reduced scope.
    Returns None if simplification is not possible for this milestone type.

    Args:
        milestone: The milestone that failed execution.
        planner_agent: Optional pre-configured agent. If None, creates one.
        model: PydanticAI model string for the LLM backend.

    Returns:
        A simplified ResearchMilestone, or None if not simplifiable.
    """
    base_model, model_settings = resolve_model_and_settings(model)
    agent = planner_agent or Agent(
        base_model,
        output_type=ResearchMilestone,
        retries=1,
        system_prompt=(
            "You are a physics research simplification agent. Given a failed milestone, "
            "produce a simplified version with: coarser resolution, fewer parameters, "
            "reduced scope, or simpler tool arguments. Keep the same milestone_id and tools "
            "but adjust the description and expected_outputs to reflect reduced scope. "
            "If the milestone cannot be meaningfully simplified, return the milestone unchanged."
        ),
    )

    prompt = (
        f"Simplify this failed milestone:\n"
        f"ID: {milestone.milestone_id}\n"
        f"Description: {milestone.description}\n"
        f"Tools: {milestone.tools}\n"
        f"Expected outputs: {milestone.expected_outputs}\n"
        f"Success criteria: {milestone.success_criteria}"
    )

    result = await agent.run(prompt, model_settings=model_settings)
    simplified = result.output

    # If the agent returned essentially the same milestone, it cannot be simplified
    if simplified.description == milestone.description and simplified.expected_outputs == milestone.expected_outputs:
        return None

    return simplified


async def find_substitute_tool(
    milestone: ResearchMilestone,
    available_tools: list[dict],
    model: str = GPD_DEFAULT_MODEL,
) -> ResearchMilestone | None:
    """Use PydanticAI Agent to find an alternative tool for a failed milestone.

    Returns None if no substitute exists.

    Args:
        milestone: The milestone whose tools failed.
        available_tools: List of tool metadata dicts with name/description.
        model: PydanticAI model string for the LLM backend.

    Returns:
        A ResearchMilestone with substitute tools, or None if no substitute found.
    """
    base_model, model_settings = resolve_model_and_settings(model)
    agent = Agent(
        base_model,
        output_type=ResearchMilestone,
        retries=1,
        system_prompt=(
            "You are a physics tool substitution agent. Given a failed milestone and a list "
            "of available tools, find an alternative tool that can accomplish the same goal. "
            "Return the milestone with updated tools list. If no suitable substitute exists, "
            "return the milestone with an empty tools list."
        ),
    )

    tools_context = "\n".join(
        f"- {t.get('name', 'unknown')}: {t.get('description', 'no description')}" for t in available_tools
    )

    prompt = (
        f"Find a substitute tool for this failed milestone:\n"
        f"ID: {milestone.milestone_id}\n"
        f"Description: {milestone.description}\n"
        f"Failed tools: {milestone.tools}\n\n"
        f"Available tools:\n{tools_context}"
    )

    result = await agent.run(prompt, model_settings=model_settings)
    substitute = result.output

    # If no tools were suggested, substitution failed
    if not substitute.tools:
        return None

    # If the same tools came back, no substitute was found
    if substitute.tools == milestone.tools:
        return None

    return substitute


async def execute_milestone_with_recovery(
    milestone: ResearchMilestone,
    prior_results: dict[str, MilestoneResult],
    tool_router: Callable | None,
    dashboard_callback: Callable | None = None,
    available_tools: list[dict] | None = None,
) -> MilestoneResult:
    """Execute a milestone with the four-tier recovery chain.

    Recovery sequence:
    1. Direct execution with retry (tenacity exponential backoff)
    2. Simplify milestone and retry once
    3. Substitute tools and retry once
    4. Skip/fail with error

    Args:
        milestone: The milestone to execute.
        prior_results: Results from previously completed milestones.
        tool_router: Callable for MCP tool execution.
        dashboard_callback: Optional callback for progress reporting.
            Called with (phase_name, milestone, extra_info).
        available_tools: Available tools for substitution fallback.

    Returns:
        MilestoneResult with execution outcome.
    """
    start_time = time.monotonic()
    attempt_count = 0
    tool_outputs: list[dict[str, object]] = []
    citations: list[str] = []

    # --- Phase 1: Direct execution with retry ---
    retry_decorator = make_retry_decorator(milestone.retry_policy)

    async def _execute_tools(ms: ResearchMilestone) -> list[dict[str, object]]:
        outputs = []
        for tool_name in ms.tools:
            result = await execute_tool_call(tool_name, {"milestone": ms.milestone_id}, tool_router)
            outputs.append(result)
        return outputs

    try:

        @retry_decorator
        async def _retried_execution() -> list[dict[str, object]]:
            nonlocal attempt_count
            attempt_count += 1
            if dashboard_callback:
                dashboard_callback("attempt", milestone, attempt_count, milestone.retry_policy.max_retries + 1)
            return await _execute_tools(milestone)

        tool_outputs = await _retried_execution()
        elapsed = time.monotonic() - start_time
        return MilestoneResult(
            milestone_id=milestone.milestone_id,
            is_error=False,
            result_summary=f"Completed after {attempt_count} attempt(s)",
            tool_outputs=tool_outputs,
            attempt_count=attempt_count,
            elapsed_seconds=elapsed,
        )
    except (TimeoutError, ConnectionError, RuntimeError):
        logger.warning(
            "All retries exhausted for milestone %s after %d attempts",
            milestone.milestone_id,
            attempt_count,
        )

    # --- Phase 2: Simplify ---
    if dashboard_callback:
        dashboard_callback("simplify", milestone)

    try:
        simplified = await simplify_milestone(milestone)
        if simplified is not None:
            attempt_count += 1
            tool_outputs = await _execute_tools(simplified)
            elapsed = time.monotonic() - start_time
            return MilestoneResult(
                milestone_id=milestone.milestone_id,
                is_error=False,
                result_summary=f"Completed via simplified execution after {attempt_count} attempts",
                tool_outputs=tool_outputs,
                attempt_count=attempt_count,
                elapsed_seconds=elapsed,
            )
    except (TimeoutError, ConnectionError, RuntimeError):
        logger.warning("Simplified execution also failed for milestone %s", milestone.milestone_id)

    # --- Phase 3: Substitute ---
    if dashboard_callback:
        dashboard_callback("substitute", milestone)

    try:
        substitute = await find_substitute_tool(milestone, available_tools or [])
        if substitute is not None:
            attempt_count += 1
            tool_outputs = await _execute_tools(substitute)
            elapsed = time.monotonic() - start_time
            return MilestoneResult(
                milestone_id=milestone.milestone_id,
                is_error=False,
                result_summary=f"Completed via substitute tool after {attempt_count} attempts",
                tool_outputs=tool_outputs,
                attempt_count=attempt_count,
                elapsed_seconds=elapsed,
            )
    except (TimeoutError, ConnectionError, RuntimeError):
        logger.warning("Substitute execution also failed for milestone %s", milestone.milestone_id)

    # --- Phase 4: Exhausted ---
    if dashboard_callback:
        dashboard_callback("exhausted", milestone)

    elapsed = time.monotonic() - start_time
    return MilestoneResult(
        milestone_id=milestone.milestone_id,
        is_error=True,
        error_message=f"All recovery strategies exhausted after {attempt_count} attempts",
        error_type="all_recovery_exhausted",
        tool_outputs=tool_outputs,
        citations=citations,
        attempt_count=attempt_count,
        elapsed_seconds=elapsed,
    )
