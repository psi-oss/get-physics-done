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
from gpd.core.resume_surface import (
    lookup_resume_surface_list,
    lookup_resume_surface_mapping,
    lookup_resume_surface_text,
    resolve_resume_compat_surface,
    resume_candidate_kind,
    resume_candidate_origin,
    resume_origin_for_bounded_segment,
    resume_origin_for_handoff,
    resume_source_from_origin,
)
from gpd.core.surface_phrases import (
    recovery_continue_reason,
    recovery_fast_next_reason,
    recovery_primary_reason,
)

__all__ = [
    "RecoveryAdvice",
    "RecoveryAdviceAction",
    "build_recovery_advice",
    "serialize_recovery_orientation",
]

RESUME_SURFACE_SCHEMA_VERSION = 1


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
    status: str = "no-recovery"
    decision_source: str = "none"
    primary_command: str | None = None
    primary_reason: str | None = None
    continue_command: str | None = None
    continue_reason: str | None = None
    fast_next_command: str | None = None
    fast_next_reason: str | None = None
    workspace_root: str | None = None
    project_root: str | None = None
    project_root_source: str | None = None
    project_root_auto_selected: bool = False
    project_reentry_mode: str | None = None
    project_reentry_requires_selection: bool = False
    project_reentry_reason: str | None = None
    current_workspace_resumable: bool = False
    current_workspace_has_recovery: bool = False
    current_workspace_has_resume_file: bool = False
    current_workspace_candidate_count: int = 0
    active_resume_kind: str | None = None
    active_resume_origin: str | None = None
    active_resume_pointer: str | None = None
    continuity_handoff_file: str | None = None
    recorded_continuity_handoff_file: str | None = None
    missing_continuity_handoff_file: str | None = None
    has_continuity_handoff: bool = False
    missing_continuity_handoff: bool = False
    has_local_recovery_target: bool = False
    resume_candidates_count: int = 0
    has_live_execution: bool = False
    execution_resumable: bool = False
    has_interrupted_agent: bool = False
    recent_projects_count: int = 0
    resumable_projects_count: int = 0
    available_projects_count: int = 0
    machine_change_notice: str | None = None
    actions: list[RecoveryAdviceAction] = Field(default_factory=list)

    @property
    def resume_mode(self) -> str | None:
        if self.active_resume_kind in {"bounded_segment", "interrupted_agent"}:
            return self.active_resume_kind
        return None

    @property
    def execution_resume_file(self) -> str | None:
        return self.active_resume_pointer

    @property
    def execution_resume_file_source(self) -> str | None:
        return resume_source_from_origin(self.active_resume_origin)

    @property
    def has_session_resume_file(self) -> bool:
        return self.has_continuity_handoff

    @property
    def missing_session_resume_file(self) -> bool:
        return self.missing_continuity_handoff

    @property
    def segment_candidates_count(self) -> int:
        return self.resume_candidates_count


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


def _compat_resume_surface(payload: Mapping[str, object]) -> Mapping[str, object] | None:
    return resolve_resume_compat_surface(payload)


def _canonical_text_field(
    payload: Mapping[str, object],
    compat_surface: Mapping[str, object] | None,
    field: str,
    *,
    compat_fields: Sequence[str] = (),
) -> str | None:
    return lookup_resume_surface_text(
        payload,
        field,
        compat_surface=compat_surface,
        compat_key=field,
        compat_keys=compat_fields,
    )


def _legacy_text_field(
    payload: Mapping[str, object],
    compat_surface: Mapping[str, object] | None,
    field: str,
    *,
    compat_fields: Sequence[str] = (),
) -> str | None:
    return lookup_resume_surface_text(
        payload,
        field,
        compat_surface=compat_surface,
        compat_key=field,
        compat_keys=compat_fields,
        prefer_compat=True,
    )


def _canonical_mapping_field(
    payload: Mapping[str, object],
    compat_surface: Mapping[str, object] | None,
    field: str,
    *,
    compat_fields: Sequence[str] = (),
) -> Mapping[str, object] | None:
    return lookup_resume_surface_mapping(
        payload,
        field,
        compat_surface=compat_surface,
        compat_key=field,
        compat_keys=compat_fields,
    )


