"""Session-focused local observability helpers for GPD.

Observability is written to the project-local ``.gpd/observability/`` tree:

- ``sessions/<session-id>.jsonl`` stores the full event stream for one session
- ``current-session.json`` points at the latest observed session summary

Automatic low-level function/span logging is intentionally disabled. Only
explicit session/workflow events should be recorded here.
"""

from __future__ import annotations

import functools
import inspect
import json
import os
import secrets
import sys
from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from itertools import count
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from gpd.core.constants import ProjectLayout
from gpd.core.utils import atomic_write, file_lock, safe_read_file

__all__ = [
    "LocalSpan",
    "ObservabilityEvent",
    "ObservabilitySession",
    "ObserveEventResult",
    "ObservabilitySessionsResult",
    "ObservabilityShowResult",
    "ensure_session",
    "ensure_observability_session",
    "get_current_session",
    "get_current_session_id",
    "gpd_span",
    "instrument_gpd_function",
    "list_sessions",
    "log_event",
    "observe_event",
    "record_event",
    "show_events",
]


_session_id_var: ContextVar[str | None] = ContextVar("gpd_observability_session_id", default=None)
_session_cwd_var: ContextVar[Path | None] = ContextVar("gpd_observability_session_cwd", default=None)
_event_counter = count(1)


