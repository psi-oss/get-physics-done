"""Pydantic models for the research milestone DAG.

Defines the type system for research milestones, plans, cost estimates,
citations, approval gates, retry policies, and plan evolution tracking.
Uses graphlib.TopologicalSorter for DAG validation and execution ordering.
"""

from __future__ import annotations

import graphlib
import logging
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class MilestoneStatus(StrEnum):
    """Execution status of a research milestone."""

    PENDING = "pending"
    """Awaiting execution or approval."""

    APPROVED = "approved"
    """User approved this gate."""

    RUNNING = "running"
    """Currently executing."""

    COMPLETED = "completed"
    """Successfully finished."""

    FAILED = "failed"
    """Execution failed after retries."""

    SKIPPED = "skipped"
    """Non-critical milestone skipped due to failure."""

    REPLANNED = "replanned"
    """Replaced by a new milestone during plan evolution."""


class ApprovalGate(StrEnum):
    """Approval gate level for a milestone."""

    NONE = "none"
    """No approval needed -- executes autonomously."""

    REQUIRED = "required"
    """Must get explicit user approval before execution."""

    SUGGESTED = "suggested"
    """Suggested gate -- user can skip during plan review."""


class RetryPolicy(BaseModel):
    """Configurable retry policy for milestone execution."""

    max_retries: int = 2
    """Maximum number of retry attempts."""

    backoff_base: float = 2.0
    """Exponential backoff base in seconds."""

    backoff_max: float = 60.0
    """Maximum wait between retries in seconds."""

    jitter: bool = True
    """Add random jitter to backoff timing."""

    retryable_errors: list[str] = Field(default_factory=list)
    """Error types worth retrying. Empty list means all errors are retryable."""


class CostEstimate(BaseModel):
    """Modal compute cost estimate for a milestone or plan."""

    gpu_type: str = ""
    """GPU type identifier (e.g., 'A10G', 'T4', 'CPU')."""

    estimated_seconds: float = 0.0
    """Estimated compute time in seconds."""

    rate_per_second: float = 0.0
    """Effective USD rate per second."""

    estimated_cost_usd: float = 0.0
    """Point estimate of cost in USD."""

    confidence: str = "LOW"
    """Confidence level: LOW, MEDIUM, or HIGH."""

    @property
    def estimated_cost_range(self) -> tuple[float, float]:
        """Return (low, high) cost range.

        Low estimate is 70% of point estimate; high is 150%.
        Shows ranges instead of point values per RESEARCH.md Pitfall 5.
        """
        return (self.estimated_cost_usd * 0.7, self.estimated_cost_usd * 1.5)


class CitationEntry(BaseModel):
    """Provenance record for a data source or tool output."""

    citation_id: str
    """Unique identifier (e.g., 'cite-001')."""

    source_type: str
    """One of: tool_output, paper, dataset, calculation, derived."""

    tool_call_id: str = ""
    """MCP tool call that produced this data."""

    milestone_id: str = ""
    """Which milestone produced this citation."""

    title: str = ""
    """Human-readable title of the source."""

    authors: list[str] = Field(default_factory=list)
    """Author names."""

    url: str = ""
    """URL to the source."""

    timestamp: str = ""
    """ISO 8601 timestamp of when the data was produced."""

    metadata: dict[str, object] = Field(default_factory=dict)
    """Arbitrary source-specific metadata."""


class MilestoneResult(BaseModel):
    """Result of executing a single milestone."""

    milestone_id: str
    """Which milestone produced this result."""

    is_error: bool = False
    """Whether this result represents a failure."""

    error_message: str = ""
    """Human-readable error description."""

    error_type: str = ""
    """Error classification for retry/recovery logic."""

    result_summary: str = ""
    """Brief summary of findings (2-3 key points)."""

    citations: list[str] = Field(default_factory=list)
    """Citation IDs produced by this milestone."""

    attempt_count: int = 1
    """Number of attempts before this result was produced."""

    tool_outputs: list[dict[str, object]] = Field(default_factory=list)
    """Raw tool outputs for report generation."""

    elapsed_seconds: float = 0.0
    """Wall-clock time for this milestone."""

    actual_cost: CostEstimate | None = None
    """Actual cost after execution (filled post-completion)."""


class ResearchMilestone(BaseModel):
    """A single step in a research plan DAG."""

    milestone_id: str
    """Unique identifier within the plan."""

    description: str
    """Human-readable description of what this milestone accomplishes."""

    depends_on: list[str] = Field(default_factory=list)
    """Milestone IDs that must complete before this one can start."""

    tools: list[str] = Field(default_factory=list)
    """MCP tool names needed for this milestone."""

    expected_outputs: list[str] = Field(default_factory=list)
    """Expected deliverables from this milestone."""

    success_criteria: str = ""
    """How to determine if this milestone succeeded."""

    approval_gate: ApprovalGate = ApprovalGate.NONE
    """Approval gate level for this milestone."""

    is_critical: bool = True
    """Whether this milestone is on the critical path."""

    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    """Retry configuration for this milestone."""

    cost_estimate: CostEstimate = Field(default_factory=CostEstimate)
    """Estimated compute cost."""

    status: MilestoneStatus = MilestoneStatus.PENDING
    """Current execution status."""

    result_summary: str = ""
    """Brief findings summary, filled after completion."""

    citations: list[str] = Field(default_factory=list)
    """Citation IDs produced by this milestone."""

    attempt_count: int = 0
    """Number of execution attempts so far."""


