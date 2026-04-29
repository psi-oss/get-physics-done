"""Focused assertions for execution lineage and reducer semantics."""

from __future__ import annotations

import json
from pathlib import Path


def _bootstrap_project(tmp_path: Path) -> Path:
    planning = tmp_path / "GPD"
    planning.mkdir()
    return tmp_path


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_execution_lineage_does_not_export_a_separate_append_helper() -> None:
    import gpd.core.execution_lineage as execution_lineage

    assert "append_execution_lineage_entry" not in execution_lineage.__all__
    assert not hasattr(execution_lineage, "append_execution_lineage_entry")


def test_execution_lineage_reduces_same_seq_minimal_noop_as_ordered_cursor_advance() -> None:
    from gpd.core.execution_lineage import (
        ExecutionHeadEffect,
        build_execution_lineage_entry,
        derive_execution_lineage_head,
    )

    seed = build_execution_lineage_entry(
        kind="segment.start",
        event_id="evt-seed",
        recorded_at="2026-03-29T12:00:00+00:00",
        head_effect=ExecutionHeadEffect.SEED,
        head_after={
            "session_id": "sess-1",
            "phase": "03",
            "plan": "01",
            "segment_id": "seg-1",
            "segment_status": "active",
        },
        bounded_segment_after={
            "resume_file": "GPD/phases/03/.continue-here.md",
            "phase": "03",
            "plan": "01",
            "segment_id": "seg-1",
            "segment_status": "paused",
        },
        seq=4,
    )
    legacy_noop = build_execution_lineage_entry(
        kind="segment.heartbeat",
        event_id="evt-noop",
        recorded_at="2026-03-29T12:01:00+00:00",
        head_effect=ExecutionHeadEffect.NOOP,
        seq=4,
    )

    head = derive_execution_lineage_head([legacy_noop, seed])

    assert head is not None
    assert head.last_applied_seq == 4
    assert head.last_applied_event_id == "evt-noop"
    assert head.recorded_at == "2026-03-29T12:01:00+00:00"
    assert head.execution is not None
    assert head.execution["segment_id"] == "seg-1"
    assert head.bounded_segment is not None
    assert head.bounded_segment.segment_id == "seg-1"


def test_execution_lineage_rederives_stale_same_seq_noop_cache(tmp_path: Path) -> None:
    from gpd.core.execution_lineage import (
        ExecutionHeadEffect,
        build_execution_lineage_entry,
        execution_lineage_ledger_path,
        load_execution_lineage_head,
        project_execution_lineage_head,
        write_execution_lineage_head,
    )

    project = _bootstrap_project(tmp_path)
    seed = build_execution_lineage_entry(
        kind="segment.start",
        event_id="evt-seed",
        recorded_at="2026-03-29T12:00:00+00:00",
        head_effect=ExecutionHeadEffect.SEED,
        head_after={"phase": "03", "plan": "01", "segment_id": "seg-1"},
        bounded_segment_after={
            "resume_file": "GPD/phases/03/.continue-here.md",
            "phase": "03",
            "plan": "01",
            "segment_id": "seg-1",
            "segment_status": "paused",
        },
        seq=4,
        reducer_version="1",
    )
    legacy_noop = build_execution_lineage_entry(
        kind="segment.heartbeat",
        event_id="evt-noop",
        recorded_at="2026-03-29T12:01:00+00:00",
        head_effect=ExecutionHeadEffect.NOOP,
        seq=4,
        reducer_version="1",
    )
    ledger_path = execution_lineage_ledger_path(project)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(
        "\n".join(entry.model_dump_json() for entry in (seed, legacy_noop)) + "\n",
        encoding="utf-8",
    )
    write_execution_lineage_head(
        project,
        project_execution_lineage_head(
            None,
            last_applied_seq=4,
            last_applied_event_id="evt-noop",
            recorded_at="2026-03-29T12:01:00+00:00",
            reducer_version="1",
        ),
    )

    head = load_execution_lineage_head(project)

    assert head is not None
    assert head.last_applied_event_id == "evt-noop"
    assert head.execution is not None
    assert head.execution["segment_id"] == "seg-1"
    assert head.bounded_segment is not None
    assert head.bounded_segment.segment_id == "seg-1"
    assert head.reducer_version != "1"


def test_execution_lineage_noop_after_clear_advances_cursor_without_resurrecting_head() -> None:
    from gpd.core.execution_lineage import (
        ExecutionHeadEffect,
        build_execution_lineage_entry,
        derive_execution_lineage_head,
    )

    clear = build_execution_lineage_entry(
        kind="execution.finish",
        event_id="evt-clear",
        recorded_at="2026-03-29T12:00:00+00:00",
        head_effect=ExecutionHeadEffect.CLEAR,
        seq=10,
    )
    stale_noop = build_execution_lineage_entry(
        kind="segment.heartbeat",
        event_id="evt-noop",
        recorded_at="2026-03-29T12:01:00+00:00",
        head_effect=ExecutionHeadEffect.NOOP,
        head_after={"phase": "03", "plan": "01", "segment_id": "seg-stale"},
        bounded_segment_after={
            "resume_file": "GPD/phases/03/.continue-here.md",
            "phase": "03",
            "plan": "01",
            "segment_id": "seg-stale",
            "segment_status": "paused",
        },
        seq=11,
    )

    head = derive_execution_lineage_head([clear, stale_noop])

    assert head is not None
    assert head.last_applied_seq == 11
    assert head.last_applied_event_id == "evt-noop"
    assert head.execution is None
    assert head.bounded_segment is None


