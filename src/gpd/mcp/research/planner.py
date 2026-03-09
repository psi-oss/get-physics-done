"""LLM-driven research planner via PydanticAI Agent.

Decomposes a research question into a milestone DAG, estimates costs,
provides plan display via Rich, handles plan approval flow, and evolves
plans based on intermediate research findings.
"""

from __future__ import annotations

import datetime
import logging
from uuid import uuid4

from pydantic_ai import Agent
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from gpd.core.errors import ValidationError
from gpd.core.model_defaults import GPD_DEFAULT_MODEL, resolve_model_and_settings
from gpd.mcp.research.cost_estimator import estimate_milestone_cost, estimate_plan_cost, format_cost_display
from gpd.mcp.research.schemas import (
    ApprovalGate,
    MilestoneResult,
    MilestoneStatus,
    PlanEvolution,
    ResearchPlan,
)

logger = logging.getLogger(__name__)

MAX_VALIDATION_RETRIES: int = 2
"""Maximum number of retry attempts for plan tool-reference validation (3 total attempts)."""


class PlanValidationError(ValidationError):
    """Raised when plan validation fails after exhausting all retries."""


PLAN_SYSTEM_PROMPT = """\
You are a physics research planner for GPD. Your job is to decompose a physics
research question into a directed acyclic graph (DAG) of milestones that will
answer the question rigorously, efficiently, and with built-in validation.

Before writing any milestones, apply the methodologies below in order. They
transform a vague research intent into a precise, verifiable execution plan.


## Goal-Backward Planning Methodology

Before decomposing into milestones, reason backward from the research goal.

**Step 1: State the goal** -- What must be TRUE when this research succeeds?
  Not "run simulations" but "quantify how X affects Y across parameter range Z."

**Step 2: Derive observable truths** -- What specific results prove the goal?
  Examples: "Convergence study shows grid-independent results",
  "Parameter sweep covers N points in range [a, b]",
  "Comparison with analytical/experimental data within X%."

**Step 3: Derive required artifacts** -- What must EXIST for each truth?
  Mesh files, simulation configs, post-processing scripts, comparison datasets.
  Each artifact maps to calling a specific MCP tool operation.

**Step 4: Derive required wiring** -- What must be CONNECTED?
  Simulation output feeds into post-processing.
  Parameter sweep results feed into comparison analysis.
  All results feed into final synthesis.

**Step 5: Identify key links** -- Where is this most likely to break?
  Simulation divergence, missing comparison data, tool output format mismatches.

Use the goal-backward analysis to inform your milestone DAG. Each milestone
should map directly to producing one or more required artifacts.


## Hypothesis-Driven Research

Before computing, consider: can you state "in this limit, the answer must
behave as X" before deriving? If yes, this is a hypothesis-driven investigation.

For hypothesis-driven milestones, structure as PREDICT -> DERIVE -> VERIFY:
1. PREDICT: State expected behavior before calculation (limiting cases,
   symmetry constraints, dimensional scaling, known asymptotic forms).
2. DERIVE: Perform the calculation or simulation.
3. VERIFY: Check predictions against results. Discrepancies reveal errors
   or new physics -- either is valuable.

The predict-derive-verify cycle catches errors that purely mechanical
calculation would miss: sign errors produce "reasonable-looking" answers until
you check a limiting case that pins the sign. Dimensional analysis catches
missing factors. Conservation laws catch dropped terms.

Mark milestones as hypothesis-driven when:
- Calculations have known limiting cases to check against
- Results must satisfy conservation laws or sum rules
- Symmetry constrains the answer's form
- Dimensional analysis constrains the scaling
- Phase diagrams where topology is known from general arguments
- Transport coefficients with Onsager relations or other exact constraints

Skip the hypothesis-driven structure when:
- Purely exploratory parameter sweeps with no prior expectations
- Data processing, formatting, or infrastructure setup
- Straightforward evaluation of known formulas


## Convention Tracking

Every research plan MUST establish or inherit conventions. Ambiguous notation
is the #1 source of cascading errors in physics calculations. At minimum, note:
- Units: natural (hbar=c=1), SI, CGS, lattice
- Metric signature: (+,-,-,-) vs (-,+,+,+) vs Euclidean
- Coordinate system and gauge choice
- Fourier convention: physics exp(-iwt) vs math exp(+iwt)
- Normalization of states and fields

If prior milestones established conventions, ALL subsequent milestones MUST
use the same conventions unless an explicit convention change step is included.
Convention mismatches between milestones are plan-level bugs -- catch them now.


## Plan Quality: 15 Verification Dimensions

After generating the plan, self-check against these 15 dimensions (from GPD's
plan verification methodology). If any CRITICAL dimension fails, reject the
plan and regenerate with corrected constraints.

1. Research Question Coverage -- every aspect of the question has milestones
   addressing it. No orphaned sub-questions.
2. Task Completeness -- every milestone has tools, success criteria, expected
   outputs, and a validation strategy.
3. Mathematical Prerequisites -- all required math/physics machinery is
   available or derived in a preceding milestone.
4. Approximation Validity -- all approximations are appropriate for the
   physical regime. Validity bounds stated, not assumed.
5. Computational Feasibility -- algorithms scale to the problem size, converge
   within budget, and are numerically stable.
6. Validation Strategy -- dimensional analysis, limiting cases, symmetry
   checks, and comparison with known results are planned for every computation.
7. Anomaly and Topological Awareness -- quantum anomalies, topological
   invariants, and non-perturbative effects are handled when relevant.
8. Result Wiring -- outputs of each milestone feed into downstream inputs with
   consistent notation, units, and conventions throughout the DAG.
9. Dependency Correctness -- the DAG is acyclic, dependencies reflect genuine
   mathematical and computational prerequisites, not just ordering preferences.
10. Scope Sanity -- 3-8 milestones for a typical research question, each
    mapping to 1-2 MCP tool calls. More signals scope creep.
11. Deliverable Derivation -- must-haves trace back to the research question,
    not to implementation details.
12. Literature Awareness -- the plan is aware of prior work and does not
    rediscover known results. References are cited when building on them.
13. Path to Publication -- there is a clear trajectory from computation to a
    communicable, reproducible result.
14. Failure Mode Identification -- what if the simulation diverges? The series
    does not converge? The approximation breaks down? Fallback strategies noted.
15. Context Compliance -- the plan honors user decisions, excludes deferred
    investigations, and respects locked conventions from prior phases.


## Milestone DAG Rules

A milestone is a self-contained research step with:
- Clear inputs (from prior milestones or initial data)
- Specific tools to call (MCP tool names from the AVAILABLE list only)
- Expected outputs (data, analysis, or synthesis)
- Success criteria (how to know it succeeded)

Rules for plan generation:
1. Produce ALL milestones upfront -- the full plan before execution starts.
2. Assign dependencies between milestones via depends_on (milestone IDs).
3. Mark milestones as is_critical=True if failure would block the research goal.
4. Suggest approval gates (suggested_gate=True) at: initial data gathering,
   key finding analysis, and final report synthesis.
5. For each milestone, estimate gpu_type and estimated_gpu_seconds for cost
   estimation.
6. Keep milestone descriptions concise but specific.
7. The DAG must be acyclic -- no circular dependencies.
8. Include a 'reasoning' field explaining your planning rationale.

CRITICAL CONSTRAINTS:
- ONLY reference tools from the Available Tools list below. NEVER invent tool
  names.
- Each tool has specific operations listed -- only plan tasks those operations
  can do.
- If the available tools cannot accomplish a research step, say so explicitly
  in the milestone description rather than inventing a fictional tool.
- Keep the plan FEASIBLE: 3-8 milestones for a typical research question.
  Do not generate 15+ milestones unless the problem genuinely requires it.
- Each milestone should map directly to calling one or two available MCP tools.
- Use the user's constraints and preferences (if provided) to scope the plan.
"""

