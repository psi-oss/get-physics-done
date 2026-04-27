"""Assertions for planner workflow prompt deduplication."""

from __future__ import annotations

from pathlib import Path

from gpd.adapters.install_utils import expand_at_includes

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
REFERENCES_DIR = REPO_ROOT / "src/gpd/specs/references"


def _read(name: str) -> str:
    return (WORKFLOWS_DIR / name).read_text(encoding="utf-8")


def _expand(name: str) -> str:
    return expand_at_includes(_read(name), REPO_ROOT / "src/gpd", "/runtime/")


def _between(text: str, start: str, end: str) -> str:
    _, marker, tail = text.partition(start)
    assert marker, f"missing marker: {start}"
    body, end_marker, _ = tail.partition(end)
    assert end_marker, f"missing marker: {end}"
    return body


def test_installed_prompt_paths_do_not_reference_source_specs_segment() -> None:
    for directory in (WORKFLOWS_DIR, TEMPLATES_DIR, AGENTS_DIR, REFERENCES_DIR):
        for path in sorted(directory.rglob("*.md")):
            content = path.read_text(encoding="utf-8")
            assert "{GPD_INSTALL_DIR}/specs/" not in content, path.relative_to(REPO_ROOT)
            assert "src/gpd/specs/" not in content, path.relative_to(REPO_ROOT)


def test_shipped_templates_do_not_contain_runtime_installer_comments() -> None:
    for path in sorted(TEMPLATES_DIR.rglob("*.md")):
        content = path.read_text(encoding="utf-8")
        assert "installer adapts" not in content, path.relative_to(REPO_ROOT)
        assert not any(line.lstrip().startswith("#") and "<!--" in line for line in content.splitlines()), (
            path.relative_to(REPO_ROOT)
        )


def test_command_wrappers_do_not_duplicate_workflow_routing_boilerplate() -> None:
    forbidden_phrases = (
        "Routes to the",
        "workflow which handles:",
        "The workflow handles all logic including:",
    )
    for path in sorted(COMMANDS_DIR.rglob("*.md")):
        content = path.read_text(encoding="utf-8")
        for phrase in forbidden_phrases:
            assert phrase not in content, path.relative_to(REPO_ROOT)


def test_planner_workflows_expand_the_shared_planner_template_once_per_route() -> None:
    plan_phase_raw = _read("plan-phase.md")
    quick_raw = _read("quick.md")
    verify_work_raw = _read("verify-work.md")
    planner_agent_raw = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")

    quick = _expand("quick.md")
    verify_work = _expand("verify-work.md")
    planner_template = (TEMPLATES_DIR / "planner-subagent-prompt.md").read_text(encoding="utf-8")

    assert "templates/planner-subagent-prompt.md" in plan_phase_raw
    assert "# Planner Subagent Prompt Template" not in plan_phase_raw
    assert "templates/planner-subagent-prompt.md" in verify_work_raw
    assert "# Planner Subagent Prompt Template" not in verify_work_raw

    assert plan_phase_raw.count("templates/planner-subagent-prompt.md") == 2
    assert verify_work_raw.count("templates/planner-subagent-prompt.md") == 2
    assert "templates/planner-subagent-prompt.md" not in quick_raw
    assert planner_agent_raw.count("@{GPD_INSTALL_DIR}/templates/phase-prompt.md") == 1
    assert planner_agent_raw.count("@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md") == 1
    assert "These are the hard planner contract gates." in planner_agent_raw

    assert planner_template.count("## Standard Planning Template") == 1
    assert planner_template.count("## Revision Template") == 1
    assert planner_template.count("@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md") == 1
    assert "project_contract_gate.authoritative" in quick
    assert "# Planner Subagent Prompt Template" not in verify_work
    assert "## Standard Planning Template" not in verify_work
    assert "## Revision Template" not in verify_work
    assert "project_contract_load_info.status" in verify_work
    assert "project_contract_load_info.errors" in verify_work_raw

    assert "project_contract_gate.authoritative" in planner_template
    plan_phase_prompt = _between(plan_phase_raw, "Planner prompt:", "task(")
    assert "project_contract_gate.authoritative" not in plan_phase_prompt
    assert "{GPD_INSTALL_DIR}/templates/phase-prompt.md" not in plan_phase_prompt
    assert "{GPD_INSTALL_DIR}/templates/plan-contract-schema.md" not in plan_phase_prompt
    assert "<physics_planning_requirements>" not in plan_phase_prompt
    assert "<downstream_consumer>" not in plan_phase_prompt
    assert "<quality_gate>" not in plan_phase_prompt


