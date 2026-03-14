from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"


def test_compare_branches_uses_project_local_transient_scratch() -> None:
    workflow_text = (WORKFLOWS_DIR / "compare-branches.md").read_text(encoding="utf-8")

    assert "Prefer parsing the `git show` output directly in memory." in workflow_text
    assert 'SCRATCH_SUMMARY=".gpd/tmp/gpd-branch-summary.md"' in workflow_text
    assert 'gpd summary-extract "${SCRATCH_SUMMARY}" --field key_results' in workflow_text
    assert 'rm -f "${SCRATCH_SUMMARY}"' in workflow_text
    assert "Do not use `/tmp` or another OS temp root for branch-summary extraction." in workflow_text
