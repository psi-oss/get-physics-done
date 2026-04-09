"""Regression tests for respond-to-referees handoff and artifact-gate semantics."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / "src" / "gpd" / "specs" / "workflows" / "respond-to-referees.md"


def test_respond_to_referees_group_b_completion_requires_fresh_child_files_written_and_rejects_stale_edits() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert "If you need user input, return `status: checkpoint` and stop; do not wait inside this run." in source
    assert (
        "Return only after the fresh `gpd_return.files_written` set names the revised section file plus `GPD/AUTHOR-RESPONSE{round_suffix}.md` and `GPD/review/REFEREE_RESPONSE{round_suffix}.md`; stale pre-existing edits do not count."
        in source
    )
    assert (
        "Check the fresh child `gpd_return.files_written` first; the section is complete only when it names the revised section file plus both response artifacts."
        in source
    )
    assert "If the section file changed but the response trackers did not, or vice versa, treat that section as failed" in source


def test_respond_to_referees_response_letter_generation_stays_file_backed_and_fresh_return_based() -> None:
    source = WORKFLOW.read_text(encoding="utf-8")

    assert (
        "Treat those files as complete only if the expected mirrored artifacts exist on disk and the orchestrator has aggregated every section handoff: the revised section file exists, both response artifacts exist, and the fresh child `gpd_return.files_written` for that section names all required outputs."
        in source
    )
    assert "Do not rely on stale pre-existing edits or prose completion alone." in source