EVOLUTION_SYSTEM_PROMPT = (
    "You are a physics research plan evolution agent. Given the current state of a "
    "research plan, completed milestone results, and the latest milestone's output, "
    "determine if the remaining milestones should be modified.\n\n"
    "Rules for plan evolution:\n"
    "1. Preserve existing approval gates on unchanged milestones.\n"
    "2. Default new milestones to approval_gate='suggested'.\n"
    "3. Only modify milestones that are still 'pending' -- never change completed or running milestones.\n"
    "4. Output the complete updated plan (not just changes).\n"
    "5. If no changes are needed, return the plan as-is.\n"
    "6. Include reasoning for each change.\n"
    "7. Keep the DAG acyclic after modifications.\n"
    "8. For new milestones, estimate gpu_type and estimated_gpu_seconds.\n\n"
    "Types of changes:\n"
    "- add: New milestone needed based on findings\n"
    "- remove: Milestone no longer relevant\n"
    "- modify: Milestone tools, dependencies, or criteria need updating"
)

_GATE_ICONS = {
    ApprovalGate.REQUIRED: "[bold red]LOCK[/]",
    ApprovalGate.SUGGESTED: "[yellow]FLAG[/]",
    ApprovalGate.NONE: "[dim]-[/]",
}

_STATUS_STYLES = {
    MilestoneStatus.PENDING: "dim",
    MilestoneStatus.APPROVED: "bold cyan",
    MilestoneStatus.RUNNING: "bold yellow",
    MilestoneStatus.COMPLETED: "bold green",
    MilestoneStatus.FAILED: "bold red",
    MilestoneStatus.SKIPPED: "dim strike",
    MilestoneStatus.REPLANNED: "dim italic",
}


