"""Focused regression tests for session-scoped gpd.core.observability behavior."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path


def _bootstrap_project(tmp_path: Path) -> Path:
    planning = tmp_path / ".gpd"
    planning.mkdir()
    return tmp_path


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_ensure_session_writes_single_session_log_and_current_pointer(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import ensure_session

    session = ensure_session(project, source="cli", metadata={"argv": ["execute-phase"]}, command="execute-phase")
    assert session is not None

    observability_dir = project / ".gpd" / "observability"
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
    session_log = project / ".gpd" / "observability" / "sessions" / f"{session.session_id}.jsonl"
    events = _read_jsonl(session_log)
    assert len(events) == 3
    assert events[0]["category"] == "session"
    assert events[1]["category"] == "trace"
    assert events[1]["name"] == "trace_stop"
    assert events[2]["category"] == "session"
    assert events[2]["action"] == "finish"
    assert events[2]["status"] == "ok"
    assert events[2]["data"]["ended_by"]["name"] == "trace_stop"

    current_session = json.loads((project / ".gpd" / "observability" / "current-session.json").read_text(encoding="utf-8"))
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


def test_get_current_execution_normalizes_phase_plan_and_checkpoint_reason(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    observability_dir = project / ".gpd" / "observability"
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

    sessions_dir = project / ".gpd" / "observability" / "sessions"
    session_logs = sorted(sessions_dir.glob("*.jsonl"))
    assert len(session_logs) == 1

    events = _read_jsonl(session_logs[0])
    assert len(events) == 2
    assert events[0]["action"] == "start"
    assert events[1]["category"] == "workflow"
    assert events[1]["name"] == "resume"
    assert events[1]["command"] == "resume-work"

    current_session = json.loads((project / ".gpd" / "observability" / "current-session.json").read_text(encoding="utf-8"))
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

    current_session = json.loads((project / ".gpd" / "observability" / "current-session.json").read_text(encoding="utf-8"))
    assert current_session["session_id"] == session.session_id
    assert current_session["status"] == "ok"

    next_session = ensure_session(project, source="trace", command="trace resume")
    assert next_session is not None
    assert next_session.session_id != session.session_id

    session_log = project / ".gpd" / "observability" / "sessions" / f"{session.session_id}.jsonl"
    events = _read_jsonl(session_log)
    assert events[-1]["name"] == "late_note"
    assert events[-2]["action"] == "finish"


def test_gpd_span_does_not_write_observability_artifacts(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import gpd_span

    with gpd_span("test.span", domain="physics"):
        pass

    assert not (project / ".gpd" / "observability").exists()


def test_instrument_gpd_function_sync_does_not_emit_local_events(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import instrument_gpd_function

    @instrument_gpd_function("test.func")
    def my_func(x: int) -> int:
        return x * 2

    assert my_func(5) == 10
    assert not (project / ".gpd" / "observability").exists()


def test_instrument_gpd_function_async_does_not_emit_local_events(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import instrument_gpd_function

    @instrument_gpd_function("test.async_func")
    async def my_async_func(x: int) -> int:
        return x + 1

    result = asyncio.run(my_async_func(3))
    assert result == 4
    assert not (project / ".gpd" / "observability").exists()


def test_show_events_reads_session_streams(tmp_path: Path) -> None:
    project = _bootstrap_project(tmp_path)
    sessions_dir = project / ".gpd" / "observability" / "sessions"
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

    assert not (project / ".gpd" / "observability").exists()


def test_gpd_span_accepts_prefixed_cwd_without_side_effects(tmp_path: Path, monkeypatch) -> None:
    project = _bootstrap_project(tmp_path)
    monkeypatch.chdir(project)

    from gpd.core.observability import gpd_span

    with gpd_span("test.prefixed_cwd", **{"gpd.cwd": str(project)}):
        pass

    assert not (project / ".gpd" / "observability").exists()


def test_list_sessions_empty_project(tmp_path: Path) -> None:
    project = _bootstrap_project(tmp_path)
    from gpd.core.observability import list_sessions

    result = list_sessions(project)
    assert result.count == 0
    assert result.sessions == []


def test_list_sessions_returns_sessions_from_logs(tmp_path: Path) -> None:
    project = _bootstrap_project(tmp_path)
    sessions_dir = project / ".gpd" / "observability" / "sessions"
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
