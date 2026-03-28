from __future__ import annotations

import json
from pathlib import Path

from gpd.core.costs import UsageRecord, usage_ledger_path
from gpd.core.recent_projects import record_recent_project
from gpd.core.runtime_hints import build_runtime_hint_payload


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


def _write_current_execution(project: Path, *, session_id: str) -> None:
    execution_path = project / "GPD" / "observability" / "current-execution.json"
    execution_path.write_text(
        json.dumps(
            {
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
        ),
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
    assert set(dumped) == {"source_meta", "execution", "recovery", "cost", "workflow_presets", "next_actions"}
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

    assert payload.cost["workspace_root"] == project.resolve(strict=False).as_posix()
    assert payload.cost["project"]["record_count"] == 1
    assert payload.cost["project"]["usage_status"] == "measured"
    assert any("pricing snapshot" in item for item in payload.cost["guidance"])

    assert payload.workflow_presets["ready"] == 5
    assert payload.workflow_presets["degraded"] == 0
    assert payload.workflow_presets["blocked"] == 0
    assert payload.workflow_presets["latex_capability"]["paper_build_ready"] is True
    assert payload.workflow_presets["latex_capability"]["arxiv_submission_ready"] is True

    assert "Run `gpd resume` to inspect the current recovery snapshot for this project." in payload.next_actions
    assert any("pricing snapshot" in action for action in payload.next_actions)
    assert any("latexmk" in action for action in payload.next_actions)
    assert any("kpsewhich" in action for action in payload.next_actions)
    assert any("Workflow presets ready" in action for action in payload.next_actions)
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
    assert payload.cost["workspace_root"] == project.resolve(strict=False).as_posix()
    assert payload.workflow_presets["blocked"] == 5
    assert any("resume --recent" in action for action in payload.next_actions)
    assert any("base runtime-readiness" in action for action in payload.next_actions)
