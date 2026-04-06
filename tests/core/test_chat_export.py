"""Tests for gpd.core.chat_export — chat log export for sharing and debugging."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core.chat_export import (
    ChatExportError,
    ChatExportResult,
    ChatSessionListResult,
    export_chat,
    list_chat_sessions,
)


# ─── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def project(tmp_path: Path) -> Path:
    """Minimal project with GPD/ directory."""
    (tmp_path / "GPD").mkdir()
    return tmp_path


@pytest.fixture
def project_with_sessions(project: Path) -> Path:
    """Project with sample observability sessions."""
    sessions_dir = project / "GPD" / "observability" / "sessions"
    sessions_dir.mkdir(parents=True)

    # Session 1 -- a simple session with start + event + finish
    session1 = sessions_dir / "session-001.jsonl"
    events = [
        {
            "event_id": "evt-1",
            "timestamp": "2026-01-15T10:00:00+00:00",
            "session_id": "session-001",
            "category": "session",
            "name": "lifecycle",
            "action": "start",
            "status": "active",
            "command": "gpd:execute-phase",
        },
        {
            "event_id": "evt-2",
            "timestamp": "2026-01-15T10:01:00+00:00",
            "session_id": "session-001",
            "category": "workflow",
            "name": "plan_execution",
            "action": "log",
            "status": "ok",
            "command": "gpd:execute-phase",
            "phase": "01",
            "plan": "setup",
            "data": {"task": "initialize project"},
        },
        {
            "event_id": "evt-3",
            "timestamp": "2026-01-15T10:05:00+00:00",
            "session_id": "session-001",
            "category": "session",
            "name": "lifecycle",
            "action": "finish",
            "status": "completed",
            "command": "gpd:execute-phase",
        },
    ]
    session1.write_text("\n".join(json.dumps(e) for e in events) + "\n")

    # Session 2 -- a smaller session
    session2 = sessions_dir / "session-002.jsonl"
    events2 = [
        {
            "event_id": "evt-4",
            "timestamp": "2026-01-15T11:00:00+00:00",
            "session_id": "session-002",
            "category": "session",
            "name": "lifecycle",
            "action": "start",
            "status": "active",
            "command": "gpd:progress",
        },
    ]
    session2.write_text("\n".join(json.dumps(e) for e in events2) + "\n")

    return project


@pytest.fixture
def project_with_traces(project: Path) -> Path:
    """Project with sample trace events."""
    traces_dir = project / "GPD" / "traces"
    traces_dir.mkdir(parents=True)

    trace_file = traces_dir / "01-setup.jsonl"
    events = [
        {
            "timestamp": "2026-01-15T10:00:30+00:00",
            "type": "trace_start",
            "phase": "01",
            "plan": "setup",
            "trace_id": "01-setup",
        },
        {
            "timestamp": "2026-01-15T10:01:00+00:00",
            "type": "file_write",
            "phase": "01",
            "plan": "setup",
            "trace_id": "01-setup",
            "data": {"path": "src/main.py", "action": "created"},
        },
        {
            "timestamp": "2026-01-15T10:02:00+00:00",
            "type": "trace_stop",
            "phase": "01",
            "plan": "setup",
            "trace_id": "01-setup",
            "summary": {"started_at": "2026-01-15T10:00:30+00:00", "event_counts": {"file_write": 1}},
        },
    ]
    trace_file.write_text("\n".join(json.dumps(e) for e in events) + "\n")

    return project


@pytest.fixture
def project_with_all(project_with_sessions: Path) -> Path:
    """Project with both sessions and traces."""
    traces_dir = project_with_sessions / "GPD" / "traces"
    traces_dir.mkdir(parents=True, exist_ok=True)

    trace_file = traces_dir / "01-setup.jsonl"
    events = [
        {
            "timestamp": "2026-01-15T10:00:30+00:00",
            "type": "trace_start",
            "phase": "01",
            "plan": "setup",
            "trace_id": "01-setup",
        },
        {
            "timestamp": "2026-01-15T10:02:00+00:00",
            "type": "trace_stop",
            "phase": "01",
            "plan": "setup",
            "trace_id": "01-setup",
        },
    ]
    trace_file.write_text("\n".join(json.dumps(e) for e in events) + "\n")

    return project_with_sessions


# ─── list_chat_sessions ─────────────────────────────────────────────────────


class TestListChatSessions:
    def test_empty_project(self, project: Path) -> None:
        result = list_chat_sessions(project)
        assert isinstance(result, ChatSessionListResult)
        assert result.count == 0
        assert result.sessions == []

    def test_lists_sessions(self, project_with_sessions: Path) -> None:
        result = list_chat_sessions(project_with_sessions)
        assert result.count == 2
        assert len(result.sessions) == 2

        # Sessions are sorted by last_event_at descending
        ids = [s.session_id for s in result.sessions]
        assert "session-001" in ids
        assert "session-002" in ids

    def test_session_metadata(self, project_with_sessions: Path) -> None:
        result = list_chat_sessions(project_with_sessions)
        session1 = next(s for s in result.sessions if s.session_id == "session-001")
        assert session1.event_count == 3
        assert session1.command == "gpd:execute-phase"

    def test_no_sessions_dir(self, project: Path) -> None:
        """No observability dir at all."""
        result = list_chat_sessions(project)
        assert result.count == 0


# ─── export_chat — markdown format ──────────────────────────────────────────


class TestExportChatMarkdown:
    def test_export_empty_project(self, project: Path) -> None:
        result = export_chat(project, format="markdown")
        assert isinstance(result, ChatExportResult)
        assert result.exported is True
        assert result.format == "markdown"
        assert result.file.endswith("chat-log.md")
        assert Path(result.file).exists()

        content = Path(result.file).read_text()
        assert "GPD Chat Log Export" in content
        assert "No events found to export" in content

    def test_export_with_sessions(self, project_with_sessions: Path) -> None:
        result = export_chat(project_with_sessions, format="markdown")
        # session-001 has 3 events, session-002 has 1 event => 4 total
        assert result.session_count == 4
        assert result.event_count >= 4

        content = Path(result.file).read_text()
        assert "Session Events" in content
        assert "gpd:execute-phase" in content

    def test_export_with_traces(self, project_with_traces: Path) -> None:
        result = export_chat(project_with_traces, format="markdown")
        assert result.event_count >= 3  # 3 trace events

        content = Path(result.file).read_text()
        assert "Trace Events" in content

    def test_export_specific_session(self, project_with_sessions: Path) -> None:
        result = export_chat(project_with_sessions, format="markdown", session_id="session-001")
        assert result.session_count == 3  # Only events from session-001

        content = Path(result.file).read_text()
        assert "session-001" in content

    def test_no_traces_flag(self, project_with_all: Path) -> None:
        result = export_chat(project_with_all, format="markdown", include_traces=False)
        content = Path(result.file).read_text()
        assert "Trace Events" not in content

    def test_custom_output_path(self, project_with_sessions: Path) -> None:
        out = project_with_sessions / "my-export.md"
        result = export_chat(project_with_sessions, format="markdown", output_path=str(out))
        assert result.file == str(out)
        assert out.exists()

    def test_default_output_in_exports_dir(self, project: Path) -> None:
        result = export_chat(project, format="markdown")
        assert "exports" in result.file
        assert (project / "exports" / "chat-log.md").exists()

    def test_last_n_events(self, project_with_sessions: Path) -> None:
        result = export_chat(project_with_sessions, format="markdown", last=2)
        assert result.session_count == 2


# ─── export_chat — JSON format ──────────────────────────────────────────────


class TestExportChatJson:
    def test_export_json_format(self, project_with_sessions: Path) -> None:
        result = export_chat(project_with_sessions, format="json")
        assert result.format == "json"
        assert result.file.endswith("chat-log.json")
        assert Path(result.file).exists()

        data = json.loads(Path(result.file).read_text())
        assert data["gpd_chat_export"] is True
        assert data["version"] == "1.0"
        assert isinstance(data["session_events"], list)
        assert data["session_event_count"] == 4

    def test_json_includes_metadata(self, project: Path) -> None:
        result = export_chat(project, format="json")
        data = json.loads(Path(result.file).read_text())
        assert "metadata" in data
        assert "exported_at" in data["metadata"]
        assert "format" in data["metadata"]

    def test_json_with_traces(self, project_with_all: Path) -> None:
        result = export_chat(project_with_all, format="json")
        data = json.loads(Path(result.file).read_text())
        assert data["trace_event_count"] >= 2


# ─── Sanitization ───────────────────────────────────────────────────────────


class TestSanitization:
    def test_api_keys_redacted(self, project: Path) -> None:
        """API keys should be replaced with <REDACTED_API_KEY>."""
        sessions_dir = project / "GPD" / "observability" / "sessions"
        sessions_dir.mkdir(parents=True)
        session_file = sessions_dir / "test-session.jsonl"
        event = {
            "event_id": "evt-1",
            "timestamp": "2026-01-15T10:00:00+00:00",
            "session_id": "test-session",
            "category": "test",
            "name": "test",
            "action": "log",
            "status": "ok",
            "data": {"api_key": "sk-abc123def456ghi789jkl012mno"},
        }
        session_file.write_text(json.dumps(event) + "\n")

        result = export_chat(project, format="markdown", sanitize=True)
        content = Path(result.file).read_text()
        assert "sk-abc123def456ghi789jkl012mno" not in content
        assert "REDACTED" in content

    def test_home_paths_redacted(self, project: Path) -> None:
        """Home directory paths should be replaced with ~."""
        sessions_dir = project / "GPD" / "observability" / "sessions"
        sessions_dir.mkdir(parents=True)
        session_file = sessions_dir / "test-session.jsonl"
        event = {
            "event_id": "evt-1",
            "timestamp": "2026-01-15T10:00:00+00:00",
            "session_id": "test-session",
            "category": "test",
            "name": "test",
            "action": "log",
            "status": "ok",
            "data": {"path": "/Users/researcher/projects/physics"},
        }
        session_file.write_text(json.dumps(event) + "\n")

        result = export_chat(project, format="markdown", sanitize=True)
        content = Path(result.file).read_text()
        assert "/Users/researcher" not in content

    def test_no_sanitize_preserves_data(self, project: Path) -> None:
        """When sanitize=False, data should be preserved as-is."""
        sessions_dir = project / "GPD" / "observability" / "sessions"
        sessions_dir.mkdir(parents=True)
        session_file = sessions_dir / "test-session.jsonl"
        event = {
            "event_id": "evt-1",
            "timestamp": "2026-01-15T10:00:00+00:00",
            "session_id": "test-session",
            "category": "test",
            "name": "test",
            "action": "log",
            "status": "ok",
            "data": {"path": "/Users/researcher/projects/physics"},
        }
        session_file.write_text(json.dumps(event) + "\n")

        result = export_chat(project, format="markdown", sanitize=False)
        content = Path(result.file).read_text()
        assert "/Users/researcher/projects/physics" in content

    def test_json_sanitization(self, project: Path) -> None:
        """JSON export should also sanitize."""
        sessions_dir = project / "GPD" / "observability" / "sessions"
        sessions_dir.mkdir(parents=True)
        session_file = sessions_dir / "test-session.jsonl"
        event = {
            "event_id": "evt-1",
            "timestamp": "2026-01-15T10:00:00+00:00",
            "session_id": "test-session",
            "category": "test",
            "name": "test",
            "action": "log",
            "status": "ok",
            "data": {"secret_key": "sk-verySecretKey1234567890abcdef"},
        }
        session_file.write_text(json.dumps(event) + "\n")

        result = export_chat(project, format="json", sanitize=True)
        data = json.loads(Path(result.file).read_text())
        raw_text = json.dumps(data)
        assert "sk-verySecretKey1234567890abcdef" not in raw_text


# ─── Error Handling ──────────────────────────────────────────────────────────


class TestErrorHandling:
    def test_invalid_format(self, project: Path) -> None:
        with pytest.raises(ChatExportError, match="Unsupported format"):
            export_chat(project, format="xml")

    def test_export_creates_exports_dir(self, project: Path) -> None:
        """exports/ directory should be created automatically."""
        exports_dir = project / "exports"
        assert not exports_dir.exists()
        export_chat(project, format="markdown")
        assert exports_dir.exists()


# ─── Trace Filtering ────────────────────────────────────────────────────────


class TestTraceFiltering:
    def test_filter_by_phase(self, project_with_traces: Path) -> None:
        result = export_chat(project_with_traces, format="json", phase="01")
        data = json.loads(Path(result.file).read_text())
        assert data["trace_event_count"] == 3

    def test_filter_by_phase_no_match(self, project_with_traces: Path) -> None:
        result = export_chat(project_with_traces, format="json", phase="99")
        data = json.loads(Path(result.file).read_text())
        assert data["trace_event_count"] == 0

    def test_filter_by_phase_and_plan(self, project_with_traces: Path) -> None:
        result = export_chat(project_with_traces, format="json", phase="01", plan="setup")
        data = json.loads(Path(result.file).read_text())
        assert data["trace_event_count"] == 3
