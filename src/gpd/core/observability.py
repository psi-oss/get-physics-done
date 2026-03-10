"""Local observability helpers for GPD.

Observability is written to the project-local ``.gpd/observability/`` tree:

- ``events.jsonl`` stores the append-only project-wide event stream
- ``sessions/<session-id>.jsonl`` stores per-session event streams
- ``sessions/<session-id>.json`` stores session metadata
- ``current-session.json`` points at the latest active session

The public API intentionally preserves the legacy ``gpd_span`` /
``instrument_gpd_function`` surface so existing callers do not need to care
how the observability backend is implemented.
"""

from __future__ import annotations

import functools
import inspect
import os
import secrets
import sys
from collections.abc import Callable, Generator
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import UTC, datetime
from itertools import count
from pathlib import Path
from time import perf_counter

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
_span_stack_var: ContextVar[tuple[str, ...]] = ContextVar("gpd_observability_span_stack", default=())
_event_counter = count(1)


class ObservabilitySession(BaseModel):
    """Session metadata stored under ``.gpd/observability/sessions``."""

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
        import json

        raw = json.loads(content)
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def _append_event(path: Path, payload: dict[str, object]) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, default=str)
    with file_lock(path):
        with open(path, "a", encoding="utf-8") as handle:
            handle.write(line + "\n")


def _save_session_meta(layout: ProjectLayout, session: ObservabilitySession) -> None:
    atomic_write(layout.observability_session_meta(session.session_id), session.model_dump_json(indent=2))
    atomic_write(layout.current_observability_session, session.model_dump_json(indent=2))


def _load_session_meta(layout: ProjectLayout, session_id: str) -> ObservabilitySession | None:
    content = safe_read_file(layout.observability_session_meta(session_id))
    if content is None:
        return None
    try:
        return ObservabilitySession.model_validate_json(content)
    except Exception:
        return None


def _current_command(argv: list[str] | None = None) -> str | None:
    if argv is None:
        argv = sys.argv[1:]
    cleaned = [part for part in argv if part not in {"--raw"}]
    if not cleaned:
        return None
    if cleaned[0] == "--cwd":
        cleaned = cleaned[2:]
    return " ".join(cleaned[:2]) if cleaned else None


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
    resolved_cwd = layout.root
    existing_id = _session_id_var.get()
    if existing_id and _session_cwd_var.get() == resolved_cwd:
        existing = _load_session_meta(layout, existing_id)
        if existing is not None and existing.status == "active":
            return existing

    now = _now_iso()
    session_id = f"{now.replace(':', '').replace('-', '')[:15]}-{os.getpid()}-{secrets.token_hex(3)}"
    session = ObservabilitySession(
        session_id=session_id,
        started_at=now,
        last_event_at=now,
        cwd=str(resolved_cwd),
        source=source,
        pid=os.getpid(),
        command=command or _current_command(),
        metadata=metadata or {},
    )
    _save_session_meta(layout, session)
    _session_id_var.set(session_id)
    _session_cwd_var.set(resolved_cwd)
    return session


ensure_observability_session = ensure_session


