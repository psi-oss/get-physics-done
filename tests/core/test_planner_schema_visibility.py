"""Regression tests for explicit planner schema visibility."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
PLANNER_ROLE = REPO_ROOT / "src" / "gpd" / "agents" / "gpd-planner.md"
PLAN_PHASE = REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "plan-phase.md"
VERIFY_WORK = REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "verify-work.md"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_planner_role_and_workflows_explicitly_require_phase_prompt_and_plan_contract_schema() -> None:
    planner_role = _read(PLANNER_ROLE)
    plan_phase = _read(PLAN_PHASE)
    verify_work = _read(VERIFY_WORK)

    required_markers = (
        "{GPD_INSTALL_DIR}/templates/phase-prompt.md",
        "{GPD_INSTALL_DIR}/templates/plan-contract-schema.md",
    )

    for marker in required_markers:
        assert marker in planner_role
        assert marker in plan_phase
        assert marker in verify_work

    assert "Do not rely on nested include expansion" in planner_role
    direct_instruction = (
        "First, read {GPD_AGENTS_DIR}/gpd-planner.md, {GPD_INSTALL_DIR}/templates/phase-prompt.md, "
        "and {GPD_INSTALL_DIR}/templates/plan-contract-schema.md for your role and instructions."
    )
    assert plan_phase.count(direct_instruction) == 2
    assert verify_work.count(direct_instruction) == 2
