from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from gpd.adapters import get_adapter, list_runtimes
from gpd.core.recent_projects import record_recent_project
from gpd.core.runtime_hints import build_runtime_hint_payload


def _bootstrap_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "GPD" / "observability").mkdir(parents=True, exist_ok=True)
    (project / "GPD" / "STATE.md").write_text("# Research State\n", encoding="utf-8")
    (project / "GPD" / "ROADMAP.md").write_text("# Roadmap\n", encoding="utf-8")
    (project / "GPD" / "PROJECT.md").write_text("# Project\n", encoding="utf-8")
    return project


def _write_current_session(project: Path, *, session_id: str) -> None:
    (project / "GPD" / "observability" / "current-session.json").write_text(
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
    (project / "GPD" / "observability" / "current-execution.json").write_text(
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


def test_build_runtime_hint_payload_reuses_one_resolved_runtime_for_commands_and_source_meta(
    tmp_path: Path,
) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"
    runtime = list_runtimes()[0]
    alternate_runtime = next((candidate for candidate in list_runtimes() if candidate != runtime), runtime)
    resume_file = project / "GPD" / "phases" / "03" / ".continue-here.md"
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text("resume\n", encoding="utf-8")

    record_recent_project(
        project,
        session_data={
            "last_date": "2026-03-27T12:05:00+00:00",
            "stopped_at": "Phase 03",
            "resume_file": "GPD/phases/03/.continue-here.md",
        },
        store_root=data_root,
    )
    _write_current_session(project, session_id="sess-runtime-consistency")
    _write_current_execution(project, session_id="sess-runtime-consistency")

    def unstable_detector(*, cwd=None, home=None):
        if unstable_detector.calls == 0:
            unstable_detector.calls += 1
            return runtime
        return alternate_runtime

    unstable_detector.calls = 0  # type: ignore[attr-defined]

    with patch("gpd.hooks.runtime_detect.detect_runtime_for_gpd_use", unstable_detector), patch(
        "gpd.hooks.runtime_detect.detect_runtime_install_target",
        side_effect=lambda runtime_name, cwd=None, home=None: SimpleNamespace(
            config_dir=project / "runtime-install",
            install_scope="local",
        )
        if runtime_name == runtime
        else None,
    ):
        payload = build_runtime_hint_payload(
            project,
            data_root=data_root,
            include_cost=False,
            include_workflow_presets=False,
        )

    adapter = get_adapter(runtime)
    assert unstable_detector.calls == 1  # type: ignore[attr-defined]
    assert payload.source_meta["active_runtime"] == runtime
    assert payload.orientation["continue_command"] == adapter.format_command("resume-work")
    assert payload.orientation["fast_next_command"] == adapter.format_command("suggest-next")


def test_build_runtime_hint_payload_keeps_ambient_runtime_metadata_without_native_commands_when_no_install_runtime_exists(
    tmp_path: Path,
) -> None:
    project = _bootstrap_project(tmp_path)
    data_root = tmp_path / "data"
    runtime = list_runtimes()[0]
    alternate_runtime = next((candidate for candidate in list_runtimes() if candidate != runtime), runtime)
    resume_file = project / "GPD" / "phases" / "03" / ".continue-here.md"
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text("resume\n", encoding="utf-8")

    record_recent_project(
        project,
        session_data={
            "last_date": "2026-03-27T12:05:00+00:00",
            "stopped_at": "Phase 03",
            "resume_file": "GPD/phases/03/.continue-here.md",
        },
        store_root=data_root,
    )
    _write_current_execution(project, session_id="sess-runtime-fallback")

    fake_summary = SimpleNamespace(
        current_session_id="sess-cost-fallback",
        active_runtime=runtime,
        model_profile="review",
        project=SimpleNamespace(record_count=0, usage_status="unavailable", cost_status="unavailable"),
        budget_thresholds=[],
        pricing_snapshot_configured=False,
    )

    with patch("gpd.core.runtime_hints._installed_runtime_for_surface", return_value=None), patch(
        "gpd.core.runtime_hints.build_cost_summary",
        return_value=fake_summary,
    ), patch(
        "gpd.hooks.runtime_detect.detect_runtime_for_gpd_use",
        return_value=alternate_runtime,
    ):
        payload = build_runtime_hint_payload(
            project,
            data_root=data_root,
            include_workflow_presets=False,
        )

    assert payload.source_meta["active_runtime"] == runtime
    assert payload.source_meta["current_session_id"] == "sess-cost-fallback"
    assert payload.orientation["continue_command"] == "runtime `resume-work`"
    assert payload.orientation["fast_next_command"] == "runtime `suggest-next`"
    assert "resume-work" in payload.orientation["continue_command"]
    assert "suggest-next" in payload.orientation["fast_next_command"]