class ObservabilitySession(BaseModel):
    """Summary metadata for a local observability session."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    started_at: str
    last_event_at: str
    cwd: str = ""
    source: str = "python"
    pid: int | None = None
    command: str | None = None
    status: str = "active"
    metadata: dict[str, object] = Field(default_factory=dict)


class ObservabilityEvent(BaseModel):
    """One local observability event."""

    model_config = ConfigDict(frozen=True)

    event_id: str
    timestamp: str
    session_id: str
    category: str
    name: str
    action: str = "log"
    status: str = "ok"
    command: str | None = None
    phase: str | None = None
    plan: str | None = None
    trace_id: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    data: dict[str, object] = Field(default_factory=dict)


class ObserveEventResult(BaseModel):
    """Return value for ``observe_event``."""

    model_config = ConfigDict(frozen=True)

    recorded: bool
    session_id: str | None = None
    event_id: str | None = None
    category: str | None = None
    name: str | None = None
    action: str | None = None
    status: str | None = None
    command: str | None = None
    phase: str | None = None
    plan: str | None = None
    trace_id: str | None = None
    data: dict[str, object] = Field(default_factory=dict)
    reason: str | None = None


class ObservabilityShowResult(BaseModel):
    """Filtered observability events."""

    model_config = ConfigDict(frozen=True)

    count: int
    events: list[dict[str, object]] = Field(default_factory=list)


class ObservabilitySessionsResult(BaseModel):
    """Available observability sessions."""

    model_config = ConfigDict(frozen=True)

    count: int
    sessions: list[dict[str, object]] = Field(default_factory=list)


class LocalSpan:
    """Minimal span object returned by :func:`gpd_span`."""

    def __init__(
        self,
        *,
        session_id: str | None,
        span_id: str | None,
        name: str,
        attrs: dict[str, object],
    ) -> None:
        self.session_id = session_id
        self.span_id = span_id
        self.name = name
        self.attrs = attrs

    def set_attribute(self, key: str, value: object) -> None:
        attr_key = key if key.startswith("gpd.") else f"gpd.{key}"
        self.attrs[attr_key] = value


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _new_id(prefix: str) -> str:
    return f"{prefix}-{int(datetime.now(UTC).timestamp() * 1000)}-{next(_event_counter)}"


def _extract_cwd(value: object | None) -> Path | None:
    if value is None:
        return None
    if isinstance(value, Path):
        return value
    if isinstance(value, str) and value:
        return Path(value)
    return None


def _project_root(cwd: Path | None = None) -> Path | None:
    if cwd is not None:
        candidate = cwd
    else:
        pwd = Path.cwd()
        if ProjectLayout(pwd).gpd.exists():
            candidate = pwd
        else:
            candidate = _session_cwd_var.get() or pwd
    layout = ProjectLayout(candidate)
    if not layout.gpd.exists():
        return None
    return candidate


def _layout(cwd: Path | None = None) -> ProjectLayout | None:
    root = _project_root(cwd)
    if root is None:
        return None
    return ProjectLayout(root)


def _ensure_dirs(layout: ProjectLayout) -> None:
    layout.observability_dir.mkdir(parents=True, exist_ok=True)
    layout.observability_sessions_dir.mkdir(parents=True, exist_ok=True)


def _read_json(path: Path) -> dict[str, object] | None:
    content = safe_read_file(path)
    if content is None:
        return None
    try:
        raw = json.loads(content)
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def _append_event(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, default=str)
    with file_lock(path):
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def _save_current_session(layout: ProjectLayout, session: ObservabilitySession) -> None:
    atomic_write(layout.current_observability_session, session.model_dump_json(indent=2))


def _current_command(argv: list[str] | None = None) -> str | None:
    if argv is None:
        argv = sys.argv[1:]
    cleaned = [part for part in argv if part not in {"--raw"}]
    if not cleaned:
        return None
    if cleaned[0] == "--cwd":
        cleaned = cleaned[2:]
    return " ".join(cleaned[:2]) if cleaned else None


def _session_log(layout: ProjectLayout, session_id: str) -> Path:
    return layout.observability_session_events(session_id)


def _session_lifecycle_event(
    session: ObservabilitySession,
    *,
    action: str,
    status: str,
    timestamp: str,
    data: dict[str, object],
) -> ObservabilityEvent:
    return ObservabilityEvent(
        event_id=_new_id("evt"),
        timestamp=timestamp,
        session_id=session.session_id,
        category="session",
        name="lifecycle",
        action=action,
        status=status,
        command=session.command,
        data=data,
    )


def _session_start_event(session: ObservabilitySession) -> ObservabilityEvent:
    return _session_lifecycle_event(
        session,
        action="start",
        status="active",
        timestamp=session.started_at,
        data={
            "cwd": session.cwd,
            "source": session.source,
            "pid": session.pid,
            "metadata": session.metadata,
        },
    )


def _session_finish_event(
    session: ObservabilitySession,
    *,
    status: str,
    ended_at: str,
    ended_by: dict[str, object],
) -> ObservabilityEvent:
    return _session_lifecycle_event(
        session,
        action="error" if status == "error" else "finish",
        status=status,
        timestamp=ended_at,
        data={
            "ended_at": ended_at,
            "ended_by": ended_by,
            "source": session.source,
        },
    )


def _lifecycle_event_data(event: dict[str, object]) -> dict[str, object]:
    data = event.get("data")
    return dict(data) if isinstance(data, dict) else {}


def _session_from_events(
    session_id: str,
    events: list[dict[str, object]],
    *,
    default_cwd: Path,
) -> ObservabilitySession | None:
    if not events:
        return None

    first_event = events[0]
    last_event = events[-1]
    started_at = str(first_event.get("timestamp") or "")
    last_event_at = str(last_event.get("timestamp") or started_at)
    cwd = str(default_cwd)
    source = "python"
    pid: int | None = None
    command_value = last_event.get("command") or first_event.get("command")
    command = str(command_value) if isinstance(command_value, str) and command_value else None
    metadata: dict[str, object] = {}
    status = "active"

    start_event = next(
        (
            event
            for event in events
            if event.get("category") == "session"
            and event.get("name") == "lifecycle"
            and event.get("action") == "start"
        ),
        None,
    )
    if start_event is not None:
        started_at = str(start_event.get("timestamp") or started_at)
        start_data = _lifecycle_event_data(start_event)
        cwd_value = start_data.get("cwd")
        if isinstance(cwd_value, str) and cwd_value:
            cwd = cwd_value
        source_value = start_data.get("source")
        if isinstance(source_value, str) and source_value:
            source = source_value
        pid_value = start_data.get("pid")
        if isinstance(pid_value, int):
            pid = pid_value
        meta_value = start_data.get("metadata")
        if isinstance(meta_value, dict):
            metadata = dict(meta_value)
        start_command = start_event.get("command")
        if isinstance(start_command, str) and start_command:
            command = start_command

    finish_event = next(
        (
            event
            for event in reversed(events)
            if event.get("category") == "session"
            and event.get("name") == "lifecycle"
            and event.get("action") in {"finish", "error"}
        ),
        None,
    )
    if finish_event is not None:
        finish_data = _lifecycle_event_data(finish_event)
        status_value = finish_event.get("status")
        if isinstance(status_value, str) and status_value:
            status = status_value
        ended_at = finish_data.get("ended_at")
        if isinstance(ended_at, str) and ended_at:
            metadata = {**metadata, "ended_at": ended_at}

    return ObservabilitySession(
        session_id=session_id,
        started_at=started_at,
        last_event_at=last_event_at,
        cwd=cwd,
        source=source,
        pid=pid,
        command=command,
        status=status,
        metadata=metadata,
    )


def _load_session_from_log(layout: ProjectLayout, session_id: str) -> ObservabilitySession | None:
    events = _read_events(_session_log(layout, session_id))
    return _session_from_events(session_id, events, default_cwd=layout.root)


def get_current_session(cwd: Path | None = None) -> ObservabilitySession | None:
    layout = _layout(cwd)
    if layout is None:
        return None

    current = _read_json(layout.current_observability_session)
    if current is None:
        return None
    try:
        return ObservabilitySession.model_validate(current)
    except Exception:
        return None


def get_current_session_id(cwd: Path | None = None) -> str | None:
    current = get_current_session(cwd)
    return current.session_id if current is not None else None


def _active_context_session(layout: ProjectLayout) -> ObservabilitySession | None:
    existing_id = _session_id_var.get()
    if not existing_id or _session_cwd_var.get() != layout.root:
        return None
    current = get_current_session(layout.root)
    if current is None or current.session_id != existing_id or current.status != "active":
        return None
    return current


def ensure_session(
    cwd: Path | None = None,
    *,
    source: str = "python",
    metadata: dict[str, object] | None = None,
    command: str | None = None,
) -> ObservabilitySession | None:
    layout = _layout(cwd)
    if layout is None:
        return None

    _ensure_dirs(layout)
    existing = _active_context_session(layout)
    if existing is not None:
        return existing

    now = _now_iso()
    session = ObservabilitySession(
        session_id=f"{now.replace(':', '').replace('-', '')[:15]}-{os.getpid()}-{secrets.token_hex(3)}",
        started_at=now,
        last_event_at=now,
        cwd=str(layout.root),
        source=source,
        pid=os.getpid(),
        command=command or _current_command(),
        metadata=metadata or {},
    )
    _append_event(_session_log(layout, session.session_id), _session_start_event(session).model_dump(mode="json"))
    _save_current_session(layout, session)
    _session_id_var.set(session.session_id)
    _session_cwd_var.set(layout.root)
    return session


ensure_observability_session = ensure_session


def _resolve_session(
    layout: ProjectLayout,
    *,
    cwd: Path | None,
    session_id: str | None,
    command: str | None,
) -> ObservabilitySession | None:
    if session_id:
        session = _load_session_from_log(layout, session_id)
        if session is not None:
            return session
    return ensure_session(cwd, source="python", command=command)


def _updated_session(
    session: ObservabilitySession,
    *,
    timestamp: str,
    command: str | None,
    status: str | None = None,
    ended_at: str | None = None,
) -> ObservabilitySession:
    metadata = dict(session.metadata)
    if ended_at:
        metadata["ended_at"] = ended_at
    return session.model_copy(
        update={
            "last_event_at": timestamp,
            "command": command or session.command,
            "status": status or session.status,
            "metadata": metadata,
        }
    )


def _finalize_session(
    layout: ProjectLayout,
    session: ObservabilitySession,
    *,
    status: str,
    ended_at: str,
    ended_by: dict[str, object],
) -> ObservabilitySession:
    final_session = _updated_session(session, timestamp=ended_at, command=session.command, status=status, ended_at=ended_at)
    finish_event = _session_finish_event(final_session, status=status, ended_at=ended_at, ended_by=ended_by)
    _append_event(_session_log(layout, final_session.session_id), finish_event.model_dump(mode="json"))
    _save_current_session(layout, final_session)
    if _session_id_var.get() == final_session.session_id and _session_cwd_var.get() == layout.root:
        _session_id_var.set(None)
        _session_cwd_var.set(None)
    return final_session


def observe_event(
    cwd: Path | None = None,
    *,
    category: str,
    name: str,
    action: str = "log",
    status: str = "ok",
    command: str | None = None,
    phase: str | None = None,
    plan: str | None = None,
    trace_id: str | None = None,
    entity_type: str | None = None,
    entity_id: str | None = None,
    session_id: str | None = None,
    span_id: str | None = None,
    parent_span_id: str | None = None,
    data: dict[str, object] | None = None,
    end_session: bool = False,
) -> ObserveEventResult:
    layout = _layout(cwd)
    if layout is None:
        return ObserveEventResult(recorded=False, reason="observability_unavailable")

    _ensure_dirs(layout)
    session = _resolve_session(layout, cwd=cwd, session_id=session_id, command=command)
    if session is None:
        return ObserveEventResult(recorded=False, reason="session_unavailable")

    payload = ObservabilityEvent(
        event_id=_new_id("evt"),
        timestamp=_now_iso(),
        session_id=session.session_id,
        category=category,
        name=name,
        action=action,
        status=status,
        command=command or session.command,
        phase=phase,
        plan=plan,
        trace_id=trace_id,
        entity_type=entity_type,
        entity_id=entity_id,
        span_id=span_id,
        parent_span_id=parent_span_id,
        data=data or {},
    )
    _append_event(_session_log(layout, session.session_id), payload.model_dump(mode="json"))

    updated = _updated_session(
        session,
        timestamp=payload.timestamp,
        command=payload.command,
        status="active" if not end_session else status,
    )
    if end_session:
        _finalize_session(
            layout,
            updated,
            status=status,
            ended_at=payload.timestamp,
            ended_by={
                "category": category,
                "name": name,
                "action": action,
                "status": status,
            },
        )
    else:
        _save_current_session(layout, updated)
        _session_id_var.set(updated.session_id)
        _session_cwd_var.set(layout.root)

    return ObserveEventResult(
        recorded=True,
        session_id=payload.session_id,
        event_id=payload.event_id,
        category=payload.category,
        name=payload.name,
        action=payload.action,
        status=payload.status,
        command=payload.command,
        phase=payload.phase,
        plan=payload.plan,
        trace_id=payload.trace_id,
        data=payload.data,
    )


record_event = observe_event
log_event = observe_event


def _prefixed_attrs(attrs: dict[str, object]) -> dict[str, object]:
    prefixed: dict[str, object] = {}
    for key, value in attrs.items():
        attr_key = key if key.startswith("gpd.") else f"gpd.{key}"
        prefixed[attr_key] = value
    return prefixed


@contextmanager
def gpd_span(name: str, **attrs: object) -> Generator[LocalSpan, None, None]:
    """No-op local span kept for structural instrumentation boundaries."""
    prefixed = _prefixed_attrs(attrs)
    span = LocalSpan(session_id=None, span_id=None, name=name, attrs=prefixed)
    yield span


def _call_cwd(func: Callable, args: tuple[object, ...], kwargs: dict[str, object]) -> Path | None:
    if "cwd" in kwargs:
        return _extract_cwd(kwargs["cwd"])
    if args:
        return _extract_cwd(args[0])
    return None


def instrument_gpd_function(
    span_name: str | None = None,
    **default_attrs: object,
) -> Callable:
    """Decorator factory that preserves span structure without emitting events."""

    def decorator(func: Callable) -> Callable:
        name = span_name or f"{func.__module__}.{func.__qualname__}"

        if inspect.isgeneratorfunction(func):
            @functools.wraps(func)
            def gen_wrapper(*args: object, **kwargs: object) -> object:
                return func(*args, **kwargs)

            return gen_wrapper

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: object, **kwargs: object) -> object:
                cwd = _call_cwd(func, args, kwargs)
                with gpd_span(name, cwd=str(cwd) if cwd is not None else "", **default_attrs):
                    return await func(*args, **kwargs)

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: object, **kwargs: object) -> object:
            cwd = _call_cwd(func, args, kwargs)
            with gpd_span(name, cwd=str(cwd) if cwd is not None else "", **default_attrs):
                return func(*args, **kwargs)

        return sync_wrapper

    return decorator


def _iter_session_meta(layout: ProjectLayout) -> list[ObservabilitySession]:
    if not layout.observability_sessions_dir.is_dir():
        return []
    sessions: list[ObservabilitySession] = []
    for session_path in sorted(layout.observability_sessions_dir.glob("*.jsonl")):
        session = _load_session_from_log(layout, session_path.stem)
        if session is not None:
            sessions.append(session)
    return sorted(sessions, key=lambda item: item.last_event_at, reverse=True)


def list_sessions(
    cwd: Path | None = None,
    *,
    command: str | None = None,
    last: int | None = None,
) -> ObservabilitySessionsResult:
    layout = _layout(cwd)
    if layout is None:
        return ObservabilitySessionsResult(count=0, sessions=[])

    sessions = _iter_session_meta(layout)
    if command:
        sessions = [session for session in sessions if session.command == command]
    if last and last > 0:
        sessions = sessions[:last]
    payload = [session.model_dump(mode="json") for session in sessions]
    return ObservabilitySessionsResult(count=len(payload), sessions=payload)


def _read_events(path: Path) -> list[dict[str, object]]:
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
        except Exception:
            continue
        if isinstance(raw, dict):
            events.append(raw)
    return events


def _read_session_events(layout: ProjectLayout) -> list[dict[str, object]]:
    """Read and merge per-session event streams in timestamp order."""
    if not layout.observability_sessions_dir.is_dir():
        return []

    events: list[dict[str, object]] = []
    for session_events_path in sorted(layout.observability_sessions_dir.glob("*.jsonl")):
        events.extend(_read_events(session_events_path))
    events.sort(key=lambda item: str(item.get("timestamp", "")))
    return events


def _filter_events(
    events: list[dict[str, object]],
    *,
    category: str | None = None,
    name: str | None = None,
    action: str | None = None,
    status: str | None = None,
    command: str | None = None,
    phase: str | None = None,
    plan: str | None = None,
    last: int | None = None,
) -> list[dict[str, object]]:
    """Apply the public ``show_events`` filters to a raw event list."""
    if category:
        events = [event for event in events if event.get("category") == category]
    if name:
        events = [event for event in events if event.get("name") == name]
    if action:
        events = [event for event in events if event.get("action") == action]
    if status:
        events = [event for event in events if event.get("status") == status]
    if command:
        events = [event for event in events if event.get("command") == command]
    if phase:
        events = [event for event in events if event.get("phase") == phase]
    if plan:
        events = [event for event in events if event.get("plan") == plan]
    if last and last > 0:
        events = events[-last:]
    return events


def show_events(
    cwd: Path | None = None,
    *,
    session: str | None = None,
    category: str | None = None,
    name: str | None = None,
    action: str | None = None,
    status: str | None = None,
    command: str | None = None,
    phase: str | None = None,
    plan: str | None = None,
    last: int | None = None,
) -> ObservabilityShowResult:
    layout = _layout(cwd)
    if layout is None:
        return ObservabilityShowResult(count=0, events=[])

    if session:
        events = _filter_events(
            _read_events(_session_log(layout, session)),
            category=category,
            name=name,
            action=action,
            status=status,
            command=command,
            phase=phase,
            plan=plan,
            last=last,
        )
    else:
        events = _filter_events(
            _read_session_events(layout),
            category=category,
            name=name,
            action=action,
            status=status,
            command=command,
            phase=phase,
            plan=plan,
            last=last,
        )

    return ObservabilityShowResult(count=len(events), events=events)
