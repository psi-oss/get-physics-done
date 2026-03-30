"""Focused regression tests for session-scoped gpd.core.observability behavior."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path


def _bootstrap_project(tmp_path: Path) -> Path:
    planning = tmp_path / "GPD"
    planning.mkdir()
    return tmp_path


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _read_state_json(project: Path) -> dict[str, object]:
    return json.loads((project / "GPD" / "state.json").read_text(encoding="utf-8"))


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _observability_sync_helper():
    import gpd.core.observability as observability

    for helper_name in (
        "sync_execution_visibility_from_canonical_continuation",
        "sync_current_execution_from_canonical_continuation",
        "sync_current_execution_visibility_from_canonical_continuation",
        "sync_live_execution_visibility_from_canonical_continuation",
        "sync_execution_visibility_cache_from_continuation",
        "sync_execution_cache_from_canonical_continuation",
        "_sync_execution_visibility_from_canonical_continuation",
    ):
        helper = getattr(observability, helper_name, None)
        if callable(helper):
            return helper
    raise AssertionError("Expected a canonical-continuation observability sync helper to be available")


def _iso_minutes_ago(minutes: int) -> str:
    return (datetime.now(UTC) - timedelta(minutes=minutes)).isoformat()


def test_ensure_session_writes_single_session_log_and_current_pointer(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import ensure_session

    session = ensure_session(project, source="cli", metadata={"argv": ["execute-phase"]}, command="execute-phase")
    assert session is not None

    observability_dir = project / "GPD" / "observability"
    current_session_path = observability_dir / "current-session.json"
    sessions_dir = observability_dir / "sessions"
    session_logs = sorted(sessions_dir.glob("*.jsonl"))

    assert current_session_path.exists()
    assert len(session_logs) == 1

    current_session = json.loads(current_session_path.read_text(encoding="utf-8"))
    assert current_session["session_id"] == session.session_id
    assert current_session["status"] == "active"

    events = _read_jsonl(session_logs[0])
    assert len(events) == 1
    assert events[0]["category"] == "session"
    assert events[0]["name"] == "lifecycle"
    assert events[0]["action"] == "start"
    assert events[0]["command"] == "execute-phase"
    assert events[0]["data"]["source"] == "cli"


def test_ensure_session_resolves_nested_workspace_to_project_root(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    nested = project / "workspace" / "nested"
    nested.mkdir(parents=True)
    monkeypatch.chdir(nested)

    from gpd.core.observability import ensure_session

    session = ensure_session(nested, source="cli", command="execute-phase")
    assert session is not None
    assert (project / "GPD" / "observability" / "current-session.json").exists()
    assert not (nested / "GPD" / "observability").exists()


def test_resolve_project_root_uses_shared_root_resolution_for_nested_workspace(tmp_path: Path) -> None:
    project = _bootstrap_project(tmp_path)
    nested = project / "workspace" / "nested"
    nested.mkdir(parents=True)

    from gpd.core.observability import resolve_project_root

    resolved = resolve_project_root(nested)

    assert resolved == project


def test_observe_event_appends_session_event_and_finish_marker(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import ensure_session, observe_event, show_events

    session = ensure_session(project, source="trace", command="trace start")
    assert session is not None

    result = observe_event(
        project,
        category="trace",
        name="trace_stop",
        action="stop",
        status="ok",
        session_id=session.session_id,
        data={"phase": "03"},
        end_session=True,
    )

    assert result.recorded is True
    session_log = project / "GPD" / "observability" / "sessions" / f"{session.session_id}.jsonl"
    events = _read_jsonl(session_log)
    assert len(events) == 3
    assert events[0]["category"] == "session"
    assert events[1]["category"] == "trace"
    assert events[1]["name"] == "trace_stop"
    assert events[2]["category"] == "session"
    assert events[2]["action"] == "finish"
    assert events[2]["status"] == "ok"
    assert events[2]["data"]["ended_by"]["name"] == "trace_stop"

    current_session = json.loads((project / "GPD" / "observability" / "current-session.json").read_text(encoding="utf-8"))
    assert current_session["session_id"] == session.session_id
    assert current_session["status"] == "ok"

    shown = show_events(project, session=session.session_id)
    assert shown.count == 3


def test_execution_events_write_current_execution_snapshot(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import ensure_session, get_current_execution, observe_event

    session = ensure_session(project, source="cli", command="execute-phase")
    assert session is not None

    observe_event(
        project,
        category="execution",
        name="segment",
        action="start",
        status="active",
        command="execute-phase",
        phase="03",
        plan="01",
        session_id=session.session_id,
        data={
            "execution": {
                "workflow": "execute-phase",
                "segment_id": "seg-01",
                "segment_reason": "task_budget",
                "review_cadence": "adaptive",
                "current_task": "Assemble benchmark",
            }
        },
    )
    observe_event(
        project,
        category="execution",
        name="gate",
        action="enter",
        status="ok",
        command="execute-phase",
        phase="03",
        plan="01",
        session_id=session.session_id,
        data={
            "execution": {
                "checkpoint_reason": "first_result",
                "first_result_ready": True,
                "first_result_gate_pending": True,
                "last_result_label": "Benchmark reproduction",
            }
        },
    )

    snapshot = get_current_execution(project)
    assert snapshot is not None
    assert snapshot.segment_id == "seg-01"
    assert snapshot.waiting_for_review is True
    assert snapshot.first_result_gate_pending is True
    assert snapshot.last_result_label == "Benchmark reproduction"
    assert snapshot.downstream_locked is True


def test_execution_events_dual_write_durable_bounded_segment_from_resumable_snapshot(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import ensure_session, observe_event

    session = ensure_session(project, source="cli", command="execute-phase")
    assert session is not None

    resume_file = project / "GPD" / "phases" / "05-test" / ".continue-here.md"
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text("", encoding="utf-8")

    observe_event(
        project,
        category="execution",
        name="segment",
        action="start",
        status="active",
        command="execute-phase",
        phase="05",
        plan="01",
        session_id=session.session_id,
        data={"execution": {"segment_id": "seg-resume", "current_task": "Keep working"}},
    )
    observe_event(
        project,
        category="execution",
        name="segment",
        action="pause",
        status="ok",
        command="execute-phase",
        phase="05",
        plan="01",
        session_id=session.session_id,
        data={
            "execution": {
                "segment_status": "awaiting_user",
                "resume_file": "GPD/phases/05-test/.continue-here.md",
            }
        },
    )

    current_execution = json.loads((project / "GPD" / "observability" / "current-execution.json").read_text(encoding="utf-8"))
    assert current_execution["segment_status"] == "awaiting_user"
    assert current_execution["resume_file"] == "GPD/phases/05-test/.continue-here.md"

    state = _read_state_json(project)
    bounded_segment = state["continuation"]["bounded_segment"]
    assert bounded_segment["resume_file"] == "GPD/phases/05-test/.continue-here.md"
    assert bounded_segment["phase"] == "05"
    assert bounded_segment["plan"] == "01"
    assert bounded_segment["segment_status"] == "awaiting_user"
    assert bounded_segment["source_session_id"] == session.session_id


def test_execution_events_clear_durable_bounded_segment_when_execution_becomes_non_resumable(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import ensure_session, get_current_execution, observe_event

    session = ensure_session(project, source="cli", command="execute-phase")
    assert session is not None

    resume_file = project / "GPD" / "phases" / "05-test" / ".continue-here.md"
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text("", encoding="utf-8")

    (project / "GPD" / "state.json").write_text(
        json.dumps(
            {
                "continuation": {
                    "bounded_segment": {
                        "resume_file": "GPD/phases/05-test/.continue-here.md",
                        "phase": "05",
                        "plan": "01",
                        "segment_status": "paused",
                        "updated_at": "2026-03-14T12:00:00+00:00",
                    }
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    observe_event(
        project,
        category="execution",
        name="segment",
        action="start",
        status="active",
        command="execute-phase",
        phase="05",
        plan="01",
        session_id=session.session_id,
        data={"execution": {"segment_id": "seg-clear", "current_task": "Keep working"}},
    )

    snapshot = get_current_execution(project)
    assert snapshot is not None
    assert snapshot.resume_file is None

    state = _read_state_json(project)
    assert state["continuation"]["bounded_segment"] is None

    observe_event(
        project,
        category="execution",
        name="segment",
        action="finish",
        status="ok",
        command="execute-phase",
        phase="05",
        plan="01",
        session_id=session.session_id,
        data={"execution": {"segment_status": "completed"}},
    )

    assert get_current_execution(project) is None
    state = _read_state_json(project)
    assert state["continuation"]["bounded_segment"] is None


def test_sync_execution_visibility_from_canonical_continuation_updates_live_caches_and_preserves_provenance(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    resume_file = project / "GPD" / "phases" / "03-analysis" / ".continue-here.md"
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text("", encoding="utf-8")

    state = {
        "intermediate_results": [
            {
                "id": "R-canonical",
                "equation": "F = ma",
                "description": "Canonical benchmark reproduction",
                "phase": "03",
            }
        ],
        "continuation": {
            "handoff": {"last_result_id": "R-canonical"},
            "bounded_segment": {
                "resume_file": "GPD/phases/03-analysis/.continue-here.md",
                "phase": "03",
                "plan": "01",
                "segment_id": "seg-7",
                "segment_status": "paused",
                "transition_id": "transition-7",
                "last_result_id": "R-canonical",
                "updated_at": "2026-03-29T12:00:00+00:00",
                "source_session_id": "sess-7",
                "recorded_by": "state_record_session",
            },
        },
    }
    _write_json(project / "GPD" / "state.json", state)

    current_execution = {
        "session_id": "sess-live",
        "phase": "03",
        "plan": "01",
        "segment_id": "seg-7",
        "segment_status": "paused",
        "resume_file": "GPD/phases/03-analysis/.continue-here.md",
        "transition_id": "transition-7",
        "current_task": "Keep working",
        "last_result_id": "R-old",
        "last_result_label": "Old label",
        "updated_at": "2026-03-29T12:05:00+00:00",
    }
    observability_dir = project / "GPD" / "observability"
    _write_json(observability_dir / "current-execution.json", current_execution)

    head = {
        "execution": {
            **current_execution,
            "last_result_id": "R-old",
            "last_result_label": "Old label",
        },
        "bounded_segment": {
            "resume_file": "GPD/phases/03-analysis/.continue-here.md",
            "phase": "03",
            "plan": "01",
            "segment_id": "seg-7",
            "segment_status": "paused",
            "transition_id": "transition-7",
            "last_result_id": "R-old",
            "updated_at": "2026-03-29T12:05:00+00:00",
        },
        "last_applied_seq": 11,
        "last_applied_event_id": "evt-head-11",
        "recorded_at": "2026-03-29T12:05:00+00:00",
    }
    from gpd.core.execution_lineage import project_execution_lineage_head, write_execution_lineage_head

    write_execution_lineage_head(
        project,
        project_execution_lineage_head(
            head["execution"],
            bounded_segment=head["bounded_segment"],
            last_applied_seq=head["last_applied_seq"],
            last_applied_event_id=head["last_applied_event_id"],
            recorded_at=head["recorded_at"],
        ),
    )

    from gpd.core.observability import get_current_execution

    _observability_sync_helper()(project)

    reloaded_current = json.loads((observability_dir / "current-execution.json").read_text(encoding="utf-8"))
    reloaded_head = json.loads((project / "GPD" / "lineage" / "execution-head.json").read_text(encoding="utf-8"))
    snapshot = get_current_execution(project)

    assert reloaded_current["last_result_id"] == "R-canonical"
    assert reloaded_current["last_result_label"] == "Canonical benchmark reproduction"
    assert reloaded_current["updated_at"] == "2026-03-29T12:05:00+00:00"
    assert reloaded_current["segment_id"] == "seg-7"
    assert reloaded_current["transition_id"] == "transition-7"

    assert reloaded_head["execution"]["last_result_id"] == "R-canonical"
    assert reloaded_head["execution"]["last_result_label"] == "Canonical benchmark reproduction"
    assert reloaded_head["execution"]["updated_at"] == "2026-03-29T12:05:00+00:00"
    assert reloaded_head["bounded_segment"]["last_result_id"] == "R-canonical"
    assert reloaded_head["last_applied_seq"] == 11
    assert reloaded_head["last_applied_event_id"] == "evt-head-11"
    assert reloaded_head["recorded_at"] == "2026-03-29T12:05:00+00:00"

    assert snapshot is not None
    assert snapshot.last_result_id == "R-canonical"
    assert snapshot.last_result_label == "Canonical benchmark reproduction"


def test_sync_execution_visibility_from_canonical_continuation_noops_without_live_execution(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    resume_file = project / "GPD" / "phases" / "03-analysis" / ".continue-here.md"
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text("", encoding="utf-8")

    _write_json(
        project / "GPD" / "state.json",
        {
            "intermediate_results": [
                {
                    "id": "R-canonical",
                    "equation": "F = ma",
                    "description": "Canonical benchmark reproduction",
                    "phase": "03",
                }
            ],
            "continuation": {
                "handoff": {"last_result_id": "R-canonical"},
                "bounded_segment": {
                    "resume_file": "GPD/phases/03-analysis/.continue-here.md",
                    "phase": "03",
                    "plan": "01",
                    "segment_id": "seg-7",
                    "segment_status": "paused",
                    "transition_id": "transition-7",
                    "last_result_id": "R-canonical",
                    "updated_at": "2026-03-29T12:00:00+00:00",
                },
            },
        },
    )

    _observability_sync_helper()(project)

    observability_dir = project / "GPD" / "observability"
    assert not (observability_dir / "current-execution.json").exists()
    assert not (project / "GPD" / "lineage" / "execution-head.json").exists()


def test_sync_execution_visibility_from_canonical_continuation_noops_on_conflicting_lane_identity(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    resume_file = project / "GPD" / "phases" / "03-analysis" / ".continue-here.md"
    resume_file.parent.mkdir(parents=True, exist_ok=True)
    resume_file.write_text("", encoding="utf-8")

    _write_json(
        project / "GPD" / "state.json",
        {
            "intermediate_results": [
                {
                    "id": "R-canonical",
                    "equation": "F = ma",
                    "description": "Canonical benchmark reproduction",
                    "phase": "03",
                }
            ],
            "continuation": {
                "handoff": {"last_result_id": "R-canonical"},
                "bounded_segment": {
                    "resume_file": "GPD/phases/03-analysis/.continue-here.md",
                    "phase": "03",
                    "plan": "01",
                    "segment_id": "seg-7",
                    "segment_status": "paused",
                    "transition_id": "transition-7",
                    "last_result_id": "R-canonical",
                    "updated_at": "2026-03-29T12:00:00+00:00",
                },
            },
        },
    )

    observability_dir = project / "GPD" / "observability"
    stale_current_execution = {
        "session_id": "sess-live",
        "phase": "03",
        "plan": "01",
        "segment_id": "seg-other",
        "segment_status": "paused",
        "resume_file": "GPD/phases/03-analysis/.continue-here.md",
        "transition_id": "transition-7",
        "current_task": "Keep working",
        "last_result_id": "R-old",
        "last_result_label": "Old label",
        "updated_at": "2026-03-29T12:05:00+00:00",
    }
    _write_json(observability_dir / "current-execution.json", stale_current_execution)

    from gpd.core.execution_lineage import project_execution_lineage_head, write_execution_lineage_head

    write_execution_lineage_head(
        project,
        project_execution_lineage_head(
            stale_current_execution,
            bounded_segment={
                "resume_file": "GPD/phases/03-analysis/.continue-here.md",
                "phase": "03",
                "plan": "01",
                "segment_id": "seg-other",
                "segment_status": "paused",
                "transition_id": "transition-7",
                "last_result_id": "R-old",
                "updated_at": "2026-03-29T12:05:00+00:00",
            },
            last_applied_seq=11,
            last_applied_event_id="evt-head-11",
            recorded_at="2026-03-29T12:05:00+00:00",
        ),
    )

    before_current = json.loads((observability_dir / "current-execution.json").read_text(encoding="utf-8"))
    before_head = json.loads((project / "GPD" / "lineage" / "execution-head.json").read_text(encoding="utf-8"))

    _observability_sync_helper()(project)

    after_current = json.loads((observability_dir / "current-execution.json").read_text(encoding="utf-8"))
    after_head = json.loads((project / "GPD" / "lineage" / "execution-head.json").read_text(encoding="utf-8"))

    assert after_current == before_current
    assert after_head == before_head


def test_derive_execution_visibility_marks_old_active_segment_as_possibly_stalled(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    observability_dir = project / "GPD" / "observability"
    observability_dir.mkdir(parents=True, exist_ok=True)
    (observability_dir / "current-execution.json").write_text(
        json.dumps(
            {
                "session_id": "sess-raw",
                "phase": "03",
                "plan": "02",
                "segment_status": "active",
                "current_task": "Benchmark reproduction",
                "updated_at": "2000-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    from gpd.core.observability import derive_execution_visibility

    visibility = derive_execution_visibility(project)
    assert visibility is not None
    assert visibility.status_classification == "active"
    assert visibility.assessment == "possibly stalled"
    assert visibility.possibly_stalled is True
    assert visibility.stale_after_minutes == 30
    assert visibility.current_task == "Benchmark reproduction"
    assert visibility.last_updated_at == "2000-01-01T00:00:00+00:00"
    assert visibility.last_updated_age_label is not None


def test_derive_execution_visibility_waiting_state_is_not_marked_possibly_stalled(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    observability_dir = project / "GPD" / "observability"
    observability_dir.mkdir(parents=True, exist_ok=True)
    (observability_dir / "current-execution.json").write_text(
        json.dumps(
            {
                "session_id": "sess-raw",
                "phase": "03",
                "plan": "02",
                "segment_status": "waiting_review",
                "waiting_for_review": True,
                "checkpoint_reason": "first_result",
                "updated_at": "2000-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    from gpd.core.observability import derive_execution_visibility

    visibility = derive_execution_visibility(project)
    assert visibility is not None
    assert visibility.status_classification == "waiting"
    assert visibility.assessment == "waiting"
    assert visibility.possibly_stalled is False
    assert visibility.review_reason == "first-result review pending"


def test_derive_execution_visibility_without_snapshot_is_idle_not_possibly_stalled(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import derive_execution_visibility

    visibility = derive_execution_visibility(project)
    assert visibility is not None
    assert visibility.has_live_execution is False
    assert visibility.status_classification == "idle"
    assert visibility.assessment == "idle"
    assert visibility.possibly_stalled is False


def test_get_current_execution_normalizes_phase_plan_and_checkpoint_reason(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    observability_dir = project / "GPD" / "observability"
    observability_dir.mkdir(parents=True, exist_ok=True)
    (observability_dir / "current-execution.json").write_text(
        json.dumps(
            {
                "session_id": "sess-raw",
                "phase": "3",
                "plan": "2",
                "segment_status": "waiting_review",
                "checkpoint_reason": "pre-fanout",
                "updated_at": "2026-03-14T12:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    from gpd.core.observability import get_current_execution

    snapshot = get_current_execution(project)
    assert snapshot is not None
    assert snapshot.phase == "03"
    assert snapshot.plan == "02"
    assert snapshot.checkpoint_reason == "pre_fanout"


def test_get_current_execution_normalizes_tangent_decision(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    observability_dir = project / "GPD" / "observability"
    observability_dir.mkdir(parents=True, exist_ok=True)
    (observability_dir / "current-execution.json").write_text(
        json.dumps(
            {
                "session_id": "sess-raw",
                "phase": "3",
                "plan": "2",
                "segment_status": "waiting_review",
                "tangent_summary": "Check whether the 2D case is degenerate",
                "tangent_decision": "branch-later",
                "updated_at": "2026-03-14T12:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    from gpd.core.observability import get_current_execution

    snapshot = get_current_execution(project)
    assert snapshot is not None
    assert snapshot.tangent_summary == "Check whether the 2D case is degenerate"
    assert snapshot.tangent_decision == "branch_later"


def test_derive_execution_visibility_marks_only_active_segments_possibly_stalled_after_30_minutes(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    observability_dir = project / "GPD" / "observability"
    observability_dir.mkdir(parents=True, exist_ok=True)
    (observability_dir / "current-execution.json").write_text(
        json.dumps(
            {
                "session_id": "sess-active",
                "phase": "03",
                "plan": "01",
                "segment_status": "active",
                "current_task": "Inspect a long-running segment",
                "updated_at": _iso_minutes_ago(31),
            }
        ),
        encoding="utf-8",
    )

    from gpd.core.observability import derive_execution_visibility

    visibility = derive_execution_visibility(project)
    assert visibility is not None
    assert visibility.has_live_execution is True
    assert visibility.status_classification == "active"
    assert visibility.possibly_stalled is True
    assert visibility.last_updated_age_minutes is not None
    assert visibility.last_updated_age_minutes >= 30.0
    assert visibility.suggested_next_commands[0].command == "gpd observe show --session sess-active --last 20"
    assert "has stalled" in visibility.suggested_next_commands[0].reason
    assert any("before assuming the run has stalled" in step for step in visibility.suggested_next_steps)
    assert any("gpd observe show --session sess-active --last 20" in step for step in visibility.suggested_next_steps)


def test_derive_execution_visibility_surfaces_pending_tangent_without_new_classification(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    observability_dir = project / "GPD" / "observability"
    observability_dir.mkdir(parents=True, exist_ok=True)
    (observability_dir / "current-execution.json").write_text(
        json.dumps(
            {
                "session_id": "sess-tangent",
                "phase": "03",
                "plan": "01",
                "segment_status": "waiting_review",
                "waiting_for_review": True,
                "checkpoint_reason": "pre_fanout",
                "tangent_summary": "Check whether the 2D case is degenerate",
                "updated_at": _iso_minutes_ago(5),
            }
        ),
        encoding="utf-8",
    )

    from gpd.core.observability import derive_execution_visibility

    visibility = derive_execution_visibility(project)
    assert visibility is not None
    assert visibility.status_classification == "waiting"
    assert visibility.tangent_summary == "Check whether the 2D case is degenerate"
    assert visibility.tangent_pending is True
    assert visibility.tangent_decision is None
    assert any("Tangent proposal pending" in step for step in visibility.suggested_next_steps)
    assert any("runtime, use the `tangent` command" in step for step in visibility.suggested_next_steps)


def test_derive_execution_visibility_surfaces_tangent_decision_label_without_changing_waiting_state(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    observability_dir = project / "GPD" / "observability"
    observability_dir.mkdir(parents=True, exist_ok=True)
    (observability_dir / "current-execution.json").write_text(
        json.dumps(
            {
                "session_id": "sess-tangent",
                "phase": "03",
                "plan": "01",
                "segment_status": "waiting_review",
                "waiting_for_review": True,
                "checkpoint_reason": "pre_fanout",
                "tangent_summary": "Check whether the 2D case is degenerate",
                "tangent_decision": "defer",
                "updated_at": _iso_minutes_ago(5),
            }
        ),
        encoding="utf-8",
    )

    from gpd.core.observability import derive_execution_visibility

    visibility = derive_execution_visibility(project)
    assert visibility is not None
    assert visibility.status_classification == "waiting"
    assert visibility.tangent_pending is False
    assert visibility.tangent_decision == "defer"
    assert visibility.tangent_decision_label == "capture and defer"
    assert any("capture and defer" in step for step in visibility.suggested_next_steps)


def test_derive_execution_visibility_reuses_branch_later_tangent_follow_up(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    observability_dir = project / "GPD" / "observability"
    observability_dir.mkdir(parents=True, exist_ok=True)
    (observability_dir / "current-execution.json").write_text(
        json.dumps(
            {
                "session_id": "sess-tangent",
                "phase": "03",
                "plan": "01",
                "segment_status": "waiting_review",
                "waiting_for_review": True,
                "checkpoint_reason": "pre_fanout",
                "tangent_summary": "Check whether the 2D case is degenerate",
                "tangent_decision": "branch_later",
                "updated_at": _iso_minutes_ago(5),
            }
        ),
        encoding="utf-8",
    )

    from gpd.core.observability import derive_execution_visibility

    visibility = derive_execution_visibility(project)
    assert visibility is not None
    assert visibility.tangent_decision == "branch_later"
    assert any("Recommendation: branch later." in step for step in visibility.suggested_next_steps)
    assert any("After the bounded stop" in step for step in visibility.suggested_next_steps)
    assert any("`branch-hypothesis`" in step for step in visibility.suggested_next_steps)


def test_derive_execution_visibility_keeps_recent_active_segments_active(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    observability_dir = project / "GPD" / "observability"
    observability_dir.mkdir(parents=True, exist_ok=True)
    (observability_dir / "current-execution.json").write_text(
        json.dumps(
            {
                "session_id": "sess-active",
                "phase": "03",
                "plan": "01",
                "segment_status": "active",
                "current_task": "Inspect a recent segment",
                "updated_at": _iso_minutes_ago(29),
            }
        ),
        encoding="utf-8",
    )

    from gpd.core.observability import derive_execution_visibility

    visibility = derive_execution_visibility(project)
    assert visibility is not None
    assert visibility.has_live_execution is True
    assert visibility.status_classification == "active"
    assert visibility.possibly_stalled is False


def test_derive_execution_visibility_never_flags_paused_segments_as_stalled(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    observability_dir = project / "GPD" / "observability"
    observability_dir.mkdir(parents=True, exist_ok=True)
    (observability_dir / "current-execution.json").write_text(
        json.dumps(
            {
                "session_id": "sess-paused",
                "phase": "03",
                "plan": "01",
                "segment_status": "paused",
                "resume_file": "GPD/phases/03-test-phase/.continue-here.md",
                "updated_at": _iso_minutes_ago(45),
            }
        ),
        encoding="utf-8",
    )

    from gpd.core.observability import derive_execution_visibility

    visibility = derive_execution_visibility(project)
    assert visibility is not None
    assert visibility.has_live_execution is True
    assert visibility.status_classification == "paused-or-resumable"
    assert visibility.possibly_stalled is False
    assert any("inspect the ranked recovery candidates" in step for step in visibility.suggested_next_steps)


def test_pre_fanout_gate_records_skeptical_review_state(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import ensure_session, get_current_execution, observe_event

    session = ensure_session(project, source="cli", command="execute-phase")
    assert session is not None

    observe_event(
        project,
        category="execution",
        name="segment",
        action="start",
        status="active",
        command="execute-phase",
        phase="05",
        plan="03",
        session_id=session.session_id,
        data={
            "execution": {
                "workflow": "execute-phase",
                "segment_id": "seg-9",
                "segment_reason": "pre_fanout",
                "review_cadence": "adaptive",
                "current_task": "Review benchmark anchor",
            }
        },
    )
    observe_event(
        project,
        category="execution",
        name="gate",
        action="enter",
        status="ok",
        command="execute-phase",
        phase="05",
        plan="03",
        session_id=session.session_id,
        data={
            "execution": {
                "checkpoint_reason": "pre_fanout",
                "last_result_label": "Proxy consistency pass",
                "skeptical_requestioning_required": True,
                "skeptical_requestioning_summary": "Proxy passed, but decisive benchmark anchor is still unchecked.",
                "weakest_unchecked_anchor": "Published benchmark table",
                "disconfirming_observation": "Direct benchmark reproduction misses the published tolerance band.",
            }
        },
    )

    snapshot = get_current_execution(project)
    assert snapshot is not None
    assert snapshot.waiting_for_review is True
    assert snapshot.pre_fanout_review_pending is True
    assert snapshot.skeptical_requestioning_required is True
    assert snapshot.downstream_locked is True
    assert snapshot.weakest_unchecked_anchor == "Published benchmark table"
    assert snapshot.disconfirming_observation == "Direct benchmark reproduction misses the published tolerance band."


def test_gate_clear_requires_matching_unlock_for_pre_fanout_state(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import ensure_session, get_current_execution, observe_event

    session = ensure_session(project, source="cli", command="execute-phase")
    assert session is not None

    observe_event(
        project,
        category="execution",
        name="gate",
        action="enter",
        status="ok",
        command="execute-phase",
        phase="05",
        plan="03",
        session_id=session.session_id,
        data={
            "execution": {
                "segment_id": "seg-9",
                "checkpoint_reason": "pre_fanout",
                "pre_fanout_review_pending": True,
                "waiting_for_review": True,
                "downstream_locked": True,
            }
        },
    )
    observe_event(
        project,
        category="execution",
        name="gate",
        action="clear",
        status="ok",
        command="execute-phase",
        phase="05",
        plan="03",
        session_id=session.session_id,
        data={"execution": {"checkpoint_reason": "pre_fanout"}},
    )

    snapshot = get_current_execution(project)
    assert snapshot is not None
    assert snapshot.waiting_for_review is True
    assert snapshot.pre_fanout_review_pending is True
    assert snapshot.pre_fanout_review_cleared is True
    assert snapshot.downstream_locked is True

    observe_event(
        project,
        category="execution",
        name="fanout",
        action="unlock",
        status="ok",
        command="execute-phase",
        phase="05",
        plan="03",
        session_id=session.session_id,
        data={"execution": {"checkpoint_reason": "pre_fanout"}},
    )

    snapshot = get_current_execution(project)
    assert snapshot is not None
    assert snapshot.waiting_for_review is False
    assert snapshot.pre_fanout_review_pending is False
    assert snapshot.pre_fanout_review_cleared is False
    assert snapshot.downstream_locked is False


def test_fanout_lock_normalizes_to_pre_fanout_review_stop(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import ensure_session, get_current_execution, observe_event

    session = ensure_session(project, source="cli", command="execute-phase")
    assert session is not None

    observe_event(
        project,
        category="execution",
        name="fanout",
        action="lock",
        status="ok",
        command="execute-phase",
        phase="06",
        plan="02",
        session_id=session.session_id,
        data={"execution": {"last_result_label": "Benchmark anchor comparison"}},
    )

    snapshot = get_current_execution(project)
    assert snapshot is not None
    assert snapshot.checkpoint_reason == "pre_fanout"
    assert snapshot.pre_fanout_review_pending is True
    assert snapshot.waiting_for_review is True
    assert snapshot.review_required is True
    assert snapshot.downstream_locked is True
    assert snapshot.segment_status == "waiting_review"


def test_fanout_unlock_does_not_clear_pre_fanout_review_without_gate_clear(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import ensure_session, get_current_execution, observe_event

    session = ensure_session(project, source="cli", command="execute-phase")
    assert session is not None

    observe_event(
        project,
        category="execution",
        name="gate",
        action="enter",
        status="ok",
        command="execute-phase",
        phase="06",
        plan="02",
        session_id=session.session_id,
        data={"execution": {"checkpoint_reason": "pre_fanout", "pre_fanout_review_pending": True, "downstream_locked": True}},
    )
    observe_event(
        project,
        category="execution",
        name="fanout",
        action="unlock",
        status="ok",
        command="execute-phase",
        phase="06",
        plan="02",
        session_id=session.session_id,
        data={"execution": {"checkpoint_reason": "pre_fanout"}},
    )

    snapshot = get_current_execution(project)
    assert snapshot is not None
    assert snapshot.pre_fanout_review_pending is True
    assert snapshot.pre_fanout_review_cleared is False
    assert snapshot.waiting_for_review is True
    assert snapshot.downstream_locked is False
    assert snapshot.checkpoint_reason == "pre_fanout"


def test_unrelated_gate_clear_preserves_pre_fanout_and_skeptical_state(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import ensure_session, get_current_execution, observe_event

    session = ensure_session(project, source="cli", command="execute-phase")
    assert session is not None

    observe_event(
        project,
        category="execution",
        name="gate",
        action="enter",
        status="ok",
        command="execute-phase",
        phase="07",
        plan="01",
        session_id=session.session_id,
        data={"execution": {"checkpoint_reason": "first_result", "first_result_gate_pending": True, "downstream_locked": True}},
    )
    observe_event(
        project,
        category="execution",
        name="gate",
        action="enter",
        status="ok",
        command="execute-phase",
        phase="07",
        plan="01",
        session_id=session.session_id,
        data={
            "execution": {
                "checkpoint_reason": "pre_fanout",
                "pre_fanout_review_pending": True,
                "skeptical_requestioning_required": True,
                "skeptical_requestioning_summary": "Need decisive anchor evidence before fanout.",
                "weakest_unchecked_anchor": "Benchmark table",
                "downstream_locked": True,
            }
        },
    )
    observe_event(
        project,
        category="execution",
        name="gate",
        action="clear",
        status="ok",
        command="execute-phase",
        phase="07",
        plan="01",
        session_id=session.session_id,
        data={"execution": {"checkpoint_reason": "first_result"}},
    )

    snapshot = get_current_execution(project)
    assert snapshot is not None
    assert snapshot.first_result_gate_pending is False
    assert snapshot.pre_fanout_review_pending is True
    assert snapshot.skeptical_requestioning_required is True
    assert snapshot.skeptical_requestioning_summary == "Need decisive anchor evidence before fanout."
    assert snapshot.downstream_locked is True
    assert snapshot.waiting_for_review is True
    assert snapshot.checkpoint_reason == "pre_fanout"


def test_gate_clear_without_explicit_target_leaves_first_result_gate_pending(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import ensure_session, get_current_execution, observe_event

    session = ensure_session(project, source="cli", command="execute-phase")
    assert session is not None

    observe_event(
        project,
        category="execution",
        name="gate",
        action="enter",
        status="ok",
        command="execute-phase",
        phase="08",
        plan="02",
        session_id=session.session_id,
        data={"execution": {"checkpoint_reason": "first_result", "first_result_gate_pending": True}},
    )
    observe_event(
        project,
        category="execution",
        name="gate",
        action="clear",
        status="ok",
        command="execute-phase",
        phase="08",
        plan="02",
        session_id=session.session_id,
        data={"execution": {}},
    )

    snapshot = get_current_execution(project)
    assert snapshot is not None
    assert snapshot.first_result_gate_pending is True
    assert snapshot.waiting_for_review is True
    assert snapshot.checkpoint_reason == "first_result"


def test_skeptical_review_without_explicit_reason_normalizes_checkpoint_reason(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import ensure_session, get_current_execution, observe_event

    session = ensure_session(project, source="cli", command="execute-phase")
    assert session is not None

    observe_event(
        project,
        category="execution",
        name="gate",
        action="enter",
        status="ok",
        command="execute-phase",
        phase="07",
        plan="01",
        session_id=session.session_id,
        data={
            "execution": {
                "skeptical_requestioning_required": True,
                "skeptical_requestioning_summary": "The first fit matches a proxy but not the decisive observable.",
                "weakest_unchecked_anchor": "Direct observable benchmark",
            }
        },
    )

    snapshot = get_current_execution(project)
    assert snapshot is not None
    assert snapshot.checkpoint_reason == "skeptical_requestioning"
    assert snapshot.waiting_for_review is True
    assert snapshot.review_required is True
    assert snapshot.skeptical_requestioning_required is True


def test_execution_finish_clears_current_execution_snapshot(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import ensure_session, get_current_execution, observe_event

    session = ensure_session(project, source="cli", command="execute-phase")
    assert session is not None

    observe_event(
        project,
        category="execution",
        name="segment",
        action="start",
        status="active",
        phase="04",
        plan="02",
        session_id=session.session_id,
        data={"execution": {"segment_id": "seg-02"}},
    )
    observe_event(
        project,
        category="execution",
        name="segment",
        action="finish",
        status="ok",
        phase="04",
        plan="02",
        session_id=session.session_id,
        data={"execution": {"segment_status": "completed"}},
    )

    assert get_current_execution(project) is None


def test_new_segment_start_clears_stale_review_and_blocked_state(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import ensure_session, get_current_execution, observe_event

    session = ensure_session(project, source="cli", command="execute-phase")
    assert session is not None

    observe_event(
        project,
        category="execution",
        name="gate",
        action="enter",
        status="ok",
        command="execute-phase",
        phase="04",
        plan="02",
        session_id=session.session_id,
        data={
            "execution": {
                "segment_id": "seg-old",
                "checkpoint_reason": "first_result",
                "first_result_gate_pending": True,
                "waiting_for_review": True,
                "downstream_locked": True,
                "tangent_summary": "Check whether the 2D case is degenerate",
                "tangent_decision": "branch_later",
                "resume_file": "GPD/phases/04-test/.continue-here.md",
            }
        },
    )
    observe_event(
        project,
        category="execution",
        name="segment",
        action="start",
        status="active",
        command="execute-phase",
        phase="04",
        plan="02",
        session_id=session.session_id,
        data={"execution": {"segment_id": "seg-new", "current_task": "Continue after gate"}},
    )

    snapshot = get_current_execution(project)
    assert snapshot is not None
    assert snapshot.segment_id == "seg-new"
    assert snapshot.segment_status == "active"
    assert snapshot.current_task == "Continue after gate"
    assert snapshot.waiting_for_review is False
    assert snapshot.review_required is False
    assert snapshot.waiting_reason is None
    assert snapshot.blocked_reason is None
    assert snapshot.first_result_gate_pending is False
    assert snapshot.pre_fanout_review_pending is False
    assert snapshot.skeptical_requestioning_required is False
    assert snapshot.downstream_locked is False
    assert snapshot.tangent_summary is None
    assert snapshot.tangent_decision is None
    assert snapshot.resume_file is None
    assert snapshot.segment_started_at is not None


def test_gate_clear_clears_tangent_state_when_review_stop_resolves(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import ensure_session, get_current_execution, observe_event

    session = ensure_session(project, source="cli", command="execute-phase")
    assert session is not None

    observe_event(
        project,
        category="execution",
        name="gate",
        action="enter",
        status="ok",
        command="execute-phase",
        phase="04",
        plan="02",
        session_id=session.session_id,
        data={
            "execution": {
                "segment_id": "seg-old",
                "checkpoint_reason": "first_result",
                "first_result_gate_pending": True,
                "waiting_for_review": True,
                "tangent_summary": "Check whether the 2D case is degenerate",
                "tangent_decision": "defer",
            }
        },
    )
    observe_event(
        project,
        category="execution",
        name="gate",
        action="clear",
        status="ok",
        command="execute-phase",
        phase="04",
        plan="02",
        session_id=session.session_id,
        data={"execution": {"checkpoint_reason": "first_result"}},
    )

    snapshot = get_current_execution(project)
    assert snapshot is not None
    assert snapshot.segment_status == "active"
    assert snapshot.waiting_for_review is False
    assert snapshot.tangent_summary is None
    assert snapshot.tangent_decision is None


def test_segment_pause_forces_paused_status_and_keeps_resume_semantics(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import ensure_session, get_current_execution, observe_event

    session = ensure_session(project, source="cli", command="execute-phase")
    assert session is not None

    observe_event(
        project,
        category="execution",
        name="gate",
        action="enter",
        status="ok",
        command="execute-phase",
        phase="05",
        plan="01",
        session_id=session.session_id,
        data={
            "execution": {
                "segment_id": "seg-1",
                "checkpoint_reason": "first_result",
                "first_result_gate_pending": True,
                "waiting_for_review": True,
                "downstream_locked": True,
            }
        },
    )
    observe_event(
        project,
        category="execution",
        name="segment",
        action="pause",
        status="ok",
        command="execute-phase",
        phase="05",
        plan="01",
        session_id=session.session_id,
        data={"execution": {"segment_status": "awaiting_user", "resume_file": "GPD/phases/05-test/.continue-here.md"}},
    )

    snapshot = get_current_execution(project)
    assert snapshot is not None
    assert snapshot.segment_status == "awaiting_user"
    assert snapshot.waiting_for_review is False
    assert snapshot.review_required is False
    assert snapshot.first_result_gate_pending is False
    assert snapshot.downstream_locked is False
    assert snapshot.resume_file == "GPD/phases/05-test/.continue-here.md"


def test_segment_finish_clears_snapshot_even_after_blocked_state(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import ensure_session, get_current_execution, observe_event

    session = ensure_session(project, source="cli", command="execute-phase")
    assert session is not None

    observe_event(
        project,
        category="execution",
        name="segment",
        action="start",
        status="active",
        command="execute-phase",
        phase="06",
        plan="01",
        session_id=session.session_id,
        data={"execution": {"segment_id": "seg-blocked"}},
    )
    observe_event(
        project,
        category="execution",
        name="gate",
        action="enter",
        status="ok",
        command="execute-phase",
        phase="06",
        plan="01",
        session_id=session.session_id,
        data={"execution": {"blocked_reason": "manual stop required"}},
    )

    snapshot = get_current_execution(project)
    assert snapshot is not None
    assert snapshot.segment_status == "blocked"

    observe_event(
        project,
        category="execution",
        name="segment",
        action="finish",
        status="ok",
        command="execute-phase",
        phase="06",
        plan="01",
        session_id=session.session_id,
        data={"execution": {"segment_status": "completed"}},
    )

    assert get_current_execution(project) is None


def test_derive_execution_visibility_treats_awaiting_user_as_paused_or_resumable(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    observability_dir = project / "GPD" / "observability"
    observability_dir.mkdir(parents=True, exist_ok=True)
    (observability_dir / "current-execution.json").write_text(
        json.dumps(
            {
                "session_id": "sess-awaiting",
                "phase": "03",
                "plan": "01",
                "segment_status": "awaiting_user",
                "resume_file": "GPD/phases/03-test/.continue-here.md",
                "updated_at": _iso_minutes_ago(45),
            }
        ),
        encoding="utf-8",
    )

    from gpd.core.observability import derive_execution_visibility

    visibility = derive_execution_visibility(project)
    assert visibility is not None
    assert visibility.status_classification == "paused-or-resumable"
    assert visibility.assessment == "paused-or-resumable"
    assert visibility.possibly_stalled is False


def test_foreign_session_cannot_clear_live_review_gate(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import ensure_session, get_current_execution, observe_event

    foreign_session = ensure_session(project, source="cli", command="resume-work")
    assert foreign_session is not None
    observe_event(
        project,
        category="trace",
        name="resume-review",
        action="stop",
        status="ok",
        command="resume-work",
        session_id=foreign_session.session_id,
        end_session=True,
    )

    active_session = ensure_session(project, source="cli", command="execute-phase")
    assert active_session is not None
    observe_event(
        project,
        category="execution",
        name="gate",
        action="enter",
        status="ok",
        command="execute-phase",
        phase="03",
        plan="01",
        session_id=active_session.session_id,
        data={
            "execution": {
                "segment_id": "seg-01",
                "checkpoint_reason": "first_result",
                "first_result_gate_pending": True,
                "waiting_for_review": True,
                "downstream_locked": True,
            }
        },
    )

    observe_event(
        project,
        category="execution",
        name="gate",
        action="clear",
        status="ok",
        command="resume-work",
        phase="03",
        plan="01",
        session_id=foreign_session.session_id,
        data={"execution": {"checkpoint_reason": "first_result"}},
    )

    snapshot = get_current_execution(project)
    assert snapshot is not None
    assert snapshot.session_id == active_session.session_id
    assert snapshot.first_result_gate_pending is True
    assert snapshot.downstream_locked is True


def test_observe_event_reuses_persisted_active_session_when_contextvars_are_empty(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    import gpd.core.observability as observability

    session = observability.ensure_session(project, source="cli", command="execute-phase")
    assert session is not None

    observability._session_id_var.set(None)
    observability._session_cwd_var.set(None)

    result = observability.observe_event(
        project,
        category="workflow",
        name="resume",
        action="log",
        status="ok",
        command="resume-work",
        data={"phase": "03"},
    )

    assert result.recorded is True
    assert result.session_id == session.session_id

    sessions_dir = project / "GPD" / "observability" / "sessions"
    session_logs = sorted(sessions_dir.glob("*.jsonl"))
    assert len(session_logs) == 1

    events = _read_jsonl(session_logs[0])
    assert len(events) == 2
    assert events[0]["action"] == "start"
    assert events[1]["category"] == "workflow"
    assert events[1]["name"] == "resume"
    assert events[1]["command"] == "resume-work"

    current_session = json.loads((project / "GPD" / "observability" / "current-session.json").read_text(encoding="utf-8"))
    assert current_session["session_id"] == session.session_id
    assert current_session["status"] == "active"
    assert current_session["command"] == "resume-work"


def test_late_observe_event_on_finished_session_does_not_reactivate_current_pointer(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import ensure_session, observe_event

    session = ensure_session(project, source="trace", command="trace start")
    assert session is not None

    observe_event(
        project,
        category="trace",
        name="trace_stop",
        action="stop",
        status="ok",
        session_id=session.session_id,
        end_session=True,
    )

    late_result = observe_event(
        project,
        category="trace",
        name="late_note",
        action="log",
        status="ok",
        session_id=session.session_id,
        data={"note": "after finish"},
    )

    assert late_result.recorded is True

    current_session = json.loads((project / "GPD" / "observability" / "current-session.json").read_text(encoding="utf-8"))
    assert current_session["session_id"] == session.session_id
    assert current_session["status"] == "ok"

    next_session = ensure_session(project, source="trace", command="trace resume")
    assert next_session is not None
    assert next_session.session_id != session.session_id

    session_log = project / "GPD" / "observability" / "sessions" / f"{session.session_id}.jsonl"
    events = _read_jsonl(session_log)
    assert events[-1]["name"] == "late_note"
    assert events[-2]["action"] == "finish"


def test_gpd_span_does_not_write_observability_artifacts(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import gpd_span

    with gpd_span("test.span", domain="physics"):
        pass

    assert not (project / "GPD" / "observability").exists()


def test_instrument_gpd_function_sync_does_not_emit_local_events(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import instrument_gpd_function

    @instrument_gpd_function("test.func")
    def my_func(x: int) -> int:
        return x * 2

    assert my_func(5) == 10
    assert not (project / "GPD" / "observability").exists()


def test_instrument_gpd_function_async_does_not_emit_local_events(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import instrument_gpd_function

    @instrument_gpd_function("test.async_func")
    async def my_async_func(x: int) -> int:
        return x + 1

    result = asyncio.run(my_async_func(3))
    assert result == 4
    assert not (project / "GPD" / "observability").exists()


def test_show_events_reads_session_streams(tmp_path: Path) -> None:
    project = _bootstrap_project(tmp_path)
    sessions_dir = project / "GPD" / "observability" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    (sessions_dir / "session-a.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-03-10T00:00:00+00:00",
                        "event_id": "evt-1",
                        "session_id": "session-a",
                        "category": "session",
                        "name": "lifecycle",
                        "action": "start",
                        "status": "active",
                        "command": "execute-phase",
                        "data": {"cwd": str(project), "source": "cli", "pid": 100, "metadata": {}},
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-10T00:00:01+00:00",
                        "event_id": "evt-2",
                        "session_id": "session-a",
                        "category": "workflow",
                        "name": "wave-start",
                        "action": "start",
                        "status": "active",
                        "command": "execute-phase",
                        "data": {"wave": 2},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    from gpd.core.observability import show_events

    result = show_events(project, category="workflow", command="execute-phase")
    assert result.count == 1
    assert result.events[0]["session_id"] == "session-a"
    assert result.events[0]["name"] == "wave-start"


def test_prefixed_attrs_renames_cwd_to_gpd_cwd() -> None:
    from gpd.core.observability import _prefixed_attrs

    result = _prefixed_attrs({"cwd": "/some/path"})
    assert "gpd.cwd" in result
    assert "cwd" not in result
    assert result["gpd.cwd"] == "/some/path"


def test_gpd_span_accepts_bare_cwd_without_side_effects(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import gpd_span

    with gpd_span("test.cwd_resolution", cwd=str(project)):
        pass

    assert not (project / "GPD" / "observability").exists()


def test_gpd_span_accepts_prefixed_cwd_without_side_effects(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import gpd_span

    with gpd_span("test.prefixed_cwd", **{"gpd.cwd": str(project)}):
        pass

    assert not (project / "GPD" / "observability").exists()


def test_list_sessions_empty_project(tmp_path: Path) -> None:
    project = _bootstrap_project(tmp_path)
    from gpd.core.observability import list_sessions

    result = list_sessions(project)
    assert result.count == 0
    assert result.sessions == []


def test_list_sessions_returns_sessions_from_logs(tmp_path: Path) -> None:
    project = _bootstrap_project(tmp_path)
    sessions_dir = project / "GPD" / "observability" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    (sessions_dir / "test-session.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-03-10T00:00:00+00:00",
                        "event_id": "evt-1",
                        "session_id": "test-session",
                        "category": "session",
                        "name": "lifecycle",
                        "action": "start",
                        "status": "active",
                        "command": "execute-phase",
                        "data": {"cwd": str(project), "source": "cli", "pid": 100, "metadata": {}},
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-10T00:01:00+00:00",
                        "event_id": "evt-2",
                        "session_id": "test-session",
                        "category": "session",
                        "name": "lifecycle",
                        "action": "finish",
                        "status": "ok",
                        "command": "execute-phase",
                        "data": {"ended_at": "2026-03-10T00:01:00+00:00", "ended_by": {"name": "command"}},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    from gpd.core.observability import list_sessions

    result = list_sessions(project)
    assert result.count == 1
    assert result.sessions[0]["session_id"] == "test-session"
    assert result.sessions[0]["command"] == "execute-phase"
    assert result.sessions[0]["status"] == "ok"


def test_list_sessions_no_gpd_dir(tmp_path: Path) -> None:
    from gpd.core.observability import list_sessions

    result = list_sessions(tmp_path)
    assert result.count == 0


def test_export_logs_writes_filtered_json_exports(tmp_path: Path) -> None:
    project = _bootstrap_project(tmp_path)
    sessions_dir = project / "GPD" / "observability" / "sessions"
    sessions_dir.mkdir(parents=True, exist_ok=True)
    traces_dir = project / "GPD" / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)

    session_id = "session-export"
    (sessions_dir / f"{session_id}.jsonl").write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "timestamp": "2026-03-10T00:00:00+00:00",
                        "event_id": "evt-1",
                        "session_id": session_id,
                        "category": "session",
                        "name": "lifecycle",
                        "action": "start",
                        "status": "active",
                        "command": "execute-phase",
                        "data": {"cwd": str(project), "source": "cli", "pid": 100, "metadata": {}},
                    }
                ),
                json.dumps(
                    {
                        "timestamp": "2026-03-10T00:00:05+00:00",
                        "event_id": "evt-2",
                        "session_id": session_id,
                        "category": "workflow",
                        "name": "wave-start",
                        "action": "start",
                        "status": "active",
                        "command": "execute-phase",
                        "phase": "03",
                        "data": {"wave": 1},
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    (traces_dir / "trace-export.jsonl").write_text(
        json.dumps({"timestamp": "2026-03-10T00:00:06+00:00", "type": "span", "summary": "trace entry"}) + "\n",
        encoding="utf-8",
    )

    from gpd.core.observability import export_logs

    output_dir = project / "exports"
    result = export_logs(project, output_dir=str(output_dir), phase="03", format="json")

    assert result.exported is True
    assert result.output_dir == str(output_dir)
    assert result.sessions_exported == 1
    assert result.events_exported == 1
    assert result.traces_exported == 1
    assert len(result.files_written) == 3

    sessions_payload = json.loads((output_dir / Path(result.files_written[0]).name).read_text(encoding="utf-8"))
    events_payload = json.loads((output_dir / Path(result.files_written[1]).name).read_text(encoding="utf-8"))
    traces_payload = json.loads((output_dir / Path(result.files_written[2]).name).read_text(encoding="utf-8"))

    assert sessions_payload[0]["session_id"] == session_id
    assert events_payload == [
        {
            "timestamp": "2026-03-10T00:00:05+00:00",
            "event_id": "evt-2",
            "session_id": session_id,
            "category": "workflow",
            "name": "wave-start",
            "action": "start",
            "status": "active",
            "command": "execute-phase",
            "phase": "03",
            "data": {"wave": 1},
        }
    ]
    assert traces_payload[0]["summary"] == "trace entry"
