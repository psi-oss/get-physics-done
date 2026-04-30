"""Phase 22 assertions for `execute-phase` ownership boundaries."""

from __future__ import annotations

import re
from pathlib import Path

from gpd.core.config import GPDProjectConfig

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


def test_execute_workflow_fallback_defaults_match_project_config_defaults() -> None:
    execute_phase = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")
    defaults = GPDProjectConfig()

    assert (
        f".max_unattended_minutes_per_plan --default {defaults.max_unattended_minutes_per_plan})"
        in execute_plan
    )
    assert f".checkpoint_after_n_tasks --default {defaults.checkpoint_after_n_tasks})" in execute_plan
    assert (
        f".max_unattended_minutes_per_plan --default {defaults.max_unattended_minutes_per_plan})"
        in execute_phase
    )
    assert (
        f".max_unattended_minutes_per_wave --default {defaults.max_unattended_minutes_per_wave})"
        in execute_phase
    )
    assert f".checkpoint_after_n_tasks --default {defaults.checkpoint_after_n_tasks})" in execute_phase


def test_autonomous_prompt_uses_supported_transition_and_discuss_contracts() -> None:
    autonomous = (WORKFLOWS_DIR / "autonomous.md").read_text(encoding="utf-8")

    assert "workflow.skip_discuss" not in autonomous
    assert "--no-transition" not in autonomous
    assert "execute-phase` owns its normal phase transition / closeout path" in autonomous
    assert "Execute-phase invoked with only the phase number" in autonomous


def test_autonomous_assigns_phase_dir_before_first_verification_status_read() -> None:
    autonomous = (WORKFLOWS_DIR / "autonomous.md").read_text(encoding="utf-8")

    assignment_index = autonomous.index('PHASE_DIR=$(echo "$PHASE_STATE" | gpd json get .phase_dir --default "")')
    first_status_read_index = autonomous.index(
        'VERIFY_STATUS=$(grep "^status:" "${PHASE_DIR}"/*-VERIFICATION.md'
    )

    assert assignment_index < first_status_read_index
