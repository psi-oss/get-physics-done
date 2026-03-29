from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from gpd.core.costs import UsageRecord, usage_ledger_path
from gpd.core.recent_projects import record_recent_project
from gpd.core.runtime_hints import build_runtime_hint_payload, workflow_preset_surface_note
from gpd.core.surface_phrases import cost_inspect_action


def _bootstrap_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "GPD" / "observability").mkdir(parents=True, exist_ok=True)
    return project


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


def _write_usage_record(*, data_root: Path, project_root: Path, session_id: str) -> None:
    ledger_path = usage_ledger_path(data_root)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    record = UsageRecord(
        record_id="usage-001",
        recorded_at="2026-03-27T12:00:00+00:00",
        runtime="codex",
        model="gpt-5.4",
        session_id=session_id,
        workspace_root=project_root.resolve(strict=False).as_posix(),
        project_root=project_root.resolve(strict=False).as_posix(),
        input_tokens=100,
        output_tokens=25,
        total_tokens=125,
    )
    ledger_path.write_text(record.model_dump_json() + "\n", encoding="utf-8")


def _latex_capability(**overrides: object) -> dict[str, object]:
    capability = {
        "compiler_available": True,
        "compiler_path": "/usr/bin/pdflatex",
        "distribution": "TeX Live",
        "bibtex_available": True,
        "latexmk_available": True,
        "kpsewhich_available": True,
        "warnings": [],
    }
    capability.update(overrides)
    return capability


