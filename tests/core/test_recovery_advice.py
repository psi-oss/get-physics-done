from __future__ import annotations

from pathlib import Path

from gpd.core.recent_projects import list_recent_projects, record_recent_project
from gpd.core.recovery_advice import (
    build_recovery_advice,
    serialize_recovery_advice,
    serialize_recovery_orientation,
)
from gpd.core.resume_surface import RESUME_BACKEND_ONLY_FIELDS


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
            "active_resume_kind": "bounded_segment",
            "active_resume_origin": "continuation.bounded_segment",
            "active_resume_pointer": "GPD/phases/03/.continue-here.md",
            "resume_candidates": [
                {
                    "kind": "bounded_segment",
                    "origin": "continuation.bounded_segment",
                    "status": "waiting",
                    "resume_file": "GPD/phases/03/.continue-here.md",
                }
            ],
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
    assert advice.active_resume_origin == "continuation.bounded_segment"
    assert advice.current_workspace_has_recovery is True
    assert advice.current_workspace_resumable is True
    assert [action.availability for action in advice.actions] == ["now", "now", "now"]


def test_build_recovery_advice_rejects_truthy_string_bools_in_payload(tmp_path: Path) -> None:
    project = _project(tmp_path)

    advice = build_recovery_advice(
        project,
        recent_rows=[
            {
                "project_root": (tmp_path / "recent-project").as_posix(),
                "available": "false",
                "resumable": "false",
            }
        ],
        resume_payload={
            "planning_exists": True,
            "has_live_execution": "false",
            "has_interrupted_agent": "false",
            "project_root_auto_selected": "false",
            "project_reentry_requires_selection": "false",
            "resume_candidates": [],
        },
    )

    assert advice.has_live_execution is False
    assert advice.has_interrupted_agent is False
    assert advice.project_root_auto_selected is False
    assert advice.project_reentry_requires_selection is False
    assert advice.available_projects_count == 0
    assert advice.resumable_projects_count == 0


