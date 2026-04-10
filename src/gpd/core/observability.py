"""Session-focused local observability helpers for GPD.

Observability is written to the project-local telemetry and lineage surfaces:

- ``sessions/<session-id>.jsonl`` stores the full event stream for one session
- ``current-session.json`` points at the latest observed session summary
- ``GPD/lineage/execution-lineage.jsonl`` stores append-only execution lineage
- ``GPD/lineage/execution-head.json`` stores the derived execution head cache
- ``current-execution.json`` remains the compatibility mirror for legacy readers

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

from gpd.core import continuation as _continuation_module
from gpd.core.constants import ProjectLayout
from gpd.core.continuation import ContinuationBoundedSegment
from gpd.core.execution_lineage import (
    ExecutionHeadEffect,
    ExecutionLineageHead,
    build_execution_lineage_entry,
    clear_execution_lineage_head,
    execution_lineage_ledger_path,
    load_execution_lineage_entries,
    load_execution_lineage_head,
    project_execution_lineage_head,
    write_execution_lineage_head,
)
from gpd.core.public_surface_contract import recovery_local_snapshot_command
from gpd.core.root_resolution import normalize_workspace_hint as _normalize_workspace_path
from gpd.core.root_resolution import resolve_project_root as _shared_resolve_project_root
from gpd.core.utils import atomic_write, file_lock, phase_normalize, safe_read_file

__all__ = [
    "CurrentExecutionState",
    "ExecutionVisibilitySuggestion",
    "ExecutionVisibilityState",
    "ExportLogsResult",
    "LocalSpan",
    "ObservabilityEvent",
    "ObservabilitySession",
    "ObserveEventResult",
    "ObservabilitySessionsResult",
    "ObservabilityShowResult",
    "ensure_session",
    "ensure_observability_session",
    "derive_execution_visibility",
    "export_logs",
    "get_current_execution",
    "get_current_session",
    "get_current_session_id",
    "gpd_span",
    "humanize_execution_reason",
    "instrument_gpd_function",
    "list_sessions",
    "log_event",
    "observe_event",
    "record_event",
    "resolve_project_root",
    "show_events",
    "sync_execution_visibility_from_canonical_continuation",
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
    tangent_summary: str | None = None
    tangent_decision: str | None = None
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

    @field_validator("tangent_decision", mode="before")
    @classmethod
    def _normalize_tangent_decision_field(cls, value: object) -> object:
        return _normalized_tangent_decision(value)


class ExecutionVisibilityState(BaseModel):
    """Normalized read-only execution visibility payload for local status surfaces."""

    model_config = ConfigDict(frozen=True)

    workspace_root: str | None = None
    has_live_execution: bool = False
    visibility_mode: str = "idle"
    visibility_note: str | None = None
    status_classification: str = "idle"
    assessment: str = "idle"
    possibly_stalled: bool = False
    stale_after_minutes: int = 30
    last_updated_at: str | None = None
    last_updated_age_label: str | None = None
    last_updated_age_minutes: float | None = None
    phase: str | None = None
    plan: str | None = None
    wave: int | str | None = None
    segment_status: str | None = None
    current_task: str | None = None
    current_task_index: int | None = None
    current_task_total: int | None = None
    current_task_progress: str | None = None
    segment_reason: str | None = None
    checkpoint_reason: str | None = None
    waiting_reason: str | None = None
    waiting_reason_label: str | None = None
    blocked_reason: str | None = None
    blocked_reason_label: str | None = None
    review_reason: str | None = None
    tangent_summary: str | None = None
    tangent_decision: str | None = None
    tangent_decision_label: str | None = None
    tangent_pending: bool = False
    last_result_label: str | None = None
    last_artifact_path: str | None = None
    resume_file: str | None = None
    current_execution: dict[str, object] | None = None
    suggested_next_commands: list[ExecutionVisibilitySuggestion] = Field(default_factory=list)
    suggested_next_steps: list[str] = Field(default_factory=list)


class ExecutionVisibilitySuggestion(BaseModel):
    """One prioritized follow-up command for the current execution snapshot."""

    model_config = ConfigDict(frozen=True)

    command: str
    reason: str


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


def resolve_project_root(
    cwd: Path | str | None = None,
    *,
    project_dir: Path | str | None = None,
) -> Path | None:
    """Compatibility wrapper around the canonical shared root resolver."""
    return _shared_resolve_project_root(cwd, project_dir=project_dir)


def _project_root(cwd: Path | None = None) -> Path | None:
    if cwd is not None:
        candidate = resolve_project_root(cwd)
    else:
        pwd = _normalize_workspace_path(Path.cwd()) or Path.cwd()
        if ProjectLayout(pwd).gpd.exists():
            candidate = pwd
        else:
            candidate = resolve_project_root(_session_cwd_var.get()) or pwd
    if candidate is None:
        return None
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
    layout.lineage_dir.mkdir(parents=True, exist_ok=True)


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


def _append_event_locked(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(payload, default=str)
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


def _current_execution_snapshot(layout: ProjectLayout) -> CurrentExecutionState | None:
    head_snapshot = load_execution_lineage_head(layout.root)
    if head_snapshot is not None and isinstance(head_snapshot.execution, dict):
        try:
            return CurrentExecutionState.model_validate(head_snapshot.execution)
        except Exception:
            pass
    raw = _read_current_execution_raw(layout)
    if raw is None:
        return None
    try:
        return CurrentExecutionState.model_validate(raw)
    except Exception:
        return None


def _normalized_execution_snapshot(snapshot: CurrentExecutionState | None) -> dict[str, object]:
    if snapshot is None:
        return {}
    return snapshot.model_dump(mode="json")


def _phase_like_or_none(value: object) -> str | None:
    if isinstance(value, int):
        return phase_normalize(str(value))
    if isinstance(value, str):
        stripped = value.strip()
        return phase_normalize(stripped) if stripped else None
    return None


def _execution_identity_value(field_name: str, value: object) -> str | None:
    if field_name in {"phase", "plan"}:
        return _phase_like_or_none(value)
    return _str_or_none(value)


def _execution_lane_field_value(payload: object, field: str) -> str | None:
    if isinstance(payload, dict):
        return _execution_identity_value(field, payload.get(field))
    if hasattr(payload, field):
        return _execution_identity_value(field, getattr(payload, field))
    return None


def _execution_lanes_compatible(left: object, right: object) -> bool:
    comparisons = 0
    for field in ("resume_file", "segment_id", "phase", "plan", "transition_id"):
        left_value = _execution_lane_field_value(left, field)
        right_value = _execution_lane_field_value(right, field)
        if left_value is None or right_value is None:
            continue
        comparisons += 1
        if left_value != right_value:
            return False
    return comparisons > 0


def _canonical_result_payload(state_obj: dict[str, object], result_id: str) -> dict[str, object] | None:
    results = state_obj.get("intermediate_results")
    if not isinstance(results, list):
        return None
    for result in results:
        if isinstance(result, dict) and _str_or_none(result.get("id")) == result_id:
            return result
    return None


def _canonical_result_label(result: object) -> str | None:
    if not isinstance(result, dict):
        return None
    description = _str_or_none(result.get("description"))
    if description is not None:
        return description
    equation = _str_or_none(result.get("equation"))
    if equation is not None:
        return equation
    return None


def _sync_execution_visibility_anchors_from_canonical_continuation(
    layout: ProjectLayout | Path,
    *,
    state_obj: dict[str, object] | None = None,
) -> bool:
    """Project canonical continuity anchors into existing live execution caches."""

    layout = layout if isinstance(layout, ProjectLayout) else ProjectLayout(Path(layout).expanduser().resolve(strict=False))
    current_exists = layout.current_observability_execution.exists()
    head_exists = layout.execution_lineage_head.exists()
    if not current_exists and not head_exists:
        return False

    if state_obj is None:
        from gpd.core.state import peek_state_json

        loaded_state_obj, _issues, _source = peek_state_json(layout.root, recover_intent=False)
        state_obj = loaded_state_obj

    if not isinstance(state_obj, dict):
        return False

    canonical_continuation = state_obj.get("continuation")
    if not isinstance(canonical_continuation, dict):
        return False

    canonical_bounded_segment = canonical_continuation.get("bounded_segment")
    if not isinstance(canonical_bounded_segment, dict):
        return False

    canonical_last_result_id = _str_or_none(canonical_bounded_segment.get("last_result_id"))
    if canonical_last_result_id is None:
        return False
    canonical_result = _canonical_result_payload(state_obj, canonical_last_result_id)

    current_snapshot: CurrentExecutionState | None = None
    current_raw: dict[str, object] | None = None
    if current_exists:
        current_raw = _read_current_execution_raw(layout)
        if isinstance(current_raw, dict):
            try:
                current_snapshot = CurrentExecutionState.model_validate(current_raw)
            except Exception:
                current_snapshot = None

    head_snapshot: CurrentExecutionState | None = None
    head_payload: ExecutionLineageHead | None = None
    head_raw: dict[str, object] | None = None
    if head_exists:
        head_raw = _read_json(layout.execution_lineage_head)
        if isinstance(head_raw, dict):
            try:
                head_payload = ExecutionLineageHead.model_validate(head_raw)
            except Exception:
                head_payload = None
            else:
                if isinstance(head_payload.execution, dict):
                    try:
                        head_snapshot = CurrentExecutionState.model_validate(head_payload.execution)
                    except Exception:
                        head_snapshot = None

    live_snapshot = head_snapshot or current_snapshot
    if live_snapshot is None:
        return False

    if current_snapshot is not None and head_snapshot is not None and not _execution_lanes_compatible(current_snapshot, head_snapshot):
        return False
    if not _execution_lanes_compatible(live_snapshot, canonical_bounded_segment):
        return False

    updated_fields = {
        "last_result_id": canonical_last_result_id,
        "last_result_label": _canonical_result_label(canonical_result),
    }
    updated_snapshot = live_snapshot.model_copy(update=updated_fields)
    wrote = False
    lock_target = layout.execution_lineage_head if head_exists else layout.current_observability_execution

    with file_lock(lock_target):
        if current_exists:
            current_updated = (
                updated_snapshot if head_snapshot is not None else current_snapshot.model_copy(update=updated_fields)
                if current_snapshot is not None
                else updated_snapshot
            )
            if current_raw != current_updated.model_dump(mode="json"):
                _save_current_execution(layout, current_updated)
                wrote = True

        if head_exists:
            head_bounded_segment = None
            if head_payload is not None and head_payload.bounded_segment is not None:
                head_bounded_segment = head_payload.bounded_segment.model_copy(
                    update={"last_result_id": canonical_last_result_id}
                )
            elif isinstance(head_raw, dict) and isinstance(head_raw.get("bounded_segment"), dict):
                head_bounded_segment = {
                    **head_raw["bounded_segment"],
                    "last_result_id": canonical_last_result_id,
                }

            next_head = project_execution_lineage_head(
                updated_snapshot.model_dump(mode="json"),
                bounded_segment=head_bounded_segment,
                last_applied_seq=(
                    head_payload.last_applied_seq
                    if head_payload is not None
                    else head_raw.get("last_applied_seq")
                    if isinstance(head_raw, dict)
                    else None
                ),
                last_applied_event_id=(
                    head_payload.last_applied_event_id
                    if head_payload is not None
                    else head_raw.get("last_applied_event_id")
                    if isinstance(head_raw, dict)
                    else None
                ),
                recorded_at=(
                    head_payload.recorded_at
                    if head_payload is not None
                    else head_raw.get("recorded_at")
                    if isinstance(head_raw, dict)
                    else None
                ),
                reducer_version=(
                    head_payload.reducer_version
                    if head_payload is not None
                    else head_raw.get("reducer_version")
                    if isinstance(head_raw, dict)
                    else None
                ),
            )
            if not isinstance(head_raw, dict) or head_raw != next_head.model_dump(mode="json"):
                write_execution_lineage_head(layout.root, next_head)
                wrote = True

    return wrote


def sync_execution_visibility_from_canonical_continuation(
    layout: ProjectLayout | Path,
    *,
    state_obj: dict[str, object] | None = None,
) -> bool:
    """Sync live execution visibility caches from canonical continuation state."""

    return _sync_execution_visibility_anchors_from_canonical_continuation(layout, state_obj=state_obj)


def _bounded_segment_helper() -> Callable | None:
    helper = getattr(_continuation_module, "canonical_bounded_segment_from_execution_snapshot", None)
    return helper if callable(helper) else None


def _bounded_segment_from_normalized_execution_snapshot(
    cwd: Path,
    snapshot: CurrentExecutionState | None,
) -> ContinuationBoundedSegment | None:
    if snapshot is None:
        return None

    helper = _bounded_segment_helper()
    if helper is None:
        return None

    payload = _normalized_execution_snapshot(snapshot)
    for candidate in (payload, snapshot):
        try:
            derived = helper(cwd, candidate)
        except TypeError:
            continue
        except Exception:
            return None
        if derived is None:
            return None
        if isinstance(derived, ContinuationBoundedSegment):
            return derived
        try:
            return ContinuationBoundedSegment.model_validate(derived)
        except Exception:
            return None
    return None


def _persist_durable_bounded_segment(layout: ProjectLayout, next_execution: CurrentExecutionState | None) -> None:
    """Best-effort durable continuation write for the normalized execution snapshot."""
    from gpd.core.state import (
        state_clear_continuation_bounded_segment,
        state_set_continuation_bounded_segment,
    )

    desired_bounded_segment = _bounded_segment_from_normalized_execution_snapshot(layout.root, next_execution)
    if desired_bounded_segment is None:
        state_clear_continuation_bounded_segment(layout.root)
        return
    state_set_continuation_bounded_segment(layout.root, desired_bounded_segment)


def get_current_execution(cwd: Path | None = None) -> CurrentExecutionState | None:
    layout = _layout(cwd)
    if layout is None:
        return None
    return _current_execution_snapshot(layout)


def _execution_visibility_age_minutes(updated_at: str | None) -> float | None:
    if not isinstance(updated_at, str) or not updated_at.strip():
        return None
    observed_at = _parse_iso_datetime(updated_at)
    if observed_at is None:
        return None
    age_minutes = (datetime.now(UTC) - observed_at).total_seconds() / 60.0
    return round(max(0.0, age_minutes), 1)


def _execution_visibility_age_label(updated_at: str | None) -> str | None:
    """Return a compact human label like ``12m ago`` for one update timestamp."""
    if not isinstance(updated_at, str) or not updated_at.strip():
        return None
    observed_at = _parse_iso_datetime(updated_at)
    if observed_at is None:
        return None
    elapsed_seconds = max(0, int((datetime.now(UTC) - observed_at).total_seconds()))
    if elapsed_seconds < 60:
        return f"{elapsed_seconds}s ago"
    if elapsed_seconds < 3600:
        return f"{elapsed_seconds // 60}m ago"
    return f"{elapsed_seconds // 3600}h ago"


def _execution_visibility_review_reason(snapshot: CurrentExecutionState | None) -> str | None:
    """Return the most relevant review-stop reason for one execution snapshot."""
    if snapshot is None:
        return None
    checkpoint = _str_or_none(snapshot.checkpoint_reason)
    if snapshot.first_result_gate_pending:
        return "first-result review pending"
    if snapshot.pre_fanout_review_pending:
        return "pre-fanout review pending"
    if snapshot.skeptical_requestioning_required:
        return "skeptical re-questioning required"
    if snapshot.waiting_for_review:
        if checkpoint == "first_result":
            return "first-result review pending"
        if checkpoint == "pre_fanout":
            return "pre-fanout review pending"
        if checkpoint == "skeptical_requestioning":
            return "skeptical re-questioning required"
        if checkpoint is not None:
            return checkpoint.replace("_", " ")
        return "review checkpoint pending"
    return None


def _execution_visibility_classification(snapshot: CurrentExecutionState | None) -> str:
    if snapshot is None:
        return "idle"

    blocked_reason = _str_or_none(snapshot.blocked_reason)
    if blocked_reason:
        return "blocked"

    waiting_markers = (
        snapshot.waiting_for_review,
        snapshot.review_required,
        snapshot.first_result_gate_pending,
        snapshot.pre_fanout_review_pending,
        snapshot.skeptical_requestioning_required,
        snapshot.downstream_locked,
        _str_or_none(snapshot.waiting_reason),
    )
    segment_status = (snapshot.segment_status or "").strip().lower()
    if any(bool(marker) for marker in waiting_markers) or segment_status == "waiting_review":
        return "waiting"

    paused_states = {"paused", "awaiting_user", "ready_to_continue"}
    if segment_status in paused_states:
        return "paused-or-resumable"
    if segment_status == "blocked":
        return "blocked"
    if segment_status in {"completed", "complete", "done", "finished"}:
        return "idle"
    if _str_or_none(snapshot.resume_file):
        return "paused-or-resumable"
    return "active"


_EXECUTION_REASON_LABELS = {
    "first_result": "first-result",
    "pre_fanout": "pre-fanout",
    "first_result_review_required": "first-result review required",
    "skeptical_requestioning": "skeptical re-questioning",
    "skeptical_requestioning_required": "skeptical re-questioning required",
    "task_budget_reached": "task budget reached",
    "time_budget_exceeded": "time budget exceeded",
    "segment_boundary": "segment boundary reached",
    "awaiting_user": "awaiting user input",
    "ready_to_continue": "ready to continue",
}

_TANGENT_DECISION_LABELS = {
    "ignore": "stay on main path",
    "defer": "capture and defer",
    "branch_later": "branch later",
    "pursue_now": "pursue now",
}


def humanize_execution_reason(reason: str | None) -> str | None:
    """Return one human-readable label for an execution checkpoint or wait reason."""
    normalized = _normalized_checkpoint_reason(reason)
    if normalized is None:
        return None
    return _EXECUTION_REASON_LABELS.get(normalized, normalized.replace("_", " "))


def _humanize_tangent_decision(decision: str | None) -> str | None:
    normalized = _normalized_tangent_decision(decision)
    if normalized is None:
        return None
    return _TANGENT_DECISION_LABELS.get(normalized, normalized.replace("_", " "))


def _execution_visibility_tangent_steps(snapshot: CurrentExecutionState | None) -> list[str]:
    if snapshot is None:
        return []

    tangent_summary = _str_or_none(snapshot.tangent_summary)
    if tangent_summary is None:
        return []

    from gpd.core.surface_phrases import tangent_branch_later_action, tangent_chooser_action

    decision = _normalized_tangent_decision(snapshot.tangent_decision)
    decision_label = _humanize_tangent_decision(decision)
    if decision is None:
        return [
            f"Tangent proposal pending at this review stop: {tangent_summary}.",
            tangent_chooser_action(),
        ]
    if decision == "branch_later":
        return [
            f"Tangent proposal recorded: {tangent_summary}. Recommendation: {decision_label}.",
            tangent_branch_later_action(),
        ]
    if decision == "defer":
        return [f"Tangent proposal recorded: {tangent_summary}. Recommendation: {decision_label}."]
    if decision == "pursue_now":
        return [
            f"Tangent proposal recorded: {tangent_summary}. Recommendation: {decision_label} within the current bounded stop."
        ]
    return [f"Tangent proposal recorded: {tangent_summary}. Recommendation: {decision_label}."]


def _execution_visibility_next_commands(
    *,
    classification: str,
    snapshot: CurrentExecutionState | None,
    possibly_stalled: bool,
    visibility_mode: str = "full",
) -> list[ExecutionVisibilitySuggestion]:
    suggestions: list[ExecutionVisibilitySuggestion] = []
    if snapshot is None:
        if visibility_mode == "degraded":
            return [
                ExecutionVisibilitySuggestion(
                    command="gpd observe sessions --last 5",
                    reason="inspect recent observability sessions because the live execution telemetry is degraded",
                ),
                ExecutionVisibilitySuggestion(
                    command="gpd progress bar",
                    reason="cross-check workspace progress separately while the live execution telemetry is degraded",
                ),
            ]
        return [
            ExecutionVisibilitySuggestion(
                command="gpd observe sessions --last 5",
                reason="inspect recent local observability sessions",
            ),
            ExecutionVisibilitySuggestion(
                command="gpd progress bar",
                reason="inspect the workspace state separately from live execution telemetry",
            ),
        ]

    phase_plan = "-".join(part for part in (snapshot.phase, snapshot.plan) if part) or "current execution"
    session_scope = f" --session {snapshot.session_id}" if snapshot.session_id else ""
    observe_command = f"gpd observe show{session_scope} --last 20"
    recovery_command = recovery_local_snapshot_command()

    if visibility_mode in {"snapshot-only", "trace-only"}:
        mode_reason = (
            "inspect recent observability sessions because only the compatibility snapshot is available"
            if visibility_mode == "snapshot-only"
            else "inspect recent observability sessions because only the lineage trace head is available"
        )
        return [
            ExecutionVisibilitySuggestion(
                command="gpd observe sessions --last 5",
                reason=mode_reason,
            ),
            ExecutionVisibilitySuggestion(
                command="gpd progress bar",
                reason="cross-check workspace progress separately from the partial execution visibility",
            ),
        ]

    if classification == "blocked":
        suggestions.append(
            ExecutionVisibilitySuggestion(
                command=recovery_command,
                reason="inspect the current recovery snapshot and blocker context",
            )
        )
        suggestions.append(
            ExecutionVisibilitySuggestion(
                command=observe_command,
                reason=f"inspect the recent execution event trail for {phase_plan}",
            )
        )
    elif classification == "waiting":
        suggestions.append(
            ExecutionVisibilitySuggestion(
                command=recovery_command,
                reason="inspect the resumable checkpoint and review context",
            )
        )
        suggestions.append(
            ExecutionVisibilitySuggestion(
                command=observe_command,
                reason=f"inspect the recent execution event trail for {phase_plan}",
            )
        )
    elif classification == "paused-or-resumable":
        suggestions.append(
            ExecutionVisibilitySuggestion(
                command=recovery_command,
                reason="inspect the ranked recovery candidates before continuing inside the runtime",
            )
        )
        suggestions.append(
            ExecutionVisibilitySuggestion(
                command=observe_command,
                reason=f"inspect the recent execution event trail for {phase_plan}",
            )
        )
    elif classification == "active":
        if possibly_stalled:
            suggestions.append(
                ExecutionVisibilitySuggestion(
                    command=observe_command,
                    reason=f"inspect the recent execution event trail for {phase_plan} before assuming the run has stalled",
                )
            )
            suggestions.append(
                ExecutionVisibilitySuggestion(
                    command=recovery_command,
                    reason="inspect the latest recovery snapshot if the run should already have paused",
                )
            )
            suggestions.append(
                ExecutionVisibilitySuggestion(
                    command="gpd progress bar",
                    reason="cross-check broader workspace progress separately from the live execution state",
                )
            )
        else:
            suggestions.append(
                ExecutionVisibilitySuggestion(
                    command=observe_command,
                    reason=f"inspect the recent observability event trail for {phase_plan} when you want more detail",
                )
            )
            suggestions.append(
                ExecutionVisibilitySuggestion(
                    command="gpd progress bar",
                    reason="check a compact workspace-level summary separately from the live execution state",
                )
            )
    else:
        suggestions.append(
            ExecutionVisibilitySuggestion(
                command="gpd observe sessions --last 5",
                reason="inspect recent local observability sessions",
            )
        )
        suggestions.append(
            ExecutionVisibilitySuggestion(
                command="gpd progress bar",
                reason="inspect the current workspace state",
            )
        )
    return suggestions


def _execution_visibility_next_steps(
    suggestions: list[ExecutionVisibilitySuggestion],
) -> list[str]:
    from gpd.core.surface_phrases import command_follow_up_action

    return [
        command_follow_up_action(command=suggestion.command, reason=suggestion.reason)
        for suggestion in suggestions
    ]


def _execution_visibility_source_state(
    layout: ProjectLayout,
) -> tuple[CurrentExecutionState | None, str, str | None]:
    authoritative_snapshot = get_current_execution(layout.root)
    current_exists = layout.current_observability_execution.exists()
    head_exists = layout.execution_lineage_head.exists()

    current_raw = _read_current_execution_raw(layout) if current_exists else None
    head_raw = _read_json(layout.execution_lineage_head) if head_exists else None

    current_snapshot: CurrentExecutionState | None = None
    head_snapshot: CurrentExecutionState | None = None
    current_valid = False
    head_valid = False
    degraded_reasons: list[str] = []

    if current_exists:
        if isinstance(current_raw, dict):
            try:
                current_snapshot = CurrentExecutionState.model_validate(current_raw)
            except Exception:
                degraded_reasons.append("current-execution.json is malformed")
            else:
                current_valid = True
        else:
            degraded_reasons.append("current-execution.json is missing or unreadable")

    if head_exists:
        if isinstance(head_raw, dict):
            try:
                head_payload = ExecutionLineageHead.model_validate(head_raw)
            except Exception:
                degraded_reasons.append("execution-head.json is malformed")
            else:
                if isinstance(head_payload.execution, dict):
                    try:
                        head_snapshot = CurrentExecutionState.model_validate(head_payload.execution)
                    except Exception:
                        degraded_reasons.append("execution-head.json payload is malformed")
                    else:
                        head_valid = True
                else:
                    degraded_reasons.append("execution-head.json is incomplete")
        else:
            degraded_reasons.append("execution-head.json is missing or unreadable")

    snapshot = authoritative_snapshot or head_snapshot or current_snapshot
    if snapshot is None:
        if current_exists or head_exists:
            note = "; ".join(dict.fromkeys(degraded_reasons)) or "live execution telemetry is incomplete"
            return None, "degraded", note
        return None, "idle", None

    if current_valid and head_valid:
        return snapshot, "full", None
    if current_valid and not head_exists:
        return snapshot, "full", None
    if head_valid and not current_exists:
        return snapshot, "full", None
    if current_valid and head_exists and not head_valid:
        note = "; ".join(dict.fromkeys(degraded_reasons)) or "compatibility snapshot only"
        return snapshot, "snapshot-only", note
    if head_valid and current_exists and not current_valid:
        note = "; ".join(dict.fromkeys(degraded_reasons)) or "lineage trace only"
        return snapshot, "trace-only", note

    note = "; ".join(dict.fromkeys(degraded_reasons)) or "live execution telemetry is incomplete"
    return snapshot, "degraded", note


def derive_execution_visibility(cwd: Path | None = None) -> ExecutionVisibilityState | None:
    """Derive a normalized local execution visibility payload from the current snapshot."""
    layout = _layout(cwd)
    if layout is None:
        return None

    snapshot, visibility_mode, visibility_note = _execution_visibility_source_state(layout)
    if snapshot is None:
        degraded = visibility_mode == "degraded"
        suggestions = _execution_visibility_next_commands(
            classification="idle",
            snapshot=None,
            possibly_stalled=False,
            visibility_mode=visibility_mode,
        )
        return ExecutionVisibilityState(
            workspace_root=str(layout.root),
            has_live_execution=False,
            visibility_mode=visibility_mode,
            visibility_note=visibility_note,
            status_classification="degraded" if degraded else "idle",
            assessment="degraded" if degraded else "idle",
            suggested_next_commands=suggestions,
            suggested_next_steps=_execution_visibility_next_steps(suggestions),
        )

    classification = _execution_visibility_classification(snapshot)
    age_minutes = _execution_visibility_age_minutes(snapshot.updated_at)
    age_label = _execution_visibility_age_label(snapshot.updated_at)
    possibly_stalled = classification == "active" and age_minutes is not None and age_minutes >= 30.0
    if visibility_mode == "full":
        assessment = "possibly stalled" if possibly_stalled else classification
    elif visibility_mode in {"snapshot-only", "trace-only"}:
        assessment = f"{visibility_mode} {classification}"
    else:
        assessment = visibility_mode
    current_task_progress: str | None = None
    if snapshot.current_task_index is not None and snapshot.current_task_total is not None:
        current_task_progress = f"{snapshot.current_task_index}/{snapshot.current_task_total}"

    suggestions = _execution_visibility_next_commands(
        classification=classification,
        snapshot=snapshot,
        possibly_stalled=possibly_stalled,
        visibility_mode=visibility_mode,
    )
    tangent_steps = _execution_visibility_tangent_steps(snapshot)

    return ExecutionVisibilityState(
        workspace_root=str(layout.root),
        has_live_execution=True,
        visibility_mode=visibility_mode,
        visibility_note=visibility_note,
        status_classification=classification,
        assessment=assessment,
        possibly_stalled=possibly_stalled,
        stale_after_minutes=30,
        last_updated_at=snapshot.updated_at,
        last_updated_age_label=age_label,
        last_updated_age_minutes=age_minutes,
        phase=snapshot.phase,
        plan=snapshot.plan,
        wave=snapshot.wave,
        segment_status=snapshot.segment_status,
        current_task=snapshot.current_task,
        current_task_index=snapshot.current_task_index,
        current_task_total=snapshot.current_task_total,
        current_task_progress=current_task_progress,
        segment_reason=snapshot.segment_reason,
        checkpoint_reason=snapshot.checkpoint_reason,
        waiting_reason=snapshot.waiting_reason,
        waiting_reason_label=humanize_execution_reason(snapshot.waiting_reason),
        blocked_reason=snapshot.blocked_reason,
        blocked_reason_label=humanize_execution_reason(snapshot.blocked_reason),
        review_reason=_execution_visibility_review_reason(snapshot),
        tangent_summary=snapshot.tangent_summary,
        tangent_decision=snapshot.tangent_decision,
        tangent_decision_label=_humanize_tangent_decision(snapshot.tangent_decision),
        tangent_pending=bool(snapshot.tangent_summary) and not bool(snapshot.tangent_decision),
        last_result_label=snapshot.last_result_label,
        last_artifact_path=snapshot.last_artifact_path,
        resume_file=snapshot.resume_file,
        current_execution=snapshot.model_dump(mode="json"),
        suggested_next_commands=suggestions,
        suggested_next_steps=[*_execution_visibility_next_steps(suggestions), *tangent_steps],
    )


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


def _normalized_tangent_decision(value: object) -> str | None:
    decision = _str_or_none(value)
    if decision is None:
        return None
    return decision.strip().replace("-", "_")


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


def _clear_tangent_state(current: dict[str, object]) -> None:
    current["tangent_summary"] = None
    current["tangent_decision"] = None


def _clear_execution_hold_state(current: dict[str, object], *, clear_first_result_ready: bool = False) -> None:
    """Clear transient waiting/review/blocked state from one execution snapshot."""

    current["waiting_for_review"] = False
    current["review_required"] = False
    current["checkpoint_reason"] = None
    current["waiting_reason"] = None
    current["blocked_reason"] = None
    current["first_result_gate_pending"] = False
    current["pre_fanout_review_pending"] = False
    current["pre_fanout_review_cleared"] = False
    current["downstream_locked"] = False
    if clear_first_result_ready:
        current["first_result_ready"] = False
    _clear_skeptical_review(current)
    _clear_tangent_state(current)


def _reset_execution_segment_state(current: dict[str, object]) -> None:
    """Reset one execution snapshot for the start of a fresh segment."""

    _clear_execution_hold_state(current, clear_first_result_ready=True)
    for key in (
        "segment_id",
        "segment_status",
        "segment_reason",
        "current_task",
        "current_task_index",
        "current_task_total",
        "last_result_id",
        "last_result_label",
        "last_artifact_path",
        "resume_file",
        "segment_started_at",
        "transition_id",
    ):
        current[key] = None


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


def _execution_head_effect(
    previous: CurrentExecutionState | None,
    next_execution: CurrentExecutionState | None,
) -> ExecutionHeadEffect:
    if next_execution is None:
        return ExecutionHeadEffect.CLEAR
    if previous is None:
        return ExecutionHeadEffect.SEED
    if previous.model_dump(mode="json") == next_execution.model_dump(mode="json"):
        return ExecutionHeadEffect.NOOP
    return ExecutionHeadEffect.REPLACE


def _persist_execution_lineage_transition(
    layout: ProjectLayout,
    payload: ObservabilityEvent,
    *,
    previous_execution: CurrentExecutionState | None,
    next_execution: CurrentExecutionState | None,
) -> None:
    lineage_entries = load_execution_lineage_entries(layout.root)
    previous_record = lineage_entries[-1] if lineage_entries else None
    execution = _execution_data(payload.data)
    segment_id = _str_or_none(execution.get("segment_id"))
    bounded_segment = _bounded_segment_from_normalized_execution_snapshot(layout.root, next_execution)
    record = build_execution_lineage_entry(
        kind=f"{payload.name}.{payload.action}",
        event_id=payload.event_id,
        recorded_at=payload.timestamp,
        session_id=payload.session_id,
        phase=payload.phase,
        plan=payload.plan,
        segment_id=segment_id or (next_execution.segment_id if next_execution is not None else None),
        parent_segment_id=previous_execution.segment_id
        if payload.name == "segment" and payload.action == "start" and previous_execution is not None
        else None,
        prev_event_id=previous_record.event_id if previous_record is not None else None,
        causation_event_id=payload.event_id,
        source_category=payload.category,
        source_name=payload.name,
        source_action=payload.action,
        head_effect=_execution_head_effect(previous_execution, next_execution),
        head_after=next_execution,
        bounded_segment_after=bounded_segment,
        data=payload.data,
        seq=(previous_record.seq + 1) if previous_record is not None else 1,
    )
    _append_event_locked(execution_lineage_ledger_path(layout.root), record.model_dump(mode="json"))

    if next_execution is None:
        clear_execution_lineage_head(layout.root)
        _clear_current_execution(layout)
    else:
        head = project_execution_lineage_head(
            next_execution,
            bounded_segment=bounded_segment,
            last_applied_seq=record.seq,
            last_applied_event_id=record.event_id,
            recorded_at=payload.timestamp,
        )
        write_execution_lineage_head(layout.root, head)
        _save_current_execution(layout, next_execution)


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

    segment_action = payload.action if payload.name == "segment" else None
    if segment_action == "start":
        _reset_execution_segment_state(current)
    elif segment_action in {"pause", "finish", "stop"}:
        _clear_execution_hold_state(current)

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
        "tangent_summary",
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
    tangent_decision = _normalized_tangent_decision(execution.get("tangent_decision"))
    if tangent_decision is not None:
        current["tangent_decision"] = tangent_decision

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
        current["segment_started_at"] = payload.timestamp
        current["segment_status"] = "active"
    elif payload.name == "segment" and payload.action == "pause":
        pause_status = (current.get("segment_status") or "").strip().lower()
        current["segment_status"] = pause_status if pause_status in {"paused", "awaiting_user", "ready_to_continue"} else "paused"
    elif payload.name == "segment" and payload.action in {"finish", "stop"}:
        current["segment_status"] = "completed"

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
            if not _review_gate_pending(current):
                current["waiting_for_review"] = False
                current["review_required"] = False
            if current.get("segment_status") == "waiting_review" and not _review_gate_pending(current):
                current["segment_status"] = "active"
            if not _review_gate_pending(current):
                _clear_tangent_state(current)
        elif not _review_gate_pending(current):
            current["waiting_for_review"] = False
            current["review_required"] = False
            current["waiting_reason"] = None
            if current.get("segment_status") == "waiting_review":
                current["segment_status"] = "active"
            _clear_tangent_state(current)

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
            _clear_tangent_state(current)

    if payload.name == "result" and payload.action in {"produce", "log"}:
        if current.get("checkpoint_reason") == "first_result" or _bool_or_none(execution.get("load_bearing")):
            current["first_result_ready"] = True

    if payload.name != "segment" or payload.action not in {"pause", "finish", "stop"}:
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

    if payload.name == "segment" and payload.action == "start":
        current["segment_status"] = "active"
    elif payload.name == "segment" and payload.action == "pause":
        pause_status = (current.get("segment_status") or "").strip().lower()
        current["segment_status"] = pause_status if pause_status in {"paused", "awaiting_user", "ready_to_continue"} else "paused"
    elif payload.name == "segment" and payload.action in {"finish", "stop"}:
        current["segment_status"] = "completed"

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
    session_log = _session_log(layout, session.session_id)
    if payload.category == "execution":
        lineage_path = execution_lineage_ledger_path(layout.root)
        with file_lock(lineage_path):
            _append_event_locked(session_log, payload.model_dump(mode="json"))
            previous_execution = _current_execution_snapshot(layout)
            next_execution = _updated_execution_state(previous_execution, payload, cwd=layout.root)
            _persist_execution_lineage_transition(
                layout,
                payload,
                previous_execution=previous_execution,
                next_execution=next_execution,
            )
            _persist_durable_bounded_segment(layout, next_execution)
    else:
        _append_event(session_log, payload.model_dump(mode="json"))
        next_execution = _updated_execution_state(get_current_execution(layout.root), payload, cwd=layout.root)
        if next_execution is None:
            _clear_current_execution(layout)
        else:
            _save_current_execution(layout, next_execution)
        _persist_durable_bounded_segment(layout, next_execution)

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


class ExportLogsResult(BaseModel):
    """Return value for ``export_logs``."""

    model_config = ConfigDict(frozen=True)

    exported: bool
    output_dir: str
    sessions_exported: int = 0
    events_exported: int = 0
    traces_exported: int = 0
    files_written: list[str] = Field(default_factory=list)
    reason: str | None = None


def export_logs(
    cwd: Path | None = None,
    *,
    output_dir: str | None = None,
    session: str | None = None,
    category: str | None = None,
    command: str | None = None,
    phase: str | None = None,
    last: int | None = None,
    include_traces: bool = True,
    format: str = "jsonl",
) -> ExportLogsResult:
    """Export session logs and traces to files.

    Reads observability sessions and optionally traces, applies filters,
    and writes the results to the specified output directory.

    Supported formats: ``jsonl`` (raw, one JSON object per line),
    ``json`` (pretty-printed array), ``markdown`` (human-readable report).
    """
    layout = _layout(cwd)
    if layout is None:
        return ExportLogsResult(
            exported=False,
            output_dir=output_dir or "",
            reason="No GPD project found in working directory",
        )

    dest = Path(output_dir) if output_dir else layout.root / "GPD" / "exports" / "logs"
    dest.mkdir(parents=True, exist_ok=True)

    if format not in {"jsonl", "json", "markdown"}:
        return ExportLogsResult(
            exported=False,
            output_dir=str(dest),
            reason=f"Unsupported format: {format}. Use jsonl, json, or markdown.",
        )

    files_written: list[str] = []
    sessions_exported = 0
    events_exported = 0
    traces_exported = 0

    sessions = _iter_session_meta(layout)
    if command:
        sessions = [s for s in sessions if s.command == command]
    if session:
        sessions = [s for s in sessions if s.session_id == session]
    if last and last > 0:
        sessions = sessions[:last]

    sessions_exported = len(sessions)

    all_events: list[dict[str, object]] = []
    for sess in sessions:
        events = _filter_events(
            _read_events(_session_log(layout, sess.session_id)),
            category=category,
            phase=phase,
        )
        all_events.extend(events)
    all_events.sort(key=lambda e: str(e.get("timestamp", "")))
    events_exported = len(all_events)

    timestamp_slug = _now_iso().replace(":", "").replace("-", "")[:15]

    if format == "jsonl":
        sessions_path = dest / f"sessions-{timestamp_slug}.jsonl"
        lines = [json.dumps(s.model_dump(mode="json")) for s in sessions]
        atomic_write(sessions_path, "\n".join(lines) + "\n" if lines else "")
        files_written.append(str(sessions_path))

        events_path = dest / f"events-{timestamp_slug}.jsonl"
        event_lines = [json.dumps(e) for e in all_events]
        atomic_write(events_path, "\n".join(event_lines) + "\n" if event_lines else "")
        files_written.append(str(events_path))

    elif format == "json":
        sessions_path = dest / f"sessions-{timestamp_slug}.json"
        atomic_write(
            sessions_path,
            json.dumps([s.model_dump(mode="json") for s in sessions], indent=2) + "\n",
        )
        files_written.append(str(sessions_path))

        events_path = dest / f"events-{timestamp_slug}.json"
        atomic_write(events_path, json.dumps(all_events, indent=2) + "\n")
        files_written.append(str(events_path))

    elif format == "markdown":
        report_path = dest / f"log-report-{timestamp_slug}.md"
        md_lines = [
            "# GPD Session Log Export",
            "",
            f"**Exported:** {_now_iso()}",
            f"**Sessions:** {sessions_exported}",
            f"**Events:** {events_exported}",
            "",
            "## Sessions",
            "",
            "| Session ID | Started | Last Event | Command | Status |",
            "|------------|---------|------------|---------|--------|",
        ]
        for sess in sessions:
            md_lines.append(
                f"| `{sess.session_id}` | {sess.started_at} | {sess.last_event_at} "
                f"| {sess.command or '—'} | {sess.status} |"
            )
        md_lines.extend(["", "## Events", ""])
        for evt in all_events:
            ts = evt.get("timestamp", "?")
            cat = evt.get("category", "?")
            nm = evt.get("name", "?")
            act = evt.get("action", "?")
            st = evt.get("status", "?")
            md_lines.append(f"- **{ts}** [{cat}/{nm}] action={act} status={st}")
            if evt.get("phase"):
                md_lines.append(f"  - Phase: {evt['phase']}")
            if evt.get("data"):
                md_lines.append(f"  - Data: `{json.dumps(evt['data'])}`")
        md_lines.append("")
        atomic_write(report_path, "\n".join(md_lines))
        files_written.append(str(report_path))

    if include_traces and layout.traces_dir.is_dir():
        trace_files = sorted(layout.traces_dir.glob("*.jsonl"))
        if trace_files:
            if format == "jsonl":
                traces_path = dest / f"traces-{timestamp_slug}.jsonl"
                trace_lines: list[str] = []
                for tf in trace_files:
                    content = safe_read_file(tf)
                    if content:
                        trace_lines.extend(line for line in content.splitlines() if line.strip())
                atomic_write(traces_path, "\n".join(trace_lines) + "\n" if trace_lines else "")
                files_written.append(str(traces_path))
                traces_exported = len(trace_lines)

            elif format == "json":
                traces_path = dest / f"traces-{timestamp_slug}.json"
                all_traces: list[dict[str, object]] = []
                for tf in trace_files:
                    content = safe_read_file(tf)
                    if content:
                        for line in content.splitlines():
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                all_traces.append(json.loads(line))
                            except Exception:
                                continue
                atomic_write(traces_path, json.dumps(all_traces, indent=2) + "\n")
                files_written.append(str(traces_path))
                traces_exported = len(all_traces)

            elif format == "markdown":
                trace_section: list[str] = ["", "## Traces", ""]
                trace_count = 0
                for tf in trace_files:
                    trace_section.append(f"### {tf.stem}")
                    trace_section.append("")
                    content = safe_read_file(tf)
                    if content:
                        for line in content.splitlines():
                            line = line.strip()
                            if not line:
                                continue
                            try:
                                obj = json.loads(line)
                            except Exception:
                                continue
                            trace_count += 1
                            ts = obj.get("timestamp", "?")
                            etype = obj.get("type", obj.get("event_type", "?"))
                            trace_section.append(f"- **{ts}** [{etype}]")
                            if obj.get("summary"):
                                trace_section.append(f"  - {obj['summary']}")
                    trace_section.append("")
                traces_exported = trace_count

                report_path_obj = Path(files_written[-1]) if files_written else dest / f"log-report-{timestamp_slug}.md"
                existing = safe_read_file(report_path_obj) or ""
                atomic_write(report_path_obj, existing + "\n".join(trace_section))

    return ExportLogsResult(
        exported=True,
        output_dir=str(dest),
        sessions_exported=sessions_exported,
        events_exported=events_exported,
        traces_exported=traces_exported,
        files_written=files_written,
    )