def test_execution_lineage_rejects_stale_head_when_ledger_is_absent(tmp_path: Path) -> None:
    from gpd.core.execution_lineage import (
        load_execution_lineage_head,
        project_execution_lineage_head,
        write_execution_lineage_head,
    )

    project = _bootstrap_project(tmp_path)
    write_execution_lineage_head(
        project,
        project_execution_lineage_head(
            {"phase": "03", "plan": "01", "segment_id": "seg-1"},
            last_applied_seq=4,
            last_applied_event_id="evt-stale",
            recorded_at="2026-03-29T12:01:00+00:00",
            reducer_version="1",
        ),
    )

    assert load_execution_lineage_head(project) is None


def test_execution_lineage_rejects_current_head_when_ledger_is_absent(tmp_path: Path) -> None:
    from gpd.core.execution_lineage import (
        load_execution_lineage_head,
        project_execution_lineage_head,
        write_execution_lineage_head,
    )

    project = _bootstrap_project(tmp_path)
    write_execution_lineage_head(
        project,
        project_execution_lineage_head(
            {"phase": "03", "plan": "01", "segment_id": "seg-1"},
            last_applied_seq=4,
            last_applied_event_id="evt-orphan",
            recorded_at="2026-03-29T12:01:00+00:00",
        ),
    )

    assert load_execution_lineage_head(project) is None


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


def test_get_current_execution_honors_clear_lineage_when_head_cache_is_missing(
    tmp_path: Path, monkeypatch
) -> None:
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
    layout.current_observability_execution.write_text(
        json.dumps(
            {
                "session_id": "stale-session",
                "phase": "06",
                "plan": "01",
                "segment_id": "seg-clear",
                "segment_status": "waiting_review",
                "current_task": "Stale snapshot task",
                "updated_at": "2026-03-29T12:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    assert get_current_execution(project) is None


def test_stale_execution_head_cache_does_not_override_newer_clear_row(
    tmp_path: Path, monkeypatch
) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.constants import ProjectLayout
    from gpd.core.execution_lineage import load_execution_lineage_head
    from gpd.core.observability import derive_execution_visibility, ensure_session, get_current_execution, observe_event

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
        data={"execution": {"segment_id": "seg-stale"}},
    )
    layout = ProjectLayout(project)
    stale_head = layout.execution_lineage_head.read_text(encoding="utf-8")

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
    layout.execution_lineage_head.write_text(stale_head, encoding="utf-8")

    lineage_rows = _read_jsonl(layout.execution_lineage_ledger)
    derived_head = load_execution_lineage_head(project)
    visibility = derive_execution_visibility(project)

    assert lineage_rows[-1]["head_effect"] == "clear"
    assert derived_head is not None
    assert derived_head.last_applied_event_id == lineage_rows[-1]["event_id"]
    assert derived_head.execution is None
    assert get_current_execution(project) is None
    assert visibility is not None
    assert visibility.has_live_execution is False


def test_get_current_execution_prefers_lineage_head_over_stale_snapshot(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.constants import ProjectLayout
    from gpd.core.execution_lineage import (
        ExecutionHeadEffect,
        build_execution_lineage_entry,
        execution_lineage_ledger_path,
        project_execution_lineage_head,
        write_execution_lineage_head,
    )
    from gpd.core.observability import get_current_execution

    layout = ProjectLayout(project)
    layout.observability_dir.mkdir(parents=True, exist_ok=True)
    layout.current_observability_execution.write_text(
        json.dumps(
            {
                "session_id": "stale-session",
                "phase": "03",
                "plan": "02",
                "segment_status": "paused",
                "current_task": "Stale snapshot task",
                "updated_at": "2026-03-29T12:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )

    lineage_execution = {
        "session_id": "lineage-session",
        "phase": "03",
        "plan": "02",
        "segment_status": "blocked",
        "blocked_reason": "manual stop required",
        "current_task": "Lineage head task",
        "updated_at": "2026-03-29T12:03:00+00:00",
    }
    lineage_entry = build_execution_lineage_entry(
        kind="segment.blocked",
        event_id="evt-lineage",
        recorded_at="2026-03-29T12:03:00+00:00",
        head_effect=ExecutionHeadEffect.SEED,
        head_after=lineage_execution,
        seq=4,
    )
    ledger_path = execution_lineage_ledger_path(project)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    ledger_path.write_text(lineage_entry.model_dump_json() + "\n", encoding="utf-8")
    write_execution_lineage_head(
        project,
        project_execution_lineage_head(
            lineage_execution,
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
    assert snapshot.current_task != "Stale snapshot task"


def test_get_current_execution_falls_back_to_stale_snapshot_when_head_cache_is_missing(
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
