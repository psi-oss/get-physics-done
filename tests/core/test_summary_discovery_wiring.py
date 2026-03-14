from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src/gpd/specs/workflows"


def test_peer_review_surfaces_legacy_and_plan_scoped_summary_artifacts() -> None:
    workflow_text = (WORKFLOWS_DIR / "peer-review.md").read_text(encoding="utf-8")

    assert ".gpd/phases/*/SUMMARY.md" in workflow_text
    assert ".gpd/phases/*/*-SUMMARY.md" in workflow_text


def test_regression_check_searches_legacy_and_plan_scoped_summary_artifacts() -> None:
    workflow_text = (WORKFLOWS_DIR / "regression-check.md").read_text(encoding="utf-8")

    assert '-name "SUMMARY.md"' in workflow_text
    assert '-name "*-SUMMARY.md"' in workflow_text


def test_verify_work_searches_legacy_and_plan_scoped_summary_artifacts() -> None:
    workflow_text = (WORKFLOWS_DIR / "verify-work.md").read_text(encoding="utf-8")

    assert 'ls "$phase_dir"/SUMMARY.md "$phase_dir"/*-SUMMARY.md 2>/dev/null' in workflow_text
    assert "ls .gpd/phases/*/SUMMARY.md .gpd/phases/*/*-SUMMARY.md 2>/dev/null | sort" in workflow_text
