from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from gpd.adapters import get_adapter, list_runtimes
from gpd.adapters.runtime_catalog import get_runtime_descriptor
from gpd.core.constants import ENV_GPD_ACTIVE_RUNTIME, ProjectLayout
from gpd.core.costs import UsageRecord, _profile_tier_mix, usage_ledger_path
from gpd.core.recent_projects import record_recent_project
from gpd.core.resume_surface import RESUME_COMPATIBILITY_ALIAS_FIELDS
from gpd.core.runtime_command_surfaces import format_active_runtime_command
from gpd.core.runtime_hints import (
    _hydrate_resume_context_from_recent_project,
    build_runtime_hint_payload,
    workflow_preset_surface_note,
)
from gpd.core.surface_phrases import (
    cost_inspect_action,
    recovery_continue_reason,
    recovery_fast_next_reason,
)
from tests.latex_test_support import latex_capability_payload as _latex_capability
from tests.runtime_install_helpers import seed_complete_runtime_install

_TEST_RUNTIME = "runtime-under-test"
_TEST_MODEL = "model-under-test"
_RUNTIME_NAMES = tuple(list_runtimes())
_SUPPORTED_RUNTIME_DESCRIPTORS = tuple(get_runtime_descriptor(runtime) for runtime in _RUNTIME_NAMES)
_RUNTIME_WITH_ALIAS_AND_DISPLAY_NAME = next(
    (
        descriptor
        for descriptor in _SUPPORTED_RUNTIME_DESCRIPTORS
        if descriptor.display_name.casefold() != descriptor.runtime_name.casefold()
        and any(alias.casefold() != descriptor.runtime_name.casefold() for alias in descriptor.selection_aliases)
    ),
    _SUPPORTED_RUNTIME_DESCRIPTORS[0],
)
_RUNTIME_ENV_VARS_TO_CLEAR = {
    ENV_GPD_ACTIVE_RUNTIME,
    *(
        env_var
        for descriptor in _SUPPORTED_RUNTIME_DESCRIPTORS
        for env_var in (
            *descriptor.activation_env_vars,
            descriptor.global_config.env_var,
            descriptor.global_config.env_dir_var,
            descriptor.global_config.env_file_var,
            "XDG_CONFIG_HOME" if descriptor.global_config.strategy == "xdg_app" else None,
        )
        if env_var
    ),
}


class _ExecutionSnapshot(SimpleNamespace):
    def model_dump(self, mode: str = "json") -> dict[str, object]:
        return dict(self.__dict__)

    def __getattr__(self, name: str) -> object:
        return None


