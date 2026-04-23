"""Focused assertions for the quick command wrapper contract."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
QUICK_COMMAND = REPO_ROOT / "src" / "gpd" / "commands" / "quick.md"


def test_quick_command_wrapper_surfaces_staged_handoff_and_preserves_workflow_gates() -> None:
    command = QUICK_COMMAND.read_text(encoding="utf-8")

    assert "workflow owns the staged quick planner handoff" in command
    assert "staged planner loading" in command
    assert "Preserve all workflow gates (validation, task description, staged planner loading, planning, execution, preflight, state updates, commits)." in command