def _legacy_mapping_field(
    payload: Mapping[str, object],
    compat_surface: Mapping[str, object] | None,
    field: str,
    *,
    compat_fields: Sequence[str] = (),
) -> Mapping[str, object] | None:
    return lookup_resume_surface_mapping(
        payload,
        field,
        compat_surface=compat_surface,
        compat_key=field,
        compat_keys=compat_fields,
        prefer_compat=True,
    )


def _canonical_list_field(
    payload: Mapping[str, object],
    compat_surface: Mapping[str, object] | None,
    field: str,
    *,
    compat_fields: Sequence[str] = (),
) -> list[object] | None:
    return lookup_resume_surface_list(
        payload,
        field,
        compat_surface=compat_surface,
        compat_key=field,
        compat_keys=compat_fields,
    )


def _legacy_list_field(
    payload: Mapping[str, object],
    compat_surface: Mapping[str, object] | None,
    field: str,
    *,
    compat_fields: Sequence[str] = (),
) -> list[object] | None:
    return lookup_resume_surface_list(
        payload,
        field,
        compat_surface=compat_surface,
        compat_key=field,
        compat_keys=compat_fields,
        prefer_compat=True,
    )


def _canonical_project_reentry_candidates(
    payload: Mapping[str, object],
    compat_surface: Mapping[str, object] | None,
) -> list[Mapping[str, object]] | None:
    candidates = _canonical_list_field(payload, compat_surface, "project_reentry_candidates")
    if candidates is None:
        return None
    return [candidate for candidate in candidates if isinstance(candidate, Mapping)]


def _selected_project_reentry_candidate(
    payload: Mapping[str, object],
    candidates: Sequence[Mapping[str, object]] | None,
    compat_surface: Mapping[str, object] | None,
) -> Mapping[str, object] | None:
    selected_candidate = _canonical_mapping_field(payload, compat_surface, "project_reentry_selected_candidate")
    if selected_candidate is not None:
        return selected_candidate

    if not candidates:
        return None
    project_root = _text_field(payload, "project_root")
    if project_root is None:
        return None
    project_root_source = _text_field(payload, "project_root_source")
    if project_root_source is not None:
        for candidate in candidates:
            if _candidate_text(candidate, "project_root") == project_root and _candidate_text(candidate, "source") == project_root_source:
                return candidate
    return next((candidate for candidate in candidates if _candidate_text(candidate, "project_root") == project_root), None)


def _selected_recent_project_resume_family(
    candidate: Mapping[str, object] | None,
) -> tuple[str | None, str | None]:
    if candidate is None or _candidate_text(candidate, "source") != "recent_project":
        return None, None

    resume_target_kind = _candidate_text(candidate, "resume_target_kind")
    source_kind = _candidate_text(candidate, "source_kind")
    if resume_target_kind == "bounded_segment":
        return "bounded_segment", source_kind or resume_origin_for_bounded_segment()
    if resume_target_kind == "handoff":
        return "continuity_handoff", source_kind or resume_origin_for_handoff()
    return None, None


def _candidate_kind(candidate: Mapping[str, object]) -> str | None:
    return resume_candidate_kind(candidate)


def _candidate_origin(candidate: Mapping[str, object]) -> str | None:
    return resume_candidate_origin(candidate)


def _has_candidate(
    segment_candidates: Sequence[Mapping[str, object]],
    *,
    kind: str | None = None,
    origin: str | None = None,
    status: str | None = None,
) -> bool:
    for candidate in segment_candidates:
        if kind is not None and _candidate_kind(candidate) != kind:
            continue
        if origin is not None and _candidate_origin(candidate) != origin:
            continue
        if status is not None and _candidate_text(candidate, "status") != status:
            continue
        return True
    return False


def _has_usable_candidate(
    segment_candidates: Sequence[Mapping[str, object]],
    *,
    kind: str | None = None,
    origin: str | None = None,
) -> bool:
    for candidate in segment_candidates:
        if kind is not None and _candidate_kind(candidate) != kind:
            continue
        if origin is not None and _candidate_origin(candidate) != origin:
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


