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


def test_build_recovery_advice_treats_canonical_bounded_segment_as_authoritative_without_live_overlay(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    advice = build_recovery_advice(
        project,
        recent_rows=[],
        resume_payload={
            "active_execution_segment": None,
            "execution_resume_file": "GPD/phases/06/.continue-here.md",
            "execution_resume_file_source": "current_execution",
            "execution_resumable": True,
            "has_live_execution": False,
            "resume_mode": "bounded_segment",
            "segment_candidates": [],
        },
    )

    assert advice.mode == "current-workspace"
    assert advice.status == "bounded-segment"
    assert advice.primary_command == "gpd resume"
    assert advice.current_workspace_resumable is True
    assert advice.current_workspace_has_resume_file is True
    assert advice.has_local_recovery_target is True
    assert advice.execution_resume_file == "GPD/phases/06/.continue-here.md"
    assert advice.execution_resume_file_source == "current_execution"


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


def test_build_recovery_advice_keeps_interrupted_agent_in_current_workspace_mode(tmp_path: Path) -> None:
    project = _project(tmp_path)

    advice = build_recovery_advice(
        project,
        recent_rows=[{"project_root": "/tmp/other", "available": True, "resumable": True}],
        resume_payload={"has_interrupted_agent": True},
    )

    assert advice.mode == "current-workspace"
    assert advice.status == "interrupted-agent"
    assert advice.primary_command == "gpd resume"
    assert advice.current_workspace_has_recovery is True
    assert advice.current_workspace_resumable is False
    assert advice.has_interrupted_agent is True


def test_build_recovery_advice_prefers_session_handoff_over_advisory_live_execution(tmp_path: Path) -> None:
    project = _project(tmp_path)
    handoff = project / "GPD" / "phases" / "07" / ".continue-here.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text("resume\n", encoding="utf-8")

    advice = build_recovery_advice(
        project,
        recent_rows=[{"project_root": "/tmp/other", "available": True, "resumable": True}],
        resume_payload={
            "has_live_execution": True,
            "session_resume_file": "GPD/phases/07/.continue-here.md",
        },
    )

    assert advice.mode == "current-workspace"
    assert advice.status == "session-handoff"
    assert advice.primary_command == "gpd resume"
    assert advice.current_workspace_has_resume_file is True
    assert advice.primary_reason == "Current workspace has a recorded session handoff."


def test_build_recovery_advice_recovers_session_handoff_from_candidate_only_payload(tmp_path: Path) -> None:
    project = _project(tmp_path)

    advice = build_recovery_advice(
        project,
        recent_rows=[],
        resume_payload={
            "segment_candidates": [
                {
                    "source": "session_resume_file",
                    "status": "handoff",
                    "resume_file": "GPD/phases/05/.continue-here.md",
                }
            ]
        },
    )

    assert advice.mode == "current-workspace"
    assert advice.status == "session-handoff"
    assert advice.has_session_resume_file is True
    assert advice.current_workspace_has_resume_file is True


def test_build_recovery_advice_keeps_missing_handoff_without_false_resume_file(tmp_path: Path) -> None:
    project = _project(tmp_path)

    advice = build_recovery_advice(
        project,
        recent_rows=[],
        resume_payload={
            "missing_session_resume_file": "GPD/phases/06/.continue-here.md",
        },
    )

    assert advice.mode == "current-workspace"
    assert advice.status == "missing-handoff"
    assert advice.primary_command == "gpd resume"
    assert advice.current_workspace_has_recovery is True
    assert advice.current_workspace_has_resume_file is False
    assert advice.has_local_recovery_target is False


def test_build_recovery_advice_prefers_missing_handoff_over_advisory_live_execution(tmp_path: Path) -> None:
    project = _project(tmp_path)

    advice = build_recovery_advice(
        project,
        recent_rows=[],
        resume_payload={
            "has_live_execution": True,
            "missing_session_resume_file": "GPD/phases/08/.continue-here.md",
        },
    )

    assert advice.mode == "current-workspace"
    assert advice.status == "missing-handoff"
    assert advice.primary_command == "gpd resume"
    assert advice.current_workspace_has_resume_file is False
    assert advice.has_local_recovery_target is False
    assert advice.primary_reason == "Current workspace has recorded recovery state, but the last handoff file is missing."


def test_build_recovery_advice_keeps_machine_change_notice_in_current_workspace_priority(tmp_path: Path) -> None:
    project = _project(tmp_path)

    advice = build_recovery_advice(
        project,
        recent_rows=[{"project_root": "/tmp/other", "available": True, "resumable": True}],
        resume_payload={
            "machine_change_notice": (
                "Machine change detected: last active on old-host (Linux 5.15 x86_64); "
                "current machine new-host (Linux 6.1 x86_64). "
                "The project state is portable and does not require repair. "
                "Rerun the installer if runtime-local config may be stale on this machine."
            ),
            "has_live_execution": False,
        },
    )

    assert advice.mode == "current-workspace"
    assert advice.status == "workspace-recovery"
    assert advice.primary_command == "gpd resume"
    assert advice.recent_projects_count == 1
    assert advice.machine_change_notice is not None
    assert advice.primary_reason == "Current workspace has recorded recovery state and a machine-change notice to inspect."
    assert "Rerun the installer" in advice.machine_change_notice
    assert [(action.kind, action.command, action.availability) for action in advice.actions] == [
        ("primary", "gpd resume", "now")
    ]
