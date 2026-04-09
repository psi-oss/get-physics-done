"""Workflow seam regressions for the research-synthesizer vertical."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_new_project_synthesizer_seam_routes_on_typed_returns_and_rejects_stale_summary_files() -> None:
    workflow = _read(WORKFLOWS_DIR / "new-project.md")

    assert "After all 4 scout artifacts are present on disk and each fresh `gpd_return.files_written` proves its expected artifact, spawn synthesizer to create SUMMARY.md:" in workflow
    assert "<research_files>" in workflow
    assert "- GPD/PROJECT.md" in workflow
    assert "- GPD/config.json" in workflow
    assert "- GPD/literature/SUMMARY.md (if re-synthesizing an existing survey)" in workflow
    assert "Handle the synthesizer return:" in workflow
    assert "Route on the full canonical `gpd_return` envelope (`status`, `files_written`, `issues`, and `next_actions`)" in workflow
    assert "`GPD/literature/SUMMARY.md` is freshly named in `gpd_return.files_written`" in workflow
    assert "If `checkpoint`, present it to the user, collect the response, and spawn a fresh continuation after the response." in workflow
    assert "If `blocked`, surface the blocker and stop this synth path until it is resolved." in workflow
    assert "If `failed`, surface the failure and retry once." in workflow
    assert "If the synthesizer agent fails to spawn or returns an error:" in workflow
    assert "Treat any preexisting `GPD/literature/SUMMARY.md` as stale." in workflow
    assert "If the summary artifact is still missing, or the retry does not produce a fresh typed return naming it, STOP and surface the blocker." in workflow
    assert "Do not trust the runtime handoff status by itself." in workflow


def test_new_milestone_synthesizer_seam_keeps_child_contract_visible_and_task_local() -> None:
    workflow = _read(WORKFLOWS_DIR / "new-milestone.md")

    assert "This is a one-shot handoff. Return a typed `gpd_return` envelope with `status` and `files_written`." in workflow
    assert "Treat each scout as a one-shot handoff: if it needs user input, it must return `status: checkpoint` and stop, not wait in place." in workflow
    assert "Treat `gpd_return.status` and `gpd_return.files_written` as the only freshness signal for a scout result." in workflow
    assert "After all 4 complete and required artifacts are present, spawn synthesizer:" in workflow
    assert "task(prompt=\"First, read {GPD_AGENTS_DIR}/gpd-research-synthesizer.md for your role and instructions." in workflow
    assert "<files_to_read>" in workflow
    assert "- GPD/literature/PRIOR-WORK.md" in workflow
    assert "- GPD/literature/METHODS.md" in workflow
    assert "- GPD/literature/COMPUTATIONAL.md" in workflow
    assert "- GPD/literature/PITFALLS.md" in workflow
    assert "Write to: GPD/literature/SUMMARY.md" in workflow
    assert "Use template: {GPD_INSTALL_DIR}/templates/research-project/SUMMARY.md" in workflow
    assert "<spawn_contract>" in workflow
    assert "allowed_paths:" in workflow
    assert "    - GPD/literature/SUMMARY.md" in workflow
    assert "shared_state_policy: return_only" in workflow
    assert "This synthesizer contract is task-local. Do not reuse survey write scopes or widen the summary handoff." in workflow
    assert "If the synthesizer agent fails to spawn or returns an error:" in workflow
    assert "Retry once if `GPD/literature/SUMMARY.md` is missing." in workflow
    assert "If `gpd_return.status: checkpoint`" in workflow
    assert "If `gpd_return.status: blocked`" in workflow
    assert "If `gpd_return.status: failed`" in workflow
    assert "Do not fabricate a fallback summary in the main context, do not infer survey conclusions from partial files, and do not display or commit from a preexisting summary without a fresh `gpd_return.files_written` proof." in workflow
    assert "If the synthesizer reports `gpd_return.status: completed`, verify that `GPD/literature/SUMMARY.md` is readable and named in `gpd_return.files_written`." in workflow
    assert "Do not create SUMMARY.md in the main context from partial scout output or from a stale summary that was not named in the fresh return." in workflow
