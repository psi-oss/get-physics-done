"""Phase 36 assertions for the new-project scout seam."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS_DIR = REPO_ROOT / "src" / "gpd" / "specs" / "workflows"
AGENTS_DIR = REPO_ROOT / "src" / "gpd" / "agents"


def _read_workflow(name: str) -> str:
    return (WORKFLOWS_DIR / name).read_text(encoding="utf-8")


def _read_agent(name: str) -> str:
    return (AGENTS_DIR / name).read_text(encoding="utf-8")


def test_project_researcher_uses_staged_mode_and_one_shot_checkpoint_language() -> None:
    source = _read_agent("gpd-project-researcher.md")

    assert "This is a one-shot handoff." in source
    assert "typed `gpd_return.status: checkpoint`" in source
    assert "fresh continuation" in source
    assert "Do not wait inside the same spawned run." in source
    assert "Do not query config or reread init JSON inside this agent." in source
    assert "Write only the assigned `write_scope.allowed_paths`" in source
    assert "Execute all 4 parallel research threads independently" not in source


def test_new_project_scout_returns_route_on_typed_status_and_files_written() -> None:
    workflow = _read_workflow("new-project.md")

    assert "Use the staged `research_mode` from `POST_SCOPE_INIT` for all scout handoffs." in workflow
    assert "Handle scout returns:" in workflow
    assert "Route on `gpd_return.status` and `gpd_return.files_written`." in workflow
    assert "spawn a fresh continuation" in workflow
    assert "Treat any preexisting scout file as stale unless the same path appears in the fresh return." in workflow
    assert "Do not trust runtime completion text alone." in workflow


def test_new_project_synthesizer_return_stays_typed_and_file_backed() -> None:
    workflow = _read_workflow("new-project.md")

    assert "Handle the synthesizer return:" in workflow
    assert "Route on `gpd_return.status` and `gpd_return.files_written`." in workflow
    assert (
        "If `checkpoint`, present it to the user, collect the response, and spawn a fresh continuation after the response."
        in workflow
    )
    assert "If `completed`, verify `GPD/literature/SUMMARY.md` exists and is named in the fresh return." in workflow