class PlanEvolution(BaseModel):
    """Record of a change to the research plan during execution."""

    version: int
    """Plan version after this change."""

    timestamp: str
    """ISO 8601 timestamp of when the change occurred."""

    change_type: str
    """One of: add, remove, modify."""

    affected_milestones: list[str] = Field(default_factory=list)
    """Milestone IDs affected by this change."""

    reason: str = ""
    """Why this change was made."""

    auto_triggered: bool = False
    """Whether this was triggered automatically by milestone results."""


class ResearchPlan(BaseModel):
    """A complete research plan as a milestone DAG.

    Represents the full plan generated by the LLM planner, including
    milestones with dependencies, cost estimates, approval gates,
    and evolution history.
    """

    plan_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    """Unique plan identifier."""

    query: str
    """Original research question."""

    milestones: list[ResearchMilestone]
    """Ordered list of milestones forming the DAG."""

    reasoning: str
    """LLM's rationale for the plan decomposition."""

    total_cost_estimate: CostEstimate = Field(default_factory=CostEstimate)
    """Aggregated cost estimate across all milestones."""

    approval_gates: list[str] = Field(default_factory=list)
    """Milestone IDs that require approval."""

    citation_registry: list[CitationEntry] = Field(default_factory=list)
    """All citations collected during execution."""

    version: int = 1
    """Plan version, incremented on each evolution."""

    evolution_log: list[PlanEvolution] = Field(default_factory=list)
    """History of plan changes during execution."""

    down_tools_needing_repair: list[str] = Field(default_factory=list)
    """Tools referenced in the plan that exist in catalog but are currently unavailable.

    Populated by plan validation when tools have status 'unavailable'.
    Signals the executor/orchestrator to trigger MCP Builder self-healing.
    """

    def validate_no_cycles(self) -> list[str]:
        """Check the milestone DAG for cycles using graphlib.TopologicalSorter.

        Returns:
            Empty list if DAG is valid; list of error messages if cycles detected.
        """
        graph: dict[str, set[str]] = {}
        milestone_ids = {m.milestone_id for m in self.milestones}

        errors: list[str] = []
        for milestone in self.milestones:
            deps = set(milestone.depends_on)
            # Check for references to non-existent milestones
            unknown = deps - milestone_ids
            if unknown:
                errors.append(f"Milestone '{milestone.milestone_id}' depends on unknown milestones: {sorted(unknown)}")
            graph[milestone.milestone_id] = deps & milestone_ids

        if errors:
            return errors

        try:
            sorter = graphlib.TopologicalSorter(graph)
            sorter.prepare()
        except graphlib.CycleError as exc:
            return [f"Cycle detected: {exc}"]

        return []

    def get_execution_order(self) -> list[list[str]]:
        """Return milestone IDs grouped by parallel execution layers.

        Each inner list contains milestones that can run concurrently.
        The outer list is ordered by execution dependency.

        Returns:
            List of layers, each layer being a list of milestone IDs.
        """
        graph: dict[str, set[str]] = {m.milestone_id: set(m.depends_on) for m in self.milestones}
        sorter = graphlib.TopologicalSorter(graph)
        sorter.prepare()

        layers: list[list[str]] = []
        while sorter.is_active():
            ready = sorted(sorter.get_ready())
            layers.append(ready)
            for node in ready:
                sorter.done(node)

        return layers

    def get_critical_path(self) -> list[str]:
        """Return milestone IDs on the critical path.

        The critical path includes milestones marked is_critical=True
        plus all their transitive dependencies (regardless of is_critical flag).

        Returns:
            Sorted list of milestone IDs on the critical path.
        """
        milestone_map = {m.milestone_id: m for m in self.milestones}

        # Find all critical milestones
        critical_ids: set[str] = {m.milestone_id for m in self.milestones if m.is_critical}

        # Add transitive dependencies of critical milestones
        visited: set[str] = set()
        stack = list(critical_ids)
        while stack:
            mid = stack.pop()
            if mid in visited:
                continue
            visited.add(mid)
            if mid in milestone_map:
                for dep in milestone_map[mid].depends_on:
                    if dep not in visited:
                        stack.append(dep)

        return sorted(visited)

    def get_pending_approval_gates(self) -> list[str]:
        """Return milestone IDs where approval is needed and status is pending.

        Returns:
            List of milestone IDs with approval_gate != NONE and status == PENDING.
        """
        return [
            m.milestone_id
            for m in self.milestones
            if m.approval_gate != ApprovalGate.NONE and m.status == MilestoneStatus.PENDING
        ]


class ActualCostRecord(BaseModel):
    """Observed cost from actual milestone execution for discrepancy logging."""

    milestone_id: str
    tool_name: str
    estimated_seconds: float
    actual_seconds: float
    estimated_cost_usd: float
    actual_cost_usd: float
    gpu_type: str = ""
    discrepancy_ratio: float = 0.0  # actual/estimated, >1 means over-budget