def test_planner_workflows_do_not_embed_the_removed_long_policy_blocks() -> None:
    plan_phase = _read("plan-phase.md")
    quick = _read("quick.md")
    verify_work = _read("verify-work.md")

    for removed_phrase in (
        "Each plan has a complete contract block (claims, deliverables, acceptance tests, forbidden proxies, uncertainty markers, and `references[]` whenever grounding is not already explicit elsewhere in the contract)",
        "Non-scoping plans keep `claims[]`, `deliverables[]`, `acceptance_tests[]`, and `forbidden_proxies[]` non-empty.",
        "Include `references[]` only when the plan relies on external grounding",
        "Keep the full canonical frontmatter, including `wave`, `depends_on`, `files_modified`, `interactive`, `conventions`, and `contract`.",
        "If the downstream fix plan will need specialized tooling or any other machine-checkable hard validation requirement, surface it in PLAN frontmatter `tool_requirements` before drafting task prose.",
        "If the revised fix plan still needs specialized tooling or any other machine-checkable hard validation requirement, keep it in PLAN frontmatter `tool_requirements` before rewriting task prose.",
    ):
        assert removed_phrase not in plan_phase
        assert removed_phrase not in verify_work

    assert "Render the template's `## Standard Planning Template` into `filled_prompt`" in plan_phase
    assert "Render the template's `## Revision Template` into `revision_prompt`" in plan_phase
    assert "Do not restate template-owned contract gates" in plan_phase
    assert "Use the shared planner template, phase template, and `templates/plan-contract-schema.md`." not in plan_phase
    assert (
        "Before planning, load the shared planner template, phase template, and canonical contract schema." not in quick
    )
    assert "The shared planner template owns the canonical planning policy and contract gate." not in verify_work
    assert "The shared planner template owns the canonical planning and revision policy." not in verify_work


def test_new_project_workflow_keeps_contract_preservation_rules_single_sourced() -> None:
    new_project = _read("new-project.md")

    assert (
        "If the init JSON already contains `project_contract`, `project_contract_load_info`, or "
        "`project_contract_validation`, preserve that state in the approval gate and continuation decision."
    ) in new_project
    assert (
        "preserve any init-surfaced `project_contract`, `project_contract_load_info`, and "
        "`project_contract_validation` state while deciding whether this is fresh work or a continuation."
    ) not in new_project
    assert (
        "`schema_version` must be the integer `1`, `references[].must_surface` must stay a boolean `true` or "
        "`false`, and `context_intake`, `uncertainty_markers`, and `references[]` must stay visible in the approval gate"
    ) in new_project
    assert (
        "keep `schema_version` at `1`, and keep `references[].must_surface` as a boolean, not a synonym"
        not in new_project
    )


def test_planner_workflows_keep_tangent_policy_single_sourced() -> None:
    plan_phase = _read("plan-phase.md")

    assert plan_phase.count("Required 4-way tangent decision model:") == 1
    assert plan_phase.count("Branch as alternative hypothesis") == 1


def test_context_pressure_default_threshold_table_is_single_sourced() -> None:
    infra = (REPO_ROOT / "src/gpd/specs/references/orchestration/agent-infrastructure.md").read_text(
        encoding="utf-8"
    )
    thresholds = (REPO_ROOT / "src/gpd/specs/references/orchestration/context-pressure-thresholds.md").read_text(
        encoding="utf-8"
    )

    assert infra.count("| GREEN | < 40% | Proceed normally |") == 1
    assert "| GREEN | < 40% | Proceed normally |" not in thresholds
    assert "This file only lists per-agent overrides and calibration notes." in thresholds


