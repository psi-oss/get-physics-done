"""Phase 16 resume/observe projection oracle.

This slice compares canonical continuity and visibility facts across the
resume, observe, and suggest surfaces for the resume-handoff and
resume-recent-noise fixture families.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core.observability import derive_execution_visibility
from gpd.core.runtime_hints import build_runtime_hint_payload
from gpd.core.suggest import suggest_next
from tests.phase16_projection_oracle_helpers import (
    HANDOFF_BUNDLE_ROOT,
    ProjectionOracleCase,
    assert_projection_records_match,
    copy_fixture_workspace,
    phase16_cases,
)


def _recent_project_noise_rows() -> list[dict[str, object]]:
    noise_path = (
        HANDOFF_BUNDLE_ROOT
        / "resume-recent-noise"
        / "mutation"
        / "machine-local"
        / "recent-projects.json"
    )
    payload = json.loads(noise_path.read_text(encoding="utf-8"))
    rows: list[dict[str, object]] = []
    for entry in payload.get("entries", []):
        if not isinstance(entry, dict):
            continue
        project_root = entry.get("path")
        if not isinstance(project_root, str) or not project_root.strip():
            continue
        rows.append(
            {
                "project_root": project_root,
                "available": False,
                "resumable": False,
            }
        )
    return rows


def _write_recent_projects_index(data_root: Path, rows: list[dict[str, object]]) -> None:
    index_path = data_root / "recent-projects" / "index.json"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(json.dumps({"rows": rows}, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _collect_projection_record(workspace_root: Path, *, data_root: Path | None = None) -> dict[str, object]:
    if data_root is not None:
        data_root.mkdir(parents=True, exist_ok=True)

    payload = build_runtime_hint_payload(
        workspace_root,
        data_root=data_root,
        include_cost=False,
        include_workflow_presets=False,
    )
    visibility = derive_execution_visibility(workspace_root)
    suggestion = suggest_next(workspace_root)

    assert payload.execution is not None
    assert visibility is not None

    orientation = payload.orientation
    execution = payload.execution
    visibility_commands = tuple(command.command for command in visibility.suggested_next_commands)
    execution_commands = tuple(
        command["command"]
        for command in execution.get("suggested_next_commands", [])
        if isinstance(command, dict) and isinstance(command.get("command"), str)
    )

    assert visibility.workspace_root == workspace_root.resolve(strict=False).as_posix()
    assert execution.get("workspace_root") == workspace_root.resolve(strict=False).as_posix()
    assert execution.get("has_live_execution") == visibility.has_live_execution
    assert execution.get("visibility_mode") == visibility.visibility_mode
    assert execution.get("visibility_note") == visibility.visibility_note
    assert execution.get("status_classification") == visibility.status_classification
    assert execution.get("assessment") == visibility.assessment
    assert execution.get("possibly_stalled") == visibility.possibly_stalled
    assert execution.get("last_updated_age_minutes") == visibility.last_updated_age_minutes
    assert execution.get("last_updated_age_label") == visibility.last_updated_age_label
    assert execution.get("review_reason") == visibility.review_reason
    assert execution.get("blocked_reason") == visibility.blocked_reason
    assert execution.get("waiting_reason") == visibility.waiting_reason
    assert execution.get("tangent_pending") == visibility.tangent_pending
    assert execution_commands == visibility_commands

    return {
        "workspace_root": workspace_root.resolve(strict=False).as_posix(),
        "project_root": orientation.get("project_root"),
        "project_root_source": orientation.get("project_root_source"),
        "project_root_auto_selected": orientation.get("project_root_auto_selected"),
        "project_reentry_mode": orientation.get("project_reentry_mode"),
        "project_reentry_requires_selection": orientation.get("project_reentry_requires_selection"),
        "decision_source": orientation.get("decision_source"),
        "status": orientation.get("status"),
        "active_resume_kind": orientation.get("active_resume_kind"),
        "active_resume_origin": orientation.get("active_resume_origin"),
        "active_resume_pointer": orientation.get("active_resume_pointer"),
        "continuity_handoff_file": orientation.get("continuity_handoff_file"),
        "recorded_continuity_handoff_file": orientation.get("recorded_continuity_handoff_file"),
        "missing_continuity_handoff_file": orientation.get("missing_continuity_handoff_file"),
        "has_continuity_handoff": orientation.get("has_continuity_handoff"),
        "missing_continuity_handoff": orientation.get("missing_continuity_handoff"),
        "current_workspace_has_resume_file": orientation.get("current_workspace_has_resume_file"),
        "current_workspace_resumable": orientation.get("current_workspace_resumable"),
        "current_workspace_candidate_count": orientation.get("current_workspace_candidate_count"),
        "has_local_recovery_target": orientation.get("has_local_recovery_target"),
        "resume_candidates_count": orientation.get("resume_candidates_count"),
        "has_live_execution": execution.get("has_live_execution"),
        "execution_resumable": orientation.get("execution_resumable"),
        "has_interrupted_agent": orientation.get("has_interrupted_agent"),
        "recent_projects_count": orientation.get("recent_projects_count"),
        "resumable_projects_count": orientation.get("resumable_projects_count"),
        "available_projects_count": orientation.get("available_projects_count"),
        "visibility_mode": execution.get("visibility_mode"),
        "visibility_note": execution.get("visibility_note"),
        "status_classification": execution.get("status_classification"),
        "assessment": execution.get("assessment"),
        "possibly_stalled": execution.get("possibly_stalled"),
        "last_updated_age_minutes": execution.get("last_updated_age_minutes"),
        "last_updated_age_label": execution.get("last_updated_age_label"),
        "review_reason": execution.get("review_reason"),
        "blocked_reason": execution.get("blocked_reason"),
        "waiting_reason": execution.get("waiting_reason"),
        "tangent_pending": execution.get("tangent_pending"),
        "observe_commands": execution_commands,
        "suggest_actions": tuple(suggestion_item.action for suggestion_item in suggestion.suggestions),
        "suggest_status": suggestion.context.status,
        "suggest_current_phase": suggestion.context.current_phase,
    }


EXPECTED_BY_CASE_KEY: dict[str, dict[str, object]] = {
    "resume-handoff/positive": {
        "status": "session-handoff",
        "active_resume_kind": "continuity_handoff",
        "active_resume_origin": "continuation.handoff",
        "active_resume_pointer": "HANDOFF.md",
        "continuity_handoff_file": "HANDOFF.md",
        "recorded_continuity_handoff_file": "HANDOFF.md",
        "missing_continuity_handoff_file": None,
        "has_continuity_handoff": True,
        "missing_continuity_handoff": False,
        "current_workspace_has_resume_file": True,
        "current_workspace_resumable": False,
        "current_workspace_candidate_count": 1,
        "has_local_recovery_target": True,
        "resume_candidates_count": 1,
        "has_live_execution": False,
        "execution_resumable": False,
        "has_interrupted_agent": False,
        "recent_projects_count": 0,
        "resumable_projects_count": 0,
        "available_projects_count": 0,
        "observe_commands": ("gpd observe sessions --last 5", "gpd progress bar"),
        "suggest_actions": ("verify-work", "discuss-phase", "set-conventions", "address-questions"),
        "suggest_status": "Planning",
        "suggest_current_phase": "02",
    },
    "resume-handoff/mutation": {
        "status": "no-recovery",
        "active_resume_kind": None,
        "active_resume_origin": None,
        "active_resume_pointer": None,
        "continuity_handoff_file": None,
        "recorded_continuity_handoff_file": None,
        "missing_continuity_handoff_file": None,
        "has_continuity_handoff": False,
        "missing_continuity_handoff": False,
        "current_workspace_has_resume_file": False,
        "current_workspace_resumable": False,
        "current_workspace_candidate_count": 0,
        "has_local_recovery_target": False,
        "resume_candidates_count": 0,
        "has_live_execution": False,
        "execution_resumable": False,
        "has_interrupted_agent": False,
        "recent_projects_count": 0,
        "resumable_projects_count": 0,
        "available_projects_count": 0,
        "observe_commands": ("gpd observe sessions --last 5", "gpd progress bar"),
        "suggest_actions": ("verify-work", "discuss-phase", "set-conventions", "address-questions"),
        "suggest_status": "Planning",
        "suggest_current_phase": "02",
    },
    "resume-recent-noise/positive": {
        "status": "session-handoff",
        "active_resume_kind": "continuity_handoff",
        "active_resume_origin": "continuation.handoff",
        "active_resume_pointer": "HANDOFF.md",
        "continuity_handoff_file": "HANDOFF.md",
        "recorded_continuity_handoff_file": "HANDOFF.md",
        "missing_continuity_handoff_file": None,
        "has_continuity_handoff": True,
        "missing_continuity_handoff": False,
        "current_workspace_has_resume_file": True,
        "current_workspace_resumable": False,
        "current_workspace_candidate_count": 1,
        "has_local_recovery_target": True,
        "resume_candidates_count": 1,
        "has_live_execution": False,
        "execution_resumable": False,
        "has_interrupted_agent": False,
        "recent_projects_count": 0,
        "resumable_projects_count": 0,
        "available_projects_count": 0,
        "observe_commands": ("gpd observe sessions --last 5", "gpd progress bar"),
        "suggest_actions": ("execute-phase", "verify-results", "set-conventions", "address-questions"),
        "suggest_status": "Ready to execute",
        "suggest_current_phase": "01",
    },
    "resume-recent-noise/mutation": {
        "status": "session-handoff",
        "active_resume_kind": "continuity_handoff",
        "active_resume_origin": "continuation.handoff",
        "active_resume_pointer": "HANDOFF.md",
        "continuity_handoff_file": "HANDOFF.md",
        "recorded_continuity_handoff_file": "HANDOFF.md",
        "missing_continuity_handoff_file": None,
        "has_continuity_handoff": True,
        "missing_continuity_handoff": False,
        "current_workspace_has_resume_file": True,
        "current_workspace_resumable": False,
        "current_workspace_candidate_count": 1,
        "has_local_recovery_target": True,
        "resume_candidates_count": 1,
        "has_live_execution": False,
        "execution_resumable": False,
        "has_interrupted_agent": False,
        "recent_projects_count": 3,
        "resumable_projects_count": 0,
        "available_projects_count": 0,
        "observe_commands": ("gpd observe sessions --last 5", "gpd progress bar"),
        "suggest_actions": ("execute-phase", "verify-results", "set-conventions", "address-questions"),
        "suggest_status": "Ready to execute",
        "suggest_current_phase": "01",
    },
}


@pytest.mark.parametrize("case", phase16_cases(family="resume-observe"), ids=lambda case: case.case_key)
def test_resume_observe_projection_oracle(
    tmp_path: Path,
    case: ProjectionOracleCase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    workspace_root = copy_fixture_workspace(tmp_path, case.fixture_slug, case.variant)
    data_root = tmp_path / f"{case.fixture_slug}-{case.variant}" / "data"

    if case.case_key == "resume-recent-noise/mutation":
        _write_recent_projects_index(data_root, _recent_project_noise_rows())

    monkeypatch.setenv("GPD_DATA_DIR", str(data_root))

    record = _collect_projection_record(workspace_root, data_root=data_root)
    expected = {
        "workspace_root": workspace_root.resolve(strict=False).as_posix(),
        "project_root": workspace_root.resolve(strict=False).as_posix(),
        "project_root_source": "current_workspace",
        "project_root_auto_selected": False,
        "project_reentry_mode": "current-workspace",
        "project_reentry_requires_selection": False,
        "decision_source": "no-recovery" if case.case_key == "resume-handoff/mutation" else "current-workspace",
        "visibility_mode": "idle",
        "visibility_note": None,
        "status_classification": "idle",
        "assessment": "idle",
        "possibly_stalled": False,
        "last_updated_age_minutes": None,
        "last_updated_age_label": None,
        "review_reason": None,
        "blocked_reason": None,
        "waiting_reason": None,
        "tangent_pending": False,
        **EXPECTED_BY_CASE_KEY[case.case_key],
    }

    assert_projection_records_match(expected, record)
