"""Chat log export for sharing, debugging, and bug reports.

Collects observability sessions and trace events from the project-local
``GPD/observability/`` and ``GPD/traces/`` trees and serializes them into
shareable formats (Markdown and JSON).

Public API
----------
export_chat  -- export chat logs to file(s)
list_chat_sessions  -- list available sessions for export
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

from gpd.core.constants import ProjectLayout
from gpd.core.errors import GPDError
from gpd.core.observability import instrument_gpd_function
from gpd.core.utils import safe_read_file

__all__ = [
    "ChatExportError",
    "ChatExportResult",
    "ChatSessionInfo",
    "ChatSessionListResult",
    "export_chat",
    "list_chat_sessions",
]


class ChatExportError(GPDError, ValueError):
    """Raised when chat export fails."""


# ─── Result Models ───────────────────────────────────────────────────────────


class ChatSessionInfo(BaseModel):
    """Summary of an available chat session."""

    session_id: str
    started_at: str = ""
    last_event_at: str = ""
    command: str | None = None
    event_count: int = 0
    status: str = "unknown"


class ChatSessionListResult(BaseModel):
    """Result from listing available chat sessions."""

    count: int
    sessions: list[ChatSessionInfo] = Field(default_factory=list)


class ChatExportResult(BaseModel):
    """Result from exporting chat logs."""

    exported: bool = True
    format: str
    file: str
    session_count: int = 0
    event_count: int = 0
    sanitized: bool = True


# ─── Sanitization ────────────────────────────────────────────────────────────

# Patterns to redact from exported content
_SENSITIVE_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    # API keys and tokens
    (re.compile(r"(sk-[A-Za-z0-9_-]{20,})"), "<REDACTED_API_KEY>"),
    (re.compile(r"(token|key|secret|password|credential)([\"']?\s*[:=]\s*[\"']?)([^\s\"',}{]+)", re.IGNORECASE), r"\1\2<REDACTED>"),
    # Home directory paths -- replace with ~
    (re.compile(r"/(?:Users|home)/[A-Za-z0-9._-]+"), "~"),
]


def _sanitize_text(text: str) -> str:
    """Remove sensitive data from exported text."""
    result = text
    for pattern, replacement in _SENSITIVE_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def _sanitize_dict(data: dict[str, object]) -> dict[str, object]:
    """Recursively sanitize values in a dict."""
    cleaned: dict[str, object] = {}
    for key, value in data.items():
        if isinstance(value, str):
            cleaned[key] = _sanitize_text(value)
        elif isinstance(value, dict):
            cleaned[key] = _sanitize_dict(value)  # type: ignore[arg-type]
        elif isinstance(value, list):
            cleaned[key] = [
                _sanitize_dict(item) if isinstance(item, dict)
                else _sanitize_text(item) if isinstance(item, str)
                else item
                for item in value
            ]
        else:
            cleaned[key] = value
    return cleaned


# ─── Internal Helpers ────────────────────────────────────────────────────────


def _read_jsonl_events(path: Path) -> list[dict[str, object]]:
    """Read JSONL events from a file."""
    content = safe_read_file(path)
    if content is None:
        return []
    events: list[dict[str, object]] = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue
        if isinstance(raw, dict):
            events.append(raw)
    return events


def _collect_session_events(
    layout: ProjectLayout,
    *,
    session_id: str | None = None,
    last: int | None = None,
) -> list[dict[str, object]]:
    """Collect observability events, optionally filtered by session."""
    sessions_dir = layout.observability_sessions_dir
    if not sessions_dir.is_dir():
        return []

    if session_id:
        path = layout.observability_session_events(session_id)
        return _read_jsonl_events(path)

    # All sessions, merged by timestamp
    all_events: list[dict[str, object]] = []
    for session_path in sorted(sessions_dir.glob("*.jsonl")):
        all_events.extend(_read_jsonl_events(session_path))

    all_events.sort(key=lambda e: str(e.get("timestamp", "")))

    if last and last > 0:
        all_events = all_events[-last:]

    return all_events


def _collect_trace_events(
    layout: ProjectLayout,
    *,
    phase: str | None = None,
    plan: str | None = None,
) -> list[dict[str, object]]:
    """Collect trace events, optionally filtered by phase/plan."""
    traces_dir = layout.traces_dir
    if not traces_dir.is_dir():
        return []

    if phase and plan:
        path = layout.trace_file(phase, plan)
        return _read_jsonl_events(path)

    all_events: list[dict[str, object]] = []
    for trace_path in sorted(traces_dir.glob("*.jsonl")):
        events = _read_jsonl_events(trace_path)
        if phase:
            events = [e for e in events if str(e.get("phase", "")) == phase]
        all_events.extend(events)

    all_events.sort(key=lambda e: str(e.get("timestamp", "")))
    return all_events


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _format_timestamp(ts: str) -> str:
    """Format an ISO timestamp to a more readable form."""
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%Y-%m-%d %H:%M:%S UTC")
    except (ValueError, TypeError):
        return ts


def _event_summary_line(event: dict[str, object]) -> str:
    """Create a one-line summary of an event for markdown output."""
    category = event.get("category", "")
    name = event.get("name", "")
    action = event.get("action", "")
    status = event.get("status", "")
    event_type = event.get("type", "")

    # For trace events
    if event_type and not category:
        return f"[{event_type}] {action}" if action else f"[{event_type}]"

    parts = []
    if category:
        parts.append(f"[{category}]")
    if name:
        parts.append(str(name))
    if action and action != "log":
        parts.append(f"({action})")
    if status and status not in ("ok", "active"):
        parts.append(f"-> {status}")

    return " ".join(parts) if parts else "(unknown event)"


# ─── Format Generators ───────────────────────────────────────────────────────


def _generate_markdown(
    *,
    session_events: list[dict[str, object]],
    trace_events: list[dict[str, object]],
    sanitize: bool,
    metadata: dict[str, str],
) -> str:
    """Generate markdown-formatted chat log export."""
    lines: list[str] = []

    lines.append("# GPD Chat Log Export")
    lines.append("")
    lines.append(f"**Exported:** {metadata.get('exported_at', _now_iso())}")
    if metadata.get("project_root"):
        lines.append(f"**Project:** {metadata['project_root']}")
    if metadata.get("session_id"):
        lines.append(f"**Session:** {metadata['session_id']}")
    lines.append(f"**Sanitized:** {'Yes' if sanitize else 'No'}")
    lines.append("")

    # Session events section
    if session_events:
        lines.append("## Session Events")
        lines.append("")
        lines.append(f"Total events: {len(session_events)}")
        lines.append("")

        # Group by command for readability
        current_command: str | None = None
        for event in session_events:
            event_data = _sanitize_dict(event) if sanitize else event
            cmd = str(event_data.get("command", "")) or None
            timestamp = str(event_data.get("timestamp", ""))

            if cmd != current_command:
                current_command = cmd
                lines.append(f"### Command: {cmd or '(none)'}")
                lines.append("")

            summary = _event_summary_line(event_data)
            ts_display = _format_timestamp(timestamp) if timestamp else ""
            lines.append(f"- `{ts_display}` {summary}")

            # Include relevant data fields inline
            data = event_data.get("data")
            if isinstance(data, dict) and data:
                for k, v in data.items():
                    if k in ("session_id", "event_id", "span_id", "parent_span_id"):
                        continue
                    val_str = str(v) if not isinstance(v, (dict, list)) else json.dumps(v, default=str)
                    if len(val_str) <= 200:
                        lines.append(f"  - {k}: {val_str}")

        lines.append("")

    # Trace events section
    if trace_events:
        lines.append("## Trace Events")
        lines.append("")
        lines.append(f"Total trace events: {len(trace_events)}")
        lines.append("")

        for event in trace_events:
            event_data = _sanitize_dict(event) if sanitize else event
            timestamp = str(event_data.get("timestamp", ""))
            phase = event_data.get("phase", "")
            plan = event_data.get("plan", "")

            summary = _event_summary_line(event_data)
            ts_display = _format_timestamp(timestamp) if timestamp else ""
            phase_label = f"phase {phase}" if phase else ""
            plan_label = f"plan {plan}" if plan else ""
            context = " / ".join(filter(None, [phase_label, plan_label]))
            context_str = f" ({context})" if context else ""

            lines.append(f"- `{ts_display}` {summary}{context_str}")

            data = event_data.get("data")
            if isinstance(data, dict) and data:
                for k, v in data.items():
                    if k in ("trace_id", "session_id", "event_id"):
                        continue
                    val_str = str(v) if not isinstance(v, (dict, list)) else json.dumps(v, default=str)
                    if len(val_str) <= 200:
                        lines.append(f"  - {k}: {val_str}")

        lines.append("")

    if not session_events and not trace_events:
        lines.append("*No events found to export.*")
        lines.append("")

    lines.append("---")
    lines.append("*Generated with Get Physics Done (GPD)*")
    lines.append("")

    return "\n".join(lines)


def _generate_json(
    *,
    session_events: list[dict[str, object]],
    trace_events: list[dict[str, object]],
    sanitize: bool,
    metadata: dict[str, str],
) -> str:
    """Generate JSON-formatted chat log export."""
    sanitized_sessions = [_sanitize_dict(e) for e in session_events] if sanitize else session_events
    sanitized_traces = [_sanitize_dict(e) for e in trace_events] if sanitize else trace_events

    payload: dict[str, object] = {
        "gpd_chat_export": True,
        "version": "1.0",
        "metadata": metadata,
        "sanitized": sanitize,
        "session_events": sanitized_sessions,
        "trace_events": sanitized_traces,
        "session_event_count": len(sanitized_sessions),
        "trace_event_count": len(sanitized_traces),
    }
    return json.dumps(payload, indent=2, default=str)


# ─── Public API ──────────────────────────────────────────────────────────────


@instrument_gpd_function("chat_export.list_sessions")
def list_chat_sessions(cwd: Path) -> ChatSessionListResult:
    """List available chat sessions for export."""
    layout = ProjectLayout(cwd)
    sessions_dir = layout.observability_sessions_dir
    if not sessions_dir.is_dir():
        return ChatSessionListResult(count=0)

    sessions: list[ChatSessionInfo] = []
    for session_path in sorted(sessions_dir.glob("*.jsonl")):
        events = _read_jsonl_events(session_path)
        if not events:
            continue

        session_id = session_path.stem
        started_at = ""
        last_event_at = ""
        command: str | None = None
        status = "unknown"

        for event in events:
            ts = str(event.get("timestamp", ""))
            if not started_at and ts:
                started_at = ts
            if ts:
                last_event_at = ts

            evt_action = event.get("action")
            if evt_action == "start" and event.get("category") == "session":
                cmd = event.get("command")
                if isinstance(cmd, str):
                    command = cmd
            evt_status = event.get("status")
            if isinstance(evt_status, str):
                status = evt_status

        sessions.append(
            ChatSessionInfo(
                session_id=session_id,
                started_at=started_at,
                last_event_at=last_event_at,
                command=command,
                event_count=len(events),
                status=status,
            )
        )

    sessions.sort(key=lambda s: s.last_event_at, reverse=True)
    return ChatSessionListResult(count=len(sessions), sessions=sessions)


@instrument_gpd_function("chat_export.export")
def export_chat(
    cwd: Path,
    *,
    format: str = "markdown",
    output_path: str | None = None,
    session_id: str | None = None,
    include_traces: bool = True,
    sanitize: bool = True,
    last: int | None = None,
    phase: str | None = None,
    plan: str | None = None,
) -> ChatExportResult:
    """Export chat logs to a file.

    Parameters
    ----------
    cwd:
        Project root directory.
    format:
        Output format -- ``markdown`` or ``json``.
    output_path:
        Path for the output file. Defaults to ``exports/chat-log.md``
        or ``exports/chat-log.json``.
    session_id:
        Limit export to a specific observability session.
    include_traces:
        Whether to include trace events alongside session events.
    sanitize:
        Whether to redact sensitive data (API keys, home paths).
    last:
        Limit to the most recent N session events.
    phase:
        Filter trace events by phase.
    plan:
        Filter trace events by plan (requires phase).

    Returns
    -------
    ChatExportResult
        Metadata about the exported file.

    Raises
    ------
    ChatExportError
        If the format is invalid.
    """
    fmt = format.strip().lower()
    if fmt not in ("markdown", "json"):
        raise ChatExportError(f"Unsupported format: {format!r}. Use 'markdown' or 'json'.")

    layout = ProjectLayout(cwd)

    # Collect events
    session_events = _collect_session_events(layout, session_id=session_id, last=last)
    trace_events = _collect_trace_events(layout, phase=phase, plan=plan) if include_traces else []

    # Build metadata
    project_root = str(cwd)
    if sanitize:
        project_root = _sanitize_text(project_root)

    metadata: dict[str, str] = {
        "exported_at": _now_iso(),
        "project_root": project_root,
        "format": fmt,
    }
    if session_id:
        metadata["session_id"] = session_id
    if phase:
        metadata["phase"] = phase
    if plan:
        metadata["plan"] = plan

    # Generate output
    if fmt == "markdown":
        content = _generate_markdown(
            session_events=session_events,
            trace_events=trace_events,
            sanitize=sanitize,
            metadata=metadata,
        )
        ext = "md"
    else:
        content = _generate_json(
            session_events=session_events,
            trace_events=trace_events,
            sanitize=sanitize,
            metadata=metadata,
        )
        ext = "json"

    # Resolve output path
    if output_path:
        out = Path(output_path)
        if not out.is_absolute():
            out = cwd / out
    else:
        out = cwd / "exports" / f"chat-log.{ext}"

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(content, encoding="utf-8")

    return ChatExportResult(
        exported=True,
        format=fmt,
        file=str(out),
        session_count=len(session_events),
        event_count=len(session_events) + len(trace_events),
        sanitized=sanitize,
    )