def _build_rich_tool_context(tools: list[dict[str, object]]) -> str:
    """Build a detailed tool context string for the planner prompt.

    Expected input: DiscoveredTool contract from pipeline.py discover command.
    Required keys: name, description, overview, domains, operations, status, priority, reason.

    Includes name, description, overview, domains, and available operations
    so the LLM knows exactly what each tool can do.
    """
    if not tools:
        return "(no tools available)"

    lines: list[str] = []
    for t in tools:
        name = t.get("name", "unknown")
        description = t.get("description", "")
        overview = t.get("overview", "")
        domains = t.get("domains", [])
        operations = t.get("operations", [])
        status = t.get("status", "unknown")
        priority = t.get("priority", "")
        reason = t.get("reason", "")

        # Build a rich entry
        lines.append(f"\n### {name} [{status}]")
        if description:
            lines.append(f"  Description: {description}")
        if overview:
            lines.append(f"  Capabilities: {overview}")
        if domains:
            domain_str = ", ".join(str(d) for d in domains[:5]) if isinstance(domains, list) else str(domains)
            lines.append(f"  Domains: {domain_str}")
        if operations:
            ops_str = "; ".join(str(op) for op in operations[:8]) if isinstance(operations, list) else str(operations)
            lines.append(f"  Operations: {ops_str}")
        if reason:
            lines.append(f"  Selection reason: {reason}")
        if priority:
            lines.append(f"  Priority: {priority}")

    return "\n".join(lines)


def _build_tool_name_context(valid_tool_names: set[str]) -> str:
    """Build a compact tool-name context block for validation retries."""
    if not valid_tool_names:
        return "(no validated tool catalog available)"

    return "\n".join(f"- {tool_name}" for tool_name in sorted(valid_tool_names))


def _collect_plan_validation_errors(
    plan: ResearchPlan,
    valid_tool_names: set[str],
) -> list[str]:
    """Collect tool-reference and DAG validation errors for a plan candidate."""
    errors = plan.validate_tool_references(valid_tool_names)
    errors.extend(plan.validate_no_cycles())
    return errors