def test_build_recovery_advice_treats_canonical_bounded_segment_as_authoritative_without_live_overlay(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    advice = build_recovery_advice(
        project,
        recent_rows=[],
        resume_payload={
            "active_resume_kind": "bounded_segment",
            "active_resume_origin": "continuation.bounded_segment",
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
    assert advice.active_resume_origin == "continuation.bounded_segment"
    assert advice.active_resume_pointer == "GPD/phases/06/.continue-here.md"
    assert advice.resume_candidates_count == 0


def test_build_recovery_advice_treats_canonical_continuity_handoff_pointer_as_current_workspace_resume_file(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    advice = build_recovery_advice(
        project,
        recent_rows=[],
        resume_payload={
            "active_resume_kind": "continuity_handoff",
            "active_resume_origin": "continuation.handoff",
            "active_resume_pointer": "GPD/phases/06/.continue-here.md",
            "has_live_execution": False,
            "resume_candidates": [],
        },
    )

    assert advice.mode == "current-workspace"
    assert advice.status == "session-handoff"
    assert advice.decision_source == "current-workspace"
    assert advice.project_reentry_mode == "current-workspace"
    assert advice.active_resume_kind == "continuity_handoff"
    assert advice.active_resume_origin == "continuation.handoff"
    assert advice.active_resume_pointer == "GPD/phases/06/.continue-here.md"
    assert advice.has_continuity_handoff is True
    assert advice.current_workspace_has_recovery is True
    assert advice.current_workspace_has_resume_file is True
    assert advice.has_local_recovery_target is True


def test_build_recovery_advice_passes_data_root_to_init_resume(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project = _project(tmp_path)
    data_root = tmp_path / "data"
    captured: dict[str, object] = {}

    def _fake_init_resume(cwd: Path, *, data_root: Path | None = None):
        captured["cwd"] = cwd
        captured["data_root"] = data_root
        return {}

    monkeypatch.setattr("gpd.core.recovery_advice.init_resume", _fake_init_resume)

    build_recovery_advice(project, data_root=data_root)

    assert captured == {
        "cwd": project.resolve(strict=False),
        "data_root": data_root,
    }


def test_serialize_recovery_orientation_is_canonical_first_and_omits_internal_resume_aliases(
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
                    "origin": "continuation.bounded_segment",
                    "resume_file": "GPD/phases/06/.continue-here.md",
                }
            ],
            "active_resume_kind": "bounded_segment",
            "active_resume_origin": "continuation.bounded_segment",
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
    assert orientation["active_resume_origin"] == "continuation.bounded_segment"
    assert orientation["active_resume_pointer"] == "GPD/phases/06/.continue-here.md"
    assert orientation["missing_continuity_handoff"] is False
    assert orientation["resume_candidates_count"] == 1
    assert "resume_mode" not in orientation
    assert "execution_resume_file" not in orientation
    assert "execution_resume_file_source" not in orientation
    assert "has_handoff_resume_file" not in orientation
    assert "missing_handoff_resume_file" not in orientation


def test_serialize_recovery_advice_is_canonical_first_and_omits_internal_resume_aliases(
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
                    "origin": "continuation.bounded_segment",
                    "resume_file": "GPD/phases/06/.continue-here.md",
                }
            ],
            "active_resume_kind": "bounded_segment",
            "active_resume_origin": "continuation.bounded_segment",
            "active_resume_pointer": "GPD/phases/06/.continue-here.md",
            "execution_resumable": True,
            "has_live_execution": True,
        },
    )

    public = serialize_recovery_advice(advice)

    assert list(public)[:10] == [
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
    assert public["resume_surface_schema_version"] == 1
    assert public["active_resume_kind"] == "bounded_segment"
    assert public["active_resume_origin"] == "continuation.bounded_segment"
    assert public["active_resume_pointer"] == "GPD/phases/06/.continue-here.md"
    assert public["actions"][0]["kind"] == "primary"
    assert public["actions"][0]["command"] == "gpd resume"
    assert public["actions"][-1]["kind"] == "fast-next"
    assert "resume_surface" not in public
    for key in RESUME_BACKEND_ONLY_FIELDS:
        assert key not in public


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
            "active_resume_kind": "bounded_segment",
            "active_resume_origin": "continuation.bounded_segment",
            "active_resume_pointer": "GPD/phases/02/.continue-here.md",
            "resume_candidates": [
                {
                    "kind": "bounded_segment",
                    "origin": "continuation.bounded_segment",
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
    assert advice.active_resume_origin == "continuation.bounded_segment"
    assert advice.current_workspace_has_recovery is True
    assert advice.actions[0].availability == "now"
    assert advice.actions[1].availability == "now"
    assert advice.actions[2].availability == "now"


def test_build_recovery_advice_treats_auto_selected_recent_project_as_recent_projects_when_workspace_differs(
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
            "workspace_root": workspace.as_posix(),
            "project_root": selected_project.as_posix(),
            "project_root_source": "recent_project",
            "project_root_auto_selected": True,
            "project_reentry_mode": "auto-recent-project",
            "active_resume_kind": "bounded_segment",
            "active_resume_origin": "continuation.bounded_segment",
            "active_resume_pointer": "GPD/phases/02/.continue-here.md",
            "resume_candidates": [
                {
                    "kind": "bounded_segment",
                    "origin": "continuation.bounded_segment",
                    "resume_file": "GPD/phases/02/.continue-here.md",
                    "status": "waiting",
                }
            ],
            "execution_resumable": True,
            "has_live_execution": True,
        },
    )

    assert advice.mode == "recent-projects"
    assert advice.decision_source == "auto-selected-recent-project"
    assert advice.project_root == selected_project.as_posix()
    assert advice.workspace_root == workspace.as_posix()
    assert advice.project_root_auto_selected is True
    assert advice.project_reentry_mode == "auto-recent-project"
    assert advice.current_workspace_has_recovery is False
    assert advice.current_workspace_has_resume_file is False
    assert advice.current_workspace_resumable is False
    assert advice.current_workspace_candidate_count == 0
    assert advice.status == "bounded-segment"
    assert [action.availability for action in advice.actions] == ["now", "after_selection", "after_selection"]


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


def test_list_recent_projects_treats_non_positive_limits_as_empty(tmp_path: Path) -> None:
    project = _project(tmp_path)
    store_root = tmp_path / "recent-project-cache"
    record_recent_project(
        project,
        session_data={
            "last_date": "2026-03-27T11:55:00+00:00",
            "stopped_at": "Phase 02",
            "resume_file": "GPD/phases/02/.continue-here.md",
        },
        store_root=store_root,
    )

    assert len(list_recent_projects(store_root)) == 1
    assert list_recent_projects(store_root, last=0) == []
    assert list_recent_projects(store_root, last=-4) == []


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
            "resume_candidates": [],
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
            "resume_candidates": [],
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
            "missing_continuity_handoff_file": "GPD/phases/04/.continue-here.md",
            "has_live_execution": False,
        },
    )

    assert advice.mode == "current-workspace"
    assert advice.status == "missing-handoff"
    assert advice.decision_source == "current-workspace"
    assert advice.primary_command == "gpd resume"
    assert advice.missing_continuity_handoff is True
    assert advice.recent_projects_count == 1


def test_build_recovery_advice_prefers_resumable_bounded_segment_over_missing_handoff_advisory(tmp_path: Path) -> None:
    project = _project(tmp_path)

    advice = build_recovery_advice(
        project,
        recent_rows=[],
        resume_payload={
            "missing_continuity_handoff_file": "GPD/phases/04/.continue-here.md",
            "resume_candidates": [
                {
                    "kind": "bounded_segment",
                    "origin": "continuation.bounded_segment",
                    "status": "paused",
                    "resume_file": "GPD/phases/04/04-01-EXECUTE.md",
                }
            ],
        },
    )

    assert advice.mode == "current-workspace"
    assert advice.status == "bounded-segment"
    assert advice.active_resume_kind == "bounded_segment"
    assert advice.active_resume_origin == "continuation.bounded_segment"
    assert advice.execution_resumable is True
    assert advice.missing_continuity_handoff is True


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
    assert advice.has_local_recovery_target is False
    assert [action.kind for action in advice.actions] == ["primary"]


def test_build_recovery_advice_does_not_treat_interrupted_agent_pointer_as_resume_file(tmp_path: Path) -> None:
    project = _project(tmp_path)

    advice = build_recovery_advice(
        project,
        recent_rows=[],
        resume_payload={
            "has_interrupted_agent": True,
            "active_resume_kind": "interrupted_agent",
            "active_resume_origin": "interrupted_agent_marker",
            "active_resume_pointer": "agent-123",
            "resume_candidates": [
                {
                    "kind": "interrupted_agent",
                    "origin": "interrupted_agent_marker",
                    "status": "interrupted",
                    "agent_id": "agent-123",
                    "resume_pointer": "agent-123",
                }
            ],
        },
    )

    assert advice.status == "interrupted-agent"
    assert advice.has_interrupted_agent is True
    assert advice.current_workspace_has_recovery is True
    assert advice.current_workspace_has_resume_file is False


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


def test_build_recovery_advice_prefers_canonical_continuity_fields_over_conflicting_stale_execution_flags(
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
            "execution_resume_file": "GPD/phases/09/advisory-live.md",
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


def test_build_recovery_advice_prefers_canonical_resume_fields_over_stale_top_level_aliases(
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
            "active_resume_kind": "continuity_handoff",
            "active_resume_origin": "continuation.handoff",
            "active_resume_pointer": "GPD/phases/10/.continue-here.md",
            "continuity_handoff_file": "GPD/phases/10/.continue-here.md",
            "recorded_continuity_handoff_file": "GPD/phases/10/.continue-here.md",
            "resume_mode": "bounded_segment",
            "execution_resumable": True,
            "execution_resume_file": "GPD/phases/10/advisory-live.md",
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


def test_build_recovery_advice_ignores_nested_resume_surface_compat_wrapper(
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
            "resume_surface": {
                "execution_resume_file": "GPD/phases/11/.continue-here.md",
                "execution_resume_file_source": "handoff_resume_file",
                "segment_candidates": [
                    {
                        "kind": "continuity_handoff",
                        "origin": "handoff_resume_file",
                        "status": "handoff",
                        "resume_file": "GPD/phases/11/.continue-here.md",
                    }
                ],
            },
            "has_live_execution": False,
        },
    )

    assert advice.status == "no-recovery"
    assert advice.active_resume_kind is None
    assert advice.active_resume_origin is None
    assert advice.active_resume_pointer is None
    assert advice.has_continuity_handoff is False
    assert advice.current_workspace_has_resume_file is False


def test_build_recovery_advice_ignores_arbitrary_nested_resume_surface_wrapper(
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
                    "execution_resume_file_source": "handoff_resume_file",
                    "segment_candidates": [
                        {
                            "source": "handoff_resume_file",
                            "status": "handoff",
                            "resume_file": "GPD/phases/12/.continue-here.md",
                        }
                    ],
                }
            },
            "has_live_execution": False,
        },
    )

    assert advice.status == "no-recovery"
    assert advice.active_resume_kind is None
    assert advice.active_resume_origin is None
    assert advice.active_resume_pointer is None
    assert advice.has_continuity_handoff is False
    assert advice.current_workspace_has_resume_file is False


