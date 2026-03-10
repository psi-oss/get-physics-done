"""JSONL-based execution tracing for GPD agent debugging.

Traces are stored in ``.gpd/traces/{phase}-{plan}.jsonl`` as one JSON
object per line.  An active-trace marker file tracks which trace is currently
recording.

Public API
----------
trace_start  — create trace file, set as active
trace_log    — append timestamped event to active trace
trace_stop   — close active trace, write summary line
trace_show   — display/filter trace events
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, Field

from gpd.core.constants import ProjectLayout
from gpd.core.errors import TraceError
from gpd.core.observability import gpd_span, instrument_gpd_function
from gpd.core.utils import atomic_write, file_lock, safe_read_file

logger = logging.getLogger(__name__)

__all__ = [
    "USER_EVENT_TYPES",
    "ActiveTrace",
    "TraceEvent",
    "TraceEventType",
    "TraceListResult",
    "TraceLogResult",
    "TraceShowResult",
    "TraceStartResult",
    "TraceStopResult",
    "trace_log",
    "trace_show",
    "trace_start",
    "trace_stop",
]

# ─── Event Types ──────────────────────────────────────────────────────────────


class TraceEventType(StrEnum):
    """Valid event types for trace logging."""

    CONVENTION_LOAD = "convention_load"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    CHECKPOINT = "checkpoint"
    ASSERTION = "assertion"
    DEVIATION = "deviation"
    ERROR = "error"
    CONTEXT_PRESSURE = "context_pressure"
    INFO = "info"
    # Internal bookkeeping (not user-facing)
    TRACE_START = "trace_start"
    TRACE_STOP = "trace_stop"


#: User-facing event types (excludes internal trace_start / trace_stop).
USER_EVENT_TYPES: frozenset[str] = frozenset(
    e.value for e in TraceEventType if e not in (TraceEventType.TRACE_START, TraceEventType.TRACE_STOP)
)

# ─── Pydantic Models ─────────────────────────────────────────────────────────


class TraceEvent(BaseModel):
    """A single timestamped trace event."""

    timestamp: str
    event_type: str = Field(alias="type")
    phase: str | None = None
    plan: str | None = None
    data: dict[str, object] | None = None
    summary: dict[str, object] | None = None

    model_config = {"populate_by_name": True}


class ActiveTrace(BaseModel):
    """Marker for the currently-active trace session."""

    phase: str
    plan: str
    file: str
    started_at: str


class TraceStartResult(BaseModel):
    """Returned by :func:`trace_start`."""

    started: bool = True
    phase: str
    plan: str
    file: str


class TraceLogResult(BaseModel):
    """Returned by :func:`trace_log`."""

    logged: bool = True
    event_type: str


class TraceStopResult(BaseModel):
    """Returned by :func:`trace_stop`."""

    stopped: bool = True
    phase: str
    plan: str
    event_counts: dict[str, int] = Field(default_factory=dict)


class TraceShowResult(BaseModel):
    """Returned by :func:`trace_show` when displaying events."""

    count: int
    events: list[TraceEvent] = Field(default_factory=list)


class TraceListResult(BaseModel):
    """Returned by :func:`trace_show` when listing available traces."""

    available_traces: list[str] = Field(default_factory=list)
    hint: str = "Use phase + plan to show a specific trace"


# ─── Path Resolution ─────────────────────────────────────────────────────────


def _traces_dir(cwd: Path) -> Path:
    return ProjectLayout(cwd).traces_dir


def _active_trace_path(cwd: Path) -> Path:
    return ProjectLayout(cwd).active_trace


def _trace_file_path(cwd: Path, phase: str, plan: str) -> Path:
    return ProjectLayout(cwd).trace_file(phase, plan)


# ─── Internal Helpers ─────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _read_active_trace(cwd: Path) -> ActiveTrace | None:
    """Read the active trace marker.  Returns ``None`` when absent or corrupt."""
    content = safe_read_file(_active_trace_path(cwd))
    if content is None:
        return None
    try:
        return ActiveTrace.model_validate_json(content)
    except (json.JSONDecodeError, ValueError):
        return None


def _read_trace_events(file_path: Path) -> list[TraceEvent]:
    """Read all events from a JSONL trace file."""
    content = safe_read_file(file_path)
    if content is None:
        return []
    events: list[TraceEvent] = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            events.append(TraceEvent.model_validate_json(line))
        except (json.JSONDecodeError, ValueError):
            continue
    return events


def _serialize_event(event_type: str, **extra: object) -> str:
    """Serialize one JSONL line with ``type`` key."""
    obj: dict[str, object] = {"timestamp": _now_iso(), "type": event_type}
    obj.update({k: v for k, v in extra.items() if v is not None})
    return json.dumps(obj, default=str)


def _append_line(file_path: Path, line: str) -> None:
    """Append a single JSONL line with file locking."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_lock(file_path):
        with open(file_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")


# ─── Public API ───────────────────────────────────────────────────────────────


@instrument_gpd_function("trace.start")
def trace_start(cwd: Path, phase: str, plan: str) -> TraceStartResult:
    """Create a trace file and set it as the active trace.

    Raises:
        TraceError: If *phase* or *plan* is empty, or a trace is already active.
    """
    if not phase:
        raise TraceError(
            "phase is required for trace_start. "
            "Provide a phase identifier, e.g. trace_start(cwd, phase='3', plan='01-setup')."
        )
    if not plan:
        raise TraceError(
            f"plan is required for trace_start (got phase={phase!r}, plan={plan!r}). "
            "Provide a plan name, e.g. trace_start(cwd, phase='3', plan='01-setup')."
        )

    existing = _read_active_trace(cwd)
    if existing is not None:
        raise TraceError(
            f"Active trace already exists for phase {existing.phase} plan {existing.plan}. Call trace_stop() first."
        )

    _traces_dir(cwd).mkdir(parents=True, exist_ok=True)

    trace_file = _trace_file_path(cwd, phase, plan)
    started_at = _now_iso()

    line = json.dumps({"timestamp": started_at, "type": "trace_start", "phase": phase, "plan": plan})
    _append_line(trace_file, line)

    # NOTE: active.file stores an absolute path as a string.  If the project
    # directory is moved/renamed after a trace is started, active traces and
    # trace_log / trace_stop will break because the stored path no longer
    # resolves.  A full fix requires a schema migration to store relative
    # paths; for now we document the limitation.
    marker = ActiveTrace(phase=phase, plan=plan, file=str(trace_file), started_at=started_at)
    atomic_write(_active_trace_path(cwd), marker.model_dump_json(indent=2))

    # relative_to raises ValueError when trace_file is not under cwd
    # (e.g. symlinked or non-standard layout).  Fall back to the filename.
    try:
        rel = str(trace_file.relative_to(cwd))
    except ValueError:
        rel = trace_file.name

    with gpd_span("trace.start", **{"gpd.phase": phase, "gpd.plan": plan}):
        logger.info("trace_started", extra={"phase": phase, "plan": plan, "file": rel})

    return TraceStartResult(phase=phase, plan=plan, file=rel)


@instrument_gpd_function("trace.log")
def trace_log(cwd: Path, event_type: str, data: dict[str, object] | None = None) -> TraceLogResult:
    """Append a timestamped event to the active trace.

    Raises:
        TraceError: If *event_type* is unknown or no trace is active.
    """
    if event_type not in USER_EVENT_TYPES:
        raise TraceError(f"Unknown event type: {event_type!r}. Valid: {sorted(USER_EVENT_TYPES)}")

    active = _read_active_trace(cwd)
    if active is None:
        raise TraceError("No active trace. Call trace_start() first.")

    line = _serialize_event(event_type, data=data)
    # NOTE: active.file is an absolute path string (see trace_start comment).
    # If the project directory has been moved since the trace was started,
    # this Path() will point to a stale location.
    _append_line(Path(active.file), line)

    with gpd_span("trace.log", **{"gpd.trace_event_type": event_type}):
        pass

    return TraceLogResult(event_type=event_type)


@instrument_gpd_function("trace.stop")
def trace_stop(cwd: Path) -> TraceStopResult:
    """Close the active trace and write a summary event.

    Raises:
        TraceError: If no trace is active.
    """
    active = _read_active_trace(cwd)
    if active is None:
        raise TraceError("No active trace to stop.")

    trace_file = Path(active.file)

    # Count events by type
    counts: dict[str, int] = {}
    for evt in _read_trace_events(trace_file):
        counts[evt.event_type] = counts.get(evt.event_type, 0) + 1

    stopped_at = _now_iso()
    stop_line = json.dumps(
        {
            "timestamp": stopped_at,
            "type": "trace_stop",
            "summary": {
                "started_at": active.started_at,
                "stopped_at": stopped_at,
                "event_counts": counts,
            },
        }
    )
    _append_line(trace_file, stop_line)

    _active_trace_path(cwd).unlink(missing_ok=True)

    with gpd_span("trace.stop", **{"gpd.phase": active.phase, "gpd.plan": active.plan}):
        logger.info("trace_stopped", extra={"phase": active.phase, "plan": active.plan, "counts": counts})

    return TraceStopResult(phase=active.phase, plan=active.plan, event_counts=counts)


@instrument_gpd_function("trace.show")
def trace_show(
    cwd: Path,
    *,
    phase: str | None = None,
    plan: str | None = None,
    event_type: str | None = None,
    last: int | None = None,
) -> TraceShowResult | TraceListResult:
    """Display trace events with optional filters.

    Resolution order:

    1. *phase* + *plan* → show that specific trace
    2. *phase* only → aggregate all traces for that phase
    3. Active trace → show it
    4. Otherwise → list available trace files
    """
    traces = _traces_dir(cwd)

    with gpd_span("trace.show", **{"gpd.phase": phase or "", "gpd.plan": plan or ""}):
        # Specific phase + plan
        if phase and plan:
            tf = _trace_file_path(cwd, phase, plan)
            if not tf.exists():
                raise TraceError(f"No trace found for phase {phase} plan {plan}")
            return _filter_events(_read_trace_events(tf), event_type=event_type, last=last)

        # Phase only — aggregate
        if phase:
            if not traces.is_dir():
                raise TraceError("No traces directory found.")
            prefix = f"{phase}-"
            files = sorted(f for f in traces.iterdir() if f.name.startswith(prefix) and f.suffix == ".jsonl")
            if not files:
                raise TraceError(f"No traces found for phase {phase}")
            all_events: list[TraceEvent] = []
            for f in files:
                all_events.extend(_read_trace_events(f))
            return _filter_events(all_events, event_type=event_type, last=last)

        # Active trace
        active = _read_active_trace(cwd)
        if active is not None:
            return _filter_events(
                _read_trace_events(Path(active.file)),
                event_type=event_type,
                last=last,
            )

        # If filters are provided, aggregate all traces and apply them
        if event_type or last:
            if not traces.is_dir():
                raise TraceError("No traces directory found.")
            files = sorted(f for f in traces.iterdir() if f.suffix == ".jsonl")
            if not files:
                raise TraceError("No trace files found.")
            all_events_: list[TraceEvent] = []
            for f in files:
                all_events_.extend(_read_trace_events(f))
            return _filter_events(all_events_, event_type=event_type, last=last)

        # List available traces
        if not traces.is_dir():
            raise TraceError("No traces directory found.")
        stems = sorted(f.stem for f in traces.iterdir() if f.suffix == ".jsonl")
        if not stems:
            raise TraceError("No trace files found.")
        return TraceListResult(available_traces=stems)


def _filter_events(
    events: list[TraceEvent],
    *,
    event_type: str | None = None,
    last: int | None = None,
) -> TraceShowResult:
    """Apply type filter and last-N slice to events."""
    filtered = events
    if event_type:
        filtered = [e for e in filtered if e.event_type == event_type]
    if last and last > 0:
        filtered = filtered[-last:]
    return TraceShowResult(count=len(filtered), events=filtered)
