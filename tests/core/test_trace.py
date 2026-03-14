"""Tests for gpd.core.trace — JSONL execution tracing."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import gpd.core.trace as trace_module
from gpd.core.errors import TraceError
from gpd.core.trace import (
    USER_EVENT_TYPES,
    TraceEventType,
    TraceListResult,
    TraceLogResult,
    TraceShowResult,
    TraceStartResult,
    TraceStopResult,
    trace_log,
    trace_show,
    trace_start,
    trace_stop,
)

# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Minimal project with .gpd/ directory."""
    (tmp_path / ".gpd").mkdir()
    return tmp_path


# ─── trace_start ─────────────────────────────────────────────────────────────


class TestTraceStart:
    def test_creates_trace_file(self, project: Path) -> None:
        result = trace_start(project, "01", "plan-01")
        assert isinstance(result, TraceStartResult)
        assert result.started is True
        assert result.phase == "01"
        assert result.plan == "plan-01"
        assert (project / ".gpd" / "traces" / "01-plan-01.jsonl").exists()

    def test_writes_trace_start_event(self, project: Path) -> None:
        trace_start(project, "01", "plan-01")
        trace_file = project / ".gpd" / "traces" / "01-plan-01.jsonl"
        lines = trace_file.read_text().strip().splitlines()
        assert len(lines) == 1
        event = json.loads(lines[0])
        assert event["type"] == "trace_start"
        assert event["phase"] == "01"
        assert event["plan"] == "plan-01"
        assert event["trace_id"] == "01-plan-01"
        assert "timestamp" in event

    def test_sets_active_trace_marker(self, project: Path) -> None:
        trace_start(project, "02", "test-plan")
        marker = project / ".gpd" / "traces" / ".active-trace"
        assert marker.exists()
        data = json.loads(marker.read_text())
        assert data["phase"] == "02"
        assert data["plan"] == "test-plan"

    def test_empty_phase_raises(self, project: Path) -> None:
        with pytest.raises(TraceError, match="phase is required"):
            trace_start(project, "", "plan")

    def test_empty_plan_raises(self, project: Path) -> None:
        with pytest.raises(TraceError, match="plan is required"):
            trace_start(project, "01", "")

    def test_double_start_raises(self, project: Path) -> None:
        trace_start(project, "01", "plan-01")
        with pytest.raises(TraceError, match="Active trace already exists"):
            trace_start(project, "01", "plan-02")


# ─── trace_log ───────────────────────────────────────────────────────────────


class TestTraceLog:
    def test_appends_event(self, project: Path) -> None:
        trace_start(project, "01", "plan-01")
        result = trace_log(project, "checkpoint", {"step": "verify"})
        assert isinstance(result, TraceLogResult)
        assert result.logged is True
        assert result.event_type == "checkpoint"
        assert result.phase == "01"
        assert result.plan == "plan-01"
        assert result.trace_id == "01-plan-01"

        trace_file = project / ".gpd" / "traces" / "01-plan-01.jsonl"
        lines = trace_file.read_text().strip().splitlines()
        assert len(lines) == 2  # trace_start + checkpoint
        event = json.loads(lines[1])
        assert event["type"] == "checkpoint"
        assert event["phase"] == "01"
        assert event["plan"] == "plan-01"
        assert event["trace_id"] == "01-plan-01"
        assert event["data"]["step"] == "verify"

    def test_unknown_event_type_raises(self, project: Path) -> None:
        trace_start(project, "01", "plan-01")
        with pytest.raises(TraceError, match="Unknown event type"):
            trace_log(project, "nonexistent_type")

    def test_no_active_trace_raises(self, project: Path) -> None:
        with pytest.raises(TraceError, match="No active trace"):
            trace_log(project, "info")

    def test_all_user_event_types(self, project: Path) -> None:
        trace_start(project, "01", "plan-01")
        for evt_type in USER_EVENT_TYPES:
            result = trace_log(project, evt_type)
            assert result.event_type == evt_type

    def test_internal_event_types_rejected(self, project: Path) -> None:
        trace_start(project, "01", "plan-01")
        with pytest.raises(TraceError, match="Unknown event type"):
            trace_log(project, TraceEventType.TRACE_START)
        with pytest.raises(TraceError, match="Unknown event type"):
            trace_log(project, TraceEventType.TRACE_STOP)


# ─── trace_stop ──────────────────────────────────────────────────────────────