def _derive_active_resume_kind(
    *,
    payload: Mapping[str, object],
    compat_surface: Mapping[str, object] | None,
    resume_mode: str | None,
    active_resume_pointer: str | None,
    continuity_handoff_file: str | None,
    missing_continuity_handoff_file: str | None,
    resume_candidates: Sequence[Mapping[str, object]],
) -> str | None:
    explicit = _canonical_text_field(payload, compat_surface, "active_resume_kind")
    if explicit is not None:
        return explicit
    explicit_origin = _canonical_text_field(payload, compat_surface, "active_resume_origin")
    if explicit_origin == "interrupted_agent_marker":
        return "interrupted_agent"
    if explicit_origin in {"continuation.bounded_segment", "compat.current_execution"}:
        return "bounded_segment"
    if explicit_origin in {"continuation.handoff", "compat.session_resume_file"}:
        return "continuity_handoff"
    if missing_continuity_handoff_file is not None:
        return "continuity_handoff"
    if _has_candidate(resume_candidates, kind="continuity_handoff", status="missing"):
        return "continuity_handoff"
    if _has_candidate(resume_candidates, kind="bounded_segment"):
        return "bounded_segment"
    if resume_mode == "bounded_segment":
        return "bounded_segment"
    if active_resume_pointer is not None and _legacy_text_field(
        payload,
        compat_surface,
        "execution_resume_file_source",
    ) == "session_resume_file":
        return "continuity_handoff"
    if continuity_handoff_file is not None:
        return "continuity_handoff"
    if _has_candidate(resume_candidates, kind="continuity_handoff", status="handoff"):
        return "continuity_handoff"
    if _has_candidate(resume_candidates, kind="interrupted_agent", status="interrupted"):
        return "interrupted_agent"
    return None


def _derive_active_resume_origin(
    *,
    payload: Mapping[str, object],
    compat_surface: Mapping[str, object] | None,
    active_resume_kind: str | None,
    continuity_handoff_file: str | None,
    recorded_continuity_handoff_file: str | None,
    missing_continuity_handoff_file: str | None,
    resume_candidates: Sequence[Mapping[str, object]],
) -> str | None:
    explicit = _canonical_text_field(payload, compat_surface, "active_resume_origin")
    if explicit is not None:
        return explicit

    legacy_source = _legacy_text_field(payload, compat_surface, "execution_resume_file_source")
    if active_resume_kind == "bounded_segment":
        if _canonical_mapping_field(payload, compat_surface, "active_bounded_segment") is not None:
            return "continuation.bounded_segment"
        if _canonical_mapping_field(payload, compat_surface, "derived_execution_head") is not None or _legacy_mapping_field(
            payload,
            compat_surface,
            "current_execution",
        ) is not None:
            return "compat.current_execution"
        if _has_candidate(resume_candidates, origin="compat.current_execution", kind="bounded_segment"):
            return "compat.current_execution"
        if _has_candidate(resume_candidates, origin="continuation.bounded_segment", kind="bounded_segment"):
            return "continuation.bounded_segment"
        if legacy_source == "current_execution":
            return "compat.current_execution"
        if _legacy_mapping_field(payload, compat_surface, "active_execution_segment") is not None:
            return "continuation.bounded_segment"
        return "continuation.bounded_segment"
    if active_resume_kind == "continuity_handoff":
        if any(
            value is not None
            for value in (
                _canonical_text_field(payload, compat_surface, "continuity_handoff_file"),
                _canonical_text_field(payload, compat_surface, "recorded_continuity_handoff_file"),
                _canonical_text_field(payload, compat_surface, "missing_continuity_handoff_file"),
            )
        ):
            return "continuation.handoff"
        if any(value is not None for value in (continuity_handoff_file, recorded_continuity_handoff_file, missing_continuity_handoff_file)):
            return "continuation.handoff"
        if _has_candidate(resume_candidates, origin="compat.session_resume_file", kind="continuity_handoff"):
            return "compat.session_resume_file"
        if _has_candidate(resume_candidates, origin="continuation.handoff", kind="continuity_handoff"):
            return "continuation.handoff"
        if legacy_source == "session_resume_file":
            return "compat.session_resume_file"
        if missing_continuity_handoff_file is not None:
            return "compat.session_resume_file"
        return "continuation.handoff"
    if active_resume_kind == "interrupted_agent":
        return "interrupted_agent_marker"
    if legacy_source == "current_execution":
        return "compat.current_execution"
    if legacy_source == "session_resume_file":
        return "compat.session_resume_file"
    return None


