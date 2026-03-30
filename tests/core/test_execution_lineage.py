"""Focused regression tests for execution lineage and reducer semantics."""

from __future__ import annotations

import json
from pathlib import Path


def _bootstrap_project(tmp_path: Path) -> Path:
    planning = tmp_path / "GPD"
    planning.mkdir()
    return tmp_path


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_execution_stream_appends_rows_and_reducer_stays_in_parity(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.constants import ProjectLayout
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
        phase="05",
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
    observe_event(
        project,
        category="execution",
        name="gate",
        action="clear",
        status="ok",
        command="execute-phase",
        phase="05",
        plan="01",
        session_id=session.session_id,
        data={"execution": {"checkpoint_reason": "first_result"}},
    )

    session_log = project / "GPD" / "observability" / "sessions" / f"{session.session_id}.jsonl"
    events = _read_jsonl(session_log)
    assert [event["category"] for event in events] == ["session", "execution", "execution", "execution"]
    assert [event["name"] for event in events] == ["lifecycle", "segment", "gate", "gate"]
    assert [event["action"] for event in events] == ["start", "start", "enter", "clear"]

    layout = ProjectLayout(project)
    lineage_rows = _read_jsonl(layout.execution_lineage_ledger)
    assert [row["kind"] for row in lineage_rows] == ["segment.start", "gate.enter", "gate.clear"]
    assert [row["head_effect"] for row in lineage_rows] == ["seed", "replace", "replace"]
    head = json.loads(layout.execution_lineage_head.read_text(encoding="utf-8"))
    assert head["execution"]["segment_id"] == "seg-01"
    assert head["execution"]["segment_status"] == "active"
    assert head["last_applied_event_id"] == lineage_rows[-1]["event_id"]

    snapshot = get_current_execution(project)
    assert snapshot is not None
    assert snapshot.segment_id == "seg-01"
    assert snapshot.segment_status == "active"
    assert snapshot.waiting_for_review is False
    assert snapshot.first_result_gate_pending is False
    assert snapshot.last_result_label == "Benchmark reproduction"
    assert snapshot.downstream_locked is False


def test_execution_reducer_ignores_foreign_session_mutation(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import (
        CurrentExecutionState,
        ObservabilityEvent,
        _updated_execution_state,
    )

    existing = CurrentExecutionState(
        session_id="session-a",
        phase="05",
        plan="01",
        segment_id="seg-01",
        segment_status="waiting_review",
        checkpoint_reason="first_result",
        waiting_for_review=True,
        review_required=True,
        first_result_gate_pending=True,
        downstream_locked=True,
        updated_at="2026-03-29T12:00:00+00:00",
    )
    payload = ObservabilityEvent(
        event_id="evt-foreign",
        timestamp="2026-03-29T12:01:00+00:00",
        session_id="session-b",
        category="execution",
        name="gate",
        action="clear",
        status="ok",
        command="resume-work",
        phase="05",
        plan="01",
        data={"execution": {"checkpoint_reason": "first_result", "segment_id": "seg-01"}},
    )

    updated = _updated_execution_state(existing, payload, cwd=project)

    assert updated is not None
    assert updated.model_dump(mode="json") == existing.model_dump(mode="json")


def test_execution_finish_appends_clear_row_and_removes_derived_head(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.constants import ProjectLayout
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
        data={"execution": {"segment_id": "seg-clear"}},
    )
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

    layout = ProjectLayout(project)
    lineage_rows = _read_jsonl(layout.execution_lineage_ledger)
    assert lineage_rows[-1]["kind"] == "segment.finish"
    assert lineage_rows[-1]["head_effect"] == "clear"
    assert lineage_rows[-1]["head_after"] is None
    assert not layout.execution_lineage_head.exists()
    assert get_current_execution(project) is None


def test_get_current_execution_prefers_lineage_head_over_legacy_snapshot(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.constants import ProjectLayout
    from gpd.core.execution_lineage import project_execution_lineage_head, write_execution_lineage_head
    from gpd.core.observability import get_current_execution

    layout = ProjectLayout(project)
    layout.observability_dir.mkdir(parents=True, exist_ok=True)
    layout.current_observability_execution.write_text(
        json.dumps(
            {
                "session_id": "legacy-session",
                "phase": "03",
                "plan": "02",
                "segment_status": "paused",
                "current_task": "Legacy snapshot task",
                "updated_at": "2026-03-29T12:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    write_execution_lineage_head(
        project,
        project_execution_lineage_head(
            {
                "session_id": "lineage-session",
                "phase": "03",
                "plan": "02",
                "segment_status": "blocked",
                "blocked_reason": "manual stop required",
                "current_task": "Lineage head task",
                "updated_at": "2026-03-29T12:03:00+00:00",
            },
            last_applied_seq=4,
            last_applied_event_id="evt-lineage",
            recorded_at="2026-03-29T12:03:00+00:00",
        ),
    )

    snapshot = get_current_execution(project)

    assert snapshot is not None
    assert snapshot.session_id == "lineage-session"
    assert snapshot.segment_status == "blocked"
    assert snapshot.current_task == "Lineage head task"
    assert snapshot.current_task != "Legacy snapshot task"


def test_get_current_execution_falls_back_to_legacy_snapshot_when_head_cache_is_missing(
    tmp_path: Path, monkeypatch
) -> None:
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
                "checkpoint_reason": "first_result",
                "waiting_for_review": True,
                "first_result_gate_pending": True,
                "updated_at": "2026-03-29T12:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    from gpd.core.observability import get_current_execution

    snapshot = get_current_execution(project)

    assert snapshot is not None
    assert snapshot.session_id == "sess-raw"
    assert snapshot.phase == "03"
    assert snapshot.plan == "02"
    assert snapshot.segment_status == "waiting_review"
    assert snapshot.checkpoint_reason == "first_result"
    assert snapshot.first_result_gate_pending is True