class TestTraceStop:
    def test_stop_returns_counts(self, project: Path) -> None:
        trace_start(project, "01", "plan-01")
        trace_log(project, "checkpoint")
        trace_log(project, "checkpoint")
        trace_log(project, "info")
        result = trace_stop(project)
        assert isinstance(result, TraceStopResult)
        assert result.stopped is True
        assert result.phase == "01"
        assert result.plan == "plan-01"
        assert result.event_counts.get("checkpoint") == 2
        assert result.event_counts.get("info") == 1

    def test_stop_removes_active_marker(self, project: Path) -> None:
        trace_start(project, "01", "plan-01")
        trace_stop(project)
        marker = project / ".gpd" / "traces" / ".active-trace"
        assert not marker.exists()

    def test_stop_writes_summary_event(self, project: Path) -> None:
        trace_start(project, "01", "plan-01")
        trace_log(project, "info")
        trace_stop(project)
        trace_file = project / ".gpd" / "traces" / "01-plan-01.jsonl"
        lines = trace_file.read_text().strip().splitlines()
        last = json.loads(lines[-1])
        assert last["type"] == "trace_stop"
        assert last["phase"] == "01"
        assert last["plan"] == "plan-01"
        assert last["trace_id"] == "01-plan-01"
        assert "summary" in last
        assert "event_counts" in last["summary"]

    def test_stop_without_active_raises(self, project: Path) -> None:
        with pytest.raises(TraceError, match="No active trace"):
            trace_stop(project)

    def test_can_start_new_after_stop(self, project: Path) -> None:
        trace_start(project, "01", "plan-01")
        trace_stop(project)
        result = trace_start(project, "02", "plan-01")
        assert result.phase == "02"


# ─── trace_show ──────────────────────────────────────────────────────────────


class TestTraceShow:
    def test_show_active_trace(self, project: Path) -> None:
        trace_start(project, "01", "plan-01")
        trace_log(project, "info", {"msg": "hello"})
        result = trace_show(project)
        assert isinstance(result, TraceShowResult)
        assert result.count == 2  # trace_start + info

    def test_show_by_phase_and_plan(self, project: Path) -> None:
        trace_start(project, "01", "plan-01")
        trace_log(project, "info")
        trace_stop(project)
        result = trace_show(project, phase="01", plan="plan-01")
        assert isinstance(result, TraceShowResult)
        assert result.count >= 3  # start + info + stop

    def test_show_by_phase_only(self, project: Path) -> None:
        trace_start(project, "01", "plan-01")
        trace_log(project, "info")
        trace_stop(project)
        trace_start(project, "01", "plan-02")
        trace_log(project, "checkpoint")
        trace_stop(project)
        result = trace_show(project, phase="01")
        assert isinstance(result, TraceShowResult)
        # Both traces aggregated
        assert result.count >= 4

    def test_show_filter_by_event_type(self, project: Path) -> None:
        trace_start(project, "01", "plan-01")
        trace_log(project, "info")
        trace_log(project, "checkpoint")
        trace_log(project, "info")
        result = trace_show(project, event_type="info")
        assert isinstance(result, TraceShowResult)
        assert result.count == 2
        for evt in result.events:
            assert evt.event_type == "info"

    def test_show_last_n(self, project: Path) -> None:
        trace_start(project, "01", "plan-01")
        for _ in range(5):
            trace_log(project, "info")
        result = trace_show(project, last=2)
        assert isinstance(result, TraceShowResult)
        assert result.count == 2

    def test_show_nonexistent_trace_raises(self, project: Path) -> None:
        (project / ".gpd" / "traces").mkdir(parents=True, exist_ok=True)
        with pytest.raises(TraceError, match="No trace found"):
            trace_show(project, phase="99", plan="nonexistent")

    def test_show_lists_available_when_no_active(self, project: Path) -> None:
        trace_start(project, "01", "plan-01")
        trace_stop(project)
        result = trace_show(project)
        assert isinstance(result, TraceListResult)
        assert len(result.available_traces) >= 1


    def test_show_phase_with_spaces(self, project: Path) -> None:
        """Phase names with spaces should match trace files (uses _safe_trace_component)."""
        trace_start(project, 'phase one', 'plan-01')
        trace_log(project, 'info')
        trace_stop(project)
        # The trace file is named 'phase-one-plan-01.jsonl'.
        # Filtering by phase='phase one' must sanitise the input to 'phase-one'.
        result = trace_show(project, phase='phase one')
        assert isinstance(result, TraceShowResult)
        assert result.count >= 3  # start + info + stop

    def test_show_no_traces_dir_raises(self, project: Path) -> None:
        with pytest.raises(TraceError, match="No traces directory"):
            trace_show(project)