def serialize_recovery_orientation(advice: RecoveryAdvice) -> dict[str, object]:
    """Return the explicit public orientation surface for runtime hints."""

    return {
        "resume_surface_schema_version": RESUME_SURFACE_SCHEMA_VERSION,
        "mode": advice.mode,
        "status": advice.status,
        "decision_source": advice.decision_source,
        "primary_command": advice.primary_command,
        "primary_reason": advice.primary_reason,
        "continue_command": advice.continue_command,
        "continue_reason": advice.continue_reason,
        "fast_next_command": advice.fast_next_command,
        "fast_next_reason": advice.fast_next_reason,
        "workspace_root": advice.workspace_root,
        "project_root": advice.project_root,
        "project_root_source": advice.project_root_source,
        "project_root_auto_selected": advice.project_root_auto_selected,
        "project_reentry_mode": advice.project_reentry_mode,
        "project_reentry_requires_selection": advice.project_reentry_requires_selection,
        "project_reentry_reason": advice.project_reentry_reason,
        "current_workspace_resumable": advice.current_workspace_resumable,
        "current_workspace_has_recovery": advice.current_workspace_has_recovery,
        "current_workspace_has_resume_file": advice.current_workspace_has_resume_file,
        "current_workspace_candidate_count": advice.current_workspace_candidate_count,
        "active_resume_kind": advice.active_resume_kind,
        "active_resume_origin": advice.active_resume_origin,
        "active_resume_pointer": advice.active_resume_pointer,
        "continuity_handoff_file": advice.continuity_handoff_file,
        "recorded_continuity_handoff_file": advice.recorded_continuity_handoff_file,
        "missing_continuity_handoff_file": advice.missing_continuity_handoff_file,
        "has_continuity_handoff": advice.has_continuity_handoff,
        "missing_continuity_handoff": advice.missing_continuity_handoff,
        "has_local_recovery_target": advice.has_local_recovery_target,
        "resume_candidates_count": advice.resume_candidates_count,
        "has_live_execution": advice.has_live_execution,
        "execution_resumable": advice.execution_resumable,
        "has_interrupted_agent": advice.has_interrupted_agent,
        "recent_projects_count": advice.recent_projects_count,
        "resumable_projects_count": advice.resumable_projects_count,
        "available_projects_count": advice.available_projects_count,
        "machine_change_notice": advice.machine_change_notice,
    }


def _status(
    *,
    execution_resumable: bool,
    has_interrupted_agent: bool,
    has_live_execution: bool,
    has_continuity_handoff: bool,
    missing_continuity_handoff: bool,
    current_workspace_has_recovery: bool,
    recent_projects_count: int,
) -> str:
    if execution_resumable:
        return "bounded-segment"
    if has_interrupted_agent:
        return "interrupted-agent"
    if has_continuity_handoff:
        return "session-handoff"
    if missing_continuity_handoff:
        return "missing-handoff"
    if has_live_execution:
        return "live-execution"
    if current_workspace_has_recovery:
        return "workspace-recovery"
    if recent_projects_count > 0:
        return "recent-projects"
    return "no-recovery"