@pytest.fixture(autouse=True)
def _isolate_runtime_detection(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep runtime-hints tests independent from host runtime installs."""
    for key in _RUNTIME_ENV_VARS_TO_CLEAR:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("gpd.hooks.runtime_detect.Path.home", lambda: tmp_path / "home")


def _bootstrap_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "GPD" / "observability").mkdir(parents=True, exist_ok=True)
    return project


def _bootstrap_recoverable_project(tmp_path: Path) -> Path:
    project = _bootstrap_project(tmp_path)
    (project / "GPD" / "STATE.md").write_text("# Research State\n", encoding="utf-8")
    (project / "GPD" / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
    (project / "GPD" / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
    return project


def _write_state_intent_recovery_files(project: Path) -> ProjectLayout:
    from gpd.core.state import default_state_dict

    layout = ProjectLayout(project)
    layout.state_json.parent.mkdir(parents=True, exist_ok=True)
    layout.state_json.write_text(json.dumps(default_state_dict(), indent=2) + "\n", encoding="utf-8")

    recovered_state = default_state_dict()
    recovered_state["position"]["current_phase"] = "05"
    recovered_state["position"]["status"] = "Executing"
    json_tmp = layout.gpd / ".state-json-tmp"
    md_tmp = layout.gpd / ".state-md-tmp"
    json_tmp.write_text(json.dumps(recovered_state, indent=2) + "\n", encoding="utf-8")
    md_tmp.write_text("# Recovered State\n", encoding="utf-8")
    layout.state_intent.write_text(f"{json_tmp}\n{md_tmp}\n", encoding="utf-8")
    return layout


def _write_current_session(project: Path, *, session_id: str) -> None:
    current_session_path = project / "GPD" / "observability" / "current-session.json"
    current_session_path.write_text(
        json.dumps(
            {
                "session_id": session_id,
                "started_at": "2026-03-27T12:00:00+00:00",
                "last_event_at": "2026-03-27T12:01:00+00:00",
                "cwd": project.as_posix(),
                "source": "cli",
                "status": "active",
            }
        ),
        encoding="utf-8",
    )


def _write_current_execution(project: Path, *, session_id: str, extra_execution: dict[str, object] | None = None) -> None:
    execution_path = project / "GPD" / "observability" / "current-execution.json"
    payload = {
        "session_id": session_id,
        "workflow": "execute-phase",
        "phase": "03",
        "plan": "01",
        "segment_status": "waiting_review",
        "current_task": "Assemble benchmark",
        "current_task_index": 2,
        "current_task_total": 5,
        "waiting_for_review": True,
        "review_required": True,
        "checkpoint_reason": "first_result",
        "waiting_reason": "first_result_review_required",
        "resume_file": "GPD/phases/03/.continue-here.md",
        "updated_at": "2000-01-01T00:00:00+00:00",
    }
    if extra_execution:
        payload.update(extra_execution)
    execution_path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def _write_canonical_continuation(
    project: Path,
    *,
    resume_file: str,
    phase: str = "03",
    plan: str = "01",
    segment_status: str = "paused",
) -> None:
    state_path = project / "GPD" / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "continuation": {
                    "schema_version": 1,
                    "handoff": {
                        "resume_file": resume_file,
                        "stopped_at": f"Phase {phase}",
                    },
                    "bounded_segment": {
                        "resume_file": resume_file,
                        "phase": phase,
                        "plan": plan,
                        "segment_id": "seg-canonical",
                        "segment_status": segment_status,
                    },
                    "machine": {
                        "hostname": "builder-01",
                        "platform": "Linux 6.1 x86_64",
                    },
                }
            }
        ),
        encoding="utf-8",
    )


def _write_canonical_handoff(project: Path, *, resume_file: str, phase: str = "03") -> None:
    state_path = project / "GPD" / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "continuation": {
                    "schema_version": 1,
                    "handoff": {
                        "resume_file": resume_file,
                        "stopped_at": f"Phase {phase}",
                    },
                    "machine": {
                        "hostname": "builder-01",
                        "platform": "Linux 6.1 x86_64",
                    },
                }
            }
        ),
        encoding="utf-8",
    )


def _write_usage_record(*, data_root: Path, project_root: Path, session_id: str) -> None:
    ledger_path = usage_ledger_path(data_root)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    record = UsageRecord(
        record_id="usage-001",
        recorded_at="2026-03-27T12:00:00+00:00",
        runtime=_TEST_RUNTIME,
        model=_TEST_MODEL,
        session_id=session_id,
        workspace_root=project_root.resolve(strict=False).as_posix(),
        project_root=project_root.resolve(strict=False).as_posix(),
        input_tokens=100,
        output_tokens=25,
        total_tokens=125,
    )
    ledger_path.write_text(record.model_dump_json() + "\n", encoding="utf-8")


def _assert_no_resume_compat_aliases(orientation: dict[str, object]) -> None:
    assert "compat_resume_surface" not in orientation
    for key in RESUME_COMPATIBILITY_ALIAS_FIELDS:
        assert key not in orientation
    assert "has_session_resume_file" not in orientation


def _fake_cost_summary(workspace: Path, **overrides: object) -> SimpleNamespace:
    payload: dict[str, object] = {
        "current_session_id": "sess-cost",
        "active_runtime": _TEST_RUNTIME,
        "model_profile": "review",
        "runtime_model_selection": "runtime defaults",
        "profile_tier_mix": {},
        "project_root": workspace.resolve(strict=False).as_posix(),
        "project": SimpleNamespace(record_count=0, usage_status="unavailable", cost_status="unavailable"),
        "current_session": None,
        "recent_sessions": [],
        "budget_thresholds": [],
        "pricing_snapshot_configured": False,
        "pricing_snapshot_source": None,
        "pricing_snapshot_as_of": None,
        "guidance": [],
    }
    payload.update(overrides)
    return SimpleNamespace(**payload)


def test_build_runtime_hint_payload_merges_source_sections_and_actions(tmp_path: Path) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"
    session_id = "sess-001"
    resume_file = project / "GPD" / "phases" / "03" / ".continue-here.md"
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text("resume\n", encoding="utf-8")

    _write_current_session(project, session_id=session_id)
    _write_current_execution(project, session_id=session_id)
    _write_usage_record(data_root=data_root, project_root=project, session_id=session_id)

    record_recent_project(
        project,
        session_data={
            "last_date": "2026-03-27T12:05:00+00:00",
            "stopped_at": "Phase 03",
            "resume_file": "GPD/phases/03/.continue-here.md",
            "hostname": "builder-01",
            "platform": "Linux 6.1 x86_64",
        },
        store_root=data_root,
    )

    payload = build_runtime_hint_payload(
        project,
        data_root=data_root,
        base_ready=True,
        latex_capability=_latex_capability(latexmk_available=False, kpsewhich_available=False),
        recent_projects_last=5,
        cost_last_sessions=5,
    )

    dumped = payload.model_dump()
    assert set(dumped) == {"source_meta", "execution", "recovery", "orientation", "cost", "workflow_presets", "next_actions"}
    assert payload.source_meta["project_root"] == project.resolve(strict=False).as_posix()
    assert payload.source_meta["current_session_id"] == session_id
    assert payload.source_meta["base_ready"] is True
    assert payload.source_meta["latex_capability"]["compiler_available"] is True
    assert payload.source_meta["latex_capability"]["compiler"] == "pdflatex"
    assert payload.source_meta["latex_capability"]["bibtex_available"] is True
    assert payload.source_meta["latex_capability"]["latexmk_available"] is False
    assert payload.source_meta["latex_capability"]["kpsewhich_available"] is False
    assert payload.source_meta["latex_capability"]["readiness_state"] == "ready"
    assert payload.source_meta["latex_capability"]["message"] == "pdflatex found (TeX Live): /usr/bin/pdflatex"
    assert "latex_available" not in payload.source_meta

    assert payload.execution is not None
    assert payload.execution["status_classification"] == "waiting"
    assert payload.execution["review_reason"] == "first-result review pending"

    assert len(payload.recovery["recent_projects"]) == 1
    assert payload.recovery["current_project"]["source"] == "current_workspace"
    assert payload.recovery["current_project"]["resumable"] is True
    assert payload.recovery["current_project"]["resume_file_available"] is True
    assert payload.recovery["current_project_summary"] == payload.recovery["current_project"]["summary"]
    assert "resume file ready" in payload.recovery["current_project_summary"]
    assert "current_workspace" not in payload.recovery
    assert payload.orientation["resume_surface_schema_version"] == 1
    assert payload.orientation["mode"] == "current-workspace"
    assert payload.orientation["primary_command"] == "gpd resume"
    assert "bounded resumable execution segment" in str(payload.orientation["primary_reason"])
    assert payload.orientation["continue_reason"] == recovery_continue_reason(mode="current-workspace")
    assert payload.orientation["fast_next_reason"] == recovery_fast_next_reason()
    _assert_no_resume_compat_aliases(payload.orientation)
    assert payload.orientation["active_resume_kind"] == "bounded_segment"
    assert payload.orientation["active_resume_origin"] == "continuation.bounded_segment"
    assert payload.orientation["active_resume_pointer"] == "GPD/phases/03/.continue-here.md"
    assert payload.orientation["resume_candidates_count"] >= 1
    assert payload.orientation["has_local_recovery_target"] is True
    assert "resume-work" in str(payload.orientation["continue_command"])
    assert "suggest-next" in str(payload.orientation["fast_next_command"])
    assert "actions" not in payload.orientation

    assert payload.cost["project_root"] == project.resolve(strict=False).as_posix()
    assert "workspace_root" not in payload.cost
    assert payload.cost["project"]["record_count"] == 1
    assert payload.cost["project"]["usage_status"] == "measured"
    assert payload.cost["project"]["interpretation"] == "tokens measured; USD unavailable"
    assert payload.cost["profile_tier_mix"] == _profile_tier_mix("review")
    assert payload.cost["advisory"]["state"] == "unavailable"
    assert "pricing snapshot" in payload.cost["advisory"]["message"]

    assert payload.workflow_presets["ready"] == 3
    assert payload.workflow_presets["degraded"] == 2
    assert payload.workflow_presets["blocked"] == 0
    assert payload.workflow_presets["latex_capability"]["paper_build_ready"] is True
    assert payload.workflow_presets["latex_capability"]["arxiv_submission_ready"] is False

    assert payload.cost["advisory"]["state"] == "unavailable"
    assert "next_action" not in payload.cost["advisory"]
    assert any(action.startswith("Run `gpd resume`") for action in payload.next_actions)
    assert not any("gpd cost" in action for action in payload.next_actions)
    assert not any("Workflow presets ready" in action for action in payload.next_actions)
    assert any("continues in-runtime from the selected project state" in action for action in payload.next_actions)
    assert any("fastest post-resume next command" in action for action in payload.next_actions)
    assert len(payload.next_actions) == len(set(payload.next_actions))


def test_build_runtime_hint_payload_does_not_recover_intent_during_read_only_discovery(tmp_path: Path) -> None:
    project = _bootstrap_recoverable_project(tmp_path)
    layout = _write_state_intent_recovery_files(project)

    before_state_json = layout.state_json.read_text(encoding="utf-8")
    before_state_intent = layout.state_intent.read_text(encoding="utf-8")
    before_json_tmp = (layout.gpd / ".state-json-tmp").read_text(encoding="utf-8")
    before_md_tmp = (layout.gpd / ".state-md-tmp").read_text(encoding="utf-8")

    payload = build_runtime_hint_payload(project)

    assert payload.orientation["project_root"] == project.as_posix()
    assert layout.state_json.read_text(encoding="utf-8") == before_state_json
    assert layout.state_intent.read_text(encoding="utf-8") == before_state_intent
    assert (layout.gpd / ".state-json-tmp").read_text(encoding="utf-8") == before_json_tmp
    assert (layout.gpd / ".state-md-tmp").read_text(encoding="utf-8") == before_md_tmp


def test_build_runtime_hint_payload_prefers_lineage_head_over_legacy_current_execution_snapshot(
    tmp_path: Path,
) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"

    _write_current_session(project, session_id="legacy-session")
    _write_current_execution(
        project,
        session_id="legacy-session",
        extra_execution={
            "segment_status": "waiting_review",
            "current_task": "Legacy snapshot task",
            "current_task_index": 4,
            "current_task_total": 8,
            "waiting_for_review": True,
            "review_required": True,
            "checkpoint_reason": "first_result",
            "waiting_reason": "first_result_review_required",
            "updated_at": "2026-03-27T12:01:00+00:00",
        },
    )

    head_snapshot = _ExecutionSnapshot(
        session_id="lineage-session",
        phase="03",
        plan="02",
        segment_status="blocked",
        blocked_reason="manual stop required",
        current_task="Lineage head task",
        current_task_index=1,
        current_task_total=4,
        updated_at="2026-03-27T12:03:00+00:00",
    )

    with patch("gpd.core.observability.get_current_execution", return_value=head_snapshot):
        payload = build_runtime_hint_payload(
            project,
            data_root=data_root,
            base_ready=True,
            latex_capability=_latex_capability(),
            include_cost=False,
            include_recovery=False,
            include_workflow_presets=False,
        )

    assert payload.execution is not None
    assert payload.execution["status_classification"] == "blocked"
    assert payload.execution["current_task"] == "Lineage head task"
    assert payload.execution["current_task_progress"] == "1/4"
    assert payload.execution["current_task"] != "Legacy snapshot task"
    assert payload.execution["has_live_execution"] is True


def test_build_runtime_hint_payload_reports_degraded_publication_presets_when_bibtex_is_missing(
    tmp_path: Path,
) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"

    payload = build_runtime_hint_payload(
        project,
        data_root=data_root,
        base_ready=True,
        latex_capability=_latex_capability(bibtex_available=False),
    )

    assert payload.workflow_presets["ready"] == 3
    assert payload.workflow_presets["degraded"] == 2
    assert payload.workflow_presets["blocked"] == 0
    assert payload.workflow_presets["latex_capability"]["bibliography_support_available"] is False
    assert payload.workflow_presets["latex_capability"]["paper_build_ready"] is True
    assert any(
        "BibTeX support" in warning
        for preset in payload.workflow_presets["presets"]
        for warning in preset["warnings"]
    )
    assert not any("BibTeX support" in action for action in payload.next_actions)
    assert not any("latexmk" in action for action in payload.next_actions)
    assert not any("kpsewhich" in action for action in payload.next_actions)


def test_build_runtime_hint_payload_handles_absent_execution_snapshot(tmp_path: Path) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"
    recent_project = tmp_path / "recent-project"
    recent_project.mkdir()
    record_recent_project(
        recent_project,
        session_data={
            "last_date": "2026-03-27T11:55:00+00:00",
            "stopped_at": "Phase 01",
            "resume_file": "GPD/phases/01/.continue-here.md",
        },
        store_root=data_root,
    )

    payload = build_runtime_hint_payload(
        project,
        data_root=data_root,
        base_ready=False,
        latex_capability=_latex_capability(),
    )

    assert payload.execution is not None
    assert payload.execution["has_live_execution"] is False
    assert payload.execution["status_classification"] == "idle"
    assert len(payload.recovery["recent_projects"]) == 1
    assert payload.recovery["current_project"] is not None
    assert payload.recovery["current_project"]["source"] == "current_workspace"
    assert payload.recovery["current_project"]["recoverable"] is False
    assert payload.recovery["current_project"]["resumable"] is False
    assert payload.recovery["current_project"]["summary"] is None
    assert payload.recovery["current_project_summary"] is None
    assert payload.recovery["project_reentry_summary"] == "GPD found recent projects on this machine, but none are ready to reopen automatically."
    assert payload.orientation["mode"] == "recent-projects"
    assert payload.orientation["primary_command"] == "gpd resume --recent"
    assert payload.orientation["active_resume_kind"] is None
    assert payload.orientation["resume_candidates_count"] == 0
    assert payload.orientation["has_local_recovery_target"] is False
    assert payload.cost["project_root"] == project.resolve(strict=False).as_posix()
    assert "workspace_root" not in payload.cost
    assert payload.workflow_presets["blocked"] == 5
    assert any("resume --recent" in action for action in payload.next_actions)
    assert any("resume-work" in action for action in payload.next_actions)
    assert any("suggest-next" in action for action in payload.next_actions)
    assert any("base runtime-readiness" in action for action in payload.next_actions)


def test_build_runtime_hint_payload_auto_selects_unique_recoverable_recent_project(tmp_path: Path) -> None:
    workspace = tmp_path / "outside"
    workspace.mkdir()
    project = _bootstrap_recoverable_project(tmp_path / "project-root")
    data_root = tmp_path / "data"
    resume_file = project / "GPD" / "phases" / "01" / ".continue-here.md"
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text("resume\n", encoding="utf-8")
    record_recent_project(
        project,
        session_data={
            "last_date": "2026-03-27T11:55:00+00:00",
            "stopped_at": "Phase 01",
            "resume_file": "GPD/phases/01/.continue-here.md",
        },
        store_root=data_root,
    )

    payload = build_runtime_hint_payload(
        workspace,
        data_root=data_root,
        base_ready=True,
        latex_capability=_latex_capability(),
    )

    assert payload.source_meta["project_root"] == project.resolve(strict=False).as_posix()
    assert payload.recovery["current_project"]["project_root"] == project.resolve(strict=False).as_posix()
    assert payload.recovery["project_reentry"]["project_root"] == project.resolve(strict=False).as_posix()
    assert payload.recovery["project_reentry"]["mode"] == "auto-recent-project"
    assert payload.recovery["project_reentry"]["auto_selected"] is True
    assert payload.recovery["current_project"]["source"] == "recent_project"
    assert payload.recovery["current_project"]["resume_target_kind"] == "handoff"
    assert payload.recovery["current_project"]["resume_target_recorded_at"] == "2026-03-27T11:55:00+00:00"
    assert payload.recovery["current_project"]["resume_file_reason"] is None
    assert payload.recovery["current_project_summary"] == "last seen 2026-03-27T11:55:00+00:00; stopped at Phase 01; resume file ready"
    assert payload.recovery["current_project_summary"] == payload.recovery["current_project"]["summary"]
    assert payload.recovery["project_reentry"]["candidates"][0]["resume_target_kind"] == "handoff"
    assert payload.recovery["project_reentry"]["candidates"][0]["auto_selectable"] is True
    assert payload.recovery["project_reentry"]["candidates"][0]["reason"] == "recent project cache entry with projected continuity handoff"
    assert (
        payload.recovery["project_reentry_summary"]
        == "GPD auto-selected the only recoverable recent project on this machine. last seen 2026-03-27T11:55:00+00:00; stopped at Phase 01; resume file ready."
    )
    assert "resume file ready" in payload.recovery["current_project_summary"]
    assert payload.orientation["resume_surface_schema_version"] == 1
    assert payload.orientation["mode"] == "recent-projects"
    assert payload.orientation["status"] == "session-handoff"
    assert payload.orientation["decision_source"] == "auto-selected-recent-project"
    assert payload.orientation["active_resume_kind"] == "continuity_handoff"
    assert payload.orientation["active_resume_origin"] == "continuation.handoff"
    assert payload.orientation["active_resume_pointer"] == "GPD/phases/01/.continue-here.md"
    assert payload.orientation["continuity_handoff_file"] == "GPD/phases/01/.continue-here.md"
    assert payload.orientation["recorded_continuity_handoff_file"] == "GPD/phases/01/.continue-here.md"
    assert payload.orientation["has_continuity_handoff"] is True
    assert payload.orientation["current_workspace_resumable"] is False
    assert payload.orientation["has_local_recovery_target"] is True
    assert payload.orientation["primary_command"] == "gpd resume --recent"
    assert "resume-work" in str(payload.orientation["continue_command"])
    assert "suggest-next" in str(payload.orientation["fast_next_command"])
    assert any("resume-work" in action for action in payload.next_actions)
    assert any("suggest-next" in action for action in payload.next_actions)


def test_build_runtime_hint_payload_auto_selected_bounded_segment_recent_project_stays_bounded_segment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "outside"
    workspace.mkdir()
    project = _bootstrap_recoverable_project(tmp_path / "project-root")
    data_root = tmp_path / "data"
    resume_file = project / "GPD" / "phases" / "02" / ".continue-here.md"
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text("resume\n", encoding="utf-8")
    record_recent_project(
        project,
        session_data={
            "last_date": "2026-03-27T11:55:00+00:00",
            "stopped_at": "Phase 02",
            "resume_file": "GPD/phases/02/.continue-here.md",
            "resume_target_kind": "bounded_segment",
            "resume_target_recorded_at": "2026-03-27T11:55:00+00:00",
        },
        store_root=data_root,
    )
    monkeypatch.setattr(
        "gpd.core.runtime_hints._resume_context",
        lambda _cwd, data_root=None: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "project_root": project.resolve(strict=False).as_posix(),
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
                    "status": "paused",
                    "resume_file": "GPD/phases/02/.continue-here.md",
                    "resume_pointer": "GPD/phases/02/.continue-here.md",
                }
            ],
            "execution_resumable": True,
            "has_live_execution": True,
        },
    )

    payload = build_runtime_hint_payload(
        workspace,
        data_root=data_root,
        base_ready=True,
        latex_capability=_latex_capability(),
    )

    assert payload.source_meta["project_root"] == project.resolve(strict=False).as_posix()
    assert payload.recovery["current_project"]["project_root"] == project.resolve(strict=False).as_posix()
    assert payload.recovery["current_project"]["source"] == "recent_project"
    assert payload.recovery["current_project"]["resume_target_kind"] == "bounded_segment"
    assert payload.recovery["current_project"]["resume_target_recorded_at"] == "2026-03-27T11:55:00+00:00"
    assert payload.recovery["current_project"]["resume_file_reason"] is None
    assert payload.recovery["current_project"]["resumable"] is True
    assert payload.recovery["project_reentry"]["mode"] == "auto-recent-project"
    assert payload.recovery["project_reentry"]["auto_selected"] is True
    assert payload.recovery["current_project_summary"] == "last seen 2026-03-27T11:55:00+00:00; stopped at Phase 02; resume file ready"
    assert payload.recovery["current_project_summary"] == payload.recovery["current_project"]["summary"]
    assert payload.recovery["project_reentry"]["candidates"][0]["resume_target_kind"] == "bounded_segment"
    assert payload.recovery["project_reentry"]["candidates"][0]["reason"] == "recent project cache entry with confirmed bounded segment resume target"
    assert payload.orientation["decision_source"] == "auto-selected-recent-project"
    assert payload.orientation["mode"] == "current-workspace"
    assert payload.orientation["status"] == "bounded-segment"
    assert payload.orientation["active_resume_kind"] == "bounded_segment"
    assert payload.orientation["active_resume_origin"] == "continuation.bounded_segment"
    assert payload.orientation["active_resume_pointer"] == "GPD/phases/02/.continue-here.md"
    assert payload.orientation["continuity_handoff_file"] is None
    assert payload.orientation["has_continuity_handoff"] is False
    assert payload.orientation["has_local_recovery_target"] is True
    assert payload.orientation["current_workspace_resumable"] is True
    assert payload.orientation["resume_candidates_count"] == 1
    assert payload.orientation["primary_command"] == "gpd resume --recent"
    assert "resume-work" in str(payload.orientation["continue_command"])
    assert "suggest-next" in str(payload.orientation["fast_next_command"])
    assert any("resume-work" in action for action in payload.next_actions)
    assert any("suggest-next" in action for action in payload.next_actions)


def test_build_runtime_hint_payload_recent_missing_handoff_stays_non_auto_selected_and_does_not_invent_local_pointer(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "outside"
    workspace.mkdir()
    project = _bootstrap_recoverable_project(tmp_path / "project-root")
    data_root = tmp_path / "data"

    record_recent_project(
        project,
        session_data={
            "last_date": "2026-03-27T11:55:00+00:00",
            "stopped_at": "Phase 05",
            "resume_file": "GPD/phases/05/.continue-here.md",
        },
        store_root=data_root,
    )

    payload = build_runtime_hint_payload(
        workspace,
        data_root=data_root,
        base_ready=True,
        latex_capability=_latex_capability(),
    )

    assert payload.recovery["project_reentry"]["mode"] == "recent-projects"
    assert payload.recovery["project_reentry"]["auto_selected"] is False
    assert payload.recovery["project_reentry"]["candidates"][0]["resume_file_available"] is False
    assert payload.recovery["project_reentry"]["candidates"][0]["resume_file_reason"] == "resume file missing"
    assert payload.orientation["decision_source"] == "recent-projects"
    assert payload.orientation["mode"] == "recent-projects"
    assert payload.orientation["status"] == "recent-projects"
    assert payload.orientation["active_resume_kind"] is None
    assert payload.orientation["active_resume_origin"] is None
    assert payload.orientation["active_resume_pointer"] is None
    assert payload.orientation["continuity_handoff_file"] is None
    assert payload.orientation["missing_continuity_handoff_file"] is None
    assert payload.orientation["has_continuity_handoff"] is False
    assert payload.orientation["has_local_recovery_target"] is False
    assert payload.orientation["current_workspace_resumable"] is False
    assert payload.orientation["primary_command"] == "gpd resume --recent"
    assert "resume-work" in str(payload.orientation["continue_command"])


def test_hydrate_resume_context_from_recent_project_rejects_string_booleans() -> None:
    payload = {
        "resume_candidates": [],
    }
    reentry = SimpleNamespace(auto_selected=True, mode="auto-recent-project")
    current_project = {
        "project_root": "/tmp/recent-project",
        "resume_file": "GPD/phases/05/.continue-here.md",
        "resume_file_available": "false",
        "resumable": "false",
    }

    hydrated = _hydrate_resume_context_from_recent_project(
        payload,
        reentry=reentry,
        current_project=current_project,
    )

    assert hydrated["active_resume_kind"] == "continuity_handoff"
    assert hydrated["active_resume_origin"] == "continuation.handoff"
    assert hydrated["missing_continuity_handoff_file"] == "GPD/phases/05/.continue-here.md"
    assert "active_resume_pointer" not in hydrated
    assert hydrated["resume_candidates"][0]["status"] == "missing"
    assert hydrated["resume_candidates"][0]["advisory"] is True


def test_hydrate_resume_context_from_recent_project_fails_closed_on_unknown_resume_target_kind() -> None:
    payload = {
        "resume_candidates": [],
    }
    reentry = SimpleNamespace(auto_selected=True, mode="auto-recent-project")
    current_project = {
        "project_root": "/tmp/recent-project",
        "resume_file": "GPD/phases/05/.continue-here.md",
        "resume_file_available": True,
        "resume_target_kind": "mystery-kind",
    }

    hydrated = _hydrate_resume_context_from_recent_project(
        payload,
        reentry=reentry,
        current_project=current_project,
    )

    assert hydrated == payload


def test_hydrate_resume_context_from_recent_project_keeps_bounded_segment_semantics_when_resume_file_is_missing() -> None:
    payload = {
        "resume_candidates": [],
    }
    reentry = SimpleNamespace(auto_selected=True, mode="auto-recent-project")
    current_project = {
        "project_root": "/tmp/recent-project",
        "resume_file": "GPD/phases/02/.continue-here.md",
        "resume_file_available": False,
        "resume_target_kind": "bounded_segment",
    }

    hydrated = _hydrate_resume_context_from_recent_project(
        payload,
        reentry=reentry,
        current_project=current_project,
    )

    assert hydrated["active_resume_kind"] == "bounded_segment"
    assert hydrated["active_resume_origin"] == "continuation.bounded_segment"
    assert "active_resume_pointer" not in hydrated
    assert "continuity_handoff_file" not in hydrated
    assert "recorded_continuity_handoff_file" not in hydrated
    assert "missing_continuity_handoff_file" not in hydrated
    assert hydrated["resume_candidates"][0]["kind"] == "bounded_segment"
    assert hydrated["resume_candidates"][0]["origin"] == "continuation.bounded_segment"
    assert hydrated["resume_candidates"][0]["status"] == "missing"
    assert hydrated["resume_candidates"][0]["advisory"] is True


def test_build_runtime_hint_payload_prefers_selected_project_resume_state_for_auto_selected_recent_project(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "outside"
    workspace.mkdir()
    project = _bootstrap_recoverable_project(tmp_path / "selected-project")
    data_root = tmp_path / "data"
    resume_file = project / "GPD" / "phases" / "03" / ".continue-here.md"
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text("resume\n", encoding="utf-8")
    _write_current_execution(
        project,
        session_id="sess-selected",
        extra_execution={
            "phase": "03",
            "plan": "01",
            "resume_file": "GPD/phases/03/.continue-here.md",
        },
    )
    record_recent_project(
        project,
        session_data={
            "last_date": "2026-03-27T12:05:00+00:00",
            "stopped_at": "Phase 03",
            "resume_file": "GPD/phases/03/.continue-here.md",
        },
        store_root=data_root,
    )

    payload = build_runtime_hint_payload(
        workspace,
        data_root=data_root,
        base_ready=True,
        latex_capability=_latex_capability(),
    )

    assert payload.source_meta["project_root"] == project.resolve(strict=False).as_posix()
    assert payload.recovery["current_project"]["project_root"] == project.resolve(strict=False).as_posix()
    assert payload.recovery["current_project"]["source"] == "recent_project"
    assert payload.recovery["project_reentry"]["mode"] == "auto-recent-project"
    assert payload.recovery["current_project"]["resume_target_kind"] == "handoff"
    assert payload.recovery["current_project"]["resume_file_reason"] is None
    assert payload.recovery["current_project_summary"] == "last seen 2026-03-27T12:05:00+00:00; stopped at Phase 03; resume file ready"
    assert payload.recovery["current_project_summary"] == payload.recovery["current_project"]["summary"]
    assert (
        payload.recovery["project_reentry_summary"]
        == "GPD auto-selected the only recoverable recent project on this machine. last seen 2026-03-27T12:05:00+00:00; stopped at Phase 03; resume file ready."
    )
    assert payload.recovery["project_reentry"]["candidates"][0]["resume_target_kind"] == "handoff"
    assert payload.recovery["project_reentry"]["candidates"][0]["reason"] == "recent project cache entry with projected continuity handoff"
    assert payload.orientation["mode"] == "recent-projects"
    assert payload.orientation["status"] == "bounded-segment"
    assert payload.orientation["decision_source"] == "auto-selected-recent-project"
    assert payload.orientation["project_root_auto_selected"] is True
    assert payload.orientation["active_resume_kind"] == "bounded_segment"
    assert payload.orientation["active_resume_origin"] == "continuation.bounded_segment"
    assert payload.orientation["active_resume_pointer"] == "GPD/phases/03/.continue-here.md"
    assert payload.orientation["continuity_handoff_file"] is None
    assert payload.orientation["current_workspace_resumable"] is False
    assert payload.orientation["has_local_recovery_target"] is True
    assert payload.orientation["primary_command"] == "gpd resume --recent"
    assert "resume-work" in str(payload.orientation["continue_command"])
    assert "suggest-next" in str(payload.orientation["fast_next_command"])
    assert any("resume-work" in action for action in payload.next_actions)
    assert any("suggest-next" in action for action in payload.next_actions)


def test_build_runtime_hint_payload_promotes_auto_selected_recent_bounded_segment_over_same_pointer_handoff(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "outside"
    workspace.mkdir()
    project = _bootstrap_recoverable_project(tmp_path / "selected-project")
    data_root = tmp_path / "data"
    resume_file = project / "GPD" / "phases" / "04" / ".continue-here.md"
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text("resume\n", encoding="utf-8")
    _write_canonical_handoff(project, resume_file="GPD/phases/04/.continue-here.md", phase="04")
    record_recent_project(
        project,
        session_data={
            "last_date": "2026-03-27T12:10:00+00:00",
            "stopped_at": "Phase 04",
            "resume_file": "GPD/phases/04/.continue-here.md",
            "resume_target_kind": "bounded_segment",
            "resume_target_recorded_at": "2026-03-27T12:10:00+00:00",
            "source_kind": "continuation.bounded_segment",
            "source_segment_id": "seg-recent-04",
            "source_transition_id": "transition-recent-04",
            "recovery_phase": "04",
            "recovery_plan": "02",
        },
        store_root=data_root,
    )

    payload = build_runtime_hint_payload(
        workspace,
        data_root=data_root,
        base_ready=True,
        latex_capability=_latex_capability(),
    )

    assert payload.source_meta["project_root"] == project.resolve(strict=False).as_posix()
    assert payload.recovery["current_project"]["project_root"] == project.resolve(strict=False).as_posix()
    assert payload.recovery["current_project"]["source"] == "recent_project"
    assert payload.recovery["current_project"]["resume_target_kind"] == "bounded_segment"
    assert payload.recovery["current_project"]["source_kind"] == "continuation.bounded_segment"
    assert payload.recovery["current_project"]["source_segment_id"] == "seg-recent-04"
    assert payload.recovery["current_project"]["source_transition_id"] == "transition-recent-04"
    assert payload.recovery["current_project"]["recovery_phase"] == "04"
    assert payload.recovery["current_project"]["recovery_plan"] == "02"
    assert payload.recovery["project_reentry"]["mode"] == "auto-recent-project"
    assert payload.recovery["project_reentry"]["auto_selected"] is True
    assert payload.recovery["project_reentry"]["candidates"][0]["resume_target_kind"] == "bounded_segment"
    assert payload.recovery["project_reentry"]["candidates"][0]["source_kind"] == "continuation.bounded_segment"
    assert payload.recovery["project_reentry"]["candidates"][0]["source_segment_id"] == "seg-recent-04"
    assert payload.recovery["project_reentry"]["candidates"][0]["source_transition_id"] == "transition-recent-04"
    assert payload.orientation["decision_source"] == "auto-selected-recent-project"
    assert payload.orientation["mode"] == "recent-projects"
    assert payload.orientation["status"] == "bounded-segment"
    assert payload.orientation["project_root_auto_selected"] is True
    assert payload.orientation["active_resume_kind"] == "bounded_segment"
    assert payload.orientation["active_resume_origin"] == "continuation.bounded_segment"
    assert payload.orientation["active_resume_pointer"] == "GPD/phases/04/.continue-here.md"
    assert payload.orientation["continuity_handoff_file"] == "GPD/phases/04/.continue-here.md"
    assert payload.orientation["has_continuity_handoff"] is True
    assert payload.orientation["current_workspace_resumable"] is False
    assert payload.orientation["has_local_recovery_target"] is True
    assert payload.orientation["resume_candidates_count"] == 1
    assert payload.orientation["primary_command"] == "gpd resume --recent"
    assert "resume-work" in str(payload.orientation["continue_command"])
    assert "suggest-next" in str(payload.orientation["fast_next_command"])
    assert any("resume-work" in action for action in payload.next_actions)
    assert any("suggest-next" in action for action in payload.next_actions)


def test_build_runtime_hint_payload_uses_selected_project_reentry_candidate_for_summary_text(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "outside"
    workspace.mkdir()
    selected_project = _bootstrap_recoverable_project(tmp_path / "selected-project")
    fallback_project = _bootstrap_recoverable_project(tmp_path / "fallback-project")
    selected_root = selected_project.resolve(strict=False).as_posix()
    fallback_root = fallback_project.resolve(strict=False).as_posix()

    monkeypatch.setattr(
        "gpd.core.runtime_hints.resolve_project_reentry",
        lambda _workspace_hint, data_root=None: SimpleNamespace(
            resolved_project_root=selected_project,
            source="recent_project",
            auto_selected=True,
            requires_user_selection=False,
            mode="auto-recent-project",
            project_root=selected_root,
            project_root_source="recent_project",
            project_root_auto_selected=True,
            selected_candidate={
                "project_root": selected_root,
                "source": "recent_project",
                "last_session_at": "2026-03-27T12:15:00+00:00",
                "stopped_at": "Phase 08",
                "resumable": True,
                "resume_file_available": True,
                "resume_target_kind": "handoff",
                "resume_target_recorded_at": "2026-03-27T12:15:00+00:00",
                "source_kind": "continuation.handoff",
                "reason": "recent project cache entry with projected continuity handoff",
            },
            candidates=[
                {
                    "project_root": fallback_root,
                    "source": "recent_project",
                    "last_session_at": "2026-03-27T11:55:00+00:00",
                    "stopped_at": "Phase 02",
                    "resumable": True,
                    "resume_file_available": True,
                    "resume_target_kind": "bounded_segment",
                    "resume_target_recorded_at": "2026-03-27T11:55:00+00:00",
                    "source_kind": "continuation.bounded_segment",
                    "reason": "recent project cache entry with confirmed bounded segment resume target",
                }
            ],
        ),
    )
    monkeypatch.setattr("gpd.core.runtime_hints._resume_context", lambda _cwd, data_root=None: {})
    monkeypatch.setattr("gpd.core.runtime_hints.list_recent_projects", lambda store_root=None, last=None: [])

    payload = build_runtime_hint_payload(
        workspace,
        data_root=tmp_path / "data",
        base_ready=True,
        latex_capability=_latex_capability(),
    )

    assert payload.recovery["current_project"]["project_root"] == selected_root
    assert payload.recovery["current_project"]["summary"] == "last seen 2026-03-27T12:15:00+00:00; stopped at Phase 08; resume file ready"
    assert payload.recovery["current_project_summary"] == payload.recovery["current_project"]["summary"]
    assert payload.recovery["current_project_summary"] == "last seen 2026-03-27T12:15:00+00:00; stopped at Phase 08; resume file ready"
    assert payload.recovery["project_reentry_summary"] == (
        "GPD auto-selected the only recoverable recent project on this machine. "
        "last seen 2026-03-27T12:15:00+00:00; stopped at Phase 08; resume file ready."
    )
    assert "Phase 02" not in payload.recovery["current_project_summary"]
    assert "Phase 02" not in payload.recovery["project_reentry_summary"]


def test_build_runtime_hint_payload_preserves_existing_local_target_over_recent_project_hydration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "outside"
    workspace.mkdir()
    project = _bootstrap_recoverable_project(tmp_path / "project-root")
    data_root = tmp_path / "data"
    resume_file = project / "GPD" / "phases" / "02" / ".continue-here.md"
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text("resume\n", encoding="utf-8")
    record_recent_project(
        project,
        session_data={
            "last_date": "2026-03-27T11:55:00+00:00",
            "stopped_at": "Phase 02",
            "resume_file": "GPD/phases/02/.continue-here.md",
        },
        store_root=data_root,
    )
    monkeypatch.setattr(
        "gpd.core.runtime_hints._resume_context",
        lambda _cwd, data_root=None: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "active_resume_kind": "bounded_segment",
            "active_resume_origin": "continuation.bounded_segment",
            "active_resume_pointer": "GPD/phases/08/.continue-here.md",
            "execution_resumable": True,
            "resume_candidates": [
                {
                    "kind": "bounded_segment",
                    "origin": "continuation.bounded_segment",
                    "status": "paused",
                    "resume_file": "GPD/phases/08/.continue-here.md",
                    "resume_pointer": "GPD/phases/08/.continue-here.md",
                }
            ],
            "has_live_execution": True,
        },
    )

    payload = build_runtime_hint_payload(
        workspace,
        data_root=data_root,
        base_ready=True,
        latex_capability=_latex_capability(),
    )

    assert payload.source_meta["project_root"] == project.resolve(strict=False).as_posix()
    assert payload.recovery["current_project"]["project_root"] == project.resolve(strict=False).as_posix()
    assert payload.recovery["current_project"]["resumable"] is True
    assert payload.orientation["mode"] == "current-workspace"
    assert payload.orientation["status"] == "bounded-segment"
    assert payload.orientation["active_resume_kind"] == "bounded_segment"
    assert payload.orientation["active_resume_origin"] == "continuation.bounded_segment"
    assert payload.orientation["active_resume_pointer"] == "GPD/phases/08/.continue-here.md"
    assert payload.orientation["continuity_handoff_file"] is None
    assert payload.orientation["has_local_recovery_target"] is True
    assert payload.orientation["current_workspace_resumable"] is True
    assert payload.orientation["continue_command"] is not None
    assert "resume-work" in str(payload.orientation["continue_command"])
    assert "suggest-next" in str(payload.orientation["fast_next_command"])
    assert any(action.startswith("Run `gpd resume`") for action in payload.next_actions)


def test_build_runtime_hint_payload_does_not_hydrate_over_existing_canonical_continuity_handoff_pointer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "outside"
    workspace.mkdir()
    project = _bootstrap_recoverable_project(tmp_path / "project-root")
    data_root = tmp_path / "data"
    resume_file = project / "GPD" / "phases" / "99" / ".continue-here.md"
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text("resume\n", encoding="utf-8")
    record_recent_project(
        project,
        session_data={
            "last_date": "2026-03-27T11:55:00+00:00",
            "stopped_at": "Phase 99",
            "resume_file": "GPD/phases/99/.continue-here.md",
        },
        store_root=data_root,
    )
    monkeypatch.setattr(
        "gpd.core.runtime_hints._resume_context",
        lambda _cwd, data_root=None: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "project_root": project.resolve(strict=False).as_posix(),
            "project_root_source": "recent_project",
            "project_root_auto_selected": True,
            "project_reentry_mode": "auto-recent-project",
            "active_resume_kind": "continuity_handoff",
            "active_resume_origin": "continuation.handoff",
            "active_resume_pointer": "GPD/phases/04/.continue-here.md",
            "resume_candidates": [],
            "has_live_execution": False,
        },
    )

    payload = build_runtime_hint_payload(
        workspace,
        data_root=data_root,
        base_ready=True,
        latex_capability=_latex_capability(),
    )

    assert payload.source_meta["project_root"] == project.resolve(strict=False).as_posix()
    assert payload.recovery["current_project"]["project_root"] == project.resolve(strict=False).as_posix()
    assert payload.recovery["current_project"]["source"] == "recent_project"
    assert payload.orientation["mode"] == "current-workspace"
    assert payload.orientation["status"] == "session-handoff"
    assert payload.orientation["active_resume_kind"] == "continuity_handoff"
    assert payload.orientation["active_resume_origin"] == "continuation.handoff"
    assert payload.orientation["active_resume_pointer"] == "GPD/phases/04/.continue-here.md"
    assert payload.orientation["continuity_handoff_file"] is None
    assert payload.orientation["recorded_continuity_handoff_file"] is None
    assert payload.orientation["has_continuity_handoff"] is True
    assert payload.orientation["current_workspace_has_resume_file"] is True
    assert payload.orientation["has_local_recovery_target"] is True
    assert "resume-work" in str(payload.orientation["continue_command"])
    assert "suggest-next" in str(payload.orientation["fast_next_command"])


def test_build_runtime_hint_payload_does_not_treat_missing_handoff_only_state_as_local_target(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"

    monkeypatch.setattr(
        "gpd.core.runtime_hints._resume_context",
        lambda _cwd, data_root=None: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "resume_candidates": [
                {
                    "kind": "continuity_handoff",
                    "origin": "continuation.handoff",
                    "status": "missing",
                    "resume_file": "GPD/phases/04/.continue-here.md",
                }
            ],
            "missing_continuity_handoff_file": "GPD/phases/04/.continue-here.md",
            "has_live_execution": False,
        },
    )

    payload = build_runtime_hint_payload(
        project,
        data_root=data_root,
        include_cost=False,
        include_workflow_presets=False,
    )

    assert payload.execution is not None
    assert payload.execution["has_live_execution"] is False
    assert payload.orientation["resume_surface_schema_version"] == 1
    assert payload.orientation["mode"] == "current-workspace"
    assert payload.orientation["status"] == "missing-handoff"
    assert payload.orientation["active_resume_kind"] == "continuity_handoff"
    assert payload.orientation["active_resume_origin"] == "continuation.handoff"
    assert payload.orientation["active_resume_pointer"] is None
    assert payload.orientation["continuity_handoff_file"] is None
    assert payload.orientation["recorded_continuity_handoff_file"] is None
    assert payload.orientation["missing_continuity_handoff_file"] == "GPD/phases/04/.continue-here.md"
    assert payload.orientation["has_continuity_handoff"] is False
    assert payload.orientation["missing_continuity_handoff"] is True
    assert payload.orientation["has_local_recovery_target"] is False
    assert payload.orientation["resume_candidates_count"] == 1
    assert payload.orientation["current_workspace_resumable"] is False
    assert payload.orientation["primary_command"] == "gpd resume"
    assert "resume-work" in str(payload.orientation["continue_command"])
    assert "suggest-next" in str(payload.orientation["fast_next_command"])


def test_build_runtime_hint_payload_keeps_ambiguous_recent_projects_explicit(tmp_path: Path) -> None:
    workspace = tmp_path / "outside"
    workspace.mkdir()
    first_project = _bootstrap_recoverable_project(tmp_path / "first-project")
    second_project = _bootstrap_recoverable_project(tmp_path / "second-project")
    data_root = tmp_path / "data"
    first_resume = first_project / "GPD" / "phases" / "01" / ".continue-here.md"
    second_resume = second_project / "GPD" / "phases" / "02" / ".continue-here.md"
    first_resume.parent.mkdir(parents=True, exist_ok=True)
    second_resume.parent.mkdir(parents=True, exist_ok=True)
    first_resume.write_text("resume\n", encoding="utf-8")
    second_resume.write_text("resume\n", encoding="utf-8")

    record_recent_project(
        first_project,
        session_data={
            "last_date": "2026-03-27T11:55:00+00:00",
            "stopped_at": "Phase 01",
            "resume_file": "GPD/phases/01/.continue-here.md",
        },
        store_root=data_root,
    )
    record_recent_project(
        second_project,
        session_data={
            "last_date": "2026-03-27T11:56:00+00:00",
            "stopped_at": "Phase 02",
            "resume_file": "GPD/phases/02/.continue-here.md",
        },
        store_root=data_root,
    )

    payload = build_runtime_hint_payload(
        workspace,
        data_root=data_root,
        base_ready=True,
        latex_capability=_latex_capability(),
    )

    assert payload.source_meta["project_root"] == workspace.resolve(strict=False).as_posix()
    assert payload.recovery["project_reentry"]["mode"] == "ambiguous-recent-projects"
    assert payload.recovery["project_reentry"]["requires_user_selection"] is True
    assert payload.recovery["project_reentry_summary"] == "GPD found multiple recoverable recent projects on this machine, so you need to choose one."
    assert payload.recovery["current_project"] is None
    assert payload.orientation["primary_command"] == "gpd resume --recent"
    assert not any("resume-work" in action for action in payload.next_actions)
    assert not any("suggest-next" in action for action in payload.next_actions)


def test_build_runtime_hint_payload_keeps_cost_guidance_quiet_when_best_effort_telemetry_has_no_guardrail(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)

    fake_summary = _fake_cost_summary(
        project,
        project=SimpleNamespace(record_count=0, cost_status="unavailable"),
        active_runtime_capabilities={
            "permissions_surface": "config-file",
            "statusline_surface": "none",
            "notify_surface": "explicit",
            "telemetry_source": "notify-hook",
            "telemetry_completeness": "best-effort",
        },
        guidance=[
            f"{_TEST_RUNTIME} only exposes best-effort usage telemetry through notify-hook, so missing turns remain unavailable instead of being guessed."
        ],
    )
    monkeypatch.setattr("gpd.core.runtime_hints.build_cost_summary", lambda *args, **kwargs: fake_summary)

    payload = build_runtime_hint_payload(project, include_recovery=False, include_workflow_presets=False)

    assert "advisory" not in payload.cost
    assert not any("gpd cost" in action for action in payload.next_actions)


def test_build_runtime_hint_payload_keeps_cost_actions_quiet_for_measured_usage_without_usd(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)

    fake_summary = _fake_cost_summary(
        project,
        project=SimpleNamespace(record_count=2, usage_status="measured", cost_status="unavailable"),
        guidance=[
            "Measured tokens are available, but no pricing snapshot is configured at the machine-local cost root, so USD cost is unavailable."
        ],
    )
    monkeypatch.setattr("gpd.core.runtime_hints.build_cost_summary", lambda *args, **kwargs: fake_summary)

    payload = build_runtime_hint_payload(project, include_recovery=False, include_workflow_presets=False)

    assert payload.cost["advisory"]["state"] == "unavailable"
    assert "next_action" not in payload.cost["advisory"]
    assert not any("gpd cost" in action for action in payload.next_actions)


def test_build_runtime_hint_payload_surfaces_cost_action_for_mixed_rollup_without_budget_threshold(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)

    fake_summary = _fake_cost_summary(
        project,
        project=SimpleNamespace(record_count=2, usage_status="measured", cost_status="mixed"),
        guidance=[
            "USD cost mixes measured runtime telemetry with pricing-snapshot estimates. Treat the total as advisory rather than invoice-level billing truth."
        ],
    )
    monkeypatch.setattr("gpd.core.runtime_hints.build_cost_summary", lambda *args, **kwargs: fake_summary)

    payload = build_runtime_hint_payload(project, include_recovery=False, include_workflow_presets=False)

    assert payload.cost["advisory"]["state"] == "mixed"
    assert payload.cost["advisory"]["next_action"] == cost_inspect_action()
    assert payload.next_actions.count(cost_inspect_action()) == 1


def test_build_runtime_hint_payload_surfaces_budget_guardrail_advisory_when_threshold_is_near(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)

    fake_summary = _fake_cost_summary(
        project,
        project=SimpleNamespace(record_count=2, usage_status="measured", cost_status="measured"),
        budget_thresholds=[
            SimpleNamespace(
                scope="session",
                config_key="session_usd_budget",
                state="near_budget",
                message=(
                    "Configured session USD budget is nearing budget based on measured local USD telemetry; "
                    "it stays advisory only and never stops work automatically."
                ),
            )
        ],
        pricing_snapshot_configured=True,
        pricing_snapshot_source="tests",
        pricing_snapshot_as_of="2026-03-27",
    )
    monkeypatch.setattr("gpd.core.runtime_hints.build_cost_summary", lambda *args, **kwargs: fake_summary)

    payload = build_runtime_hint_payload(project, include_recovery=False, include_workflow_presets=False)

    assert payload.cost["advisory"]["state"] == "near_budget"
    assert payload.cost["advisory"]["scope"] == "session"
    assert payload.cost["advisory"]["config_key"] == "session_usd_budget"
    assert "nearing budget" in payload.cost["advisory"]["message"]
    assert payload.cost["advisory"]["next_action"] == cost_inspect_action()
    assert payload.cost["advisory"]["next_action"] in payload.next_actions


def test_build_runtime_hint_payload_prioritizes_over_budget_guardrail_over_lower_priority_cost_signals(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)

    fake_summary = _fake_cost_summary(
        project,
        project=SimpleNamespace(record_count=3, usage_status="measured", cost_status="mixed"),
        budget_thresholds=[
            SimpleNamespace(
                scope="session",
                config_key="session_usd_budget",
                state="near_budget",
                message=(
                    "Configured session USD budget is nearing budget based on measured local USD telemetry; "
                    "it stays advisory only and never stops work automatically."
                ),
            ),
            SimpleNamespace(
                scope="project",
                config_key="project_usd_budget",
                state="at_or_over_budget",
                message=(
                    "Configured project USD budget is at or over budget based on measured local USD telemetry; "
                    "it stays advisory only and never stops work automatically."
                ),
            ),
        ],
        guidance=[
            "USD cost mixes measured runtime telemetry with pricing-snapshot estimates. Treat the total as advisory rather than invoice-level billing truth."
        ],
    )
    monkeypatch.setattr("gpd.core.runtime_hints.build_cost_summary", lambda *args, **kwargs: fake_summary)

    payload = build_runtime_hint_payload(project, include_recovery=False, include_workflow_presets=False)

    assert payload.cost["advisory"]["state"] == "at_or_over_budget"
    assert payload.cost["advisory"]["scope"] == "project"
    assert payload.cost["advisory"]["config_key"] == "project_usd_budget"
    assert payload.cost["advisory"]["next_action"] == cost_inspect_action()
    assert payload.next_actions.count(cost_inspect_action()) == 1


def test_build_runtime_hint_payload_skips_cost_advisory_when_runtime_exposes_no_threshold(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)

    fake_summary = _fake_cost_summary(
        project,
        project=SimpleNamespace(record_count=0, usage_status="unavailable", cost_status="unavailable"),
        active_runtime_capabilities={
            "permissions_surface": "config-file",
            "statusline_surface": "none",
            "notify_surface": "explicit",
            "telemetry_source": "none",
            "telemetry_completeness": "none",
        },
        guidance=[
            f"{_TEST_RUNTIME} does not currently expose a GPD-managed usage telemetry collection path, so `gpd cost` may remain empty even when work runs."
        ],
    )
    monkeypatch.setattr("gpd.core.runtime_hints.build_cost_summary", lambda *args, **kwargs: fake_summary)

    payload = build_runtime_hint_payload(project, include_recovery=False, include_workflow_presets=False)

    assert "advisory" not in payload.cost
    assert not any("gpd cost" in action for action in payload.next_actions)


def test_build_runtime_hint_payload_surfaces_tangent_follow_up_from_execution_visibility(tmp_path: Path) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"
    _write_current_execution(
        project,
        session_id="sess-009",
        extra_execution={
            "checkpoint_reason": "pre_fanout",
            "tangent_summary": "Check whether the 2D case is degenerate",
            "tangent_decision": "branch_later",
        },
    )

    payload = build_runtime_hint_payload(
        project,
        data_root=data_root,
        base_ready=True,
        latex_capability=_latex_capability(),
    )

    assert payload.execution is not None
    assert payload.execution["tangent_summary"] == "Check whether the 2D case is degenerate"
    assert payload.execution["tangent_decision"] == "branch_later"
    assert payload.execution["tangent_decision_label"] == "branch later"
    assert any("After the bounded stop" in action for action in payload.next_actions)
    assert any("`branch-hypothesis`" in action for action in payload.next_actions)
    assert not any("Tangent proposal recorded" in action for action in payload.next_actions)


def test_build_runtime_hint_payload_keeps_pending_tangent_on_generic_chooser(tmp_path: Path) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"
    _write_current_execution(
        project,
        session_id="sess-009-pending",
        extra_execution={
            "checkpoint_reason": "pre_fanout",
            "tangent_summary": "Check whether the 2D case is degenerate",
        },
    )

    payload = build_runtime_hint_payload(
        project,
        data_root=data_root,
        base_ready=True,
        latex_capability=_latex_capability(),
    )

    assert payload.execution is not None
    assert payload.execution["tangent_summary"] == "Check whether the 2D case is degenerate"
    assert payload.execution["tangent_decision"] is None
    assert any("Inside the runtime, use the `tangent` command" in action for action in payload.next_actions)
    assert not any("After the bounded stop" in action for action in payload.next_actions)


def test_build_runtime_hint_payload_uses_shared_resume_contract_without_recent_project_row(
    tmp_path: Path,
) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"
    resume_file = project / "GPD" / "phases" / "05" / ".continue-here.md"
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text("resume\n", encoding="utf-8")

    _write_current_execution(
        project,
        session_id="sess-010",
        extra_execution={
            "phase": "05",
            "plan": "02",
            "resume_file": "GPD/phases/05/.continue-here.md",
        },
    )

    payload = build_runtime_hint_payload(
        project,
        data_root=data_root,
        include_cost=False,
        include_workflow_presets=False,
    )

    assert payload.recovery["recent_projects"] == []
    assert payload.orientation["mode"] == "current-workspace"
    assert payload.orientation["primary_command"] == "gpd resume"
    assert payload.orientation["active_resume_kind"] == "bounded_segment"
    assert payload.orientation["active_resume_origin"] == "continuation.bounded_segment"
    assert payload.orientation["active_resume_pointer"] == "GPD/phases/05/.continue-here.md"
    assert payload.orientation["execution_resumable"] is True
    _assert_no_resume_compat_aliases(payload.orientation)
    assert any(action.startswith("Run `gpd resume`") for action in payload.next_actions)


def test_build_runtime_hint_payload_uses_canonical_bounded_resume_mode_without_legacy_execution_flag(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"
    monkeypatch.setattr(
        "gpd.core.runtime_hints._resume_context",
        lambda _cwd, data_root=None: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "active_resume_kind": "bounded_segment",
            "active_resume_origin": "continuation.bounded_segment",
            "active_resume_pointer": "GPD/phases/06/.continue-here.md",
            "resume_candidates": [],
            "has_live_execution": True,
        },
    )

    payload = build_runtime_hint_payload(
        project,
        data_root=data_root,
        include_cost=False,
        include_workflow_presets=False,
    )

    assert payload.orientation["mode"] == "current-workspace"
    assert payload.orientation["status"] == "bounded-segment"
    assert payload.orientation["current_workspace_resumable"] is True
    assert payload.orientation["has_local_recovery_target"] is True
    assert payload.orientation["active_resume_kind"] == "bounded_segment"
    _assert_no_resume_compat_aliases(payload.orientation)
    assert any(action.startswith("Run `gpd resume`") for action in payload.next_actions)
    assert any("resume-work" in action for action in payload.next_actions)
    assert any("suggest-next" in action for action in payload.next_actions)


def test_build_runtime_hint_payload_keeps_legacy_execution_overlay_advisory_without_resume_target(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"
    monkeypatch.setattr(
        "gpd.core.runtime_hints._resume_context",
        lambda _cwd, data_root=None: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "resume_mode": "bounded_segment",
            "execution_resumable": True,
            "active_execution_segment": {
                "segment_id": "seg-legacy",
                "phase": "04",
                "plan": "02",
                "segment_status": "paused",
            },
            "has_live_execution": True,
        },
    )

    payload = build_runtime_hint_payload(
        project,
        data_root=data_root,
        include_cost=False,
        include_workflow_presets=False,
    )

    assert payload.orientation["mode"] == "current-workspace"
    assert payload.orientation["status"] == "live-execution"
    assert payload.orientation["active_resume_kind"] is None
    assert payload.orientation["active_resume_origin"] is None
    assert payload.orientation["active_resume_pointer"] is None
    assert payload.orientation["execution_resumable"] is False
    assert payload.orientation["has_local_recovery_target"] is False
    _assert_no_resume_compat_aliases(payload.orientation)
    assert any(action.startswith("Run `gpd resume`") for action in payload.next_actions)
    assert not any("resume-work" in action for action in payload.next_actions)
    assert not any("suggest-next" in action for action in payload.next_actions)


def test_build_runtime_hint_payload_prefers_canonical_continuity_fields_over_conflicting_legacy_execution_flags(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"
    handoff = project / "GPD" / "phases" / "09" / ".continue-here.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text("resume\n", encoding="utf-8")
    monkeypatch.setattr(
        "gpd.core.runtime_hints._resume_context",
        lambda _cwd, data_root=None: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "resume_candidates": [
                {
                    "kind": "continuity_handoff",
                    "origin": "continuation.handoff",
                    "status": "handoff",
                    "resume_file": "GPD/phases/09/.continue-here.md",
                }
            ],
            "active_resume_kind": "continuity_handoff",
            "active_resume_origin": "continuation.handoff",
            "active_resume_pointer": "GPD/phases/09/.continue-here.md",
            "continuity_handoff_file": "GPD/phases/09/.continue-here.md",
            "recorded_continuity_handoff_file": "GPD/phases/09/.continue-here.md",
            "execution_resumable": True,
            "execution_resume_file": "GPD/phases/09/legacy-live.md",
            "execution_resume_file_source": "current_execution",
            "has_live_execution": True,
        },
    )
    monkeypatch.setattr(
        "gpd.core.runtime_hints.resolve_project_reentry",
        lambda _workspace_hint, data_root=None: SimpleNamespace(
            resolved_project_root=project,
            candidates=[],
            selected_candidate=None,
            auto_selected=False,
            requires_user_selection=False,
            mode="current-workspace",
        ),
    )

    payload = build_runtime_hint_payload(
        project,
        data_root=data_root,
        include_cost=False,
        include_workflow_presets=False,
    )

    assert payload.orientation["resume_surface_schema_version"] == 1
    assert payload.orientation["status"] == "session-handoff"
    assert payload.orientation["active_resume_kind"] == "continuity_handoff"
    assert payload.orientation["active_resume_origin"] == "continuation.handoff"
    assert payload.orientation["active_resume_pointer"] == "GPD/phases/09/.continue-here.md"
    assert payload.orientation["continuity_handoff_file"] == "GPD/phases/09/.continue-here.md"
    assert payload.orientation["execution_resumable"] is False
    assert payload.orientation["has_continuity_handoff"] is True
    assert "actions" not in payload.orientation
    _assert_no_resume_compat_aliases(payload.orientation)
    assert any("resume-work" in action for action in payload.next_actions)
    assert any("suggest-next" in action for action in payload.next_actions)


def test_build_runtime_hint_payload_prefers_canonical_resume_fields_over_legacy_top_level_aliases(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"
    handoff = project / "GPD" / "phases" / "10" / ".continue-here.md"
    handoff.parent.mkdir(parents=True, exist_ok=True)
    handoff.write_text("resume\n", encoding="utf-8")
    monkeypatch.setattr(
        "gpd.core.runtime_hints._resume_context",
        lambda _cwd, data_root=None: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "active_resume_kind": "continuity_handoff",
            "active_resume_origin": "continuation.handoff",
            "active_resume_pointer": "GPD/phases/10/.continue-here.md",
            "continuity_handoff_file": "GPD/phases/10/.continue-here.md",
            "recorded_continuity_handoff_file": "GPD/phases/10/.continue-here.md",
            "resume_mode": "bounded_segment",
            "execution_resumable": True,
            "execution_resume_file": "GPD/phases/10/legacy-live.md",
            "execution_resume_file_source": "current_execution",
            "has_live_execution": True,
        },
    )

    payload = build_runtime_hint_payload(
        project,
        data_root=data_root,
        include_cost=False,
        include_workflow_presets=False,
    )

    assert payload.orientation["status"] == "session-handoff"
    assert payload.orientation["active_resume_kind"] == "continuity_handoff"
    assert payload.orientation["active_resume_origin"] == "continuation.handoff"
    assert payload.orientation["active_resume_pointer"] == "GPD/phases/10/.continue-here.md"
    assert payload.orientation["continuity_handoff_file"] == "GPD/phases/10/.continue-here.md"
    assert payload.orientation["execution_resumable"] is False
    assert payload.orientation["has_continuity_handoff"] is True
    assert "actions" not in payload.orientation
    _assert_no_resume_compat_aliases(payload.orientation)
    assert any("resume-work" in action for action in payload.next_actions)
    assert any("suggest-next" in action for action in payload.next_actions)


def test_build_runtime_hint_payload_uses_canonical_bounded_segment_without_current_execution_snapshot(
    tmp_path: Path,
) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"
    resume_file = "GPD/phases/06/.continue-here.md"
    (project / resume_file).parent.mkdir(parents=True, exist_ok=True)
    (project / resume_file).write_text("resume\n", encoding="utf-8")
    _write_canonical_continuation(project, resume_file=resume_file, phase="06", plan="02")

    payload = build_runtime_hint_payload(
        project,
        data_root=data_root,
        include_cost=False,
        include_workflow_presets=False,
    )

    assert payload.execution is not None
    assert payload.execution["has_live_execution"] is False
    assert payload.orientation["mode"] == "current-workspace"
    assert payload.orientation["status"] == "bounded-segment"
    assert payload.orientation["active_resume_kind"] == "bounded_segment"
    assert payload.orientation["active_resume_origin"] == "continuation.bounded_segment"
    assert payload.orientation["active_resume_pointer"] == resume_file
    _assert_no_resume_compat_aliases(payload.orientation)
    assert payload.orientation["has_local_recovery_target"] is True
    assert "resume-work" in str(payload.orientation["continue_command"])
    assert "suggest-next" in str(payload.orientation["fast_next_command"])
    assert any(action.startswith("Run `gpd resume`") for action in payload.next_actions)


def test_build_runtime_hint_payload_prefers_canonical_bounded_segment_over_conflicting_live_overlay(
    tmp_path: Path,
) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"
    canonical_resume_file = "GPD/phases/07/.continue-here.md"
    overlay_resume_file = "GPD/phases/07/overlay.md"
    canonical_path = project / canonical_resume_file
    overlay_path = project / overlay_resume_file
    canonical_path.parent.mkdir(parents=True, exist_ok=True)
    canonical_path.write_text("canonical\n", encoding="utf-8")
    overlay_path.write_text("overlay\n", encoding="utf-8")
    _write_canonical_continuation(project, resume_file=canonical_resume_file, phase="07", plan="03")
    _write_current_execution(
        project,
        session_id="sess-conflict",
        extra_execution={
            "phase": "07",
            "plan": "03",
            "segment_status": "paused",
            "resume_file": overlay_resume_file,
            "segment_id": "seg-overlay",
        },
    )

    payload = build_runtime_hint_payload(
        project,
        data_root=data_root,
        include_cost=False,
        include_workflow_presets=False,
    )

    assert payload.orientation["active_resume_kind"] == "bounded_segment"
    assert payload.orientation["active_resume_origin"] == "continuation.bounded_segment"
    assert payload.orientation["active_resume_pointer"] == canonical_resume_file
    assert payload.orientation["status"] == "bounded-segment"
    _assert_no_resume_compat_aliases(payload.orientation)
    assert payload.execution is not None
    assert payload.execution["resume_file"] == overlay_resume_file


def test_build_runtime_hint_payload_rediscovery_branch_handles_non_resumable_current_project(
    tmp_path: Path,
) -> None:
    current_project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"
    missing_handoff = current_project / "GPD" / "phases" / "04" / ".continue-here.md"
    missing_handoff.parent.mkdir(parents=True, exist_ok=True)

    record_recent_project(
        current_project,
        session_data={
            "last_date": "2026-03-27T12:05:00+00:00",
            "stopped_at": "Phase 04",
            "resume_file": "GPD/phases/04/.continue-here.md",
        },
        store_root=data_root,
    )

    payload = build_runtime_hint_payload(
        current_project,
        data_root=data_root,
        base_ready=True,
        latex_capability=_latex_capability(),
    )

    assert missing_handoff.exists() is False
    assert payload.recovery["current_project"] is not None
    assert payload.recovery["current_project"]["resume_file"] == "GPD/phases/04/.continue-here.md"
    assert payload.recovery["current_project"]["resumable"] is False
    assert payload.recovery["current_project"]["resume_file_reason"] == "resume file missing"
    assert payload.recovery["current_project_summary"] == "last seen 2026-03-27T12:05:00+00:00; stopped at Phase 04; resume file missing"
    assert payload.recovery["project_reentry_summary"] == "GPD found recent projects on this machine, but none are ready to reopen automatically."
    assert payload.orientation["mode"] == "recent-projects"
    assert payload.orientation["primary_command"] == "gpd resume --recent"
    assert payload.orientation["active_resume_kind"] is None
    assert payload.orientation["has_local_recovery_target"] is False
    assert any("resume --recent" in action for action in payload.next_actions)
    assert any("After selecting a workspace" in action for action in payload.next_actions)
    assert any("suggest-next" in action for action in payload.next_actions)


def test_build_runtime_hint_payload_surfaces_recent_project_missing_handoff_provenance(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    data_root = tmp_path / "data"
    recent_project_root = tmp_path / "recent-project"
    recent_project_root.mkdir()
    missing_resume_file = "GPD/phases/04/.continue-here.md"
    current_project = {
        "source": "recent_project",
        "project_root": recent_project_root.resolve(strict=False).as_posix(),
        "resume_file": missing_resume_file,
        "resume_file_available": False,
        "resume_file_reason": "resume file missing",
        "resumable": False,
        "recoverable": False,
        "last_session_at": "2026-03-27T12:05:00+00:00",
        "stopped_at": "Phase 04",
        "hostname": "builder-04",
        "platform": "Linux 6.1 x86_64",
        "resume_target_kind": "handoff",
        "source_kind": "continuation.handoff",
    }
    fake_reentry = SimpleNamespace(
        resolved_project_root=recent_project_root.resolve(strict=False),
        auto_selected=True,
        mode="recent-projects",
        selected_candidate=current_project,
        candidates=[current_project],
    )

    monkeypatch.setattr(
        "gpd.core.runtime_hints._resume_context",
        lambda _cwd, data_root=None: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "resume_candidates": [],
            "has_live_execution": False,
        },
    )
    monkeypatch.setattr("gpd.core.runtime_hints.resolve_project_reentry", lambda *args, **kwargs: fake_reentry)
    monkeypatch.setattr(
        "gpd.core.runtime_hints._selected_reentry_candidate",
        lambda *args, **kwargs: current_project,
    )

    payload = build_runtime_hint_payload(
        workspace,
        data_root=data_root,
        include_cost=False,
        include_workflow_presets=False,
    )

    assert payload.recovery["current_project"] is not None
    assert payload.recovery["current_project"]["session_hostname"] == "builder-04"
    assert payload.recovery["current_project"]["session_platform"] == "Linux 6.1 x86_64"
    assert payload.recovery["current_project"]["session_last_date"] == "2026-03-27T12:05:00+00:00"
    assert payload.recovery["current_project"]["session_stopped_at"] == "Phase 04"
    assert payload.orientation["session_hostname"] == "builder-04"
    assert payload.orientation["session_platform"] == "Linux 6.1 x86_64"
    assert payload.orientation["session_last_date"] == "2026-03-27T12:05:00+00:00"
    assert payload.orientation["session_stopped_at"] == "Phase 04"
    assert payload.orientation["recorded_continuity_handoff_file"] == missing_resume_file
    assert payload.orientation["missing_continuity_handoff_file"] == missing_resume_file


def test_build_runtime_hint_payload_formats_generic_runtime_follow_up_when_runtime_detection_fails(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"
    resume_file = project / "GPD" / "phases" / "02" / ".continue-here.md"
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text("resume\n", encoding="utf-8")

    record_recent_project(
        project,
        session_data={
            "last_date": "2026-03-27T12:05:00+00:00",
            "stopped_at": "Phase 02",
            "resume_file": "GPD/phases/02/.continue-here.md",
        },
        store_root=data_root,
    )
    _write_current_execution(
        project,
        session_id="sess-011",
        extra_execution={
            "phase": "02",
            "plan": "01",
            "resume_file": "GPD/phases/02/.continue-here.md",
        },
    )
    monkeypatch.setattr("gpd.core.runtime_hints._runtime_command", lambda *args, **kwargs: None)

    payload = build_runtime_hint_payload(
        project,
        data_root=data_root,
        base_ready=True,
        latex_capability=_latex_capability(),
    )

    assert payload.orientation["continue_command"] == "runtime `resume-work`"
    assert payload.orientation["fast_next_command"] == "runtime `suggest-next`"
    assert "runtime `resume-work` continues in-runtime from the selected project state." in payload.next_actions
    assert "runtime `suggest-next` is the fastest post-resume next command when you only need the next action." in payload.next_actions
    assert not any("`runtime `resume-work``" in action for action in payload.next_actions)


def test_runtime_hints_runtime_command_delegates_to_shared_helper(tmp_path: Path) -> None:
    from gpd.core import runtime_hints

    with patch("gpd.core.runtime_hints.format_active_runtime_command", return_value="shared command") as mock_format:
        result = runtime_hints._runtime_command("resume-work", cwd=tmp_path)

    mock_format.assert_called_once_with("resume-work", cwd=tmp_path, fallback=None)
    assert result == "shared command"


def test_format_active_runtime_command_returns_none_when_no_runtime_is_detected() -> None:
    assert format_active_runtime_command("resume-work", detect_runtime=lambda **kwargs: None) is None


def test_format_active_runtime_command_formats_detected_runtime_command() -> None:
    runtime = _RUNTIME_NAMES[0]
    adapter = get_adapter(runtime)

    result = format_active_runtime_command("resume-work", detect_runtime=lambda **kwargs: runtime)

    assert result == adapter.format_command("resume-work")


@pytest.mark.parametrize(
    "detector_output",
    [
        _RUNTIME_WITH_ALIAS_AND_DISPLAY_NAME.display_name,
        next(
            alias
            for alias in _RUNTIME_WITH_ALIAS_AND_DISPLAY_NAME.selection_aliases
            if alias.casefold() != _RUNTIME_WITH_ALIAS_AND_DISPLAY_NAME.runtime_name.casefold()
        ),
    ],
)
def test_format_active_runtime_command_normalizes_detector_aliases_and_display_names(
    detector_output: str,
) -> None:
    descriptor = _RUNTIME_WITH_ALIAS_AND_DISPLAY_NAME
    adapter = get_adapter(descriptor.runtime_name)

    result = format_active_runtime_command("resume-work", detect_runtime=lambda **kwargs: detector_output)

    assert result == adapter.format_command("resume-work")


def test_format_active_runtime_command_logs_runtime_resolution_failures(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level("WARNING"):
        result = format_active_runtime_command(
            "resume-work",
            detect_runtime=lambda **kwargs: (_ for _ in ()).throw(RuntimeError("detector broke")),
            fallback="fallback command",
        )

    assert result == "fallback command"
    assert "Active runtime resolution failed: detector broke" in caplog.text


def test_format_active_runtime_command_uses_descriptor_public_surface_without_adapter_lookup() -> None:
    descriptor = SimpleNamespace(
        public_command_surface_prefix="/public:",
        command_prefix="/adapter-only:",
    )

    with patch(
        "gpd.core.runtime_command_surfaces.resolve_active_runtime_descriptor",
        return_value=descriptor,
    ), patch(
        "gpd.adapters.get_adapter",
        side_effect=AssertionError("adapter lookup should not be used"),
    ):
        assert format_active_runtime_command("resume-work") == "/public:resume-work"


def test_build_runtime_hint_payload_uses_generic_runtime_commands_when_no_install_authoritative_runtime(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"
    resume_file = project / "GPD" / "phases" / "02" / ".continue-here.md"
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text("resume\n", encoding="utf-8")

    record_recent_project(
        project,
        session_data={
            "last_date": "2026-03-27T12:05:00+00:00",
            "stopped_at": "Phase 02",
            "resume_file": "GPD/phases/02/.continue-here.md",
        },
        store_root=data_root,
    )
    _write_current_execution(
        project,
        session_id="sess-013",
        extra_execution={
            "phase": "02",
            "plan": "01",
            "resume_file": "GPD/phases/02/.continue-here.md",
        },
    )
    monkeypatch.setattr(
        "gpd.hooks.runtime_detect.detect_runtime_for_gpd_use",
        lambda *args, **kwargs: "unknown",
    )

    payload = build_runtime_hint_payload(
        project,
        data_root=data_root,
        base_ready=True,
        latex_capability=_latex_capability(),
    )

    assert payload.orientation["continue_command"] == "runtime `resume-work`"
    assert payload.orientation["fast_next_command"] == "runtime `suggest-next`"
    assert "runtime `resume-work` continues in-runtime from the selected project state." in payload.next_actions
    assert "runtime `suggest-next` is the fastest post-resume next command when you only need the next action." in payload.next_actions
    assert not any(action.startswith("runtime-under-test ") for action in payload.next_actions)


@pytest.mark.parametrize("include_local_conflict", [False, True])
def test_build_runtime_hint_payload_uses_global_runtime_commands_when_global_install_is_effective(
    tmp_path: Path, include_local_conflict: bool
) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"
    runtime = _RUNTIME_NAMES[0]
    adapter = get_adapter(runtime)
    home_dir = tmp_path / "home"
    global_config_dir = adapter.resolve_global_config_dir(home=home_dir)

    seed_complete_runtime_install(global_config_dir, runtime=runtime, install_scope="global", home=home_dir)
    if include_local_conflict:
        (project / adapter.local_config_dir_name).mkdir(parents=True, exist_ok=True)

    resume_file = project / "GPD" / "phases" / "02" / ".continue-here.md"
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text("resume\n", encoding="utf-8")

    record_recent_project(
        project,
        session_data={
            "last_date": "2026-03-27T12:05:00+00:00",
            "stopped_at": "Phase 02",
            "resume_file": "GPD/phases/02/.continue-here.md",
        },
        store_root=data_root,
    )
    _write_current_execution(
        project,
        session_id="sess-global-runtime",
        extra_execution={
            "phase": "02",
            "plan": "01",
            "resume_file": "GPD/phases/02/.continue-here.md",
        },
    )

    payload = build_runtime_hint_payload(
        project,
        data_root=data_root,
        base_ready=True,
        latex_capability=_latex_capability(),
    )

    continue_command = adapter.format_command("resume-work")
    fast_next_command = adapter.format_command("suggest-next")
    assert payload.orientation["continue_command"] == continue_command
    assert payload.orientation["fast_next_command"] == fast_next_command
    assert (
        f"`{fast_next_command}` is the fastest post-resume next command when you only need the next action."
        in payload.next_actions
    )
    assert "runtime `resume-work`" not in payload.orientation["continue_command"]
    assert "runtime `suggest-next`" not in payload.orientation["fast_next_command"]


def test_build_runtime_hint_payload_surfaces_runtime_metadata_without_cost_summary_when_installed_runtime_is_effective(
    tmp_path: Path,
) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"
    runtime = _RUNTIME_NAMES[0]
    adapter = get_adapter(runtime)
    home_dir = tmp_path / "home"
    global_config_dir = adapter.resolve_global_config_dir(home=home_dir)

    seed_complete_runtime_install(global_config_dir, runtime=runtime, install_scope="global", home=home_dir)

    resume_file = project / "GPD" / "phases" / "02" / ".continue-here.md"
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text("resume\n", encoding="utf-8")
    _write_current_session(project, session_id="sess-runtime-only")
    _write_current_execution(
        project,
        session_id="sess-runtime-only",
        extra_execution={
            "phase": "02",
            "plan": "01",
            "resume_file": "GPD/phases/02/.continue-here.md",
        },
    )
    record_recent_project(
        project,
        session_data={
            "last_date": "2026-03-27T12:05:00+00:00",
            "stopped_at": "Phase 02",
            "resume_file": "GPD/phases/02/.continue-here.md",
        },
        store_root=data_root,
    )

    payload = build_runtime_hint_payload(
        project,
        data_root=data_root,
        include_cost=False,
        include_workflow_presets=False,
    )

    assert payload.cost == {}
    assert payload.source_meta["active_runtime"] == runtime
    assert payload.source_meta["current_session_id"] == "sess-runtime-only"
    assert payload.orientation["continue_command"] == adapter.format_command("resume-work")
    assert payload.orientation["fast_next_command"] == adapter.format_command("suggest-next")


def test_build_runtime_hint_payload_machine_change_only_keeps_local_resume_without_in_runtime_followups(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"
    monkeypatch.setattr(
        "gpd.core.runtime_hints._resume_context",
        lambda _cwd, data_root=None: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "resume_candidates": [],
            "has_live_execution": False,
            "machine_change_notice": (
                "Machine change detected: last active on old-host (Linux 5.15 x86_64); "
                "current machine new-host (Linux 6.1 x86_64). The project state is portable and does not require repair. "
                "Rerun the installer if runtime-local config may be stale on this machine."
            ),
        },
    )

    payload = build_runtime_hint_payload(
        project,
        data_root=data_root,
        include_cost=False,
        include_workflow_presets=False,
    )

    assert payload.orientation["mode"] == "idle"
    assert payload.orientation["status"] == "no-recovery"
    assert payload.orientation["has_local_recovery_target"] is False
    assert payload.orientation["machine_change_notice"] is not None
    assert not any(action.startswith("Run `gpd resume`") for action in payload.next_actions)
    assert not any("resume-work" in action for action in payload.next_actions)
    assert not any("suggest-next" in action for action in payload.next_actions)


def test_build_runtime_hint_payload_missing_handoff_keeps_local_resume_without_in_runtime_followups(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"
    monkeypatch.setattr(
        "gpd.core.runtime_hints._resume_context",
        lambda _cwd, data_root=None: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "resume_candidates": [
                {
                    "kind": "continuity_handoff",
                    "origin": "continuation.handoff",
                    "status": "missing",
                    "resume_file": "GPD/phases/04/.continue-here.md",
                }
            ],
            "has_live_execution": False,
        },
    )

    payload = build_runtime_hint_payload(
        project,
        data_root=data_root,
        include_cost=False,
        include_workflow_presets=False,
    )

    assert payload.orientation["mode"] == "current-workspace"
    assert payload.orientation["status"] == "missing-handoff"
    assert payload.orientation["has_local_recovery_target"] is False
    assert any(action.startswith("Run `gpd resume`") for action in payload.next_actions)
    assert not any("resume-work" in action for action in payload.next_actions)
    assert not any("suggest-next" in action for action in payload.next_actions)


def test_build_runtime_hint_payload_include_recovery_false_ignores_recent_project_state(
    tmp_path: Path, monkeypatch
) -> None:
    workspace = tmp_path / "outside-workspace"
    workspace.mkdir()
    recent_project = _bootstrap_recoverable_project(tmp_path / "recent-project")
    data_root = tmp_path / "data"

    record_recent_project(
        recent_project,
        session_data={
            "last_date": "2026-03-27T12:20:00+00:00",
            "stopped_at": "Phase 06",
            "resume_file": "GPD/phases/06/.continue-here.md",
        },
        store_root=data_root,
    )

    monkeypatch.setattr(
        "gpd.core.runtime_hints.resolve_project_reentry",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("resolve_project_reentry should not run")),
    )
    monkeypatch.setattr(
        "gpd.core.runtime_hints.list_recent_projects",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("list_recent_projects should not run")),
    )
    monkeypatch.setattr(
        "gpd.core.runtime_hints._resume_context",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("_resume_context should not run")),
    )

    payload = build_runtime_hint_payload(
        workspace,
        data_root=data_root,
        include_recovery=False,
        include_cost=False,
        include_workflow_presets=False,
    )

    assert payload.source_meta["project_root"] == workspace.resolve(strict=False).as_posix()
    assert payload.recovery == {}
    assert payload.orientation == {}
    assert payload.next_actions == []
    assert recent_project.resolve(strict=False).as_posix() not in payload.source_meta["project_root"]


def test_build_runtime_hint_payload_suppresses_duplicate_resume_recovery_nudge(tmp_path: Path) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"
    resume_file = project / "GPD" / "phases" / "03" / ".continue-here.md"
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text("resume\n", encoding="utf-8")

    _write_current_execution(project, session_id="sess-012")

    payload = build_runtime_hint_payload(
        project,
        data_root=data_root,
        include_cost=False,
        include_workflow_presets=False,
    )

    resume_actions = [action for action in payload.next_actions if "`gpd resume`" in action]

    assert len(resume_actions) == 1
    assert "runtime `resume-work` continues in-runtime from the selected project state." in payload.next_actions
    assert "runtime `suggest-next` is the fastest post-resume next command when you only need the next action." in payload.next_actions


def test_workflow_preset_surface_note_is_command_oriented_and_preview_first() -> None:
    note = workflow_preset_surface_note()

    assert "gpd presets list" in note
    assert "gpd presets show <preset>" in note
    assert "gpd presets apply <preset> --dry-run" in note
    assert "preview" in note
    assert "before writing them" in note
    assert "changed knobs" in note
