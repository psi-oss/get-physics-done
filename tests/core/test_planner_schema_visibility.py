"""Regression tests for explicit planner schema visibility."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLANNER_ROLE = REPO_ROOT / "src" / "gpd" / "agents" / "gpd-planner.md"
PLAN_PHASE = REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "plan-phase.md"
VERIFY_WORK = REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "verify-work.md"
QUICK = REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "quick.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_planner_role_owns_schema_visibility_and_workflows_use_the_short_role_preamble() -> None:
    planner_role = _read(PLANNER_ROLE)
    plan_phase = _read(PLAN_PHASE)
    verify_work = _read(VERIFY_WORK)
    quick = _read(QUICK)

    required_markers = (
        "{GPD_INSTALL_DIR}/templates/phase-prompt.md",
        "{GPD_INSTALL_DIR}/templates/plan-contract-schema.md",
    )

    for marker in required_markers:
        assert marker in planner_role

    bootstrap = planner_role.partition("</role>")[0]

    assert "Keep this agent prompt lean." in planner_role
    assert "use this file for planner role, routing, and plan-shape guidance only." in planner_role
    assert "@{GPD_INSTALL_DIR}/workflows/execute-plan.md" not in bootstrap
    assert "@{GPD_INSTALL_DIR}/templates/summary.md" not in bootstrap
    assert "@{GPD_INSTALL_DIR}/references/protocols/order-of-limits.md" not in bootstrap
    short_instruction = "First, read {GPD_AGENTS_DIR}/gpd-planner.md for your role and instructions."
    long_instruction = (
        "First, read {GPD_AGENTS_DIR}/gpd-planner.md, {GPD_INSTALL_DIR}/templates/phase-prompt.md, "
        "and {GPD_INSTALL_DIR}/templates/plan-contract-schema.md for your role and instructions."
    )
    assert plan_phase.count(short_instruction) == 2
    assert verify_work.count(short_instruction) == 2
    assert quick.count(short_instruction) == 1
    assert long_instruction not in plan_phase
    assert long_instruction not in verify_work
    assert long_instruction not in quick

PLANNER_TEMPLATE = REPO_ROOT / "src" / "gpd" / "specs" / "templates" / "planner-subagent-prompt.md"
EXECUTOR_COMPLETION = REPO_ROOT / "src" / "gpd" / "specs" / "references" / "execution" / "executor-completion.md"


def test_planner_template_embeds_plan_contract_schema_critical_excerpt() -> None:
    planner_template = _read(PLANNER_TEMPLATE)
    plan_phase = _read(PLAN_PHASE)

    marker = "PLAN contract schema-critical excerpt"
    assert marker in planner_template
    assert "path reference alone" in planner_template
    for token in (
        "schema_version: 1",
        "scope.question",
        "scope.in_scope",
        "claims",
        "deliverables",
        "acceptance_tests",
        "forbidden_proxies",
        "uncertainty_markers",
        "Proof-bearing claims",
    ):
        assert token in planner_template

    assert marker in plan_phase
    assert plan_phase.index(marker) > plan_phase.index("Planner prompt:")


def test_executor_completion_embeds_summary_contract_schema_critical_excerpt() -> None:
    executor_completion = _read(EXECUTOR_COMPLETION)

    marker = "Verification contract schema-critical excerpt"
    assert marker in executor_completion
    assert executor_completion.index(marker) > executor_completion.index("contract-results-schema.md")
    for token in (
        "plan_contract_ref",
        "#/contract",
        "contract_results",
        "claims",
        "deliverables",
        "acceptance_tests",
        "references",
        "forbidden_proxies",
        "uncertainty_markers",
        "completed_actions",
        "missing_actions",
        "comparison_verdicts",
        "subject_role",
    ):
        assert token in executor_completion
