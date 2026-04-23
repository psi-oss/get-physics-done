"""Focused assertions for quick workflow typed return routing."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
QUICK_WORKFLOW = REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "quick.md"


def test_quick_workflow_routes_on_typed_gpd_return_and_applies_child_returns() -> None:
    workflow = QUICK_WORKFLOW.read_text(encoding="utf-8")

    assert "gpd_return.status: checkpoint" in workflow
    assert "gpd_return.status: completed" in workflow
    assert "gpd_return.status: blocked" in workflow
    assert "gpd_return.status: failed" in workflow
    assert "gpd_return.files_written" in workflow
    assert "staged planner loading" in workflow
    assert "tool_requirements" in workflow
    assert "gpd validate plan-preflight" in workflow
    assert "gpd apply-return-updates" in workflow
    assert "The `## CHECKPOINT REACHED` heading is presentation only." in workflow
    assert "The `## PLANNING COMPLETE` heading is presentation only." in workflow
    assert "Route on `gpd_return.status` and the artifact gate, not on the human-readable headings" in workflow
