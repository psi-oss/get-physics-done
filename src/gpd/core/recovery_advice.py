"""Shared recovery/orientation decision contract.

This module owns the narrow factual contract for deciding whether GPD should
point the user at the current workspace recovery snapshot or the cross-project
recent-project picker. Rendering stays in CLI/docs/runtime surfaces.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from gpd.core.context import init_resume
from gpd.core.recent_projects import list_recent_projects

__all__ = [
    "RecoveryAdvice",
    "RecoveryAdviceAction",
    "build_recovery_advice",
]


class RecoveryAdviceAction(BaseModel):
    """One structured recovery follow-up action."""

    model_config = ConfigDict(frozen=True)

    kind: str
    command: str
    reason: str
    availability: str = "now"


class RecoveryAdvice(BaseModel):
    """Shared recovery/orientation decision payload."""

    model_config = ConfigDict(frozen=True)

    mode: str = "idle"
    status: str = "idle"
    decision_source: str = "none"
    primary_command: str | None = None
    primary_reason: str | None = None
    continue_command: str | None = None
    continue_reason: str | None = None
    fast_next_command: str | None = None
    fast_next_reason: str | None = None
    current_workspace_resumable: bool = False
    current_workspace_has_recovery: bool = False
    current_workspace_has_resume_file: bool = False
    current_workspace_candidate_count: int = 0
    resume_mode: str | None = None
    execution_resume_file: str | None = None
    execution_resume_file_source: str | None = None
    has_local_recovery_target: bool = False
    segment_candidates_count: int = 0
    has_live_execution: bool = False
    execution_resumable: bool = False
    has_session_resume_file: bool = False
    missing_session_resume_file: bool = False
    has_interrupted_agent: bool = False
    recent_projects_count: int = 0
    resumable_projects_count: int = 0
    available_projects_count: int = 0
    machine_change_notice: str | None = None
    actions: list[RecoveryAdviceAction] = Field(default_factory=list)


def _row_value(row: object, field: str, default: object = None) -> object:
    if isinstance(row, Mapping):
        return row.get(field, default)
    return getattr(row, field, default)


def _normalize_command(value: str | None, *, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    return fallback


def _bool_field(payload: Mapping[str, object], field: str) -> bool:
    return bool(payload.get(field))


def _text_field(payload: Mapping[str, object], field: str) -> str | None:
    value = payload.get(field)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _candidate_text(candidate: Mapping[str, object], field: str) -> str | None:
    value = candidate.get(field)
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _has_segment_candidate(
    segment_candidates: Sequence[Mapping[str, object]],
    *,
    source: str,
    status: str,
) -> bool:
    for candidate in segment_candidates:
        if _candidate_text(candidate, "source") != source:
            continue
        if _candidate_text(candidate, "status") != status:
            continue
        return True
    return False


def _has_usable_segment_candidate(
    segment_candidates: Sequence[Mapping[str, object]],
    *,
    source: str,
) -> bool:
    for candidate in segment_candidates:
        if _candidate_text(candidate, "source") != source:
            continue
        resume_file = _candidate_text(candidate, "resume_file")
        if resume_file is None:
            continue
        if _candidate_text(candidate, "status") == "missing":
            continue
        return True
    return False


def _has_usable_candidate_resume_file(segment_candidates: Sequence[Mapping[str, object]]) -> bool:
    for candidate in segment_candidates:
        resume_file = _candidate_text(candidate, "resume_file")
        if resume_file is None:
            continue
        if _candidate_text(candidate, "status") == "missing":
            continue
        return True
    return False


def _primary_reason(
    *,
    execution_resumable: bool,
    has_interrupted_agent: bool,
    has_live_execution: bool,
    has_session_resume_file: bool,
    missing_session_resume_file: bool,
    machine_change_notice: str | None,
) -> str:
    if execution_resumable:
        return "Current workspace has a bounded resumable execution segment."
    if has_interrupted_agent:
        return "Current workspace has an interrupted-agent marker to inspect."
    if has_session_resume_file:
        return "Current workspace has a recorded session handoff."
    if missing_session_resume_file:
        return "Current workspace has recorded recovery state, but the last handoff file is missing."
    if has_live_execution:
        return "Current workspace has a live execution snapshot that should be inspected first."
    if machine_change_notice:
        return "Current workspace has recorded recovery state and a machine-change notice to inspect."
    return "Current workspace has recorded recovery state."


def _status(
    *,
    execution_resumable: bool,
    has_interrupted_agent: bool,
    has_live_execution: bool,
    has_session_resume_file: bool,
    missing_session_resume_file: bool,
    current_workspace_has_recovery: bool,
    recent_projects_count: int,
) -> str:
    if execution_resumable:
        return "bounded-segment"
    if has_interrupted_agent:
        return "interrupted-agent"
    if has_session_resume_file:
        return "session-handoff"
    if missing_session_resume_file:
        return "missing-handoff"
    if has_live_execution:
        return "live-execution"
    if current_workspace_has_recovery:
        return "workspace-recovery"
    if recent_projects_count > 0:
        return "recent-projects"
    return "idle"


def _build_actions(
    *,
    mode: str,
    has_local_recovery_target: bool,
    primary_command: str | None,
    primary_reason: str | None,
    continue_command: str,
    continue_reason: str,
    fast_next_command: str,
    fast_next_reason: str,
) -> list[RecoveryAdviceAction]:
    actions: list[RecoveryAdviceAction] = []
    if primary_command and primary_reason:
        actions.append(
            RecoveryAdviceAction(
                kind="primary",
                command=primary_command,
                reason=primary_reason,
                availability="now",
            )
        )

    if mode == "current-workspace":
        if not has_local_recovery_target:
            return actions
        availability = "now"
    elif mode == "recent-projects":
        availability = "after_selection"
    else:
        return actions

    actions.append(
        RecoveryAdviceAction(
            kind="continue",
            command=continue_command,
            reason=continue_reason,
            availability=availability,
        )
    )
    actions.append(
        RecoveryAdviceAction(
            kind="fast-next",
            command=fast_next_command,
            reason=fast_next_reason,
            availability=availability,
        )
    )
    return actions


def build_recovery_advice(
    cwd: Path,
    *,
    data_root: Path | None = None,
    recent_rows: Sequence[object] | None = None,
    recent_projects_last: int = 5,
    resume_payload: Mapping[str, object] | None = None,
    continue_command: str | None = None,
    fast_next_command: str | None = None,
    force_recent: bool = False,
) -> RecoveryAdvice:
    """Build the shared recovery/orientation contract for one workspace."""

    normalized_cwd = cwd.expanduser().resolve(strict=False)
    payload = dict(resume_payload) if resume_payload is not None else init_resume(normalized_cwd)
    rows = list(recent_rows) if recent_rows is not None else list_recent_projects(data_root, last=recent_projects_last)

    recent_projects_count = len(rows)
    resumable_projects_count = sum(1 for row in rows if bool(_row_value(row, "resumable", False)))
    available_projects_count = sum(1 for row in rows if bool(_row_value(row, "available", False)))

    segment_candidates_raw = payload.get("segment_candidates")
    segment_candidates = [item for item in segment_candidates_raw if isinstance(item, Mapping)] if isinstance(segment_candidates_raw, list) else []

    resume_mode = _text_field(payload, "resume_mode")
    execution_resume_file = _text_field(payload, "execution_resume_file")
    execution_resume_file_source = _text_field(payload, "execution_resume_file_source")
    session_resume_file = _text_field(payload, "session_resume_file")
    recorded_session_resume_file = _text_field(payload, "recorded_session_resume_file")

    has_bounded_segment_candidate = _has_usable_segment_candidate(
        segment_candidates,
        source="current_execution",
    )
    execution_resumable = (
        _bool_field(payload, "execution_resumable")
        or resume_mode == "bounded_segment"
        or has_bounded_segment_candidate
    )
    has_interrupted_agent = (
        _bool_field(payload, "has_interrupted_agent")
        or resume_mode == "interrupted_agent"
        or _has_segment_candidate(
            segment_candidates,
            source="interrupted_agent",
            status="interrupted",
        )
    )
    has_live_execution = _bool_field(payload, "has_live_execution") or isinstance(payload.get("active_execution_segment"), Mapping)
    has_session_resume_file = (
        session_resume_file is not None
        or (
            execution_resume_file_source == "session_resume_file"
            and execution_resume_file is not None
        )
        or _has_segment_candidate(
            segment_candidates,
            source="session_resume_file",
            status="handoff",
        )
    )
    missing_session_resume_file = (
        _text_field(payload, "missing_session_resume_file") is not None
        or _has_segment_candidate(
            segment_candidates,
            source="session_resume_file",
            status="missing",
        )
        or (
            recorded_session_resume_file is not None
            and session_resume_file is None
            and not has_session_resume_file
        )
    )
    current_workspace_has_resume_file = (
        execution_resume_file is not None
        or session_resume_file is not None
        or _has_usable_candidate_resume_file(segment_candidates)
    )
    machine_change_notice = _text_field(payload, "machine_change_notice")

    current_workspace_has_recovery = bool(
        segment_candidates
        or execution_resumable
        or has_interrupted_agent
        or has_session_resume_file
        or missing_session_resume_file
        or has_live_execution
        or machine_change_notice is not None
        or recorded_session_resume_file is not None
        or execution_resume_file is not None
    )
    has_local_recovery_target = bool(
        execution_resumable
        or has_interrupted_agent
        or has_session_resume_file
    )
    status = _status(
        execution_resumable=execution_resumable,
        has_interrupted_agent=has_interrupted_agent,
        has_live_execution=has_live_execution,
        has_session_resume_file=has_session_resume_file,
        missing_session_resume_file=missing_session_resume_file,
        current_workspace_has_recovery=current_workspace_has_recovery,
        recent_projects_count=recent_projects_count,
    )

    resolved_continue_command = _normalize_command(continue_command, fallback="runtime `resume-work`")
    resolved_fast_next_command = _normalize_command(fast_next_command, fallback="runtime `suggest-next`")

    if force_recent:
        if recent_projects_count > 0:
            mode = "recent-projects"
            decision_source = "forced-recent-projects"
            primary_command = "gpd resume --recent"
            primary_reason = "Use the machine-local recent-project index to choose the workspace you want to reopen."
        else:
            mode = "idle"
            decision_source = "forced-recent-projects"
            primary_command = None
            primary_reason = "No recent recovery target is currently recorded on this machine."
    elif current_workspace_has_recovery:
        mode = "current-workspace"
        decision_source = "current-workspace"
        primary_command = "gpd resume"
        primary_reason = _primary_reason(
            execution_resumable=execution_resumable,
            has_interrupted_agent=has_interrupted_agent,
            has_live_execution=has_live_execution,
            has_session_resume_file=has_session_resume_file,
            missing_session_resume_file=missing_session_resume_file,
            machine_change_notice=machine_change_notice,
        )
    elif recent_projects_count > 0:
        mode = "recent-projects"
        decision_source = "recent-projects"
        primary_command = "gpd resume --recent"
        primary_reason = "Use the machine-local recent-project index to find the workspace you want to reopen."
    else:
        mode = "idle"
        decision_source = "none"
        primary_command = None
        primary_reason = "No recent recovery target is currently recorded on this machine."

    continue_reason = (
        "Continue paused work inside the selected workspace."
        if mode == "recent-projects"
        else "Continue paused work inside the current workspace."
    )
    fast_next_reason = "Fastest post-resume next command when you only need the next action."

    return RecoveryAdvice(
        mode=mode,
        status=status,
        decision_source=decision_source,
        primary_command=primary_command,
        primary_reason=primary_reason,
        continue_command=resolved_continue_command,
        continue_reason=continue_reason,
        fast_next_command=resolved_fast_next_command,
        fast_next_reason=fast_next_reason,
        current_workspace_resumable=execution_resumable,
        current_workspace_has_recovery=current_workspace_has_recovery,
        current_workspace_has_resume_file=current_workspace_has_resume_file,
        current_workspace_candidate_count=len(segment_candidates),
        resume_mode=resume_mode,
        execution_resume_file=execution_resume_file,
        execution_resume_file_source=execution_resume_file_source,
        has_local_recovery_target=has_local_recovery_target,
        segment_candidates_count=len(segment_candidates),
        has_live_execution=has_live_execution,
        execution_resumable=execution_resumable,
        has_session_resume_file=has_session_resume_file,
        missing_session_resume_file=missing_session_resume_file,
        has_interrupted_agent=has_interrupted_agent,
        recent_projects_count=recent_projects_count,
        resumable_projects_count=resumable_projects_count,
        available_projects_count=available_projects_count,
        machine_change_notice=machine_change_notice,
        actions=_build_actions(
            mode=mode,
            has_local_recovery_target=has_local_recovery_target,
            primary_command=primary_command,
            primary_reason=primary_reason,
            continue_command=resolved_continue_command,
            continue_reason=continue_reason,
            fast_next_command=resolved_fast_next_command,
            fast_next_reason=fast_next_reason,
        ),
    )
