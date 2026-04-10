from __future__ import annotations

import json
from pathlib import Path

from gpd.core.constants import PLANNING_DIR_NAME, PROJECT_FILENAME, ROADMAP_FILENAME, STATE_JSON_FILENAME
from gpd.core.context import init_resume
from gpd.core.project_reentry import recoverable_project_context
from gpd.core.recent_projects import record_recent_project
from gpd.core.state import default_state_dict


def _make_recoverable_project(root: Path) -> Path:
    gpd_dir = root / PLANNING_DIR_NAME
    gpd_dir.mkdir(parents=True)
    (gpd_dir / STATE_JSON_FILENAME).write_text(json.dumps(default_state_dict()), encoding="utf-8")
    (gpd_dir / ROADMAP_FILENAME).write_text("# Roadmap\n", encoding="utf-8")
    (gpd_dir / PROJECT_FILENAME).write_text("# Project\n", encoding="utf-8")
    return root


def test_init_resume_keeps_requested_workspace_availability_separate_from_auto_selected_project(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    recent_project = _make_recoverable_project(tmp_path / "recent-project")
    resume_path = recent_project / PLANNING_DIR_NAME / "phases" / "02-analysis" / ".continue-here.md"
    resume_path.parent.mkdir(parents=True, exist_ok=True)
    resume_path.write_text("resume\n", encoding="utf-8")
    data_root = tmp_path / "data"
    record_recent_project(
        recent_project,
        session_data={
            "last_date": "2026-03-29T12:00:00+00:00",
            "resume_file": f"{PLANNING_DIR_NAME}/phases/02-analysis/.continue-here.md",
        },
        store_root=data_root,
    )

    ctx = init_resume(workspace, data_root=data_root)

    assert ctx["project_reentry_selected_candidate"]["source"] == "recent_project"
    assert ctx["workspace_state_exists"] is False
    assert ctx["workspace_roadmap_exists"] is False
    assert ctx["workspace_project_exists"] is False
    assert ctx["workspace_planning_exists"] is False
    assert ctx["state_exists"] is True
    assert ctx["roadmap_exists"] is True
    assert ctx["project_exists"] is True
    assert ctx["planning_exists"] is True


def test_recoverable_project_context_treats_unreadable_state_as_non_recoverable(
    monkeypatch,
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    gpd_dir = project_root / PLANNING_DIR_NAME
    gpd_dir.mkdir(parents=True)
    (gpd_dir / STATE_JSON_FILENAME).write_text('{"position": {}}', encoding="utf-8")

    def _raise_unreadable(*args, **kwargs):
        raise PermissionError("sandbox denied lockfile creation")

    monkeypatch.setattr("gpd.core.state.peek_state_json", _raise_unreadable)

    state_exists, roadmap_exists, project_exists = recoverable_project_context(project_root)

    assert state_exists is False
    assert roadmap_exists is False
    assert project_exists is False


def test_init_resume_ignores_empty_nested_gpd_stub_when_workspace_has_real_ancestor_project(
    tmp_path: Path,
) -> None:
    project_root = _make_recoverable_project(tmp_path / "project")
    nested_workspace = project_root / "workspace" / "notes"
    (nested_workspace / PLANNING_DIR_NAME).mkdir(parents=True)

    ctx = init_resume(nested_workspace)

    assert ctx["project_root"] == str(project_root.resolve(strict=False))
    assert ctx["project_root_source"] == "current_workspace"
    assert ctx["workspace_root"] == str(nested_workspace.resolve(strict=False))