def test_build_recovery_advice_ignores_resume_surface_wrapper_boolean_flags_without_canonical_support(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    advice = build_recovery_advice(
        project,
        recent_rows=[],
        resume_payload={
            "resume_surface": {
                "execution_resumable": True,
                "has_interrupted_agent": True,
                "has_live_execution": True,
            },
        },
    )

    assert advice.status == "no-recovery"
    assert advice.execution_resumable is False
    assert advice.has_interrupted_agent is False
    assert advice.has_live_execution is False


def test_build_recovery_advice_keeps_internal_execution_overlay_advisory_without_resume_target(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    advice = build_recovery_advice(
        project,
        recent_rows=[],
        resume_payload={
            "resume_mode": "bounded_segment",
            "execution_resumable": True,
            "active_execution_segment": {
                "segment_id": "seg-advisory",
                "phase": "04",
                "plan": "02",
                "segment_status": "paused",
            },
            "has_live_execution": True,
        },
    )

    assert advice.mode == "current-workspace"
    assert advice.status == "live-execution"
    assert advice.active_resume_kind is None
    assert advice.active_resume_origin is None
    assert advice.active_resume_pointer is None
    assert advice.execution_resumable is False
    assert advice.current_workspace_resumable is False
    assert advice.current_workspace_has_resume_file is False
    assert advice.has_live_execution is True
    assert advice.has_local_recovery_target is False


def test_build_recovery_advice_recovers_continuity_handoff_from_candidate_only_payload(tmp_path: Path) -> None:
    project = _project(tmp_path)

    advice = build_recovery_advice(
        project,
        recent_rows=[],
        resume_payload={
            "resume_candidates": [
                {
                    "kind": "continuity_handoff",
                    "origin": "continuation.handoff",
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
    assert advice.active_resume_origin == "continuation.handoff"
    assert advice.has_continuity_handoff is True
    assert advice.current_workspace_has_resume_file is True


def test_build_recovery_advice_ignores_nested_resume_surface_wrapper_without_canonical_support(tmp_path: Path) -> None:
    project = _project(tmp_path)

    advice = build_recovery_advice(
        project,
        recent_rows=[],
        resume_payload={
            "resume_surface": {
                "segment_candidates": [
                    {
                        "source": "handoff_resume_file",
                        "status": "handoff",
                        "resume_file": "GPD/phases/05/.continue-here.md",
                    }
                ],
                "handoff_resume_file": "GPD/phases/05/.continue-here.md",
                "recorded_handoff_resume_file": "GPD/phases/05/.continue-here.md",
                "execution_resume_file": "GPD/phases/05/.continue-here.md",
            },
            "has_live_execution": False,
        },
    )

    assert advice.mode == "idle"
    assert advice.status == "no-recovery"
    assert advice.decision_source == "no-recovery"
    assert advice.active_resume_kind is None
    assert advice.active_resume_origin is None
    assert advice.active_resume_pointer is None
    assert advice.continuity_handoff_file is None
    assert advice.has_continuity_handoff is False
    assert advice.current_workspace_has_resume_file is False


def test_build_recovery_advice_ignores_top_level_internal_segment_candidates_without_canonical_support(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    advice = build_recovery_advice(
        project,
        recent_rows=[],
        resume_payload={
            "segment_candidates": [
                {
                    "source": "handoff_resume_file",
                    "status": "handoff",
                    "resume_file": "GPD/phases/05/.continue-here.md",
                }
            ]
        },
    )

    assert advice.mode == "idle"
    assert advice.status == "no-recovery"
    assert advice.decision_source == "no-recovery"
    assert advice.has_continuity_handoff is False
    assert advice.current_workspace_has_resume_file is False


def test_build_recovery_advice_ignores_top_level_internal_handoff_aliases_without_canonical_support(tmp_path: Path) -> None:
    project = _project(tmp_path)

    advice = build_recovery_advice(
        project,
        recent_rows=[],
        resume_payload={
            "resume_mode": "continuity_handoff",
            "execution_resume_file": "GPD/phases/05/.continue-here.md",
            "execution_resume_file_source": "handoff_resume_file",
            "handoff_resume_file": "GPD/phases/05/.continue-here.md",
            "recorded_handoff_resume_file": "GPD/phases/05/.continue-here.md",
            "has_live_execution": False,
        },
    )

    assert advice.mode == "idle"
    assert advice.status == "no-recovery"
    assert advice.decision_source == "no-recovery"
    assert advice.active_resume_kind is None
    assert advice.active_resume_origin is None
    assert advice.active_resume_pointer is None
    assert advice.continuity_handoff_file is None
    assert advice.current_workspace_has_resume_file is False
    assert advice.execution_resumable is False
    assert advice.has_local_recovery_target is False


def test_build_recovery_advice_ignores_top_level_internal_missing_handoff_alias_without_canonical_support(
    tmp_path: Path,
) -> None:
    project = _project(tmp_path)

    advice = build_recovery_advice(
        project,
        recent_rows=[],
        resume_payload={
            "missing_handoff_resume_file": "GPD/phases/06/.continue-here.md",
        },
    )

    assert advice.mode == "idle"
    assert advice.status == "no-recovery"
    assert advice.decision_source == "no-recovery"
    assert advice.missing_continuity_handoff is False
    assert advice.current_workspace_has_recovery is False


def test_build_recovery_advice_keeps_missing_handoff_without_false_resume_file(tmp_path: Path) -> None:
    project = _project(tmp_path)

    advice = build_recovery_advice(
        project,
        recent_rows=[],
        resume_payload={
            "missing_continuity_handoff_file": "GPD/phases/06/.continue-here.md",
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
            "missing_continuity_handoff_file": "GPD/phases/08/.continue-here.md",
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

    assert advice.mode == "recent-projects"
    assert advice.status == "recent-projects"
    assert advice.decision_source == "recent-projects"
    assert advice.primary_command == "gpd resume --recent"
    assert advice.recent_projects_count == 1
    assert advice.machine_change_notice is not None
    assert advice.primary_reason == "GPD found recent projects on this machine, but none are selected automatically."
    assert "Rerun the installer" in advice.machine_change_notice
    assert [(action.kind, action.availability) for action in advice.actions] == [
        ("primary", "now"),
        ("continue", "after_selection"),
        ("fast-next", "after_selection"),
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


def test_build_recovery_advice_force_recent_prefers_explicit_recent_rows_over_workspace_payload(
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
                "resumable": True,
                "resume_file": "GPD/phases/02/.continue-here.md",
            }
        ],
        resume_payload={
            "workspace_root": workspace.as_posix(),
            "project_root": workspace.as_posix(),
            "project_root_source": "current_workspace",
            "project_reentry_mode": "current-workspace",
            "project_reentry_candidates": [
                {
                    "source": "current_workspace",
                    "project_root": workspace.as_posix(),
                    "available": True,
                    "recoverable": True,
                }
            ],
        },
        force_recent=True,
    )

    assert advice.mode == "recent-projects"
    assert advice.status == "recent-projects"
    assert advice.decision_source == "forced-recent-projects"
    assert advice.primary_command == "gpd resume --recent"
    assert advice.recent_projects_count == 1
    assert advice.continue_command == "runtime `resume-work`"
    assert advice.fast_next_command == "runtime `suggest-next`"


def test_build_recovery_advice_does_not_backfill_recent_candidate_for_explicit_current_workspace(
    tmp_path: Path,
) -> None:
    workspace = _project(tmp_path)

    advice = build_recovery_advice(
        workspace,
        recent_rows=[
            {
                "project_root": workspace.as_posix(),
                "available": True,
                "resumable": False,
                "resume_file": "GPD/phases/04/.continue-here.md",
                "resume_file_available": False,
                "resume_target_kind": "handoff",
                "source": "recent_project",
            }
        ],
        resume_payload={
            "workspace_root": workspace.as_posix(),
            "project_root": workspace.as_posix(),
            "project_root_source": "current_workspace",
            "project_reentry_mode": "current-workspace",
            "project_reentry_candidates": [
                {
                    "source": "recent_project",
                    "project_root": workspace.as_posix(),
                    "available": True,
                    "recoverable": False,
                    "resumable": False,
                    "resume_file": "GPD/phases/04/.continue-here.md",
                    "resume_file_available": False,
                    "resume_target_kind": "handoff",
                }
            ],
            "resume_candidates": [],
            "has_live_execution": False,
        },
    )

    assert advice.active_resume_kind is None
    assert advice.active_resume_origin is None
    assert advice.active_resume_pointer is None
    assert advice.has_local_recovery_target is False
    assert advice.decision_source == "recent-projects"