def _derive_evolution_tool_names(
    plan: ResearchPlan,
    tool_metadata_registry: dict[str, dict[str, object]],
    available_tools: list[dict[str, object]] | None,
) -> set[str]:
    """Derive the tool names an evolved plan is allowed to reference."""
    valid_tool_names = {t.get("name", "") for t in (available_tools or []) if t.get("name")}
    valid_tool_names.update(tool_name for milestone in plan.milestones for tool_name in milestone.tools)

    milestone_ids = {milestone.milestone_id for milestone in plan.milestones}
    valid_tool_names.update(tool_name for tool_name in tool_metadata_registry if tool_name not in milestone_ids)

    return {tool_name for tool_name in valid_tool_names if tool_name}


def _find_down_tools(
    plan: ResearchPlan,
    available_tools: list[dict[str, object]],
) -> list[str]:
    """Find tools referenced in the plan that exist but are currently unavailable."""
    tool_status = {t.get("name", ""): t.get("status", "unknown") for t in available_tools}
    down: list[str] = []
    for milestone in plan.milestones:
        for tool_name in milestone.tools:
            if tool_status.get(tool_name) == "unavailable" and tool_name not in down:
                down.append(tool_name)
    return down


class ResearchPlanner:
    """LLM-driven research planner that generates and evolves milestone DAGs."""

    def __init__(self, model: str = GPD_DEFAULT_MODEL) -> None:
        """Initialize the planner with PydanticAI agents.

        Args:
            model: PydanticAI model string (may include effort suffix like ``-low``).
        """
        base_model, self._model_settings = resolve_model_and_settings(model)
        self._model = base_model
        self._plan_agent: Agent[None, ResearchPlan] = Agent(
            base_model,
            output_type=ResearchPlan,
            retries=2,
            system_prompt=PLAN_SYSTEM_PROMPT,
        )
        self._evolution_agent: Agent[None, ResearchPlan] = Agent(
            base_model,
            output_type=ResearchPlan,
            retries=2,
            system_prompt=EVOLUTION_SYSTEM_PROMPT,
        )

    async def _run_agent_until_valid(
        self,
        agent: Agent[None, ResearchPlan],
        prompt: str,
        valid_tool_names: set[str],
        validation_context: str,
    ) -> ResearchPlan:
        """Run an agent and retry with validation feedback until the plan is valid."""
        current_prompt = prompt
        last_errors: list[str] = []

        for attempt in range(MAX_VALIDATION_RETRIES + 1):
            result = await agent.run(current_prompt, model_settings=self._model_settings)
            plan = result.output
            errors = _collect_plan_validation_errors(plan, valid_tool_names)
            if not errors:
                return plan

            last_errors = errors
            logger.warning(
                "Plan validation failed (attempt %d/%d): %s",
                attempt + 1,
                MAX_VALIDATION_RETRIES + 1,
                errors,
            )

            if attempt == MAX_VALIDATION_RETRIES:
                raise PlanValidationError(
                    f"Plan validation failed after {MAX_VALIDATION_RETRIES + 1} attempts: {errors}"
                )

            error_block = "\n".join(f"- {error}" for error in errors)
            current_prompt = (
                f"{prompt}\n\n"
                f"VALIDATION ERRORS FROM PREVIOUS ATTEMPT ({attempt + 1}/{MAX_VALIDATION_RETRIES + 1}):\n"
                f"{error_block}\n\n"
                f"Allowed tools and catalog context:\n{validation_context}\n\n"
                "Return the complete corrected ResearchPlan. Use only allowed tools and keep the DAG acyclic."
            )

        raise AssertionError("Unreachable validation loop exit")

    async def generate_plan(
        self,
        query: str,
        available_tools: list[dict[str, object]],
        tool_metadata_registry: dict[str, dict[str, object]],
    ) -> ResearchPlan:
        """Generate a research plan from a query using the LLM planner.

        Calls the planner agent, validates tool references and the DAG after
        each LLM attempt, estimates costs, and sets default approval gates.

        Args:
            query: The research question to decompose.
            available_tools: List of tool metadata dicts with name/description.
            tool_metadata_registry: Cost metadata keyed by tool name, milestone_id, or both.

        Returns:
            A fully costed and validated ResearchPlan.
        """
        tools_context = _build_rich_tool_context(available_tools)
        valid_tool_names = {t.get("name", "") for t in available_tools if t.get("name")}

        prompt = f"Research question: {query}\n\nAvailable MCP tools (ONLY use these names):\n{tools_context}"
        validation_context = tools_context if valid_tool_names else _build_tool_name_context(valid_tool_names)
        plan = await self._run_agent_until_valid(
            self._plan_agent,
            prompt,
            valid_tool_names,
            validation_context,
        )

        # Advisory for milestones with >2 tool calls (per MCP-02 decision)
        for i, milestone in enumerate(plan.milestones):
            if len(milestone.tools) > 2:
                logger.warning(
                    "Advisory: Milestone %d (%s) uses %d tools -- consider splitting",
                    i + 1,
                    milestone.milestone_id,
                    len(milestone.tools),
                )

        # Warn when the plan references tools that are currently unavailable.
        down_tools = _find_down_tools(plan, available_tools)
        if down_tools:
            logger.warning(
                "Plan references %d unavailable tool(s): %s",
                len(down_tools),
                down_tools,
            )

        # Set plan_id
        plan.plan_id = uuid4().hex[:12]

        # Set default approval gates
        for i, milestone in enumerate(plan.milestones):
            if i == 0 and milestone.approval_gate == ApprovalGate.NONE:
                milestone.approval_gate = ApprovalGate.SUGGESTED

        # Build approval_gates list
        plan.approval_gates = [m.milestone_id for m in plan.milestones if m.approval_gate != ApprovalGate.NONE]

        # Estimate costs
        plan.total_cost_estimate = estimate_plan_cost(plan, tool_metadata_registry)

        return plan

    async def evolve_plan(
        self,
        plan: ResearchPlan,
        completed_results: dict[str, MilestoneResult],
        latest_milestone_id: str,
        tool_metadata_registry: dict[str, dict[str, object]],
        available_tools: list[dict[str, object]] | None = None,
    ) -> tuple[ResearchPlan, list[PlanEvolution]]:
        """Evolve a plan based on completed milestone results.

        Calls the evolution agent with the current plan state and completed
        results. Compares the returned plan to detect changes, builds
        PlanEvolution entries, preserves approval gates on unchanged milestones,
        and re-estimates costs on new/modified milestones.

        Args:
            plan: Current research plan.
            completed_results: Mapping of milestone_id to MilestoneResult.
            latest_milestone_id: ID of the most recently completed milestone.
            tool_metadata_registry: Cost metadata keyed by tool name, milestone_id, or both.
            available_tools: Optional discovered tool catalog used to validate new tool refs.

        Returns:
            Tuple of (updated_plan, list_of_evolution_entries).
        """
        results_context = "\n".join(
            f"- {mid}: {'ERROR: ' + r.error_message if r.is_error else r.result_summary}"
            for mid, r in completed_results.items()
        )
        prompt = (
            f"Current plan (version {plan.version}):\n"
            f"Query: {plan.query}\n"
            f"Milestones: {[m.milestone_id for m in plan.milestones]}\n"
            f"Completed results:\n{results_context}\n"
            f"Latest completed: {latest_milestone_id}\n\n"
            "Should the remaining milestones be modified?"
        )
        valid_tool_names = _derive_evolution_tool_names(plan, tool_metadata_registry, available_tools)
        validation_context = (
            _build_rich_tool_context(available_tools)
            if available_tools
            else _build_tool_name_context(valid_tool_names)
        )
        new_plan = await self._run_agent_until_valid(
            self._evolution_agent,
            prompt,
            valid_tool_names,
            validation_context,
        )

        # Build original milestone lookup for comparison
        original_ids = {m.milestone_id for m in plan.milestones}
        new_ids = {m.milestone_id for m in new_plan.milestones}
        original_map = {m.milestone_id: m for m in plan.milestones}

        evolutions: list[PlanEvolution] = []
        timestamp = datetime.datetime.now(tz=datetime.UTC).isoformat()
        new_version = plan.version + 1

        # Detect added milestones
        added = new_ids - original_ids
        if added:
            evolutions.append(
                PlanEvolution(
                    version=new_version,
                    timestamp=timestamp,
                    change_type="add",
                    affected_milestones=sorted(added),
                    reason="New milestones added based on findings",
                    auto_triggered=True,
                )
            )

        # Detect removed milestones
        removed = original_ids - new_ids
        if removed:
            evolutions.append(
                PlanEvolution(
                    version=new_version,
                    timestamp=timestamp,
                    change_type="remove",
                    affected_milestones=sorted(removed),
                    reason="Milestones removed based on findings",
                    auto_triggered=True,
                )
            )

        # Detect modified milestones (in both old and new)
        common = original_ids & new_ids
        new_map = {m.milestone_id: m for m in new_plan.milestones}
        modified: list[str] = []
        for mid in common:
            old_m = original_map[mid]
            new_m = new_map[mid]
            if (
                old_m.description != new_m.description
                or old_m.depends_on != new_m.depends_on
                or old_m.tools != new_m.tools
                or old_m.success_criteria != new_m.success_criteria
            ):
                modified.append(mid)

        if modified:
            evolutions.append(
                PlanEvolution(
                    version=new_version,
                    timestamp=timestamp,
                    change_type="modify",
                    affected_milestones=sorted(modified),
                    reason="Milestones modified based on findings",
                    auto_triggered=True,
                )
            )

        # Preserve approval gates on unchanged milestones
        for milestone in new_plan.milestones:
            if milestone.milestone_id in original_map and milestone.milestone_id not in modified:
                milestone.approval_gate = original_map[milestone.milestone_id].approval_gate
                milestone.status = original_map[milestone.milestone_id].status

        # Default new milestones to SUGGESTED gate
        for milestone in new_plan.milestones:
            if milestone.milestone_id in added:
                milestone.approval_gate = ApprovalGate.SUGGESTED

        # Update plan metadata
        new_plan.version = new_version
        new_plan.plan_id = plan.plan_id
        new_plan.evolution_log = [*plan.evolution_log, *evolutions]
        new_plan.approval_gates = [m.milestone_id for m in new_plan.milestones if m.approval_gate != ApprovalGate.NONE]

        # Re-estimate costs on new/modified milestones
        changed_ids = added | set(modified)
        for milestone in new_plan.milestones:
            if milestone.milestone_id in changed_ids:
                milestone.cost_estimate = estimate_milestone_cost(milestone, tool_metadata_registry)

        new_plan.total_cost_estimate = estimate_plan_cost(new_plan, tool_metadata_registry)

        return new_plan, evolutions


