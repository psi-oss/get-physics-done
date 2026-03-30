from __future__ import annotations

from pathlib import Path

from gpd.core.recovery_advice import build_recovery_advice, serialize_recovery_orientation


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
    assert advice.decision_source == "current-workspace"
    assert advice.project_reentry_mode == "current-workspace"
    assert advice.primary_command == "gpd resume"
    assert advice.active_resume_kind == "bounded_segment"
    assert advice.active_resume_origin == "compat.current_execution"
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
            "active_resume_kind": "bounded_segment",
            "active_resume_origin": "compat.current_execution",
            "active_resume_pointer": "GPD/phases/06/.continue-here.md",
            "execution_resumable": True,
            "has_live_execution": False,
            "resume_candidates": [],
        },
    )

    assert advice.mode == "current-workspace"
    assert advice.status == "bounded-segment"
    assert advice.decision_source == "current-workspace"
    assert advice.project_reentry_mode == "current-workspace"
    assert advice.primary_command == "gpd resume"
    assert advice.current_workspace_resumable is True
    assert advice.current_workspace_has_resume_file is True
    assert advice.has_local_recovery_target is True
    assert advice.active_resume_kind == "bounded_segment"
    assert advice.active_resume_origin == "compat.current_execution"
    assert advice.active_resume_pointer == "GPD/phases/06/.continue-here.md"
    assert advice.resume_candidates_count == 0