def _update_session(
    layout: ProjectLayout,
    session_id: str,
    *,
    status: str | None = None,
    command: str | None = None,
    ended_at: str | None = None,
) -> ObservabilitySession | None:
    existing = _load_session_meta(layout, session_id)
    if existing is None:
        return None
    update_payload: dict[str, object] = {
        "last_event_at": _now_iso(),
        "status": status or existing.status,
    }
    if command:
        update_payload["command"] = command
    metadata = dict(existing.metadata)
    if ended_at:
        metadata["ended_at"] = ended_at
        update_payload["metadata"] = metadata
    updated = existing.model_copy(update=update_payload)
    _save_session_meta(layout, updated)
    return updated


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
) -> ObserveEventResult:
    layout = _layout(cwd)
    if layout is None:
        return ObserveEventResult(recorded=False, reason="observability_unavailable")

    _ensure_dirs(layout)
    session: ObservabilitySession | None
    if session_id:
        session = _load_session_meta(layout, session_id)
        if session is None:
            session = ensure_session(cwd, source="python", command=command)
    else:
        session = ensure_session(cwd, source="python", command=command)

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
    serialized = payload.model_dump(mode="json")
    _append_event(layout.observability_events, serialized)
    _append_event(layout.observability_session_events(session.session_id), serialized)
    final_status = status if action in {"finish", "error"} else ("active" if status == "active" else None)
    _update_session(
        layout,
        session.session_id,
        status=final_status,
        command=payload.command,
        ended_at=payload.timestamp if action == "finish" else None,
    )

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
    """Create a local observability span."""
    prefixed = _prefixed_attrs(attrs)
    cwd = _extract_cwd(prefixed.get("gpd.cwd") or prefixed.get("cwd"))
    session = ensure_session(cwd, source="span")
    span_id = _new_id("span") if session is not None else None
    parent_stack = _span_stack_var.get()
    parent_span_id = parent_stack[-1] if parent_stack else None
    span = LocalSpan(session_id=session.session_id if session else None, span_id=span_id, name=name, attrs=prefixed)

    observe_event(
        cwd,
        category="span",
        name=name,
        action="start",
        status="active",
        session_id=session.session_id if session else None,
        span_id=span_id,
        parent_span_id=parent_span_id,
        data={"attrs": prefixed},
    )

    token = _span_stack_var.set(parent_stack + ((span_id or ""),))
    started = perf_counter()
    try:
        yield span
    except Exception as exc:
        observe_event(
            cwd,
            category="span",
            name=name,
            action="error",
            status="error",
            session_id=session.session_id if session else None,
            span_id=span_id,
            parent_span_id=parent_span_id,
            data={
                "attrs": span.attrs,
                "duration_ms": round((perf_counter() - started) * 1000, 3),
                "error": {"type": exc.__class__.__name__, "message": str(exc)},
            },
        )
        raise
    else:
        observe_event(
            cwd,
            category="span",
            name=name,
            action="finish",
            status="ok",
            session_id=session.session_id if session else None,
            span_id=span_id,
            parent_span_id=parent_span_id,
            data={
                "attrs": span.attrs,
                "duration_ms": round((perf_counter() - started) * 1000, 3),
            },
        )
    finally:
        _span_stack_var.reset(token)


def _call_metadata(func: Callable, args: tuple[object, ...], kwargs: dict[str, object]) -> tuple[Path | None, dict[str, object]]:
    cwd: Path | None = None
    if "cwd" in kwargs:
        cwd = _extract_cwd(kwargs["cwd"])
    if cwd is None and args:
        cwd = _extract_cwd(args[0])

    metadata = {
        "module": func.__module__,
        "qualname": func.__qualname__,
        "args_count": len(args),
        "kwarg_keys": sorted(kwargs),
    }
    if cwd is not None:
        metadata["cwd"] = str(cwd)
    return cwd, metadata


def instrument_gpd_function(
    span_name: str | None = None,
    **default_attrs: object,
) -> Callable:
    """Decorator factory for local function observability."""

    def decorator(func: Callable) -> Callable:
        name = span_name or f"{func.__module__}.{func.__qualname__}"

        if inspect.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: object, **kwargs: object) -> object:
                cwd, metadata = _call_metadata(func, args, kwargs)
                observe_event(cwd, category="function", name=name, action="start", status="active", data=metadata)
                try:
                    with gpd_span(name, cwd=str(cwd) if cwd is not None else "", **default_attrs):
                        result = await func(*args, **kwargs)
                except Exception as exc:
                    observe_event(
                        cwd,
                        category="function",
                        name=name,
                        action="error",
                        status="error",
                        data={**metadata, "error": {"type": exc.__class__.__name__, "message": str(exc)}},
                    )
                    raise
                observe_event(cwd, category="function", name=name, action="finish", status="ok", data=metadata)
                return result

            return async_wrapper

        @functools.wraps(func)
        def sync_wrapper(*args: object, **kwargs: object) -> object:
            cwd, metadata = _call_metadata(func, args, kwargs)
            observe_event(cwd, category="function", name=name, action="start", status="active", data=metadata)
            try:
                with gpd_span(name, cwd=str(cwd) if cwd is not None else "", **default_attrs):
                    result = func(*args, **kwargs)
            except Exception as exc:
                observe_event(
                    cwd,
                    category="function",
                    name=name,
                    action="error",
                    status="error",
                    data={**metadata, "error": {"type": exc.__class__.__name__, "message": str(exc)}},
                )
                raise
            observe_event(cwd, category="function", name=name, action="finish", status="ok", data=metadata)
            return result

        return sync_wrapper

    return decorator


def _iter_session_meta(layout: ProjectLayout) -> list[ObservabilitySession]:
    if not layout.observability_sessions_dir.is_dir():
        return []
    sessions: list[ObservabilitySession] = []
    for meta_path in sorted(layout.observability_sessions_dir.glob("*.json")):
        content = safe_read_file(meta_path)
        if content is None:
            continue
        try:
            sessions.append(ObservabilitySession.model_validate_json(content))
        except Exception:
            continue
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
    import json

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
        events = _read_events(layout.observability_session_events(session))
    else:
        events = _read_events(layout.observability_events)

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

    return ObservabilityShowResult(count=len(events), events=events)
