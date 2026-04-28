"""Assertions for planner workflow prompt deduplication."""

from __future__ import annotations

import re
from pathlib import Path

from gpd.adapters.install_utils import expand_at_includes

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"
COMMANDS_DIR = REPO_ROOT / "src/gpd/commands"
REFERENCES_DIR = REPO_ROOT / "src/gpd/specs/references"
RESULT_LOOKUP_WORKFLOWS = ("explain.md", "compare-experiment.md", "limiting-cases.md")


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


def test_command_wrappers_do_not_repeat_self_workflow_reference_after_include() -> None:
    for path in sorted(COMMANDS_DIR.rglob("*.md")):
        command_slug = path.stem
        workflow_reference = re.compile(
            rf"(?<!@)\{{GPD_INSTALL_DIR\}}/workflows/{re.escape(command_slug)}\.md"
            rf"|@\{{GPD_INSTALL_DIR\}}/workflows/{re.escape(command_slug)}\.md"
        )
        content = path.read_text(encoding="utf-8")
        assert len(workflow_reference.findall(content)) <= 1, path.relative_to(REPO_ROOT)


def test_set_profile_updates_only_model_profile_through_config_cli() -> None:
    set_profile = _read("set-profile.md")

    assert 'gpd config set model_profile "$ARGUMENTS.profile"' in set_profile
    assert "preserving all other `GPD/config.json` keys" in set_profile
    assert '"model_profile": "$ARGUMENTS.profile"' not in set_profile
    assert "Write updated config back to `GPD/config.json`" not in set_profile


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
    assert planner_agent_raw.count("@{GPD_INSTALL_DIR}/templates/plan-contract-schema.md") == 0
    assert "This template carries the hard planner contract gates." in planner_agent_raw

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


def test_planner_agent_does_not_duplicate_canonical_plan_template_blocks() -> None:
    planner_agent = (AGENTS_DIR / "gpd-planner.md").read_text(encoding="utf-8")
    phase_template = (TEMPLATES_DIR / "phase-prompt.md").read_text(encoding="utf-8")

    canonical_only_markers = (
        "# Phase Plan Prompt Template",
        "## File Template",
        "phase: XX-name",
        "type: execute | tdd",
        "## Required Frontmatter",
        "## Light Plan Variant",
        "## Contract Shape Classifier",
    )

    for marker in canonical_only_markers:
        assert marker in phase_template
        assert marker not in planner_agent

    assert "## PLAN.md Source Of Truth" in planner_agent
    assert "Gap-specific fields to insert into the canonical `phase-prompt.md` template:" in planner_agent


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


def test_new_project_workflow_references_late_artifact_templates_without_inlining_skeletons() -> None:
    new_project = _read("new-project.md")
    project_template = (TEMPLATES_DIR / "project.md").read_text(encoding="utf-8")
    state_template = (TEMPLATES_DIR / "state.md").read_text(encoding="utf-8")

    assert "{GPD_INSTALL_DIR}/templates/project.md" in new_project
    assert "{GPD_INSTALL_DIR}/templates/state.md" in new_project
    assert "@{GPD_INSTALL_DIR}/templates/project.md" not in new_project
    assert "@{GPD_INSTALL_DIR}/templates/state.md" not in new_project

    assert "# {project_title}" in project_template
    assert "## Scoping Contract Summary" in project_template
    assert "## Current Position" in state_template
    assert "**Current Phase Name:** [Phase name]" in state_template

    assert new_project.count("## Scoping Contract Summary") <= 1
    for removed_project_skeleton_marker in (
        "# [Extracted Research Title]",
        "[Extracted research question]",
        "- **User-stated observables:** [Specific quantity, curve, figure, or smoking-gun signal]",
        "| Parameter | Symbol | Regime | Notes |",
        "_Last updated: [today's date] after initialization (minimal)_",
    ):
        assert removed_project_skeleton_marker not in new_project

    for removed_state_skeleton_marker in (
        "# Research State",
        "See: GPD/PROJECT.md (updated [today's date])",
        "**Current Phase:** 1",
        "**Current Phase Name:** [Phase 1 name]",
        "**Stopped at:** Project initialized (minimal)",
    ):
        assert removed_state_skeleton_marker not in new_project


