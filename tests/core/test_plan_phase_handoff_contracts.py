"""Focused plan-phase spawned handoff contract assertions."""

from __future__ import annotations

from tests.core.test_spawn_contracts import (
    WORKFLOWS_DIR,
    _assert_spawn_contract,
    _find_single_task,
    _task_blocks_by_agent,
)


def test_plan_phase_planner_and_checker_handoffs_carry_inline_spawn_contracts() -> None:
    path = WORKFLOWS_DIR / "plan-phase.md"
    planner_tasks = _task_blocks_by_agent(path, "gpd-planner")
    assert len(planner_tasks) >= 2
    for task in planner_tasks:
        _assert_spawn_contract(
            task,
            ("{phase_dir}/*-PLAN.md",),
            expected_write_paths=("{phase_dir}/*-PLAN.md",),
        )
        assert "artifact_gate: orchestrator validates files_written, scope, freshness" in task.text

    checker = _find_single_task(path, "gpd-plan-checker")
    _assert_spawn_contract(checker, ())
    assert "mode: read_only" in checker.text
    assert "files_written: []" in checker.text
    assert "orchestrator reconciles IDs against FRESH_PLAN_FILES" in checker.text
