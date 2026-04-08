"""Phase 22 regressions for `execute-phase` ownership boundaries."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"


def test_execute_phase_has_no_commented_pre_execution_specialist_task_spawns() -> None:
    workflow_text = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")

    commented_task_lines = re.findall(
        r"(?m)^\s*#\s*task\(subagent_type=\"gpd-(notation-coordinator|experiment-designer)\"",
        workflow_text,
    )

    assert commented_task_lines == []


def test_execute_phase_still_owns_wave_risk_and_artifact_gate_routing() -> None:
    workflow_text = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")

    assert "probe_then_fanout" in workflow_text
    assert "artifact gate" in workflow_text.lower()
    assert "fanout" in workflow_text.lower()


def test_execute_phase_explicitly_defers_plan_local_semantics_to_execute_plan() -> None:
    workflow_text = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")
    execute_plan_text = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")

    assert "execute-plan.md owns plan-local execution semantics" in workflow_text
    assert "autonomy` changes who is asked and when" in execute_plan_text
    assert "first-result" in execute_plan_text
    assert "pre-fanout" in execute_plan_text