def _fake_cost_summary(workspace: Path, **overrides: object) -> SimpleNamespace:
    payload: dict[str, object] = {
        "current_session_id": "sess-cost",
        "active_runtime": "codex",
        "model_profile": "review",
        "runtime_model_selection": "runtime defaults",
        "profile_tier_mix": {},
        "workspace_root": workspace.resolve(strict=False).as_posix(),
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
    assert payload.source_meta["latex_capability"]["bibtex_available"] is True
    assert payload.source_meta["latex_capability"]["latexmk_available"] is False
    assert payload.source_meta["latex_capability"]["kpsewhich_available"] is False
    assert payload.source_meta["latex_available"] is True

    assert payload.execution is not None
    assert payload.execution["status_classification"] == "waiting"
    assert payload.execution["review_reason"] == "first-result review pending"

    assert payload.recovery["recent_projects_count"] == 1
    assert payload.recovery["current_project"]["resumable"] is True
    assert payload.recovery["current_project"]["resume_file_available"] is True
    assert payload.orientation["mode"] == "current-workspace"
    assert payload.orientation["primary_command"] == "gpd resume"
    assert "bounded resumable execution segment" in str(payload.orientation["primary_reason"])
    assert payload.orientation["resume_mode"] == "bounded_segment"
    assert payload.orientation["execution_resume_file"] == "GPD/phases/03/.continue-here.md"
    assert payload.orientation["execution_resume_file_source"] == "current_execution"
    assert payload.orientation["segment_candidates_count"] >= 1
    assert payload.orientation["has_local_recovery_target"] is True
    assert "resume-work" in str(payload.orientation["continue_command"])
    assert "suggest-next" in str(payload.orientation["fast_next_command"])

    assert payload.cost["project_root"] == project.resolve(strict=False).as_posix()
    assert "workspace_root" not in payload.cost
    assert payload.cost["project"]["record_count"] == 1
    assert payload.cost["project"]["usage_status"] == "measured"
    assert payload.cost["project"]["interpretation"] == "tokens measured; USD unavailable"
    assert payload.cost["profile_tier_mix"] == {"tier-1": 12, "tier-2": 10, "tier-3": 1}
    assert any("pricing snapshot" in item for item in payload.cost["guidance"])

    assert payload.workflow_presets["ready"] == 5
    assert payload.workflow_presets["degraded"] == 0
    assert payload.workflow_presets["blocked"] == 0
    assert payload.workflow_presets["latex_capability"]["paper_build_ready"] is True
    assert payload.workflow_presets["latex_capability"]["arxiv_submission_ready"] is True

    assert payload.cost["advisory"]["state"] == "unavailable"
    assert "next_action" not in payload.cost["advisory"]
    assert any(action.startswith("Run `gpd resume`") for action in payload.next_actions)
    assert not any("gpd cost" in action for action in payload.next_actions)
    assert not any("Workflow presets ready" in action for action in payload.next_actions)
    assert any("continues in-runtime from the selected project state" in action for action in payload.next_actions)
    assert any("fastest post-resume next command" in action for action in payload.next_actions)
    assert len(payload.next_actions) == len(set(payload.next_actions))


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
    assert payload.workflow_presets["latex_capability"]["paper_build_ready"] is False
    assert any("BibTeX support" in action for action in payload.next_actions)
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
    assert payload.recovery["recent_projects_count"] == 1
    assert payload.recovery["current_project"] is None
    assert payload.orientation["mode"] == "recent-projects"
    assert payload.orientation["primary_command"] == "gpd resume --recent"
    assert payload.orientation["resume_mode"] is None
    assert payload.orientation["segment_candidates_count"] == 0
    assert payload.orientation["has_local_recovery_target"] is False
    assert payload.cost["project_root"] == project.resolve(strict=False).as_posix()
    assert "workspace_root" not in payload.cost
    assert payload.workflow_presets["blocked"] == 5
    assert any("resume --recent" in action for action in payload.next_actions)
    assert not any("resume-work" in action for action in payload.next_actions)
    assert not any("suggest-next" in action for action in payload.next_actions)
    assert any("base runtime-readiness" in action for action in payload.next_actions)


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
            "codex only exposes best-effort usage telemetry through notify-hook, so missing turns remain unavailable instead of being guessed."
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
            "codex does not currently expose a GPD-managed usage telemetry collection path, so `gpd cost` may remain empty even when work runs."
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

    assert payload.recovery["recent_projects_count"] == 0
    assert payload.orientation["mode"] == "current-workspace"
    assert payload.orientation["primary_command"] == "gpd resume"
    assert payload.orientation["resume_mode"] == "bounded_segment"
    assert payload.orientation["execution_resume_file"] == "GPD/phases/05/.continue-here.md"
    assert payload.orientation["execution_resume_file_source"] == "current_execution"
    assert any(action.startswith("Run `gpd resume`") for action in payload.next_actions)


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
    assert payload.orientation["mode"] == "recent-projects"
    assert payload.orientation["primary_command"] == "gpd resume --recent"
    assert payload.orientation["resume_mode"] is None
    assert payload.orientation["has_local_recovery_target"] is False
    assert any("resume --recent" in action for action in payload.next_actions)
    assert not any("After selecting a workspace" in action for action in payload.next_actions)
    assert not any("suggest-next" in action for action in payload.next_actions)


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


def test_build_runtime_hint_payload_machine_change_only_keeps_local_resume_without_in_runtime_followups(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"
    monkeypatch.setattr(
        "gpd.core.runtime_hints._resume_context",
        lambda _cwd: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "segment_candidates": [],
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

    assert payload.orientation["mode"] == "current-workspace"
    assert payload.orientation["status"] == "workspace-recovery"
    assert payload.orientation["has_local_recovery_target"] is False
    assert any(action.startswith("Run `gpd resume`") for action in payload.next_actions)
    assert not any("resume-work" in action for action in payload.next_actions)
    assert not any("suggest-next" in action for action in payload.next_actions)


def test_build_runtime_hint_payload_missing_handoff_keeps_local_resume_without_in_runtime_followups(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"
    monkeypatch.setattr(
        "gpd.core.runtime_hints._resume_context",
        lambda _cwd: {
            "planning_exists": True,
            "state_exists": True,
            "roadmap_exists": True,
            "project_exists": True,
            "segment_candidates": [],
            "has_live_execution": False,
            "missing_session_resume_file": "GPD/phases/04/.continue-here.md",
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