def test_notation_coordinator_references_subfield_defaults_without_inlining_table() -> None:
    notation_coordinator = (AGENTS_DIR / "gpd-notation-coordinator.md").read_text(encoding="utf-8")
    subfield_defaults = (
        REFERENCES_DIR / "conventions" / "subfield-convention-defaults.md"
    ).read_text(encoding="utf-8")
    canonical_reference = "{GPD_INSTALL_DIR}/references/conventions/subfield-convention-defaults.md"

    assert canonical_reference in notation_coordinator
    assert f"@{canonical_reference}" not in notation_coordinator
    assert "Load the canonical subfield defaults reference and look up the matching subfield." in notation_coordinator
    assert "Pre-populate `CONVENTIONS.md` with the default choices." in notation_coordinator

    assert "## Convention Defaults by Subfield" in subfield_defaults
    assert "## Convention Defaults by Subfield" not in notation_coordinator
    for canonical_row in (
        "| Units | Natural: ℏ = c = 1 | Universal in particle physics |",
        "| Metric signature | (+,−,−,−) (West Coast) | Peskin & Schroeder, Weinberg |",
        "| Brillouin zone | First BZ; high-symmetry points (Γ, X, M, K) | Setyawan & Curtarolo notation |",
    ):
        assert canonical_row in subfield_defaults
        assert canonical_row not in notation_coordinator


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


def test_result_lookup_policy_is_single_sourced_for_high_level_workflows() -> None:
    policy = (REFERENCES_DIR / "results" / "result-lookup-policy.md").read_text(encoding="utf-8")

    assert policy.count("# Result Lookup Policy") == 1
    assert policy.count("gpd result search") == 2
    assert policy.count("gpd result show") == 1
    assert policy.count("gpd result deps") == 1
    assert policy.count("gpd result downstream") == 1
    assert "Keep `gpd query search` for SUMMARY/frontmatter lookup" in policy

    for workflow_name in RESULT_LOOKUP_WORKFLOWS:
        raw = _read(workflow_name)
        expanded = _expand(workflow_name)

        assert raw.count("references/results/result-lookup-policy.md") == 1, workflow_name
        assert expanded.count("references/results/result-lookup-policy.md") == 1, workflow_name
        assert "# Result Lookup Policy" not in expanded, workflow_name

        for command in (
            "gpd result search",
            "gpd result show",
            "gpd result deps",
            "gpd result downstream",
        ):
            assert command not in raw, workflow_name
            assert command not in expanded, workflow_name
        assert "direct stored-result view before" not in raw, workflow_name
        assert "reverse dependency tree separated into direct and transitive" not in raw, workflow_name


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
    assert "The shared note owns runtime-neutral task construction and handoff gates." in execute_phase
    assert "The shared note owns empty-model omission" not in execute_phase
    assert "preserve empty-model omission, `readonly=false`, artifact-gated completion" not in execute_phase
    assert execute_phase.count("Apply the canonical runtime delegation convention above.") >= 3


def test_runtime_delegation_note_is_loaded_once_per_workflow() -> None:
    include = "@{GPD_INSTALL_DIR}/references/orchestration/runtime-delegation-note.md"
    repeated_reference = "Apply the canonical runtime delegation convention already loaded above."
    workflows_using_short_references = {
        "audit-milestone.md",
        "explain.md",
        "new-milestone.md",
        "new-project.md",
        "quick.md",
        "write-paper.md",
    }

    for path in sorted(WORKFLOWS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        assert text.count(include) <= 1, path.name
        if path.name in workflows_using_short_references:
            assert text.count(include) == 1, path.name
            assert repeated_reference in text, path.name


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


def test_bibliographer_delegates_return_boilerplate_to_agent_infrastructure() -> None:
    text = (AGENTS_DIR / "gpd-bibliographer.md").read_text(encoding="utf-8")

    assert "Use agent-infrastructure.md for checkpoint ownership, return-envelope base fields" in text
    assert "# Base fields (`status`, `files_written`, `issues`, `next_actions`) follow agent-infrastructure.md." in text

    for removed_phrase in (
        "Checkpoint ownership is orchestrator-side",
        "Runtime delegation rule:",
        "The headings in this section are presentation only.",
        "Use `gpd_return.status: checkpoint` as the control surface.",
        "Return `gpd_return.status: completed`, `checkpoint`, `blocked`, or `failed`.",
    ):
        assert removed_phrase not in text
