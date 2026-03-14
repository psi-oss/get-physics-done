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

from pydantic import BaseModel, ConfigDict, Field, field_validator

from gpd.core.constants import ProjectLayout
from gpd.core.utils import atomic_write, file_lock, phase_normalize, safe_read_file

__all__ = [
    "CurrentExecutionState",
    "LocalSpan",
    "ObservabilityEvent",
    "ObservabilitySession",
    "ObserveEventResult",
    "ObservabilitySessionsResult",
    "ObservabilityShowResult",
    "ensure_session",
    "ensure_observability_session",
    "get_current_execution",
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


class CurrentExecutionState(BaseModel):
    """Latest active or resumable execution-state snapshot."""

    model_config = ConfigDict(frozen=True)

    session_id: str | None = None
    workflow: str | None = None
    runtime: str | None = None
    command: str | None = None
    phase: str | None = None
    plan: str | None = None
    wave: int | str | None = None
    segment_id: str | None = None
    segment_status: str | None = None
    segment_reason: str | None = None
    review_cadence: str | None = None
    autonomy: str | None = None
    current_task: str | None = None
    current_task_index: int | None = None
    current_task_total: int | None = None
    waiting_for_review: bool = False
    review_required: bool = False
    checkpoint_reason: str | None = None
    waiting_reason: str | None = None
    blocked_reason: str | None = None
    first_result_ready: bool = False
    first_result_gate_pending: bool = False
    pre_fanout_review_pending: bool = False
    pre_fanout_review_cleared: bool = False
    skeptical_requestioning_required: bool = False
    downstream_locked: bool = False
    skeptical_requestioning_summary: str | None = None
    weakest_unchecked_anchor: str | None = None
    disconfirming_observation: str | None = None
    last_result_id: str | None = None
    last_result_label: str | None = None
    last_artifact_path: str | None = None
    resume_file: str | None = None
    segment_started_at: str | None = None
    transition_id: str | None = None
    updated_at: str | None = None

    @field_validator("phase", "plan", mode="before")
    @classmethod
    def _normalize_phase_like_fields(cls, value: object) -> object:
        if isinstance(value, int):
            return phase_normalize(str(value))
        if isinstance(value, str):
            stripped = value.strip()
            return phase_normalize(stripped) if stripped else None
        return value

    @field_validator("checkpoint_reason", mode="before")
    @classmethod
    def _normalize_checkpoint_reason_field(cls, value: object) -> object:
        return _normalized_checkpoint_reason(value)


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


def _save_current_execution(layout: ProjectLayout, execution: CurrentExecutionState) -> None:
    atomic_write(layout.current_observability_execution, execution.model_dump_json(indent=2))


def _clear_current_execution(layout: ProjectLayout) -> None:
    try:
        layout.current_observability_execution.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


def _read_current_execution_raw(layout: ProjectLayout) -> dict[str, object] | None:
    return _read_json(layout.current_observability_execution)


def get_current_execution(cwd: Path | None = None) -> CurrentExecutionState | None:
    layout = _layout(cwd)
    if layout is None:
        return None
    raw = _read_current_execution_raw(layout)
    if raw is None:
        return None
    try:
        return CurrentExecutionState.model_validate(raw)
    except Exception:
        return None


def _execution_data(data: dict[str, object]) -> dict[str, object]:
    nested = data.get("execution")
    if isinstance(nested, dict):
        return dict(nested)
    return dict(data)


def _bool_or_none(value: object) -> bool | None:
    return value if isinstance(value, bool) else None


def _str_or_none(value: object) -> str | None:
    return value if isinstance(value, str) and value else None


def _int_or_none(value: object) -> int | None:
    return value if isinstance(value, int) else None


def _normalized_checkpoint_reason(value: object) -> str | None:
    reason = _str_or_none(value)
    if reason is None:
        return None
    return reason.strip().replace("-", "_")


_EXECUTION_REVIEW_REASONS = frozenset({"first_result", "pre_fanout", "skeptical_requestioning"})


def _review_clear_targets(execution: dict[str, object]) -> set[str]:
    targets: set[str] = set()
    checkpoint_reason = _normalized_checkpoint_reason(execution.get("checkpoint_reason"))
    if checkpoint_reason in _EXECUTION_REVIEW_REASONS:
        targets.add(checkpoint_reason)
    if execution.get("first_result_gate_pending") is False:
        targets.add("first_result")
    if execution.get("pre_fanout_review_pending") is False:
        targets.add("pre_fanout")
    if execution.get("skeptical_requestioning_required") is False:
        targets.add("skeptical_requestioning")
    return targets


def _review_gate_pending(current: dict[str, object]) -> bool:
    return bool(
        current.get("first_result_gate_pending")
        or current.get("pre_fanout_review_pending")
        or current.get("skeptical_requestioning_required")
    )


def _clear_skeptical_review(current: dict[str, object]) -> None:
    current["skeptical_requestioning_required"] = False
    current["skeptical_requestioning_summary"] = None
    current["weakest_unchecked_anchor"] = None
    current["disconfirming_observation"] = None


def _refresh_checkpoint_reason(current: dict[str, object]) -> None:
    active_reasons: list[str] = []
    if current.get("first_result_gate_pending"):
        active_reasons.append("first_result")
    if current.get("pre_fanout_review_pending"):
        active_reasons.append("pre_fanout")
    if current.get("skeptical_requestioning_required"):
        active_reasons.append("skeptical_requestioning")

    if active_reasons:
        if current.get("checkpoint_reason") not in active_reasons:
            current["checkpoint_reason"] = active_reasons[0]
        return

    if current.get("checkpoint_reason") in _EXECUTION_REVIEW_REASONS:
        current["checkpoint_reason"] = None


def _load_execution_policy(cwd: Path | None) -> dict[str, object]:
    """Load the bounded-execution policy for one project root."""

    if cwd is None:
        return {}
    try:
        from gpd.core.config import load_config

        cfg = load_config(cwd)
    except Exception:
        return {}
    return {
        "max_unattended_minutes_per_plan": int(getattr(cfg, "max_unattended_minutes_per_plan", 0) or 0),
        "max_unattended_minutes_per_wave": int(getattr(cfg, "max_unattended_minutes_per_wave", 0) or 0),
        "checkpoint_after_n_tasks": int(getattr(cfg, "checkpoint_after_n_tasks", 0) or 0),
        "checkpoint_after_first_load_bearing_result": bool(
            getattr(cfg, "checkpoint_after_first_load_bearing_result", True)
        ),
    }


def _parse_iso_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _ensure_manual_review_stop(
    current: dict[str, object],
    *,
    checkpoint_reason: str,
    waiting_reason: str,
) -> None:
    """Promote the current segment into a resumable review stop."""

    current["checkpoint_reason"] = checkpoint_reason
    current["waiting_for_review"] = True
    current["review_required"] = True
    current["waiting_reason"] = waiting_reason
    current["segment_status"] = "waiting_review"


def _apply_automatic_execution_guards(
    current: dict[str, object],
    payload: ObservabilityEvent,
    execution: dict[str, object],
    *,
    cwd: Path | None,
) -> None:
    """Apply guardrails that should not rely entirely on prompt compliance."""

    policy = _load_execution_policy(cwd)

    load_bearing = _bool_or_none(execution.get("load_bearing")) is True
    skeptical_hints = any(
        (
            _bool_or_none(execution.get("proxy_only")) is True,
            _bool_or_none(execution.get("direct_anchor_missing")) is True,
            _bool_or_none(execution.get("comparison_gap")) is True,
            bool(current.get("weakest_unchecked_anchor")),
            bool(current.get("disconfirming_observation")),
        )
    )

    if (
        payload.name == "result"
        and payload.action in {"produce", "log"}
        and load_bearing
        and policy.get("checkpoint_after_first_load_bearing_result")
        and not current.get("first_result_gate_pending")
    ):
        current["first_result_ready"] = True
        current["first_result_gate_pending"] = True
        _ensure_manual_review_stop(
            current,
            checkpoint_reason="first_result",
            waiting_reason="first_result_review_required",
        )

    if skeptical_hints and not current.get("skeptical_requestioning_required"):
        current["skeptical_requestioning_required"] = True
        if not current.get("checkpoint_reason"):
            current["checkpoint_reason"] = "skeptical_requestioning"
        current["downstream_locked"] = True
        _ensure_manual_review_stop(
            current,
            checkpoint_reason=current.get("checkpoint_reason") or "skeptical_requestioning",
            waiting_reason="skeptical_requestioning_required",
        )

    task_cap = int(policy.get("checkpoint_after_n_tasks") or 0)
    task_index = _int_or_none(current.get("current_task_index"))
    if (
        task_cap > 0
        and task_index is not None
        and task_index > 0
        and task_index % task_cap == 0
        and not _review_gate_pending(current)
        and not current.get("blocked_reason")
    ):
        _ensure_manual_review_stop(
            current,
            checkpoint_reason=str(current.get("checkpoint_reason") or "segment_boundary"),
            waiting_reason="task_budget_reached",
        )

    started_at = _parse_iso_datetime(current.get("segment_started_at"))
    observed_at = _parse_iso_datetime(payload.timestamp)
    if started_at is None or observed_at is None or current.get("blocked_reason"):
        return

    elapsed_minutes = (observed_at - started_at).total_seconds() / 60.0
    max_minutes = int(policy.get("max_unattended_minutes_per_wave") or 0) if current.get("wave") else 0
    if max_minutes <= 0:
        max_minutes = int(policy.get("max_unattended_minutes_per_plan") or 0)
    if max_minutes > 0 and elapsed_minutes >= max_minutes and not _review_gate_pending(current):
        _ensure_manual_review_stop(
            current,
            checkpoint_reason=str(current.get("checkpoint_reason") or "segment_boundary"),
            waiting_reason="time_budget_exceeded",
        )


def _clear_execution_after_event(snapshot: CurrentExecutionState, payload: ObservabilityEvent, execution: dict[str, object]) -> bool:
    if _bool_or_none(execution.get("preserve_current")):
        return False

    waiting_statuses = {"awaiting_user", "paused", "blocked", "ready_to_continue", "waiting_review"}
    if snapshot.segment_status in waiting_statuses:
        return False

    if (
        snapshot.waiting_for_review
        or snapshot.first_result_gate_pending
        or snapshot.pre_fanout_review_pending
        or snapshot.skeptical_requestioning_required
        or snapshot.downstream_locked
        or snapshot.blocked_reason
    ):
        return False

    return payload.action in {"finish", "stop"} or snapshot.segment_status == "completed"


def _matches_active_execution(
    existing: CurrentExecutionState | None,
    payload: ObservabilityEvent,
    execution: dict[str, object],
) -> bool:
    """Return whether a mutating execution event targets the active segment."""

    if existing is None or payload.category != "execution":
        return True
    if payload.name == "segment" and payload.action == "start":
        return True

    if existing.session_id and payload.session_id != existing.session_id:
        return False
    if existing.phase and payload.phase and payload.phase != existing.phase:
        return False
    if existing.plan and payload.plan and payload.plan != existing.plan:
        return False

    incoming_segment_id = _str_or_none(execution.get("segment_id"))
    if existing.segment_id and incoming_segment_id and incoming_segment_id != existing.segment_id:
        return False
    return True


def _updated_execution_state(
    existing: CurrentExecutionState | None,
    payload: ObservabilityEvent,
    *,
    cwd: Path | None = None,
) -> CurrentExecutionState | None:
    if payload.category != "execution":
        return existing

    execution = _execution_data(payload.data)
    if not _matches_active_execution(existing, payload, execution):
        return existing
    current = existing.model_dump(mode="json") if existing is not None else {}
    prior_downstream_locked = bool(current.get("downstream_locked"))

    current["session_id"] = payload.session_id
    current["command"] = payload.command
    current["phase"] = payload.phase or current.get("phase")
    current["plan"] = payload.plan or current.get("plan")
    current["updated_at"] = payload.timestamp

    workflow = _str_or_none(execution.get("workflow"))
    if workflow:
        current["workflow"] = workflow
    runtime = _str_or_none(execution.get("runtime"))
    if runtime:
        current["runtime"] = runtime
    transition_id = _str_or_none(execution.get("transition_id"))
    if transition_id:
        current["transition_id"] = transition_id

    for key in (
        "segment_id",
        "segment_status",
        "segment_reason",
        "review_cadence",
        "autonomy",
        "current_task",
        "waiting_reason",
        "blocked_reason",
        "skeptical_requestioning_summary",
        "weakest_unchecked_anchor",
        "disconfirming_observation",
        "last_result_id",
        "last_result_label",
        "last_artifact_path",
        "resume_file",
        "segment_started_at",
    ):
        value = _str_or_none(execution.get(key))
        if value is not None:
            current[key] = value

    checkpoint_reason = _normalized_checkpoint_reason(execution.get("checkpoint_reason"))
    if checkpoint_reason is not None:
        current["checkpoint_reason"] = checkpoint_reason

    for key in ("current_task_index", "current_task_total"):
        value = _int_or_none(execution.get(key))
        if value is not None:
            current[key] = value

    if "wave" in execution and execution.get("wave") is not None:
        current["wave"] = execution.get("wave")

    for key in (
        "waiting_for_review",
        "review_required",
        "first_result_ready",
        "first_result_gate_pending",
        "pre_fanout_review_pending",
        "skeptical_requestioning_required",
        "downstream_locked",
    ):
        value = _bool_or_none(execution.get(key))
        if value is not None:
            current[key] = value
    if execution.get("pre_fanout_review_pending") is True:
        current["pre_fanout_review_cleared"] = False

    if payload.name == "segment" and payload.action == "start":
        current.setdefault("segment_started_at", payload.timestamp)
        current.setdefault("segment_status", "active")
    elif payload.name == "segment" and payload.action == "pause":
        current["segment_status"] = current.get("segment_status") or "paused"
    elif payload.name == "segment" and payload.action in {"finish", "stop"}:
        current["segment_status"] = current.get("segment_status") or "completed"

    if payload.name == "gate" and payload.action == "enter":
        current["review_required"] = True
        current["waiting_for_review"] = True
        current["segment_status"] = current.get("segment_status") or "waiting_review"
        if current.get("checkpoint_reason") == "first_result":
            current["first_result_gate_pending"] = True
            current["first_result_ready"] = True
        if current.get("checkpoint_reason") in {"pre_fanout", "pre-fanout"}:
            current["pre_fanout_review_pending"] = True
            current["pre_fanout_review_cleared"] = False
        if (
            "skeptical_requestioning_required" not in execution
            and (
                current.get("skeptical_requestioning_summary")
                or current.get("weakest_unchecked_anchor")
                or current.get("disconfirming_observation")
            )
        ):
            current["skeptical_requestioning_required"] = True
        if "downstream_locked" not in execution:
            current["downstream_locked"] = True
    elif payload.name == "gate" and payload.action in {"clear", "override"}:
        clear_targets = _review_clear_targets(execution)
        if "first_result" in clear_targets:
            current["first_result_gate_pending"] = False
        if "skeptical_requestioning" in clear_targets:
            _clear_skeptical_review(current)
        if "pre_fanout" in clear_targets:
            current["pre_fanout_review_cleared"] = True
            current["downstream_locked"] = prior_downstream_locked
            if current.get("downstream_locked"):
                current["pre_fanout_review_pending"] = True
            else:
                current["pre_fanout_review_pending"] = False
                current["pre_fanout_review_cleared"] = False
        if clear_targets:
            current["waiting_reason"] = None
            if "pre_fanout" not in clear_targets and not _review_gate_pending(current):
                current["downstream_locked"] = False
            if current.get("segment_status") == "waiting_review" and not _review_gate_pending(current):
                current["segment_status"] = "active"
        elif not _review_gate_pending(current):
            current["waiting_for_review"] = False
            current["review_required"] = False
            current["waiting_reason"] = None
            if current.get("segment_status") == "waiting_review":
                current["segment_status"] = "active"

    if payload.name == "fanout" and payload.action == "lock":
        current["downstream_locked"] = True
        current.setdefault("checkpoint_reason", "pre_fanout")
        current["pre_fanout_review_pending"] = True
        current["pre_fanout_review_cleared"] = False
        current["waiting_for_review"] = True
        current["review_required"] = True
        if current.get("segment_status") in {None, "", "active"}:
            current["segment_status"] = "waiting_review"
    elif payload.name == "fanout" and payload.action == "unlock":
        current["downstream_locked"] = False
        if current.get("pre_fanout_review_pending") and current.get("pre_fanout_review_cleared"):
            current["pre_fanout_review_pending"] = False
            current["pre_fanout_review_cleared"] = False
        if not _review_gate_pending(current):
            current["waiting_for_review"] = False
            current["review_required"] = False
            if current.get("segment_status") == "waiting_review":
                current["segment_status"] = "active"

    if payload.name == "result" and payload.action in {"produce", "log"}:
        if current.get("checkpoint_reason") == "first_result" or _bool_or_none(execution.get("load_bearing")):
            current["first_result_ready"] = True

    _apply_automatic_execution_guards(current, payload, execution, cwd=cwd)

    _refresh_checkpoint_reason(current)
    if current.get("skeptical_requestioning_required") and not current.get("waiting_for_review"):
        current["waiting_for_review"] = True
        current["review_required"] = True
    if current.get("pre_fanout_review_pending") and current.get("pre_fanout_review_cleared") and not current.get("downstream_locked"):
        current["pre_fanout_review_pending"] = False
        current["pre_fanout_review_cleared"] = False
        _refresh_checkpoint_reason(current)
    if _review_gate_pending(current):
        current["waiting_for_review"] = True
        current["review_required"] = True
    elif current.get("checkpoint_reason") in _EXECUTION_REVIEW_REASONS:
        current["waiting_for_review"] = False
        current["review_required"] = False

    if current.get("blocked_reason"):
        current["segment_status"] = "blocked"
    elif current.get("waiting_for_review"):
        current["segment_status"] = "waiting_review"
    elif current.get("waiting_reason"):
        current["segment_status"] = current.get("segment_status") or "awaiting_user"

    snapshot = CurrentExecutionState.model_validate(current)
    if _clear_execution_after_event(snapshot, payload, execution):
        return None
    return snapshot


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


def _set_session_context(layout: ProjectLayout, session: ObservabilitySession) -> None:
    _session_id_var.set(session.session_id)
    _session_cwd_var.set(layout.root)


def _persisted_active_session(layout: ProjectLayout) -> ObservabilitySession | None:
    current = get_current_session(layout.root)
    if current is None or current.status != "active":
        return None
    return current


def _active_context_session(layout: ProjectLayout) -> ObservabilitySession | None:
    existing_id = _session_id_var.get()
    if not existing_id or _session_cwd_var.get() != layout.root:
        return None
    current = _persisted_active_session(layout)
    if current is None or current.session_id != existing_id:
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
    persisted = _persisted_active_session(layout)
    if persisted is not None:
        _set_session_context(layout, persisted)
        return persisted

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
    _set_session_context(layout, session)
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
    next_execution = _updated_execution_state(get_current_execution(layout.root), payload, cwd=layout.root)
    if next_execution is None:
        _clear_current_execution(layout)
    else:
        _save_current_execution(layout, next_execution)

    updated = _updated_session(
        session,
        timestamp=payload.timestamp,
        command=payload.command,
        status=status if end_session else ("active" if session.status == "active" else session.status),
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
    elif session.status == "active":
        _save_current_session(layout, updated)
        _set_session_context(layout, updated)

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