def test_serialize_recovery_orientation_is_canonical_first_and_omits_legacy_resume_aliases(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    advice = build_recovery_advice(
        project,
        recent_rows=[],
        resume_payload={
            "resume_candidates": [
                {
                    "kind": "bounded_segment",
                    "origin": "compat.current_execution",
                    "resume_file": "GPD/phases/06/.continue-here.md",
                }
            ],
            "active_resume_kind": "bounded_segment",
            "active_resume_origin": "compat.current_execution",
            "active_resume_pointer": "GPD/phases/06/.continue-here.md",
            "execution_resumable": True,
            "has_live_execution": True,
        },
    )

    orientation = serialize_recovery_orientation(advice)

    assert list(orientation)[:10] == [
        "resume_surface_schema_version",
        "mode",
        "status",
        "decision_source",
        "primary_command",
        "primary_reason",
        "continue_command",
        "continue_reason",
        "fast_next_command",
        "fast_next_reason",
    ]
    assert orientation["active_resume_kind"] == "bounded_segment"
    assert orientation["active_resume_origin"] == "compat.current_execution"
    assert orientation["active_resume_pointer"] == "GPD/phases/06/.continue-here.md"
    assert orientation["missing_continuity_handoff"] is False
    assert orientation["resume_candidates_count"] == 1
    assert "resume_mode" not in orientation
    assert "execution_resume_file" not in orientation
    assert "execution_resume_file_source" not in orientation
    assert "has_session_resume_file" not in orientation
    assert "missing_session_resume_file" not in orientation


def test_build_recovery_advice_marks_auto_selected_recent_project_recovery(
    tmp_path: Path,
) -> None:
    workspace = _project(tmp_path)
    selected_project = _project(tmp_path, "selected")
    resume_file = selected_project / "GPD" / "phases" / "02" / ".continue-here.md"
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text("resume\n", encoding="utf-8")

    advice = build_recovery_advice(
        workspace,
        recent_rows=[
            {
                "project_root": selected_project.as_posix(),
                "available": True,
                "resumable": True,
            }
        ],
        resume_payload={
            "project_root": selected_project.as_posix(),
            "project_root_source": "recent_project",
            "project_root_auto_selected": True,
            "project_reentry_mode": "auto-recent-project",
            "segment_candidates": [
                {
                    "source": "current_execution",
                    "resume_file": "GPD/phases/02/.continue-here.md",
                    "status": "waiting",
                }
            ],
            "execution_resumable": True,
            "has_live_execution": True,
        },
    )

    assert advice.mode == "current-workspace"
    assert advice.status == "bounded-segment"
    assert advice.decision_source == "auto-selected-recent-project"
    assert advice.project_reentry_mode == "auto-recent-project"
    assert advice.project_root_auto_selected is True
    assert advice.primary_command == "gpd resume --recent"
    assert advice.project_reentry_reason == "GPD found the only recoverable recent project on this machine and selected it automatically."
    assert advice.active_resume_kind == "bounded_segment"
    assert advice.active_resume_origin == "compat.current_execution"
    assert advice.current_workspace_has_recovery is True
    assert advice.actions[0].availability == "now"
    assert advice.actions[1].availability == "now"
    assert advice.actions[2].availability == "now"


def test_build_recovery_advice_marks_auto_selected_recent_project_recovery_without_recent_rows(
    tmp_path: Path,
) -> None:
    workspace = _project(tmp_path)
    selected_project = _project(tmp_path, "selected")
    resume_file = selected_project / "GPD" / "phases" / "02" / ".continue-here.md"
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text("resume\n", encoding="utf-8")

    advice = build_recovery_advice(
        workspace,
        recent_rows=[],
        resume_payload={
            "project_root": selected_project.as_posix(),
            "project_root_source": "recent_project",
            "project_root_auto_selected": True,
            "project_reentry_mode": "auto-recent-project",
            "resume_candidates": [
                {
                    "kind": "bounded_segment",
                    "origin": "continuation.bounded_segment",
                    "status": "paused",
                    "resume_file": "GPD/phases/02/.continue-here.md",
                }
            ],
            "active_resume_pointer": "GPD/phases/02/.continue-here.md",
            "has_live_execution": False,
        },
    )

    assert advice.mode == "current-workspace"
    assert advice.status == "bounded-segment"
    assert advice.decision_source == "auto-selected-recent-project"
    assert advice.project_reentry_mode == "auto-recent-project"
    assert advice.project_root == selected_project.as_posix()
    assert advice.project_root_auto_selected is True
    assert advice.primary_command == "gpd resume --recent"
    assert advice.project_reentry_reason == "GPD found the only recoverable recent project on this machine and selected it automatically."
    assert advice.active_resume_kind == "bounded_segment"
    assert advice.active_resume_origin == "continuation.bounded_segment"
    assert advice.active_resume_pointer == "GPD/phases/02/.continue-here.md"
    assert advice.current_workspace_has_resume_file is True
    assert advice.current_workspace_resumable is True
    assert advice.recent_projects_count == 0
    assert advice.resumable_projects_count == 0
    assert advice.current_workspace_candidate_count == 1
    assert advice.has_local_recovery_target is True


def test_build_recovery_advice_uses_selected_recent_project_candidate_when_resume_surface_is_absent(
    tmp_path: Path,
) -> None:
    workspace = _project(tmp_path)
    selected_project = _project(tmp_path, "selected-candidate-only")

    advice = build_recovery_advice(
        workspace,
        recent_rows=[],
        resume_payload={
            "project_root": selected_project.as_posix(),
            "project_root_source": "recent_project",
            "project_root_auto_selected": True,
            "project_reentry_mode": "auto-recent-project",
            "project_reentry_candidates": [
                {
                    "source": "recent_project",
                    "project_root": selected_project.as_posix(),
                    "available": True,
                    "recoverable": True,
                    "resumable": True,
                    "confidence": "high",
                    "reason": "recent project cache entry with confirmed bounded segment resume target",
                    "resume_file": "GPD/phases/02/.continue-here.md",
                    "resume_target_kind": "bounded_segment",
                    "resume_target_recorded_at": "2026-03-27T11:55:00+00:00",
                    "resume_file_available": True,
                    "source_kind": "continuation.bounded_segment",
                    "source_segment_id": "segment-1",
                    "source_transition_id": "transition-1",
                    "recovery_phase": "02",
                    "recovery_plan": "01",
                    "auto_selectable": True,
                }
            ],
            "has_live_execution": False,
        },
    )

    assert advice.decision_source == "auto-selected-recent-project"
    assert advice.project_reentry_mode == "auto-recent-project"
    assert advice.primary_command == "gpd resume --recent"
    assert advice.active_resume_kind == "bounded_segment"
    assert advice.active_resume_origin == "continuation.bounded_segment"
    assert advice.current_workspace_has_resume_file is False
    assert advice.current_workspace_resumable is False
    assert advice.has_local_recovery_target is False
    assert advice.recent_projects_count == 1
    assert advice.resumable_projects_count == 1
    assert advice.available_projects_count == 1


def test_build_recovery_advice_prefers_project_reentry_selected_candidate_over_candidates_list(
    tmp_path: Path,
) -> None:
    workspace = _project(tmp_path)
    selected_project = _project(tmp_path, "selected-candidate")
    fallback_project = _project(tmp_path, "fallback-candidate")

    advice = build_recovery_advice(
        workspace,
        recent_rows=[],
        resume_payload={
            "project_root": selected_project.as_posix(),
            "project_root_source": "recent_project",
            "project_root_auto_selected": True,
            "project_reentry_mode": "auto-recent-project",
            "project_reentry_selected_candidate": {
                "source": "recent_project",
                "project_root": selected_project.as_posix(),
                "available": True,
                "recoverable": True,
                "resumable": True,
                "confidence": "high",
                "reason": "recent project cache entry with confirmed handoff resume target",
                "resume_file": "GPD/phases/04/.continue-here.md",
                "resume_target_kind": "handoff",
                "resume_target_recorded_at": "2026-03-27T12:00:00+00:00",
                "resume_file_available": True,
                "source_kind": "continuation.handoff",
                "source_segment_id": "segment-selected",
                "source_transition_id": "transition-selected",
                "recovery_phase": "04",
                "recovery_plan": "02",
                "auto_selectable": True,
            },
            "project_reentry_candidates": [
                {
                    "source": "recent_project",
                    "project_root": fallback_project.as_posix(),
                    "available": True,
                    "recoverable": True,
                    "resumable": True,
                    "confidence": "high",
                    "reason": "recent project cache entry with confirmed bounded segment resume target",
                    "resume_file": "GPD/phases/03/.continue-here.md",
                    "resume_target_kind": "bounded_segment",
                    "resume_target_recorded_at": "2026-03-27T11:55:00+00:00",
                    "resume_file_available": True,
                    "source_kind": "continuation.bounded_segment",
                    "source_segment_id": "segment-fallback",
                    "source_transition_id": "transition-fallback",
                    "recovery_phase": "03",
                    "recovery_plan": "01",
                    "auto_selectable": True,
                }
            ],
            "has_live_execution": False,
        },
    )

    assert advice.decision_source == "auto-selected-recent-project"
    assert advice.project_reentry_mode == "auto-recent-project"
    assert advice.project_root == selected_project.as_posix()
    assert advice.project_root_auto_selected is True
    assert advice.primary_command == "gpd resume --recent"
    assert advice.active_resume_kind == "continuity_handoff"
    assert advice.active_resume_origin == "continuation.handoff"
    assert advice.current_workspace_has_resume_file is False
    assert advice.current_workspace_resumable is False
    assert advice.has_local_recovery_target is False
    assert advice.recent_projects_count == 1
    assert advice.resumable_projects_count == 1
    assert advice.available_projects_count == 1


def test_build_recovery_advice_marks_ambiguous_recent_projects_as_explicit_selection(
    tmp_path: Path,
) -> None:
    workspace = _project(tmp_path)
    first = _project(tmp_path, "first")
    second = _project(tmp_path, "second")

    advice = build_recovery_advice(
        workspace,
        recent_rows=[
            {"project_root": first.as_posix(), "available": True, "resumable": True},
            {"project_root": second.as_posix(), "available": True, "resumable": True},
        ],
        resume_payload={
            "project_reentry_mode": "ambiguous-recent-projects",
            "project_reentry_requires_selection": True,
            "segment_candidates": [],
            "has_live_execution": False,
        },
    )

    assert advice.mode == "recent-projects"
    assert advice.status == "recent-projects"
    assert advice.decision_source == "ambiguous-recent-projects"
    assert advice.project_reentry_mode == "ambiguous-recent-projects"
    assert advice.project_reentry_requires_selection is True
    assert advice.primary_command == "gpd resume --recent"
    assert advice.project_reentry_reason == "GPD found 2 recoverable recent projects on this machine, so you need to choose one."
    assert advice.recent_projects_count == 2
    assert advice.actions[0].availability == "now"
    assert advice.actions[1].availability == "after_selection"
    assert advice.actions[2].availability == "after_selection"


def test_build_recovery_advice_uses_no_recovery_when_nothing_is_available(tmp_path: Path) -> None:
    workspace = _project(tmp_path)

    advice = build_recovery_advice(
        workspace,
        recent_rows=[],
        resume_payload={
            "segment_candidates": [],
            "has_live_execution": False,
        },
    )

    assert advice.mode == "idle"
    assert advice.status == "no-recovery"
    assert advice.decision_source == "no-recovery"
    assert advice.project_reentry_mode == "no-recovery"
    assert advice.primary_command is None
    assert advice.continue_command is None
    assert advice.fast_next_command is None
    assert advice.actions == []


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
    assert advice.decision_source == "current-workspace"
    assert advice.primary_command == "gpd resume"
    assert advice.missing_continuity_handoff is True
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
    assert advice.decision_source == "current-workspace"
    assert advice.primary_command == "gpd resume"
    assert advice.current_workspace_has_recovery is True
    assert advice.current_workspace_resumable is False
    assert advice.has_interrupted_agent is True


def test_build_recovery_advice_prefers_continuity_handoff_over_advisory_live_execution(tmp_path: Path) -> None:
    project = _project(tmp_path)
    handoff = project / "GPD" / "phases" / "07" / ".continue-here.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text("resume\n", encoding="utf-8")

    advice = build_recovery_advice(
        project,
        recent_rows=[{"project_root": "/tmp/other", "available": True, "resumable": True}],
        resume_payload={
            "has_live_execution": True,
            "active_resume_kind": "continuity_handoff",
            "active_resume_origin": "continuation.handoff",
            "active_resume_pointer": "GPD/phases/07/.continue-here.md",
            "continuity_handoff_file": "GPD/phases/07/.continue-here.md",
            "recorded_continuity_handoff_file": "GPD/phases/07/.continue-here.md",
        },
    )

    assert advice.mode == "current-workspace"
    assert advice.status == "session-handoff"
    assert advice.decision_source == "current-workspace"
    assert advice.primary_command == "gpd resume"
    assert advice.active_resume_kind == "continuity_handoff"
    assert advice.active_resume_origin == "continuation.handoff"
    assert advice.current_workspace_has_resume_file is True
    assert advice.primary_reason == "Current workspace has a continuity handoff projected from canonical continuation."


def test_build_recovery_advice_prefers_canonical_continuity_fields_over_conflicting_legacy_execution_flags(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    handoff = project / "GPD" / "phases" / "09" / ".continue-here.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text("resume\n", encoding="utf-8")

    advice = build_recovery_advice(
        project,
        recent_rows=[],
        resume_payload={
            "active_resume_kind": "continuity_handoff",
            "active_resume_origin": "continuation.handoff",
            "active_resume_pointer": "GPD/phases/09/.continue-here.md",
            "continuity_handoff_file": "GPD/phases/09/.continue-here.md",
            "recorded_continuity_handoff_file": "GPD/phases/09/.continue-here.md",
            "resume_candidates": [
                {
                    "kind": "continuity_handoff",
                    "origin": "continuation.handoff",
                    "status": "handoff",
                    "resume_file": "GPD/phases/09/.continue-here.md",
                }
            ],
            "execution_resumable": True,
            "execution_resume_file": "GPD/phases/09/legacy-live.md",
            "execution_resume_file_source": "current_execution",
            "has_live_execution": True,
        },
    )

    assert advice.status == "session-handoff"
    assert advice.execution_resumable is False
    assert advice.active_resume_kind == "continuity_handoff"
    assert advice.active_resume_origin == "continuation.handoff"
    assert advice.active_resume_pointer == "GPD/phases/09/.continue-here.md"
    assert advice.continuity_handoff_file == "GPD/phases/09/.continue-here.md"
    assert advice.has_continuity_handoff is True
    assert advice.current_workspace_has_resume_file is True
    assert advice.has_local_recovery_target is True


def test_build_recovery_advice_prefers_nested_compat_resume_surface_over_legacy_top_level_aliases(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    handoff = project / "GPD" / "phases" / "10" / ".continue-here.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text("resume\n", encoding="utf-8")

    advice = build_recovery_advice(
        project,
        recent_rows=[],
        resume_payload={
            "compat_resume_surface": {
                "active_resume_kind": "continuity_handoff",
                "active_resume_origin": "continuation.handoff",
                "active_resume_pointer": "GPD/phases/10/.continue-here.md",
                "continuity_handoff_file": "GPD/phases/10/.continue-here.md",
                "recorded_continuity_handoff_file": "GPD/phases/10/.continue-here.md",
                "resume_candidates": [
                    {
                        "kind": "continuity_handoff",
                        "origin": "continuation.handoff",
                        "status": "handoff",
                        "resume_file": "GPD/phases/10/.continue-here.md",
                    }
                ],
                "execution_resumable": False,
                "execution_resume_file": "GPD/phases/10/.continue-here.md",
                "execution_resume_file_source": "session_resume_file",
                "has_live_execution": False,
            },
            "resume_mode": "bounded_segment",
            "execution_resumable": True,
            "execution_resume_file": "GPD/phases/10/legacy-live.md",
            "execution_resume_file_source": "current_execution",
            "has_live_execution": True,
        },
    )

    assert advice.status == "session-handoff"
    assert advice.active_resume_kind == "continuity_handoff"
    assert advice.active_resume_origin == "continuation.handoff"
    assert advice.active_resume_pointer == "GPD/phases/10/.continue-here.md"
    assert advice.continuity_handoff_file == "GPD/phases/10/.continue-here.md"
    assert advice.execution_resumable is False
    assert advice.current_workspace_has_resume_file is True
    assert advice.has_continuity_handoff is True


def test_build_recovery_advice_recovers_nested_resume_surface_compat_wrapper(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    handoff = project / "GPD" / "phases" / "11" / ".continue-here.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text("resume\n", encoding="utf-8")

    advice = build_recovery_advice(
        project,
        recent_rows=[],
        resume_payload={
            "compat_resume_surface": {
                "resume_surface": {
                    "execution_resume_file": "GPD/phases/11/.continue-here.md",
                    "execution_resume_file_source": "session_resume_file",
                    "segment_candidates": [
                        {
                            "kind": "continuity_handoff",
                            "origin": "compat.session_resume_file",
                            "status": "handoff",
                            "resume_file": "GPD/phases/11/.continue-here.md",
                        }
                    ],
                }
            },
            "has_live_execution": False,
        },
    )

    assert advice.status == "session-handoff"
    assert advice.active_resume_kind == "continuity_handoff"
    assert advice.active_resume_origin == "compat.session_resume_file"
    assert advice.active_resume_pointer == "GPD/phases/11/.continue-here.md"
    assert advice.has_continuity_handoff is True
    assert advice.current_workspace_has_resume_file is True


def test_build_recovery_advice_recovers_arbitrary_nested_resume_surface_wrapper(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)
    handoff = project / "GPD" / "phases" / "12" / ".continue-here.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text("resume\n", encoding="utf-8")

    advice = build_recovery_advice(
        project,
        recent_rows=[],
        resume_payload={
            "recovery": {
                "resume_surface": {
                    "execution_resume_file": "GPD/phases/12/.continue-here.md",
                    "execution_resume_file_source": "session_resume_file",
                    "segment_candidates": [
                        {
                            "source": "session_resume_file",
                            "status": "handoff",
                            "resume_file": "GPD/phases/12/.continue-here.md",
                        }
                    ],
                }
            },
            "has_live_execution": False,
        },
    )

    assert advice.status == "session-handoff"
    assert advice.active_resume_kind == "continuity_handoff"
    assert advice.active_resume_origin == "compat.session_resume_file"
    assert advice.active_resume_pointer == "GPD/phases/12/.continue-here.md"
    assert advice.has_continuity_handoff is True
    assert advice.current_workspace_has_resume_file is True


def test_build_recovery_advice_recovers_continuity_handoff_from_candidate_only_payload(tmp_path: Path) -> None:
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
    assert advice.decision_source == "current-workspace"
    assert advice.active_resume_kind == "continuity_handoff"
    assert advice.active_resume_origin == "compat.session_resume_file"
    assert advice.has_continuity_handoff is True
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
    assert advice.decision_source == "current-workspace"
    assert advice.primary_command == "gpd resume"
    assert advice.active_resume_kind == "continuity_handoff"
    assert advice.active_resume_origin == "continuation.handoff"
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
    assert advice.active_resume_kind == "continuity_handoff"
    assert advice.active_resume_origin == "continuation.handoff"
    assert advice.current_workspace_has_resume_file is False
    assert advice.has_local_recovery_target is False
    assert advice.primary_reason == "Current workspace has canonical recovery state, but the last projected handoff file is missing."


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
    assert advice.decision_source == "current-workspace"
    assert advice.primary_command == "gpd resume"
    assert advice.recent_projects_count == 1
    assert advice.machine_change_notice is not None
    assert advice.primary_reason == "Current workspace has recorded recovery state and a machine-change notice to inspect."
    assert "Rerun the installer" in advice.machine_change_notice
    assert [(action.kind, action.command, action.availability) for action in advice.actions] == [
        ("primary", "gpd resume", "now")
    ]


def test_build_recovery_advice_describes_recent_projects_that_are_not_auto_selectable(
    tmp_path: Path,
) -> None:
    workspace = _project(tmp_path)
    candidate = _project(tmp_path, "candidate")

    advice = build_recovery_advice(
        workspace,
        recent_rows=[
            {
                "project_root": candidate.as_posix(),
                "available": True,
                "resumable": False,
            }
        ],
        resume_payload={},
    )

    assert advice.mode == "recent-projects"
    assert advice.status == "recent-projects"
    assert advice.decision_source == "recent-projects"
    assert advice.primary_command == "gpd resume --recent"
    assert advice.project_reentry_reason == "GPD found recent projects on this machine, but none are ready to reopen automatically."
