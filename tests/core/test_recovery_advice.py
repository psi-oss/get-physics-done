from __future__ import annotations

from pathlib import Path

from gpd.core.recent_projects import record_recent_project
from gpd.core.recovery_advice import build_recovery_advice


def _project(tmp_path: Path, name: str = "project") -> Path:
    root = tmp_path / name
    (root / "GPD" / "observability").mkdir(parents=True, exist_ok=True)
    return root


def test_build_recovery_advice_prefers_current_workspace_recovery_state(tmp_path: Path) -> None:
    project = _project(tmp_path)

    advice = build_recovery_advice(
        project,
        recent_rows=[],
        resume_payload={
            "segment_candidates": [{"source": "current_execution", "resume_file": "GPD/phases/03/.continue-here.md"}],
            "execution_resumable": True,
            "has_live_execution": True,
        },
        continue_command="/gpd:resume-work",
        fast_next_command="/gpd:suggest-next",
    )

    assert advice.mode == "current-workspace"
    assert advice.status == "bounded-segment"
    assert advice.primary_command == "gpd resume"
    assert advice.current_workspace_has_recovery is True
    assert advice.current_workspace_resumable is True
    assert [action.availability for action in advice.actions] == ["now", "now", "now"]


def test_build_recovery_advice_uses_recent_projects_when_workspace_is_idle(tmp_path: Path) -> None:
    project = _project(tmp_path)
    other = _project(tmp_path, "other")
    resume_file = other / "GPD" / "phases" / "02" / ".continue-here.md"
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text("resume\n", encoding="utf-8")

    record_recent_project(
        other,
        session_data={
            "last_date": "2026-03-28T11:00:00+00:00",
            "stopped_at": "Phase 02",
            "resume_file": "GPD/phases/02/.continue-here.md",
        },
        store_root=tmp_path / "data",
    )

    advice = build_recovery_advice(
        project,
        data_root=tmp_path / "data",
        recent_rows=None,
        resume_payload={"segment_candidates": [], "has_live_execution": False},
    )

    assert advice.mode == "recent-projects"
    assert advice.status == "recent-projects"
    assert advice.primary_command == "gpd resume --recent"
    assert advice.recent_projects_count == 1
    assert advice.actions[0].availability == "now"
    assert advice.actions[1].availability == "after_selection"
    assert advice.actions[2].availability == "after_selection"


def test_build_recovery_advice_keeps_missing_handoff_in_current_workspace_priority(tmp_path: Path) -> None:
    project = _project(tmp_path)

    advice = build_recovery_advice(
        project,
        recent_rows=[{"project_root": "/tmp/other", "available": True, "resumable": True}],
        resume_payload={
            "segment_candidates": [
                {
                    "source": "session_resume_file",
                    "status": "missing",
                    "resume_file": "GPD/phases/04/.continue-here.md",
                }
            ],
            "missing_session_resume_file": "GPD/phases/04/.continue-here.md",
            "has_live_execution": False,
        },
    )

    assert advice.mode == "current-workspace"
    assert advice.status == "missing-handoff"
    assert advice.primary_command == "gpd resume"
    assert advice.missing_session_resume_file is True
    assert advice.recent_projects_count == 1