def display_plan(plan: ResearchPlan, console: Console) -> None:
    """Render a research plan as a Rich table in a panel.

    Shows milestones with dependencies, tools, approval gates,
    critical path status, and cost estimates.

    Args:
        plan: The research plan to display.
        console: Rich Console for output.
    """
    low, high = plan.total_cost_estimate.estimated_cost_range
    header_text = Text()
    header_text.append("Query: ", style="bold")
    header_text.append(plan.query)
    header_text.append(f"\nVersion: {plan.version}")
    header_text.append(f" | Total cost: ${low:.2f}-${high:.2f}")
    header_text.append(f" ({plan.total_cost_estimate.confidence} confidence)")

    table = Table(show_header=True, header_style="bold cyan", expand=True)
    table.add_column("#", style="dim", width=4)
    table.add_column("Milestone", min_width=20)
    table.add_column("Dependencies", style="dim")
    table.add_column("Tools", style="dim")
    table.add_column("Gate", justify="center", width=6)
    table.add_column("Crit", justify="center", width=4)
    table.add_column("Est. Cost", justify="right")

    for i, milestone in enumerate(plan.milestones, 1):
        description = milestone.description
        if len(description) > 50:
            description = description[:47] + "..."

        deps = ", ".join(milestone.depends_on) if milestone.depends_on else "-"
        tools = ", ".join(milestone.tools) if milestone.tools else "-"
        gate = _GATE_ICONS.get(milestone.approval_gate, "-")
        critical = "[bold]Y[/]" if milestone.is_critical else "[dim]N[/]"
        cost = format_cost_display(milestone.cost_estimate)

        style = _STATUS_STYLES.get(milestone.status, "")
        table.add_row(str(i), f"[{style}]{description}[/]", deps, tools, gate, critical, cost)

    footer = f"\n{len(plan.milestones)} milestones | Total: ${low:.2f}-${high:.2f}"

    console.print(Panel(header_text, title="Research Plan", border_style="blue"))
    console.print(table)
    console.print(Text(footer, style="dim"))


