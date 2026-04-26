from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"
EXECUTION_REFERENCES_DIR = REPO_ROOT / "src/gpd/specs/references/execution"


def test_execute_plan_routes_checkpoints_through_orchestrator_owned_returns() -> None:
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")
    checkpoints = (EXECUTION_REFERENCES_DIR / "execute-plan-checkpoints.md").read_text(encoding="utf-8")

    assert "wait for user" not in execute_plan
    assert "wait for approval" not in execute_plan
    assert "Emit the checkpoint return with the task result and all intermediate values" in execute_plan
    assert "return structured checkpoint state to the orchestrator" in execute_plan
    assert "Awaiting (what the orchestrator must resolve before continuation)" in checkpoints
    assert "The child never waits for user approval inside the same run" in checkpoints


def test_execute_plan_clean_wave_batching_uses_typed_verification_outcome() -> None:
    execute_plan = (WORKFLOWS_DIR / "execute-plan.md").read_text(encoding="utf-8")

    assert 'verification.status="passed"' in execute_plan
    assert "verification.issue_count=0" in execute_plan
    assert "Do not parse prose such as \"failure language\" to decide batching eligibility." in execute_plan
    assert "omits the typed verification outcome" in execute_plan
    assert "verification-complete` without failure language" not in execute_plan


def test_execute_phase_requires_on_disk_artifacts_before_accepting_success() -> None:
    execute_phase = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")

    assert (
        "If the SUMMARY marks any `key-files.created` / `key-files.modified` paths as required or "
        "final-deliverable, verify those paths on disk before accepting success"
    ) in execute_phase
    assert "Verify first 2 files from `key-files.created` exist on disk" in execute_phase


def test_execute_phase_fails_closed_on_reverification_and_notation_handoffs() -> None:
    execute_phase = (WORKFLOWS_DIR / "execute-phase.md").read_text(encoding="utf-8")

    assert "Stop in a blocked state. Do not mark the phase complete or clear gap-closure state on this path." in (
        execute_phase
    )
    assert "Then verify `gpd convention check` reports `locked` or `complete`" in execute_phase
    assert "re-check any phase artifacts flagged for re-execution are still present on disk before continuing" in (
        execute_phase
    )
    assert "If the lock is still open or a flagged artifact is missing, treat the update as incomplete" in (
        execute_phase
    )
