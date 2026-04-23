"""Focused assertions for the execute-phase consistency-check seam."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"


def _read(name: str) -> str:
    return (WORKFLOWS_DIR / name).read_text(encoding="utf-8")


def test_execute_phase_consistency_check_uses_typed_return_and_file_gate() -> None:
    workflow = _read("execute-phase.md")

    assert "gpd-consistency-checker.md" in workflow
    assert "<spawn_contract>" in workflow
    assert "expected_artifacts:" in workflow
    assert "{phase_dir}/CONSISTENCY-CHECK.md" in workflow
    assert "Return exactly one typed `gpd_return` envelope with `status: completed | checkpoint | blocked | failed`" in workflow
    assert "Artifact gate:" in workflow
    assert "gpd_return.status: completed" in workflow
    assert "gpd_return.status: checkpoint" in workflow
    assert "gpd_return.status: blocked" in workflow
    assert "gpd_return.status: failed" in workflow
    assert 'CONSISTENCY_REPORT="${phase_dir}/CONSISTENCY-CHECK.md"' in workflow
    assert 'if [ ! -f "$CONSISTENCY_REPORT" ]; then' in workflow
    assert "consistency-check artifact missing" in workflow
    assert "Do not accept `gpd_return.status: completed` until" in workflow


def test_execute_phase_consistency_check_no_longer_routes_on_legacy_status() -> None:
    workflow = _read("execute-phase.md")

    assert "Return consistency_status with any issues found." not in workflow
    assert "Proceed without cross-phase consistency checking for this wave." not in workflow
    assert "Present issues to user with resolution options" not in workflow
    assert "Do not infer success from prose headings or untyped routing." in workflow