def display_plan_evolution(evolutions: list[PlanEvolution], console: Console) -> None:
    """Render plan evolution changes as a Rich panel.

    Added milestones shown in green, removed in red, modified in yellow.

    Args:
        evolutions: List of PlanEvolution entries to display.
        console: Rich Console for output.
    """
    if not evolutions:
        console.print(Panel("[dim]No plan changes.[/]", title="Plan Evolution", border_style="dim"))
        return

    lines: list[str] = []
    for evo in evolutions:
        style_map = {"add": "green", "remove": "red", "modify": "yellow"}
        style = style_map.get(evo.change_type, "white")
        prefix_map = {"add": "+", "remove": "-", "modify": "~"}
        prefix = prefix_map.get(evo.change_type, "?")

        for mid in evo.affected_milestones:
            lines.append(f"[{style}]{prefix} {mid}[/] -- {evo.reason}")

    content = "\n".join(lines) if lines else "[dim]No changes.[/]"
    console.print(Panel(content, title=f"Plan Evolution (v{evolutions[-1].version})", border_style="yellow"))


async def prompt_plan_approval(
    plan: ResearchPlan,
    console: Console,
) -> tuple[bool, ResearchPlan]:
    """Display plan and prompt user for approval.

    Shows the plan via display_plan, then prompts the user to approve,
    reject, or edit approval gates.

    Args:
        plan: The research plan to approve.
        console: Rich Console for display and input.

    Returns:
        Tuple of (approved: bool, possibly_modified_plan: ResearchPlan).
    """
    display_plan(plan, console)

    response = console.input("\n[bold]Approve plan? (y/n/edit): [/]").strip().lower()

    if response == "y":
        return True, plan

    if response == "n":
        return False, plan

    if response == "edit":
        console.print("\n[bold]Milestones with approval gates:[/]")
        for i, milestone in enumerate(plan.milestones, 1):
            gate_str = milestone.approval_gate.value
            console.print(f"  {i}. {milestone.milestone_id} [{gate_str}]")

        toggle_input = console.input("\n[bold]Toggle gates (comma-separated numbers, or 'done'): [/]").strip()
        if toggle_input.lower() != "done":
            try:
                indices = [int(x.strip()) - 1 for x in toggle_input.split(",")]
                for idx in indices:
                    if 0 <= idx < len(plan.milestones):
                        milestone = plan.milestones[idx]
                        if milestone.approval_gate == ApprovalGate.NONE:
                            milestone.approval_gate = ApprovalGate.SUGGESTED
                        elif milestone.approval_gate == ApprovalGate.SUGGESTED:
                            milestone.approval_gate = ApprovalGate.REQUIRED
                        else:
                            milestone.approval_gate = ApprovalGate.NONE
            except ValueError:
                console.print("[red]Invalid input, no changes made.[/]")

        plan.approval_gates = [m.milestone_id for m in plan.milestones if m.approval_gate != ApprovalGate.NONE]
        return True, plan

    # Default: treat unknown input as rejection
    return False, plan