# ─── TraceEventType enum ─────────────────────────────────────────────────────


class TestTraceEventType:
    def test_user_event_types_excludes_internal(self) -> None:
        assert "trace_start" not in USER_EVENT_TYPES
        assert "trace_stop" not in USER_EVENT_TYPES

    def test_user_event_types_includes_expected(self) -> None:
        assert "info" in USER_EVENT_TYPES
        assert "checkpoint" in USER_EVENT_TYPES
        assert "error" in USER_EVENT_TYPES
        assert "deviation" in USER_EVENT_TYPES
        assert "file_read" in USER_EVENT_TYPES
        assert "file_write" in USER_EVENT_TYPES


# ─── Edge cases ──────────────────────────────────────────────────────────────


class TestTraceEdgeCases:
    def test_special_chars_in_plan_name(self, project: Path) -> None:
        result = trace_start(project, "01", "my plan/with special!chars")
        assert result.started is True
        trace_file = project / ".gpd" / "traces" / "01-my-plan-with-special-chars.jsonl"
        assert trace_file.exists()

    def test_log_with_none_data(self, project: Path) -> None:
        trace_start(project, "01", "plan-01")
        result = trace_log(project, "info")
        assert result.logged is True

    def test_active_trace_survives_project_rename(self, project: Path) -> None:
        start_result = trace_start(project, "01", "plan-01")
        assert start_result.started is True

        original_trace_file = project / ".gpd" / "traces" / "01-plan-01.jsonl"
        renamed_project = project.with_name(f"{project.name}-renamed")
        project.rename(renamed_project)

        log_result = trace_log(renamed_project, "checkpoint", {"step": "after-rename"})
        stop_result = trace_stop(renamed_project)

        moved_trace_file = renamed_project / ".gpd" / "traces" / "01-plan-01.jsonl"
        assert log_result.logged is True
        assert stop_result.stopped is True
        assert moved_trace_file.exists()
        assert not original_trace_file.exists()

        events = [json.loads(line) for line in moved_trace_file.read_text(encoding="utf-8").splitlines() if line.strip()]
        assert [event["type"] for event in events] == ["trace_start", "checkpoint", "trace_stop"]
        assert events[1]["data"]["step"] == "after-rename"

        active_marker = renamed_project / ".gpd" / "traces" / ".active-trace"
        assert not active_marker.exists()

    def test_full_lifecycle(self, project: Path) -> None:
        """Complete start -> log multiple -> stop -> show cycle."""
        trace_start(project, "03", "integration")
        trace_log(project, "convention_load", {"keys": ["metric"]})
        trace_log(project, "file_write", {"path": "output.tex"})
        trace_log(project, "assertion", {"claim": "unitarity"})
        stop_result = trace_stop(project)
        assert stop_result.event_counts.get("convention_load") == 1
        assert stop_result.event_counts.get("file_write") == 1
        assert stop_result.event_counts.get("assertion") == 1

        show_result = trace_show(project, phase="03", plan="integration")
        assert isinstance(show_result, TraceShowResult)
        assert show_result.count == 5  # start + 3 logs + stop

    def test_trace_mirrors_events_to_observability_helpers(self, project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[tuple[str, dict[str, object]]] = []

        def fake_helper(helper_name: str, *, cwd: Path | None = None, **kwargs: object) -> object | None:
            if helper_name in {"ensure_session", "ensure_observability_session", "start_session"}:
                return {"session_id": "sess-trace-1"}
            if helper_name in {"observe_event", "record_event", "log_event"}:
                payload = dict(kwargs)
                if cwd is not None:
                    payload["cwd"] = cwd
                calls.append((helper_name, payload))
                return {"recorded": True}
            return None

        monkeypatch.setattr(trace_module, "_call_observability_helper", fake_helper)

        start_result = trace_start(project, "05", "plan-a")
        log_result = trace_log(project, "info", {"message": "hello"})
        stop_result = trace_stop(project)

        assert start_result.session_id == "sess-trace-1"
        assert log_result.session_id == "sess-trace-1"
        assert stop_result.session_id == "sess-trace-1"
        assert len(calls) == 3
        assert [payload["action"] for _, payload in calls] == ["start", "log", "stop"]
        assert all(payload["category"] == "trace" for _, payload in calls)
        assert all(payload["phase"] == "05" for _, payload in calls)
        assert all(payload["plan"] == "plan-a" for _, payload in calls)
        assert all(payload["trace_id"] == "05-plan-a" for _, payload in calls)