def _recent_project_reentry_reason(
    *,
    decision_source: str,
    recent_projects_count: int,
    resumable_projects_count: int,
    available_projects_count: int,
) -> str | None:
    if decision_source == "auto-selected-recent-project":
        return "GPD found the only recoverable recent project on this machine and selected it automatically."
    if decision_source == "ambiguous-recent-projects":
        if resumable_projects_count > 0:
            return f"GPD found {resumable_projects_count} recoverable recent projects on this machine, so you need to choose one."
        return "GPD found recent projects on this machine, but none are ready to reopen automatically."
    if decision_source == "forced-recent-projects":
        return "GPD will show the recent-project list so you can pick a workspace manually."
    if decision_source == "recent-projects":
        if resumable_projects_count > 0:
            return "GPD found recent projects on this machine, but none are selected automatically."
        if available_projects_count > 0:
            return "GPD found recent projects on this machine, but none are ready to reopen automatically."
        if recent_projects_count > 0:
            return "GPD found recent projects on this machine, but none can be reopened automatically."
    return None


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
    compat_resume_surface = _compat_resume_surface(payload)
    rows = list(recent_rows) if recent_rows is not None else list_recent_projects(data_root, last=recent_projects_last)
    project_reentry_candidates = _canonical_project_reentry_candidates(payload, compat_resume_surface)
    selected_project_reentry_candidate = _selected_project_reentry_candidate(
        payload,
        project_reentry_candidates,
        compat_resume_surface,
    )
    recent_project_rows = (
        [candidate for candidate in project_reentry_candidates if _row_value(candidate, "source") == "recent_project"]
        if project_reentry_candidates is not None
        else rows
    )

    recent_projects_count = len(recent_project_rows)
    resumable_projects_count = sum(1 for row in recent_project_rows if bool(_row_value(row, "resumable", False)))
    available_projects_count = sum(1 for row in recent_project_rows if bool(_row_value(row, "available", False)))

    segment_candidates_raw = _canonical_list_field(
        payload,
        compat_resume_surface,
        "resume_candidates",
        compat_fields=("segment_candidates",),
    )
    if segment_candidates_raw is None:
        segment_candidates_raw = _legacy_list_field(payload, compat_resume_surface, "segment_candidates")
    segment_candidates = [item for item in segment_candidates_raw if isinstance(item, Mapping)] if isinstance(segment_candidates_raw, list) else []

    resume_mode = _legacy_text_field(payload, compat_resume_surface, "resume_mode")
    continuity_handoff_file = _canonical_text_field(
        payload,
        compat_resume_surface,
        "continuity_handoff_file",
        compat_fields=("session_resume_file",),
    )
    if continuity_handoff_file is None:
        continuity_handoff_file = _legacy_text_field(payload, compat_resume_surface, "session_resume_file")
    recorded_continuity_handoff_file = _canonical_text_field(
        payload,
        compat_resume_surface,
        "recorded_continuity_handoff_file",
        compat_fields=("recorded_session_resume_file",),
    )
    if recorded_continuity_handoff_file is None:
        recorded_continuity_handoff_file = _legacy_text_field(payload, compat_resume_surface, "recorded_session_resume_file")
    missing_continuity_handoff_file = _canonical_text_field(
        payload,
        compat_resume_surface,
        "missing_continuity_handoff_file",
        compat_fields=("missing_session_resume_file",),
    )
    if missing_continuity_handoff_file is None:
        missing_continuity_handoff_file = _legacy_text_field(payload, compat_resume_surface, "missing_session_resume_file")
    active_resume_pointer = _canonical_text_field(
        payload,
        compat_resume_surface,
        "active_resume_pointer",
        compat_fields=("execution_resume_file",),
    )
    if active_resume_pointer is None:
        active_resume_pointer = _legacy_text_field(payload, compat_resume_surface, "execution_resume_file")
    active_resume_kind = _derive_active_resume_kind(
        payload=payload,
        compat_surface=compat_resume_surface,
        resume_mode=resume_mode,
        active_resume_pointer=active_resume_pointer,
        continuity_handoff_file=continuity_handoff_file,
        missing_continuity_handoff_file=missing_continuity_handoff_file,
        resume_candidates=segment_candidates,
    )
    active_resume_origin = _derive_active_resume_origin(
        payload=payload,
        compat_surface=compat_resume_surface,
        active_resume_kind=active_resume_kind,
        continuity_handoff_file=continuity_handoff_file,
        recorded_continuity_handoff_file=recorded_continuity_handoff_file,
        missing_continuity_handoff_file=missing_continuity_handoff_file,
        resume_candidates=segment_candidates,
    )
    selected_recent_project_resume_kind, selected_recent_project_resume_origin = _selected_recent_project_resume_family(
        selected_project_reentry_candidate
    )
    if active_resume_kind is None:
        active_resume_kind = selected_recent_project_resume_kind
    if active_resume_origin is None:
        active_resume_origin = selected_recent_project_resume_origin
    workspace_root = _text_field(payload, "workspace_root")
    project_root = _text_field(payload, "project_root")
    project_root_source = _text_field(payload, "project_root_source")
    project_root_auto_selected = _bool_field(payload, "project_root_auto_selected")
    project_reentry_mode = _text_field(payload, "project_reentry_mode")
    project_reentry_requires_selection = _bool_field(payload, "project_reentry_requires_selection")
    active_bounded_segment = _canonical_mapping_field(payload, compat_resume_surface, "active_bounded_segment")
    legacy_active_execution_segment = _legacy_mapping_field(payload, compat_resume_surface, "active_execution_segment")
    if active_bounded_segment is None and active_resume_kind == "bounded_segment" and legacy_active_execution_segment is not None:
        active_bounded_segment = legacy_active_execution_segment
    derived_execution_head = _canonical_mapping_field(payload, compat_resume_surface, "derived_execution_head")
    if derived_execution_head is None:
        derived_execution_head = _legacy_mapping_field(payload, compat_resume_surface, "current_execution")

    def _compat_bool(field: str) -> bool | None:
        if compat_resume_surface is None or field not in compat_resume_surface:
            return None
        return bool(compat_resume_surface.get(field))

    has_bounded_segment_candidate = _has_usable_candidate(segment_candidates, kind="bounded_segment")
    execution_resumable_flag = _compat_bool("execution_resumable")
    if execution_resumable_flag is None:
        execution_resumable_flag = _bool_field(payload, "execution_resumable")
    if active_resume_kind == "bounded_segment":
        execution_resumable = bool(
            active_resume_pointer
            or has_bounded_segment_candidate
            or execution_resumable_flag
            or resume_mode == "bounded_segment"
        )
    elif active_resume_kind == "continuity_handoff":
        execution_resumable = False
    else:
        execution_resumable = (
            execution_resumable_flag
            or resume_mode == "bounded_segment"
            or has_bounded_segment_candidate
        )
    interrupted_agent_flag = _compat_bool("has_interrupted_agent")
    if interrupted_agent_flag is None:
        interrupted_agent_flag = _bool_field(payload, "has_interrupted_agent")
    has_interrupted_agent = (
        interrupted_agent_flag
        or active_resume_kind == "interrupted_agent"
        or resume_mode == "interrupted_agent"
        or _has_candidate(
            segment_candidates,
            kind="interrupted_agent",
            status="interrupted",
        )
    )
    live_execution_flag = _compat_bool("has_live_execution")
    if live_execution_flag is None:
        live_execution_flag = _bool_field(payload, "has_live_execution")
    has_live_execution = (
        live_execution_flag
        or derived_execution_head is not None
        or (
            legacy_active_execution_segment is not None
            and active_resume_kind != "bounded_segment"
            and not execution_resumable
        )
    )
    has_continuity_handoff = (
        continuity_handoff_file is not None
        or (
            active_resume_kind == "continuity_handoff"
            and active_resume_pointer is not None
        )
        or _has_candidate(
            segment_candidates,
            kind="continuity_handoff",
            status="handoff",
        )
    )
    missing_continuity_handoff = (
        missing_continuity_handoff_file is not None
        or _has_candidate(
            segment_candidates,
            kind="continuity_handoff",
            status="missing",
        )
        or (
            recorded_continuity_handoff_file is not None
            and continuity_handoff_file is None
            and not has_continuity_handoff
        )
    )
    current_workspace_has_resume_file = (
        active_resume_pointer is not None
        or continuity_handoff_file is not None
        or _has_usable_candidate_resume_file(segment_candidates)
    )
    machine_change_notice = _text_field(payload, "machine_change_notice")

    current_workspace_has_recovery = bool(
        segment_candidates
        or execution_resumable
        or has_interrupted_agent
        or has_continuity_handoff
        or missing_continuity_handoff
        or has_live_execution
        or machine_change_notice is not None
        or recorded_continuity_handoff_file is not None
        or active_resume_pointer is not None
    )
    has_local_recovery_target = bool(
        execution_resumable
        or has_interrupted_agent
        or has_continuity_handoff
    )
    inferred_reentry_mode = project_reentry_mode or (
        "auto-recent-project"
        if project_root_auto_selected
        else "current-workspace"
        if current_workspace_has_recovery
        else "ambiguous-recent-projects"
        if project_reentry_requires_selection
        else "recent-projects"
        if recent_projects_count > 0
        else "no-recovery"
    )
    auto_selected_recent_project = inferred_reentry_mode == "auto-recent-project" or (
        project_root_auto_selected and current_workspace_has_recovery
    )
    ambiguous_recent_projects = inferred_reentry_mode == "ambiguous-recent-projects"
    resolved_status = _status(
        execution_resumable=execution_resumable,
        has_interrupted_agent=has_interrupted_agent,
        has_live_execution=has_live_execution,
        has_continuity_handoff=has_continuity_handoff,
        missing_continuity_handoff=missing_continuity_handoff,
        current_workspace_has_recovery=current_workspace_has_recovery,
        recent_projects_count=recent_projects_count,
    )

    decision_source: str
    if force_recent:
        if recent_projects_count > 0:
            decision_source = "forced-recent-projects"
            primary_command = "gpd resume --recent"
        else:
            decision_source = "no-recovery"
            primary_command = None
    elif auto_selected_recent_project:
        decision_source = "auto-selected-recent-project"
        primary_command = "gpd resume --recent"
    elif current_workspace_has_recovery:
        decision_source = "current-workspace"
        primary_command = "gpd resume"
    elif ambiguous_recent_projects:
        decision_source = "ambiguous-recent-projects"
        primary_command = "gpd resume --recent" if recent_projects_count > 0 else None
    elif recent_projects_count > 0:
        decision_source = "recent-projects"
        primary_command = "gpd resume --recent"
    else:
        decision_source = "no-recovery"
        primary_command = None

    if decision_source == "no-recovery":
        resolved_continue_command = None
        resolved_fast_next_command = None
        continue_reason = "No recoverable workspace is currently available."
        fast_next_reason = "No next action is available until a workspace can be recovered."
        mode = "idle"
    else:
        resolved_continue_command = _normalize_command(continue_command, fallback="runtime `resume-work`")
        resolved_fast_next_command = _normalize_command(fast_next_command, fallback="runtime `suggest-next`")
        continue_reason = recovery_continue_reason(mode="current-workspace" if auto_selected_recent_project or current_workspace_has_recovery else "recent-projects")
        fast_next_reason = recovery_fast_next_reason()

    project_reentry_reason = _recent_project_reentry_reason(
        decision_source=decision_source,
        recent_projects_count=recent_projects_count,
        resumable_projects_count=resumable_projects_count,
        available_projects_count=available_projects_count,
    )
    mode = "current-workspace" if (auto_selected_recent_project or current_workspace_has_recovery) else "recent-projects" if recent_projects_count > 0 and decision_source != "no-recovery" else "idle"
    primary_reason = recovery_primary_reason(
        mode="current-workspace"
        if decision_source == "current-workspace"
        else "recent-projects"
        if decision_source
        in {"auto-selected-recent-project", "ambiguous-recent-projects", "forced-recent-projects", "recent-projects"}
        else "idle",
        forced_recent=force_recent,
        execution_resumable=execution_resumable,
        has_interrupted_agent=has_interrupted_agent,
        has_live_execution=has_live_execution,
        has_continuity_handoff=has_continuity_handoff,
        missing_continuity_handoff=missing_continuity_handoff,
        machine_change_notice=machine_change_notice,
    )
    if project_reentry_reason is not None:
        primary_reason = project_reentry_reason
    status = "no-recovery" if decision_source == "no-recovery" else resolved_status

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
        workspace_root=workspace_root,
        project_root=project_root,
        project_root_source=project_root_source,
        project_root_auto_selected=project_root_auto_selected,
        project_reentry_mode=inferred_reentry_mode,
        project_reentry_requires_selection=project_reentry_requires_selection,
        project_reentry_reason=project_reentry_reason,
        current_workspace_resumable=execution_resumable,
        current_workspace_has_recovery=current_workspace_has_recovery,
        current_workspace_has_resume_file=current_workspace_has_resume_file,
        current_workspace_candidate_count=len(segment_candidates),
        active_resume_kind=active_resume_kind,
        active_resume_origin=active_resume_origin,
        active_resume_pointer=active_resume_pointer,
        continuity_handoff_file=continuity_handoff_file,
        recorded_continuity_handoff_file=recorded_continuity_handoff_file,
        missing_continuity_handoff_file=missing_continuity_handoff_file,
        has_continuity_handoff=has_continuity_handoff,
        missing_continuity_handoff=missing_continuity_handoff,
        has_local_recovery_target=has_local_recovery_target,
        resume_candidates_count=len(segment_candidates),
        has_live_execution=has_live_execution,
        execution_resumable=execution_resumable,
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
