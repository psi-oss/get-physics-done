"""Workflow seam assertions for the project-researcher vertical."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_new_project_project_researcher_scouts_route_on_typed_return_and_reject_stale_results() -> None:
    workflow = _read(WORKFLOWS_DIR / "new-project.md")

    assert workflow.count('subagent_type="gpd-project-researcher"') == 4
    assert "Route on `gpd_return.status` and `gpd_return.files_written`." in workflow
    assert "If `checkpoint`, present it to the user, collect the response, and spawn a fresh continuation; do not keep the original scout alive." in workflow
    assert "If `completed`, verify the expected artifact exists on disk and is named in the fresh `gpd_return.files_written`." in workflow
    assert "Treat any preexisting scout file as stale unless the same path appears in the fresh return." in workflow
    assert "Do not trust runtime completion text alone." in workflow
    assert "If a scout reports success but its `expected_artifacts` entry (`GPD/literature/{FILE}`) is missing, treat that scout as incomplete." in workflow


def test_new_milestone_project_researcher_scouts_require_fresh_continuations_and_stale_file_rejection() -> None:
    workflow = _read(WORKFLOWS_DIR / "new-milestone.md")

    assert workflow.count("Common structure for all 4 scouts:") == 1
    assert "This is a one-shot handoff. Return a typed `gpd_return` envelope with `status` and `files_written`." in workflow
    assert "Route on `gpd_return.status` and `gpd_return.files_written`, not on the human-readable handoff text." in workflow
    assert "Treat each scout as a one-shot handoff: if it needs user input, it must return `status: checkpoint` and stop, not wait in place." in workflow
    assert "Treat `gpd_return.status` and `gpd_return.files_written` as the only freshness signal for a scout result." in workflow
    assert "Before trusting the scout handoff, route on `gpd_return.status` and `gpd_return.files_written`, then re-read the expected output files from disk and count only artifacts that actually exist. Do not trust the runtime handoff status by itself." in workflow
    assert "present the checkpoint, collect the user's input, and spawn a fresh continuation for the same scout dimension." in workflow
    assert "Do not let the original scout run continue after the checkpoint." in workflow
    assert "If the artifact is still missing, stop the survey path. Do not substitute main-context research for the missing scout and do not continue with a partial survey." in workflow
    assert "If any research agent fails to spawn or returns an error:" in workflow
