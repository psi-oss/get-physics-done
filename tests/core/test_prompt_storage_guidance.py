from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"


def test_compare_branches_uses_in_memory_branch_summary_extraction() -> None:
    workflow_text = (WORKFLOWS_DIR / "compare-branches.md").read_text(encoding="utf-8")

    assert "Prefer parsing the `git show` output directly in memory." in workflow_text
    assert "do not write it to `.gpd/tmp/` just to run a path-based extractor." in workflow_text
    assert "Keep branch-summary extraction in memory/stdout only" in workflow_text
    assert "do not use `.gpd/tmp/`, `/tmp`, or another temp root for this step." in workflow_text
