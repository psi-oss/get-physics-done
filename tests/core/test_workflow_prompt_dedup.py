"""Regression checks for planner workflow prompt deduplication."""

from __future__ import annotations

from pathlib import Path

from gpd.adapters.install_utils import expand_at_includes

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
TEMPLATES_DIR = REPO_ROOT / "src/gpd/specs/templates"
AGENTS_DIR = REPO_ROOT / "src/gpd/agents"


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

    for legacy_phrase in (
        "Each plan has a complete contract block (claims, deliverables, acceptance tests, forbidden proxies, uncertainty markers, and `references[]` whenever grounding is not already explicit elsewhere in the contract)",
        "Non-scoping plans keep `claims[]`, `deliverables[]`, `acceptance_tests[]`, and `forbidden_proxies[]` non-empty.",
        "Include `references[]` only when the plan relies on external grounding",
        "Keep the full canonical frontmatter, including `wave`, `depends_on`, `files_modified`, `interactive`, `conventions`, and `contract`.",
        "If the downstream fix plan will need specialized tooling or any other machine-checkable hard validation requirement, surface it in PLAN frontmatter `tool_requirements` before drafting task prose.",
        "If the revised fix plan still needs specialized tooling or any other machine-checkable hard validation requirement, keep it in PLAN frontmatter `tool_requirements` before rewriting task prose.",
    ):
        assert legacy_phrase not in plan_phase
        assert legacy_phrase not in verify_work

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


def test_numerical_analysis_command_wrappers_stay_thin() -> None:
    command_dir = REPO_ROOT / "src/gpd/commands"
    workflow_dir = REPO_ROOT / "src/gpd/specs/workflows"

    for name in (
        "numerical-convergence",
        "sensitivity-analysis",
        "parameter-sweep",
        "error-propagation",
    ):
        command = (command_dir / f"{name}.md").read_text(encoding="utf-8")
        workflow = (workflow_dir / f"{name}.md").read_text(encoding="utf-8")

        assert f"@{{GPD_INSTALL_DIR}}/workflows/{name}.md" in command
        assert "workflow owns detailed method guidance" in command
        assert "Do not restate workflow-owned checklists" in command
        assert command.count("@{GPD_INSTALL_DIR}/workflows/") == 2
        assert len(command.splitlines()) < 45
        assert len(command) < len(workflow) // 3
        assert "```python" not in command
        assert "| Method" not in command
        assert "## 1." not in command