def test_state_portability_uses_canonical_continuation_prose() -> None:
    state_portability = (REPO_ROOT / "src/gpd/specs/references/orchestration/state-portability.md").read_text(
        encoding="utf-8"
    )

    assert "Canonical state in `state.json.continuation` wins first" in state_portability
    assert "gpd --raw resume` emits the canonical top-level list" in state_portability
    assert "A derived head without a portable usable resume file remains advisory continuity context only." not in state_portability


def test_execute_phase_runtime_delegation_rules_are_single_sourced() -> None:
    execute_phase = _read("execute-phase.md")

    assert execute_phase.count("references/orchestration/runtime-delegation-note.md") == 1
    assert "The shared note owns empty-model omission" in execute_phase
    assert "preserve empty-model omission, `readonly=false`, artifact-gated completion" not in execute_phase
    assert execute_phase.count("Apply the canonical runtime delegation convention above.") >= 3


def test_experiment_designer_uses_external_ising_example_as_single_source() -> None:
    designer = (AGENTS_DIR / "gpd-experiment-designer.md").read_text(encoding="utf-8")
    example = (
        REPO_ROOT / "src/gpd/specs/references/examples/ising-experiment-design-example.md"
    ).read_text(encoding="utf-8")

    assert "## Worked Example: 2D Ising Model Phase Diagram via Monte Carlo" not in designer
    assert designer.count("@{GPD_INSTALL_DIR}/references/examples/ising-experiment-design-example.md") == 1
    assert "This gives 15 critical-region temperatures" in example
    assert "This gives 14 temperatures" not in example


def test_numeric_context_budget_guidance_is_single_sourced() -> None:
    context_budget = (REFERENCES_DIR / "orchestration" / "context-budget.md").read_text(encoding="utf-8")
    infra = (REFERENCES_DIR / "orchestration" / "agent-infrastructure.md").read_text(encoding="utf-8")
    meta = (REFERENCES_DIR / "orchestration" / "meta-orchestration.md").read_text(encoding="utf-8")
    execute_phase = _read("execute-phase.md")

    assert "## Phase-Class Budget Targets" in context_budget
    assert "Summary aggregation heuristic" in context_budget
    assert "estimated_tokens = plan_count * tasks_per_plan * 6000" not in infra
    assert "| Phase Type | Orchestrator Budget | Agent Budget (each) | Total per Phase | Notes |" not in meta
    assert "This document owns strategic routing; it does not restate the budget table." in meta
    assert "references/orchestration/context-budget.md` as the canonical numeric source" in infra
    assert "references/orchestration/context-budget.md" in execute_phase


def test_executor_uses_plain_paths_for_inline_references_and_at_includes_only_for_real_includes() -> None:
    executor = (AGENTS_DIR / "gpd-executor.md").read_text(encoding="utf-8")

    inline_at_lines = [
        line for line in executor.splitlines() if "@{GPD_INSTALL_DIR}" in line and not line.strip().startswith("@{GPD_INSTALL_DIR}/")
    ]
    assert inline_at_lines == []
    assert "`{GPD_INSTALL_DIR}/references/orchestration/checkpoints.md`" in executor
    assert "`{GPD_INSTALL_DIR}/templates/summary.md`" in executor


def test_agent_specific_return_examples_defer_base_envelope_fields_to_infrastructure() -> None:
    trimmed_agents = (
        "gpd-experiment-designer.md",
        "gpd-notation-coordinator.md",
        "gpd-project-researcher.md",
        "gpd-phase-researcher.md",
        "gpd-plan-checker.md",
        "gpd-research-mapper.md",
        "gpd-research-synthesizer.md",
        "gpd-roadmapper.md",
        "gpd-paper-writer.md",
        "gpd-verifier.md",
        "gpd-executor.md",
        "gpd-referee.md",
        "gpd-bibliographer.md",
        "gpd-debugger.md",
        "gpd-literature-reviewer.md",
        "gpd-planner.md",
    )

    for agent_name in trimmed_agents:
        text = (AGENTS_DIR / agent_name).read_text(encoding="utf-8")
        assert "# Base fields (`status`, `files_written`, `issues`, `next_actions`) follow agent-infrastructure.md." in text, agent_name
        assert "The four base fields (`status`, `files_written`, `issues`, `next_actions`)" not in text, agent_name
