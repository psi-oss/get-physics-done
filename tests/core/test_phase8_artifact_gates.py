"""Focused assertions for Phase 8 artifact gate hardening."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"


def _read(name: str) -> str:
    return (WORKFLOWS_DIR / name).read_text(encoding="utf-8")


def test_plan_phase_requires_plan_artifacts_before_accepting_success() -> None:
    plan_phase = _read("plan-phase.md")

    assert "Runtime delegation rule: this is a one-shot handoff." in plan_phase
    assert "Accept only after `gpd_return.files_written` names at least one fresh, readable `${PHASE_DIR}/*-PLAN.md`" in plan_phase
    assert "do not trust return text or preexisting files alone" in plan_phase
    assert 'gpd validate handoff-artifacts - "${HANDOFF_ARTIFACT_ARGS[@]}"' in plan_phase
    assert 'gpd validate plan-contract "$plan_file"' in plan_phase


def test_verify_work_rechecks_proof_redteam_artifact_after_repair() -> None:
    verify_work = _read("verify-work.md")

    assert "After the proof critic returns, re-open `${PHASE_DIR_ABS}/${phase_number}-PROOF-REDTEAM.md` from disk" in verify_work
    assert "confirm the artifact exists and is `passed` before finalizing the gap ledger" in verify_work
    assert "start a fresh proof continuation" in verify_work


def test_validate_conventions_requires_artifact_and_lock_before_success() -> None:
    validate_conventions = _read("validate-conventions.md")

    assert "Runtime delegation rule: this is a one-shot handoff." in validate_conventions
    assert "gpd_return.status: completed" in validate_conventions
    assert "gpd_return.files_written" in validate_conventions
    assert "expected artifact exists on disk" in validate_conventions
    assert "Verify that `GPD/CONVENTIONS.md` exists and that `gpd convention list` reflects the resolved fields before accepting the update." in validate_conventions
    assert "Convention artifact and lock re-verified after notation resolution before success is accepted" in validate_conventions
    assert "Present options, checkpoint, and return." in validate_conventions
