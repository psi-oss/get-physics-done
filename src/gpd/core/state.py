"""Dual-write state management for GPD research projects.

The state engine maintains two files in sync:
- STATE.md  — human-readable, editable markdown
- state.json — machine-readable, authoritative for structured data

Atomic writes with intent-marker crash recovery keep both in sync.
File locking prevents concurrent modification across supported platforms.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import platform as py_platform
import re
import socket
from contextlib import nullcontext
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from gpd.contracts import (
    ConventionLock,
    ProjectContractParseResult,
    ResearchContract,
    VerificationEvidence,
    _collect_project_contract_list_member_errors,
    _collect_project_local_grounding_integrity_errors,
    collect_contract_integrity_errors,
    collect_plan_contract_integrity_errors,
    parse_project_contract_data_salvage,
    parse_project_contract_data_strict,
)
from gpd.core.constants import (
    ENV_GPD_DEBUG,
    PHASES_DIR_NAME,
    PLANNING_DIR_NAME,
    PROJECT_FILENAME,
    STATE_ARCHIVE_FILENAME,
    STATE_JSON_BACKUP_FILENAME,
    STATE_JSON_FILENAME,
    STATE_LINES_BUDGET,
    STATE_LINES_TARGET,
    ProjectLayout,
)
from gpd.core.continuation import (
    ContinuationBoundedSegment,
    ContinuationState,
    normalize_continuation,
    normalize_continuation_bounded_segment_with_issues,
    normalize_continuation_reference,
    normalize_continuation_with_issues,
    resolve_continuation,
)
from gpd.core.contract_validation import (
    _collect_list_shape_drift_errors,
    _has_authoritative_scalar_schema_findings,
    _project_contract_schema_version_missing_error,
    is_repair_relevant_project_contract_schema_finding,
    salvage_project_contract,
    split_project_contract_schema_findings,
    validate_project_contract,
)
from gpd.core.conventions import KNOWN_CONVENTIONS, is_bogus_value
from gpd.core.errors import StateError
from gpd.core.extras import Approximation
from gpd.core.extras import Uncertainty as PropagatedUncertainty
from gpd.core.observability import gpd_span, instrument_gpd_function
from gpd.core.recent_projects import (
    RecentProjectEntry,
    RecentProjectIndex,
)
from gpd.core.recent_projects import (
    load_recent_projects_index as _recent_projects_load_index,
)
from gpd.core.recent_projects import (
    recent_projects_index_path as _recent_projects_index_path_impl,
)
from gpd.core.results import IntermediateResult
from gpd.core.utils import (
    _replace_with_retry,
    atomic_write,
    compare_phase_numbers,
    file_lock,
    matching_phase_artifact_count,
    phase_normalize,
    safe_parse_int,
    safe_read_file,
)

logger = logging.getLogger(__name__)

__all__ = [
    "AddBlockerResult",
    "AddDecisionResult",
    "AdvancePlanResult",
    "Decision",
    "MetricRow",
    "PerformanceMetrics",
    "Position",
    "ProjectReference",
    "RecordMetricResult",
    "RecordSessionResult",
    "ResearchState",
    "ResolveBlockerResult",
    "SessionInfo",
    "StateCompactResult",
    "StateGetResult",
    "StateLoadResult",
    "StatePatchResult",
    "StateSnapshotResult",
    "StateUpdateResult",
    "StateValidateResult",
    "UpdateProgressResult",
    "VALID_STATUSES",
    "VALID_TRANSITIONS",
    "default_state_dict",
    "ensure_state_schema",
    "generate_state_markdown",
    "is_valid_status",
    "load_state_json",
    "load_state_json_readonly",
    "parse_state_md",
    "parse_state_to_json",
    "save_state_markdown",
    "save_state_markdown_locked",
    "save_state_json",
    "save_state_json_locked",
    "state_add_blocker",
    "state_add_decision",
    "state_advance_plan",
    "state_compact",
    "state_extract_field",
    "state_get",
    "state_has_field",
    "state_load",
    "state_patch",
    "state_record_metric",
    "state_record_session",
    "state_replace_field",
    "state_set_project_contract",
    "state_set_continuation_bounded_segment",
    "state_carry_forward_continuation_last_result_id",
    "state_clear_continuation_bounded_segment",
    "state_resolve_blocker",
    "state_snapshot",
    "state_update",
    "state_update_progress",
    "state_validate",
    "sync_state_json",
    "validate_state_transition",
]

EM_DASH = "\u2014"


def _recent_projects_index_path() -> Path:
    """Return the machine-local recent-project index path."""
    return _recent_projects_index_path_impl()


def _load_recent_projects_index(data_root: Path | None = None):
    """Load the machine-local recent-project index for recovery tests and state hooks."""
    return _recent_projects_load_index(data_root)


def _sort_recent_project_rows(rows: list[RecentProjectEntry]) -> list[RecentProjectEntry]:
    return sorted(
        rows,
        key=lambda row: (
            row.resume_target_recorded_at or row.last_session_at or row.last_seen_at or "",
            row.project_root,
        ),
        reverse=True,
    )


def _project_recent_project_entry(
    cwd: Path,
    state_obj: dict[str, object],
    *,
    existing: RecentProjectEntry | None,
) -> RecentProjectEntry | None:
    try:
        projection = resolve_continuation(cwd, state=state_obj)
    except Exception:
        logger.debug(
            "Skipping recent-project projection for %s because continuation resolution failed", cwd, exc_info=True
        )
        return None

    session = state_obj.get("session") if isinstance(state_obj.get("session"), dict) else {}
    position = state_obj.get("position") if isinstance(state_obj.get("position"), dict) else {}
    continuation = projection.continuation
    handoff = continuation.handoff
    bounded_segment = continuation.bounded_segment
    machine = continuation.machine

    def _pick(*values: object) -> str | None:
        for value in values:
            text = _optional_state_text(value)
            if text is not None:
                return text
        return None

    def _phase_plan_stop_label(
        phase: str | None,
        plan: str | None,
        *,
        fallback: str | None,
    ) -> str | None:
        phase_text = _optional_state_text(phase)
        plan_text = _optional_state_text(plan)
        if phase_text is None and plan_text is None:
            return fallback
        if phase_text is not None and not phase_text.lower().startswith("phase"):
            phase_text = f"Phase {phase_text}"
        if plan_text is not None and not plan_text.lower().startswith("plan"):
            plan_text = f"Plan {plan_text}"
        label = " ".join(part for part in (phase_text, plan_text) if part is not None).strip()
        return label or fallback

    target_kind: str | None = None
    if bounded_segment is not None and bounded_segment.resume_file is not None:
        target_kind = "bounded_segment"
    elif handoff.resume_file is not None:
        target_kind = "handoff"

    handoff_recorded_at = _pick(
        handoff.recorded_at,
        machine.recorded_at,
        session.get("last_date") if isinstance(session, dict) else None,
    )
    bounded_recorded_at = _pick(
        bounded_segment.updated_at if bounded_segment is not None else None,
        handoff_recorded_at,
    )
    resume_target_recorded_at = (
        bounded_recorded_at
        if target_kind == "bounded_segment"
        else handoff_recorded_at
        if target_kind == "handoff"
        else None
    )
    session_recorded_at = _pick(
        machine.recorded_at,
        session.get("last_date") if isinstance(session, dict) else None,
    )

    last_session_at = _pick(
        resume_target_recorded_at,
        session_recorded_at,
        existing.last_session_at if existing is not None else None,
    )
    last_seen_at = last_session_at or (existing.last_seen_at if existing is not None else None)
    recovery_phase = _pick(
        bounded_segment.phase if bounded_segment is not None else None,
        position.get("current_phase") if isinstance(position, dict) else None,
        existing.recovery_phase if existing is not None else None,
    )
    recovery_plan = _pick(
        bounded_segment.plan if bounded_segment is not None else None,
        position.get("current_plan") if isinstance(position, dict) else None,
        existing.recovery_plan if existing is not None else None,
    )
    stopped_at = _phase_plan_stop_label(
        recovery_phase if target_kind == "bounded_segment" else None,
        recovery_plan if target_kind == "bounded_segment" else None,
        fallback=_pick(
            handoff.stopped_at,
            session.get("stopped_at") if isinstance(session, dict) else None,
            existing.stopped_at if existing is not None else None,
        ),
    )
    hostname = _pick(
        machine.hostname,
        session.get("hostname") if isinstance(session, dict) else None,
        existing.hostname if existing is not None else None,
    )
    platform = _pick(
        machine.platform,
        session.get("platform") if isinstance(session, dict) else None,
        existing.platform if existing is not None else None,
    )
    last_result_id = _pick(
        bounded_segment.last_result_id if bounded_segment is not None and target_kind == "bounded_segment" else None,
        handoff.last_result_id if target_kind == "handoff" else None,
        session.get("last_result_id") if isinstance(session, dict) else None,
        existing.last_result_id if existing is not None else None,
    )
    resume_file = None
    if bounded_segment is not None and bounded_segment.resume_file is not None:
        resume_file = bounded_segment.resume_file
    elif handoff.resume_file is not None:
        resume_file = handoff.resume_file

    source_kind = (
        "continuation.bounded_segment"
        if target_kind == "bounded_segment"
        else "continuation.handoff"
        if target_kind == "handoff"
        else None
    )
    source_session_id = (
        bounded_segment.source_session_id if bounded_segment is not None and target_kind == "bounded_segment" else None
    )
    source_segment_id = (
        bounded_segment.segment_id if bounded_segment is not None and target_kind == "bounded_segment" else None
    )
    source_transition_id = (
        bounded_segment.transition_id if bounded_segment is not None and target_kind == "bounded_segment" else None
    )
    source_recorded_at = resume_target_recorded_at
    source_event_id = None
    if existing is not None and existing.resume_file == resume_file and existing.resume_target_kind == target_kind:
        if target_kind != "bounded_segment" or (
            existing.source_segment_id == source_segment_id and existing.source_transition_id == source_transition_id
        ):
            source_event_id = existing.source_event_id

    return RecentProjectEntry(
        project_root=cwd.resolve(strict=False).as_posix(),
        last_session_at=last_session_at,
        last_seen_at=last_seen_at,
        stopped_at=stopped_at,
        resume_file=resume_file,
        last_result_id=last_result_id,
        resume_target_kind=target_kind,
        resume_target_recorded_at=resume_target_recorded_at,
        resume_file_available=None,
        resume_file_reason=None,
        hostname=hostname,
        platform=platform,
        source_kind=source_kind,
        source_session_id=source_session_id,
        source_segment_id=source_segment_id,
        source_transition_id=source_transition_id,
        source_event_id=source_event_id,
        source_recorded_at=source_recorded_at,
        recovery_phase=recovery_phase,
        recovery_plan=recovery_plan,
        resumable=bool(resume_file),
        available=True,
        availability_reason=None,
    )


def _refresh_recent_project_projection(cwd: Path, state_obj: dict[str, object]) -> None:
    """Project authoritative state into the machine-local recent-project cache."""

    try:
        index_path = _recent_projects_index_path()
        with file_lock(index_path):
            current = _load_recent_projects_index()
            resolved_root = cwd.resolve(strict=False).as_posix()
            existing = next((row for row in current.rows if row.project_root == resolved_root), None)
            projected = _project_recent_project_entry(cwd, state_obj, existing=existing)
            if projected is None:
                return

            rows = [projected if row.project_root == resolved_root else row for row in current.rows]
            if existing is None:
                rows.append(projected)

            index = RecentProjectIndex(rows=_sort_recent_project_rows(rows))
            atomic_write(index_path, index.model_dump_json(indent=2) + "\n")
    except Exception:
        logger.debug("Skipping recent-project projection for %s", cwd, exc_info=True)


# ─── Pydantic State Models ────────────────────────────────────────────────────


class ProjectReference(BaseModel):
    """Project metadata reference in state."""

    model_config = ConfigDict(frozen=True)

    project_md_updated: str | None = None
    core_research_question: str | None = None
    current_focus: str | None = None


class Position(BaseModel):
    """Current position in the research workflow."""

    model_config = ConfigDict(frozen=True)

    current_phase: str | None = None
    current_phase_name: str | None = None
    total_phases: int | None = None
    current_plan: str | None = None
    total_plans_in_phase: int | None = None
    status: str | None = None
    last_activity: str | None = None
    last_activity_desc: str | None = None
    progress_percent: int | None = 0
    paused_at: str | None = None


class Decision(BaseModel):
    """A recorded research decision."""

    model_config = ConfigDict(frozen=True)

    phase: str | None = None
    summary: str = ""
    rationale: str | None = None


class MetricRow(BaseModel):
    """A performance metric entry."""

    model_config = ConfigDict(frozen=True)

    label: str = ""
    duration: str = "-"
    tasks: str | None = None
    files: str | None = None


class PerformanceMetrics(BaseModel):
    """Container for performance metric rows."""

    model_config = ConfigDict(frozen=True)

    rows: list[MetricRow] = Field(default_factory=list)


class SessionInfo(BaseModel):
    """Session continuity tracking."""

    model_config = ConfigDict(frozen=True)

    last_date: str | None = None
    hostname: str | None = None
    platform: str | None = None
    stopped_at: str | None = None
    resume_file: str | None = None
    last_result_id: str | None = None


class ResearchState(BaseModel):
    """Full research state — the schema for state.json.

    This model defines every field that state.json may contain.
    Missing fields are populated with defaults via ensure_state_schema().
    """

    project_reference: ProjectReference = Field(default_factory=ProjectReference)
    project_contract: ResearchContract | None = None
    position: Position = Field(default_factory=Position)
    active_calculations: list[str | dict] = Field(default_factory=list)
    intermediate_results: list[IntermediateResult | str] = Field(default_factory=list)
    open_questions: list[str | dict] = Field(default_factory=list)
    resolved_questions: list[dict] = Field(default_factory=list)
    performance_metrics: PerformanceMetrics = Field(default_factory=PerformanceMetrics)
    decisions: list[Decision] = Field(default_factory=list)
    approximations: list[Approximation] = Field(default_factory=list)
    convention_lock: ConventionLock = Field(default_factory=ConventionLock)
    propagated_uncertainties: list[PropagatedUncertainty] = Field(default_factory=list)
    pending_todos: list[str | dict] = Field(default_factory=list)
    blockers: list[str | dict] = Field(default_factory=list)
    session: SessionInfo = Field(default_factory=SessionInfo)
    continuation: ContinuationState = Field(default_factory=ContinuationState)

    model_config = {"extra": "allow"}


# ─── Operation Result Models ─────────────────────────────────────────────────


class StateLoadResult(BaseModel):
    """Returned by :func:`state_load`."""

    model_config = ConfigDict(frozen=True)

    state: dict = Field(default_factory=dict)
    state_raw: str = ""
    state_exists: bool = False
    roadmap_exists: bool = False
    config_exists: bool = False
    integrity_mode: str = "standard"
    integrity_status: str = "healthy"
    integrity_issues: list[str] = Field(default_factory=list)
    state_source: str | None = None
    project_contract_load_info: dict | None = None
    project_contract_validation: dict | None = None
    project_contract_gate: dict | None = None


class StateGetResult(BaseModel):
    """Returned by :func:`state_get`."""

    model_config = ConfigDict(frozen=True)

    content: str | None = None
    value: str | None = None
    section_name: str | None = None
    error: str | None = None


class StateValidateResult(BaseModel):
    """Returned by :func:`state_validate`."""

    model_config = ConfigDict(frozen=True)

    valid: bool
    issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    integrity_mode: str = "standard"
    integrity_status: str = "healthy"
    state_source: str | None = None


class StateUpdateResult(BaseModel):
    """Returned by :func:`state_update`."""

    model_config = ConfigDict(frozen=True)

    updated: bool
    unchanged: bool = Field(default=False, exclude=True)
    reason: str | None = None
    warnings: list[str] = Field(default_factory=list)
    schema_reference: str | None = None

    def model_dump(self, *args, **kwargs):  # type: ignore[override]
        payload = super().model_dump(*args, **kwargs)
        if payload.get("schema_reference") is None:
            payload.pop("schema_reference", None)
        return payload


class StatePatchResult(BaseModel):
    """Returned by :func:`state_patch`."""

    model_config = ConfigDict(frozen=True)

    updated: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)
    failure_reasons: dict[str, str] = Field(default_factory=dict)


class AdvancePlanResult(BaseModel):
    """Returned by :func:`state_advance_plan`."""

    model_config = ConfigDict(frozen=True)

    advanced: bool
    error: str | None = None
    reason: str | None = None
    previous_plan: int | None = None
    current_plan: int | None = None
    total_plans_in_phase: int | None = None
    status: str | None = None


class RecordMetricResult(BaseModel):
    """Returned by :func:`state_record_metric`."""

    model_config = ConfigDict(frozen=True)

    recorded: bool
    error: str | None = None
    reason: str | None = None
    phase: str | None = None
    plan: str | None = None
    duration: str | None = None


class UpdateProgressResult(BaseModel):
    """Returned by :func:`state_update_progress`.

    Progress recomputation no longer synchronizes checkpoint shelf artifacts or
    surfaces them through progress APIs.
    """

    model_config = ConfigDict(frozen=True)

    updated: bool
    error: str | None = None
    reason: str | None = None
    percent: int = 0
    completed: int = 0
    total: int = 0
    bar: str = ""


class AddDecisionResult(BaseModel):
    """Returned by :func:`state_add_decision`."""

    model_config = ConfigDict(frozen=True)

    added: bool
    error: str | None = None
    reason: str | None = None
    decision: str | None = None


class AddBlockerResult(BaseModel):
    """Returned by :func:`state_add_blocker`."""

    model_config = ConfigDict(frozen=True)

    added: bool
    error: str | None = None
    reason: str | None = None
    blocker: str | None = None


class ResolveBlockerResult(BaseModel):
    """Returned by :func:`state_resolve_blocker`."""

    model_config = ConfigDict(frozen=True)

    resolved: bool
    error: str | None = None
    reason: str | None = None
    blocker: str | None = None


class RecordSessionResult(BaseModel):
    """Returned by :func:`state_record_session`."""

    model_config = ConfigDict(frozen=True)

    recorded: bool
    error: str | None = None
    reason: str | None = None
    updated: list[str] = Field(default_factory=list)


class StateSnapshotResult(BaseModel):
    """Returned by :func:`state_snapshot`."""

    model_config = ConfigDict(frozen=True)

    current_phase: str | None = None
    current_phase_name: str | None = None
    total_phases: int | None = None
    current_plan: str | None = None
    total_plans_in_phase: int | None = None
    status: str | None = None
    progress_percent: int | None = None
    last_activity: str | None = None
    last_activity_desc: str | None = None
    decisions: list[dict] | None = None
    blockers: list[str | dict] | None = None
    paused_at: str | None = None
    session: dict | None = None
    error: str | None = None


class StateCompactResult(BaseModel):
    """Returned by :func:`state_compact`."""

    model_config = ConfigDict(frozen=True)

    compacted: bool
    error: str | None = None
    reason: str | None = None
    lines: int = 0
    original_lines: int = 0
    new_lines: int = 0
    archived_lines: int = 0
    soft_mode: bool = False
    warn: bool = False


# ─── Default State Object ─────────────────────────────────────────────────────


def default_state_dict() -> dict:
    """Return a dict with every field generate_state_markdown needs, initialized to defaults."""
    return ResearchState().model_dump()


def _current_machine_identity() -> dict[str, str | None]:
    """Return the current machine identity used for resume advisories."""
    hostname = socket.gethostname().strip() or None
    platform_parts = [
        py_platform.system().strip(),
        py_platform.release().strip(),
        py_platform.machine().strip(),
    ]
    platform_value = " ".join(part for part in platform_parts if part) or None
    return {"hostname": hostname, "platform": platform_value}


def _optional_state_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _state_has_canonical_result_id(state_obj: dict[str, object], result_id: str) -> bool:
    """Return whether the state tracks a canonical intermediate result with this ID."""
    results = state_obj.get("intermediate_results")
    if not isinstance(results, list):
        return False
    for item in results:
        if isinstance(item, dict) and _optional_state_text(item.get("id")) == result_id:
            return True
        if isinstance(item, IntermediateResult) and _optional_state_text(item.id) == result_id:
            return True
    return False


def _blank_session_payload() -> dict[str, str | None]:
    return SessionInfo().model_dump()


def _project_contract_source_path(cwd: Path, source_path: Path) -> str:
    """Return a stable display path for project-contract diagnostics."""

    try:
        return source_path.relative_to(cwd).as_posix()
    except ValueError:
        return str(source_path)


def _project_contract_load_payload(
    *,
    status: str,
    source_path: str,
    provenance: str = "raw",
    raw_project_contract_classified: bool = False,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
    approval_validation: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build structured project-contract load diagnostics."""

    payload = {
        "status": status,
        "source_path": source_path,
        "provenance": provenance,
        "raw_project_contract_classified": raw_project_contract_classified,
        "errors": list(errors or []),
        "warnings": list(warnings or []),
    }
    if approval_validation is not None:
        payload["approval_validation"] = dict(approval_validation)
    return payload


def _project_contract_missing_required_schema_errors(raw_contract: object) -> list[str]:
    """Return hard schema blockers that must stay non-authoritative in state loads."""

    if not isinstance(raw_contract, dict):
        return []

    errors: list[str] = []
    schema_version_error = _project_contract_schema_version_missing_error(raw_contract)
    if schema_version_error is not None:
        errors.append(schema_version_error)

    if "context_intake" not in raw_contract:
        errors.append("context_intake is required")

    if "uncertainty_markers" not in raw_contract:
        errors.append("uncertainty_markers is required")
    else:
        uncertainty_markers = raw_contract.get("uncertainty_markers")
        if isinstance(uncertainty_markers, dict):
            for field_name in ("weakest_anchors", "disconfirming_observations"):
                if field_name not in uncertainty_markers:
                    errors.append(f"uncertainty_markers.{field_name} is required")

    return list(dict.fromkeys(errors))


def _project_contract_schema_reference_for_errors(errors: list[str]) -> str:
    """Return the canonical schema reference for project-contract write failures."""

    _ = errors
    return "templates/project-contract-schema.md"


def _load_raw_project_contract_payload(cwd: Path) -> tuple[Path, object] | None:
    """Return the raw project_contract payload from state storage."""

    layout = ProjectLayout(cwd)
    _state_obj, _state_issues, state_source = peek_state_json(
        cwd,
        recover_intent=False,
        surface_blocked_project_contract=True,
    )
    if state_source == "state.json":
        source_path = layout.state_json
    elif state_source == "state.json.bak":
        source_path = layout.state_json_backup
    else:
        return None

    try:
        raw_state = json.loads(source_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    if not isinstance(raw_state, dict):
        return None
    return source_path, raw_state.get("project_contract")


def _classify_project_contract_payload(
    *,
    cwd: Path,
    source_path: Path,
    raw_contract: object,
    provenance: str = "raw",
) -> tuple[ResearchContract | None, dict[str, object]]:
    """Classify a raw project-contract payload into visibility diagnostics."""

    source_label = _project_contract_source_path(cwd, source_path)
    if raw_contract is None:
        return None, _project_contract_load_payload(
            status="missing",
            source_path=source_label,
            provenance=provenance,
            raw_project_contract_classified=provenance == "raw",
        )
    if not isinstance(raw_contract, dict):
        logger.warning("Skipping project_contract from %s because it is not a JSON object", source_path)
        return None, _project_contract_load_payload(
            status="blocked_type",
            source_path=source_label,
            provenance=provenance,
            raw_project_contract_classified=provenance == "raw",
            errors=["project contract must be a JSON object"],
        )

    list_shape_drift_errors = _collect_list_shape_drift_errors(raw_contract)
    list_member_errors = _collect_project_contract_list_member_errors(raw_contract)
    missing_required_schema_errors = _project_contract_missing_required_schema_errors(raw_contract)
    if missing_required_schema_errors:
        logger.warning(
            "Skipping project_contract from %s because required schema fields are missing: %s",
            source_path,
            "; ".join(missing_required_schema_errors),
        )
        return None, _project_contract_load_payload(
            status="blocked_schema",
            source_path=source_label,
            provenance=provenance,
            raw_project_contract_classified=provenance == "raw",
            errors=missing_required_schema_errors,
            warnings=list(dict.fromkeys([*list_shape_drift_errors, *list_member_errors])),
        )
    normalized_contract, schema_findings = salvage_project_contract(raw_contract)
    schema_warnings, schema_errors = split_project_contract_schema_findings(
        schema_findings,
        allow_case_drift_recovery=True,
    )
    schema_warnings = list(dict.fromkeys([*schema_warnings, *list_shape_drift_errors, *list_member_errors]))
    blocking_schema_errors = list(schema_errors)
    if normalized_contract is None and not blocking_schema_errors:
        blocking_schema_errors = list(parse_project_contract_data_salvage(raw_contract).blocking_errors)
    if blocking_schema_errors or normalized_contract is None:
        logger.warning(
            "Skipping project_contract from %s because blocking schema normalization would be required: %s",
            source_path,
            "; ".join(blocking_schema_errors) if blocking_schema_errors else "validation failed",
        )
        return None, _project_contract_load_payload(
            status="blocked_schema",
            source_path=source_label,
            provenance=provenance,
            raw_project_contract_classified=provenance == "raw",
            errors=blocking_schema_errors or ["blocking schema normalization would be required"],
            warnings=schema_warnings,
        )

    integrity_errors = list(collect_contract_integrity_errors(normalized_contract))
    local_grounding_errors = _collect_project_local_grounding_integrity_errors(
        normalized_contract,
        project_root=cwd,
    )
    plan_integrity_errors = set(collect_plan_contract_integrity_errors(normalized_contract, project_root=cwd))
    if local_grounding_errors and (
        "missing references or explicit grounding context" in plan_integrity_errors
        or "references must include at least one must_surface=true anchor" in plan_integrity_errors
    ):
        integrity_errors.extend(local_grounding_errors)
    if integrity_errors:
        logger.warning(
            "Loaded blocked project_contract from %s because semantic integrity checks failed: %s",
            source_path,
            "; ".join(integrity_errors),
        )
        return normalized_contract, _project_contract_load_payload(
            status="blocked_integrity",
            source_path=source_label,
            provenance=provenance,
            raw_project_contract_classified=provenance == "raw",
            errors=integrity_errors,
            warnings=schema_warnings,
        )

    if schema_warnings:
        logger.warning(
            "Loaded project_contract from %s after recoverable schema normalization: %s",
            source_path,
            "; ".join(schema_warnings),
        )

    load_info = _project_contract_load_payload(
        status="loaded",
        source_path=source_label,
        provenance=provenance,
        raw_project_contract_classified=provenance == "raw",
        warnings=schema_warnings,
    )
    if schema_warnings:
        load_info["status"] = "loaded_with_schema_normalization"
    approval_validation = validate_project_contract(normalized_contract, mode="approved", project_root=cwd)
    if not approval_validation.valid:
        logger.warning(
            "Loaded project_contract from %s with approval blockers: %s",
            source_path,
            "; ".join(approval_validation.errors) if approval_validation.errors else "validation failed",
        )
        load_info["status"] = "loaded_with_approval_blockers"
        load_info["approval_validation"] = approval_validation.model_dump(mode="json")
    return normalized_contract, load_info


def _load_project_contract_for_runtime_context(cwd: Path) -> tuple[ResearchContract | None, dict[str, object]]:
    """Load the visible project contract and raw-source diagnostics for runtime context."""

    layout = ProjectLayout(cwd)
    raw_payload = _load_raw_project_contract_payload(cwd)
    if raw_payload is not None:
        source_path, raw_contract = raw_payload
        return _classify_project_contract_payload(
            cwd=cwd,
            source_path=source_path,
            raw_contract=raw_contract,
            provenance="raw",
        )

    state, state_issues, state_source = peek_state_json(
        cwd,
        recover_intent=False,
        surface_blocked_project_contract=True,
    )
    default_source = _project_contract_source_path(cwd, layout.state_json)
    if not isinstance(state, dict):
        return None, _project_contract_load_payload(status="missing", source_path=default_source)

    source_path = (
        layout.state_json
        if state_source in (None, "state.json")
        else layout.state_json_backup
        if state_source == "state.json.bak"
        else layout.state_md
    )
    contract, load_info = _classify_project_contract_payload(
        cwd=cwd,
        source_path=source_path,
        raw_contract=state.get("project_contract"),
        provenance="fallback",
    )
    fallback_warning = next(
        (
            issue
            for issue in state_issues
            if isinstance(issue, str)
            and (
                "primary state.json was unavailable or unreadable" in issue or "primary state.json was missing" in issue
            )
        ),
        None,
    )
    if fallback_warning:
        load_info = {
            **load_info,
            "warnings": [*list(load_info.get("warnings") or []), fallback_warning],
        }
    return contract, load_info


def _project_contract_gate_payload(
    contract: ResearchContract | None,
    *,
    load_info: dict[str, object] | None,
    validation: dict[str, object] | None,
) -> dict[str, object]:
    """Return a single visible-vs-authoritative contract gate payload."""

    load_status = str((load_info or {}).get("status") or ("loaded" if contract is not None else "missing"))
    approval_valid = validation.get("valid") if isinstance(validation, dict) else None
    warnings = list((load_info or {}).get("warnings") or [])
    repair_relevant_schema_warning = any(
        is_repair_relevant_project_contract_schema_finding(warning) for warning in warnings
    )
    load_blocked = load_status.startswith("blocked")
    approval_blocked = approval_valid is False
    raw_project_contract_classified = bool((load_info or {}).get("raw_project_contract_classified"))
    visible = contract is not None
    authoritative = (
        visible
        and raw_project_contract_classified
        and not load_blocked
        and approval_valid is True
        and not repair_relevant_schema_warning
    )
    blocked = load_blocked or approval_blocked
    return {
        "status": load_status,
        "visible": visible,
        "blocked": blocked,
        "load_blocked": load_blocked,
        "approval_blocked": approval_blocked,
        "authoritative": authoritative,
        "repair_required": blocked or repair_relevant_schema_warning or not raw_project_contract_classified,
        "raw_project_contract_classified": raw_project_contract_classified,
        "provenance": (load_info or {}).get("provenance"),
        "source_path": (load_info or {}).get("source_path"),
    }


def _finalize_project_contract_gate(
    cwd: Path,
    contract: ResearchContract | None,
    load_info: dict[str, object],
) -> tuple[dict[str, object], dict[str, object] | None, dict[str, object]]:
    """Normalize final load info, approval validation, and gate payload."""

    finalized_load_info = {
        "status": load_info.get("status"),
        "source_path": load_info.get("source_path"),
        "provenance": load_info.get("provenance"),
        "raw_project_contract_classified": bool(load_info.get("raw_project_contract_classified")),
        "errors": list(load_info.get("errors") or []),
        "warnings": list(load_info.get("warnings") or []),
    }
    validation_payload: dict[str, object] | None = None
    if contract is not None:
        draft_validation = validate_project_contract(contract, mode="draft", project_root=cwd)
        if not draft_validation.valid:
            finalized_load_info["status"] = "blocked_integrity"
            finalized_load_info["errors"] = list(
                dict.fromkeys([*list(finalized_load_info.get("errors") or []), *draft_validation.errors])
            )
        raw_approval_validation = load_info.get("approval_validation")
        if isinstance(raw_approval_validation, dict):
            validation_payload = dict(raw_approval_validation)
        else:
            validation_payload = validate_project_contract(contract, mode="approved", project_root=cwd).model_dump(
                mode="json"
            )
        if finalized_load_info["status"] != "blocked_integrity":
            repair_relevant_schema_warning = any(
                is_repair_relevant_project_contract_schema_finding(warning)
                for warning in list(finalized_load_info.get("warnings") or [])
            )
            if validation_payload.get("valid") is True:
                finalized_load_info["status"] = (
                    "loaded_with_schema_normalization" if repair_relevant_schema_warning else "loaded"
                )
            else:
                finalized_load_info["status"] = "loaded_with_approval_blockers"

    gate_payload = _project_contract_gate_payload(
        contract,
        load_info=finalized_load_info,
        validation=validation_payload,
    )
    return finalized_load_info, validation_payload, gate_payload


def _normalize_continuation_payload(
    continuation: object,
    *,
    project_root: Path | None = None,
) -> dict[str, object]:
    return _normalize_continuation_payload_with_issues(continuation, project_root=project_root)[0]


def _normalize_continuation_payload_with_issues(
    continuation: object,
    *,
    project_root: Path | None = None,
) -> tuple[dict[str, object], list[str]]:
    normalized, issues = normalize_continuation_with_issues(project_root, continuation)
    return normalized.model_dump(mode="python"), issues


def _load_state_snapshot_for_mutation(cwd: Path, *, recover_intent: bool = True) -> dict:
    """Load one mutable state snapshot through the full non-persisting recovery ladder."""

    recovered_state, _integrity_issues, _state_source = _load_state_json_with_integrity_issues(
        cwd,
        persist_recovery=False,
        recover_intent=recover_intent,
        import_session_continuation_from_markdown=True,
        acquire_lock=False,
    )
    if isinstance(recovered_state, dict):
        return recovered_state

    return default_state_dict()


def _load_or_rebuild_state_markdown_locked(cwd: Path) -> str | None:
    """Return STATE.md content, rebuilding the markdown mirror from structured state when possible."""

    md_path = _state_md_path(cwd)
    try:
        return md_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        pass
    except (OSError, UnicodeDecodeError):
        logger.warning("STATE.md is unreadable during mutation; attempting to rebuild from structured state")

    recovered_state, _integrity_issues, state_source = _load_state_json_with_integrity_issues(
        cwd,
        persist_recovery=False,
        recover_intent=False,
        import_session_continuation_from_markdown=True,
        acquire_lock=False,
    )
    if not isinstance(recovered_state, dict) or state_source is None:
        return None

    save_state_json_locked(cwd, recovered_state)
    try:
        return md_path.read_text(encoding="utf-8")
    except (FileNotFoundError, OSError, UnicodeDecodeError):
        return None


def _session_payload_has_values(payload: object) -> bool:
    return isinstance(payload, dict) and any(payload.get(field) is not None for field in _blank_session_payload())


def _continuation_payload_has_values(payload: object) -> bool:
    try:
        return not ContinuationState.model_validate(_normalize_continuation_payload(payload)).is_empty
    except PydanticValidationError:
        return False


def _session_payload_has_legacy_recovery_values(payload: object) -> bool:
    """Return whether a legacy session mirror carries a real recovery target."""

    if not isinstance(payload, dict):
        return False
    return any(payload.get(field) is not None for field in ("stopped_at", "resume_file", "last_result_id"))


def _session_from_continuation_payload(continuation: object) -> dict[str, str | None]:
    session = _blank_session_payload()
    normalized = _normalize_continuation_payload(continuation)

    handoff = normalized.get("handoff")
    machine = normalized.get("machine")
    handoff_recorded_at = _optional_state_text(handoff.get("recorded_at")) if isinstance(handoff, dict) else None
    machine_recorded_at = None
    if isinstance(machine, dict):
        machine_recorded_at = _optional_state_text(machine.get("recorded_at"))
        if machine_recorded_at is None:
            machine_recorded_at = _optional_state_text(machine.get("last_seen_at"))

    session["last_date"] = handoff_recorded_at or machine_recorded_at
    if isinstance(handoff, dict):
        session["stopped_at"] = _optional_state_text(handoff.get("stopped_at"))
        session["resume_file"] = _optional_state_text(handoff.get("resume_file"))
        session["last_result_id"] = _optional_state_text(handoff.get("last_result_id"))
    if isinstance(machine, dict):
        session["hostname"] = _optional_state_text(machine.get("hostname"))
        session["platform"] = _optional_state_text(machine.get("platform"))
    return session


def _continuation_from_session_payload(
    session: object,
) -> dict[str, object]:
    """Migrate a legacy session mirror into canonical continuation state.

    Only resume-relevant legacy handoff data is migrated. Identity-only session
    mirrors should stay advisory metadata rather than minting canonical
    continuation authority on their own.
    """

    continuation = _normalize_continuation_payload(None)
    if not isinstance(session, dict):
        return continuation
    if not _session_payload_has_legacy_recovery_values(session):
        return continuation

    recorded_at = _optional_state_text(session.get("last_date"))
    handoff = continuation.get("handoff")
    machine = continuation.get("machine")
    if isinstance(handoff, dict):
        updates = {
            "recorded_at": recorded_at,
            "stopped_at": _optional_state_text(session.get("stopped_at")),
            "resume_file": _optional_state_text(session.get("resume_file")),
            "last_result_id": _optional_state_text(session.get("last_result_id")),
        }
        for key, value in updates.items():
            if value is None:
                continue
            handoff[key] = value
    if isinstance(machine, dict):
        updates = {
            "recorded_at": recorded_at,
            "hostname": _optional_state_text(session.get("hostname")),
            "platform": _optional_state_text(session.get("platform")),
        }
        for key, value in updates.items():
            if value is None:
                continue
            machine[key] = value
    return continuation


def _mirror_continuation_state(raw: dict[str, object]) -> dict[str, object]:
    """Project canonical continuation into the legacy ``session`` mirror.

    Canonical ``continuation`` stays authoritative. The ``session`` payload is
    a pure mirror and is blank when no canonical continuation exists.
    """

    mirrored = copy.deepcopy(raw)
    continuation_payload = _normalize_continuation_payload(mirrored.get("continuation"))
    mirrored["session"] = _session_from_continuation_payload(continuation_payload)
    mirrored["continuation"] = continuation_payload
    return mirrored


# ─── Status Constants ──────────────────────────────────────────────────────────

VALID_STATUSES: list[str] = [
    "Not started",
    "Planning",
    "Researching",
    "Ready to execute",
    "Executing",
    "Paused",
    "Phase complete \u2014 ready for verification",
    "Verifying",
    "Complete",
    "Blocked",
    "Ready to plan",
    "Milestone complete",
]

# Valid state transitions: maps lowercase status -> list of valid next statuses.
# None means any transition is valid (recovery states like Paused/Blocked).
VALID_TRANSITIONS: dict[str, list[str] | None] = {
    "not started": ["planning", "researching", "ready to plan", "ready to execute", "executing"],
    "ready to plan": ["planning", "researching", "paused", "blocked", "not started", "milestone complete"],
    "planning": ["ready to execute", "researching", "paused", "blocked", "ready to plan", "not started"],
    "researching": ["planning", "ready to execute", "paused", "blocked", "ready to plan", "not started"],
    "ready to execute": ["executing", "planning", "researching", "paused", "blocked", "not started"],
    "executing": [
        "phase complete \u2014 ready for verification",
        "planning",
        "researching",
        "ready to execute",
        "ready to plan",
        "milestone complete",
        "paused",
        "blocked",
    ],
    "phase complete \u2014 ready for verification": [
        "verifying",
        "not started",
        "planning",
        "executing",
        "paused",
        "ready to plan",
        "milestone complete",
    ],
    "verifying": ["complete", "phase complete \u2014 ready for verification", "planning", "blocked", "paused"],
    "complete": ["not started", "planning", "milestone complete"],
    "milestone complete": ["not started", "planning"],
    "paused": None,
    "blocked": None,
}


def is_valid_status(value: str) -> bool:
    """Check if a status value is recognized (case-insensitive exact match)."""
    if not value:
        return False
    lower = value.lower()
    return any(lower.strip() == s.lower() for s in VALID_STATUSES)


def validate_state_transition(current_status: str, new_status: str) -> str | None:
    """Validate a state transition. Returns None if valid, or an error message."""
    current_lower = current_status.strip().lower()
    new_lower = new_status.strip().lower()

    if current_lower == new_lower:
        return None

    matched_key = None
    for key in sorted(VALID_TRANSITIONS, key=len, reverse=True):
        if current_lower == key:
            matched_key = key
            break

    # Unknown current status — allow transition
    if matched_key is None:
        return None

    allowed = VALID_TRANSITIONS[matched_key]

    # None means any transition valid (recovery states)
    if allowed is None:
        return None

    if any(new_lower == target for target in allowed):
        return None

    return f'Invalid transition: "{current_status}" \u2192 "{new_status}". Valid targets: {", ".join(allowed)}'


# ─── STATE.md Field Helpers ────────────────────────────────────────────────────


def state_extract_field(content: str, field_name: str) -> str | None:
    """Extract a **Field:** value from STATE.md content."""
    escaped = re.escape(field_name)
    pattern = re.compile(rf"\*\*{escaped}:\*\*[ \t]*(.+)", re.IGNORECASE)
    match = pattern.search(content)
    if not match:
        return None
    value = match.group(1).strip()
    if value == "\u2014" or value.lower() in {"not set", "[not set]"}:
        return None
    return value


def state_replace_field(content: str, field_name: str, new_value: str) -> str:
    """Replace a **Field:** value in STATE.md content.

    Returns the updated content if the field was found, or original content unchanged.
    """
    escaped = re.escape(field_name)
    pattern = re.compile(rf"(\*\*{escaped}:\*\*[ \t]*)(.*)", re.IGNORECASE)
    if not pattern.search(content):
        if os.environ.get(ENV_GPD_DEBUG):
            logger.debug("State field '%s' not found in STATE.md — update skipped", field_name)
        return content

    # Sanitize: collapse newlines, strip control chars
    sanitized = re.sub(r"[\r\n]+", " ", str(new_value))
    sanitized = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", sanitized).strip()

    def _replacer(m: re.Match) -> str:
        return m.group(1) + sanitized

    return pattern.sub(_replacer, content, count=1)


def state_has_field(content: str, field_name: str) -> bool:
    """Check if a **Field:** exists in STATE.md content."""
    escaped = re.escape(field_name)
    return bool(re.search(rf"\*\*{escaped}:\*\*", content, re.IGNORECASE))


# ─── STATE.md Parser ──────────────────────────────────────────────────────────


def _unescape_pipe(v: str) -> str:
    return v.replace("\\|", "|")


def _extract_bullets(content: str, section_name: str) -> list[str]:
    """Extract bullet list items from a ## Section."""
    escaped = re.escape(section_name)
    pattern = re.compile(rf"##\s*{escaped}\s*\n([\s\S]*?)(?=\n##|$)", re.IGNORECASE)
    match = pattern.search(content)
    if not match:
        return []
    bullets = re.findall(r"^\s*-\s+(.+)$", match.group(1), re.MULTILINE)
    return [b.strip() for b in bullets if b.strip() and not re.match(r"^none", b.strip(), re.IGNORECASE)]


def _extract_subsection(content: str, heading: str) -> str | None:
    """Extract a ### subsection body from STATE.md."""
    escaped = re.escape(heading)
    pattern = re.compile(rf"###?\s*{escaped}\s*\n([\s\S]*?)(?=\n###?|\n##[^#]|$)", re.IGNORECASE)
    match = pattern.search(content)
    return match.group(1) if match else None


def _extract_bold_block(content: str, label: str) -> str | None:
    """Extract a bold-label block like ``**Convention Lock:**``."""
    escaped = re.escape(label)
    pattern = re.compile(rf"\*\*{escaped}:\*\*\s*\n([\s\S]*?)(?=\n###?|\n##[^#]|$)", re.IGNORECASE)
    match = pattern.search(content)
    return match.group(1) if match else None


def _has_subsection(content: str, heading: str) -> bool:
    """Return whether STATE.md includes a matching subsection heading."""
    return _extract_subsection(content, heading) is not None


def _has_bold_block(content: str, label: str) -> bool:
    """Return whether STATE.md includes a matching bold-label block."""
    return _extract_bold_block(content, label) is not None


def _has_state_section(content: str, heading: str) -> bool:
    """Return whether STATE.md contains the exact top-level heading."""
    escaped = re.escape(heading)
    return re.search(rf"^##\s*{escaped}\s*$", content, re.IGNORECASE | re.MULTILINE) is not None


def _state_markdown_structure_issues(content: str) -> list[str]:
    """Return missing canonical headings/fields for STATE.md."""
    issues: list[str] = []

    required_sections = (
        "Project Reference",
        "Current Position",
        "Active Calculations",
        "Intermediate Results",
        "Open Questions",
        "Performance Metrics",
        "Accumulated Context",
        "Session Continuity",
    )
    required_subsections = (
        "Decisions",
        "Active Approximations",
        "Propagated Uncertainties",
        "Pending Todos",
        "Blockers/Concerns",
    )
    required_fields = (
        "Core research question",
        "Current focus",
        "Current Phase",
        "Status",
        "Last session",
        "Stopped at",
        "Resume file",
    )

    if not content.lstrip().startswith("# Research State"):
        issues.append('STATE.md missing "# Research State" heading')

    for section in required_sections:
        if not _has_state_section(content, section):
            issues.append(f'STATE.md missing "## {section}" section')

    for subsection in required_subsections:
        if not _has_subsection(content, subsection):
            issues.append(f'STATE.md missing "### {subsection}" subsection')

    if not _has_bold_block(content, "Convention Lock"):
        issues.append('STATE.md missing "**Convention Lock:**" block')

    for field in required_fields:
        if not state_has_field(content, field):
            issues.append(f'STATE.md missing "**{field}:**" field')

    return issues


def _parse_table_rows(section: str | None) -> list[list[str]]:
    """Parse markdown table rows, skipping headers and placeholders."""
    if not section:
        return []

    rows = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    parsed_rows: list[list[str]] = []
    for row in rows[2:]:
        cells = [_unescape_pipe(cell.strip()) for cell in re.split(r"(?<!\\)\|", row) if cell.strip()]
        if not cells:
            continue
        if cells[0] == "-" or re.match(r"^none", cells[0], re.IGNORECASE):
            continue
        parsed_rows.append(cells)
    return parsed_rows


def _slugify_custom_convention(label: str) -> str:
    """Convert a display label into a stable custom convention key."""
    slug = re.sub(r"[^a-z0-9]+", "_", label.strip().lower()).strip("_")
    return slug or "custom_convention"


def parse_state_md(content: str) -> dict:
    """Parse STATE.md into a structured dict.

    This is the canonical parser — used by parse_state_to_json, migrate, and snapshot.
    """
    # Position fields
    current_phase_raw = state_extract_field(content, "Current Phase")
    total_phases_raw = state_extract_field(content, "Total Phases")
    total_plans_raw = state_extract_field(content, "Total Plans in Phase")
    progress_raw = state_extract_field(content, "Progress")

    position = {
        "current_phase": current_phase_raw,
        "current_phase_name": state_extract_field(content, "Current Phase Name"),
        "total_phases": safe_parse_int(total_phases_raw, None) if total_phases_raw else None,
        "current_plan": state_extract_field(content, "Current Plan"),
        "total_plans_in_phase": safe_parse_int(total_plans_raw, None) if total_plans_raw else None,
        "status": state_extract_field(content, "Status"),
        "last_activity": state_extract_field(content, "Last Activity"),
        "last_activity_desc": state_extract_field(content, "Last Activity Description"),
        "progress_percent": None,
        "paused_at": state_extract_field(content, "Paused At"),
    }
    if progress_raw:
        m = re.search(r"(\d+)%", progress_raw)
        if m:
            position["progress_percent"] = int(m.group(1))

    # Project fields
    project = {
        "core_research_question": state_extract_field(content, "Core research question"),
        "current_focus": state_extract_field(content, "Current focus"),
        "project_md_updated": None,
    }
    see_match = re.search(r"See:.*PROJECT\.md\s*\(updated\s+([^)]+)\)", content, re.IGNORECASE)
    if see_match:
        project["project_md_updated"] = see_match.group(1).strip()

    # Decisions — canonical bullet format
    decisions: list[dict] = []
    dec_bullet_match = re.search(
        r"###?\s*Decisions\s*\n([\s\S]*?)(?=\n###?|\n##[^#]|$)",
        content,
        re.IGNORECASE,
    )
    if dec_bullet_match:
        items = re.findall(r"^\s*-\s+(.+)$", dec_bullet_match.group(1), re.MULTILINE)
        for item in items:
            text = item.strip()
            if not text or re.match(r"^none", text, re.IGNORECASE):
                continue
            phase_match = re.match(r"^\[Phase\s+([^\]]+)\]:\s*(.*)", text, re.IGNORECASE)
            if phase_match:
                phase_val = phase_match.group(1)
                if phase_val == "\u2014":
                    phase_val = None
                parts = phase_match.group(2).split(" \u2014 ", 1)
                decisions.append(
                    {
                        "phase": phase_val,
                        "summary": parts[0].strip(),
                        "rationale": parts[1].strip() if len(parts) > 1 else None,
                    }
                )
            else:
                decisions.append({"phase": None, "summary": text, "rationale": None})

    # Blockers
    blockers: list[str] = []
    blockers_match = re.search(
        r"###?\s*Blockers/Concerns\s*\n([\s\S]*?)(?=\n###?|\n##[^#]|$)",
        content,
        re.IGNORECASE,
    )
    if blockers_match:
        items = re.findall(r"^\s*-\s+(.+)$", blockers_match.group(1), re.MULTILINE)
        for item in items:
            text = item.strip()
            if text and not re.match(r"^none", text, re.IGNORECASE):
                blockers.append(text)

    # Session
    session = {
        "last_date": None,
        "hostname": None,
        "platform": None,
        "stopped_at": None,
        "resume_file": None,
        "last_result_id": None,
    }
    session_match = re.search(
        r"##\s*Session Continuity\s*\n([\s\S]*?)(?=\n##|$)",
        content,
        re.IGNORECASE,
    )
    if session_match:
        sec = session_match.group(1)
        ld = re.search(r"\*\*Last session:\*\*\s*(.+)", sec)
        hn = re.search(r"\*\*Hostname:\*\*\s*(.+)", sec)
        pf = re.search(r"\*\*Platform:\*\*\s*(.+)", sec)
        sa = re.search(r"\*\*Stopped at:\*\*\s*(.+)", sec)
        rf = re.search(r"\*\*Resume file:\*\*\s*(.+)", sec)
        lr = re.search(r"\*\*Last result ID:\*\*\s*(.+)", sec)
        if ld:
            session["last_date"] = _strip_placeholder(ld.group(1))
        if hn:
            session["hostname"] = _strip_placeholder(hn.group(1))
        if pf:
            session["platform"] = _strip_placeholder(pf.group(1))
        if sa:
            session["stopped_at"] = _strip_placeholder(sa.group(1))
        if rf:
            session["resume_file"] = _strip_placeholder(rf.group(1))
        if lr:
            session["last_result_id"] = _strip_placeholder(lr.group(1))

    # Performance metrics table
    metrics: list[dict] = []
    metrics_match = re.search(
        r"##\s*Performance Metrics[\s\S]*?\n\|[^\n]+\n\|[-|\s]+\n([\s\S]*?)(?=\n##|\n$|$)",
        content,
        re.IGNORECASE,
    )
    if metrics_match:
        rows = [r for r in metrics_match.group(1).strip().split("\n") if "|" in r]
        for row in rows:
            cells = [_unescape_pipe(c.strip()) for c in re.split(r"(?<!\\)\|", row) if c.strip()]
            if len(cells) >= 2 and cells[0] != "-" and not re.match(r"none yet", cells[0], re.IGNORECASE):
                metrics.append(
                    {
                        "label": cells[0],
                        "duration": cells[1] if len(cells) > 1 else "-",
                        "tasks": re.sub(r"\s*tasks?$", "", cells[2]) if len(cells) > 2 else None,
                        "files": re.sub(r"\s*files?$", "", cells[3]) if len(cells) > 3 else None,
                    }
                )

    # Bullet-list sections
    active_calculations = _extract_bullets(content, "Active Calculations")
    intermediate_results = _extract_bullets(content, "Intermediate Results")
    open_questions = _extract_bullets(content, "Open Questions")
    pending_todos = [
        bullet.strip()
        for bullet in re.findall(r"^\s*-\s+(.+)$", _extract_subsection(content, "Pending Todos") or "", re.MULTILINE)
        if bullet.strip() and not re.match(r"^none", bullet.strip(), re.IGNORECASE)
    ]

    approximations: list[dict[str, str]] = []
    for cells in _parse_table_rows(_extract_subsection(content, "Active Approximations")):
        if len(cells) < 5:
            continue
        approximations.append(
            {
                "name": cells[0],
                "validity_range": cells[1],
                "controlling_param": cells[2],
                "current_value": cells[3],
                "status": cells[4],
            }
        )

    propagated_uncertainties: list[dict[str, str]] = []
    for cells in _parse_table_rows(_extract_subsection(content, "Propagated Uncertainties")):
        if len(cells) < 5:
            continue
        propagated_uncertainties.append(
            {
                "quantity": cells[0],
                "value": cells[1],
                "uncertainty": cells[2],
                "phase": cells[3],
                "method": cells[4],
            }
        )

    convention_lock: dict[str, object] = {}
    custom_conventions: dict[str, str] = {}
    label_to_key = {label.lower(): key for key, label in _CONVENTION_LABELS.items()}
    for entry in re.findall(r"^\s*-\s+(.+)$", _extract_bold_block(content, "Convention Lock") or "", re.MULTILINE):
        text = entry.strip()
        if not text or re.match(r"^(?:none|no conventions locked yet)", text, re.IGNORECASE):
            continue
        label, separator, value = text.partition(":")
        if not separator:
            continue
        normalized_label = label.strip()
        normalized_value = value.strip()
        key = label_to_key.get(normalized_label.lower())
        if key is not None:
            convention_lock[key] = normalized_value
        else:
            custom_conventions[_slugify_custom_convention(normalized_label)] = normalized_value
    if custom_conventions:
        convention_lock["custom_conventions"] = custom_conventions

    return {
        "project": project,
        "position": position,
        "decisions": decisions,
        "blockers": blockers,
        "session": session,
        "metrics": metrics,
        "active_calculations": active_calculations,
        "intermediate_results": intermediate_results,
        "open_questions": open_questions,
        "approximations": approximations,
        "convention_lock": convention_lock,
        "propagated_uncertainties": propagated_uncertainties,
        "pending_todos": pending_todos,
    }


def _strip_placeholder(value: str | None) -> str | None:
    """Return None if *value* is a markdown placeholder (EM_DASH, 'not set', or '[not set]')."""
    if value is None:
        return None
    stripped = value.strip()
    if stripped == "\u2014" or stripped.lower() in {"not set", "[not set]"}:
        return None
    return stripped


def parse_state_to_json(content: str, *, import_legacy_session: bool = False) -> dict:
    """Parse STATE.md content into JSON-sidecar format."""
    parsed = parse_state_md(content)

    last_date = _strip_placeholder(parsed["session"]["last_date"])
    hostname = _strip_placeholder(parsed["session"]["hostname"])
    platform_value = _strip_placeholder(parsed["session"]["platform"])
    stopped_at = _strip_placeholder(parsed["session"]["stopped_at"])
    resume_file = _strip_placeholder(parsed["session"]["resume_file"])
    last_result_id = _strip_placeholder(parsed["session"]["last_result_id"])
    session: dict[str, str | None] = {
        "last_date": last_date,
        "hostname": hostname,
        "platform": platform_value,
        "stopped_at": stopped_at,
        "resume_file": resume_file,
        "last_result_id": last_result_id,
    }
    continuation = (
        _continuation_from_session_payload(session) if import_legacy_session else _normalize_continuation_payload(None)
    )

    return {
        "_version": 1,
        "_synced_at": datetime.now(tz=UTC).isoformat(),
        "project_reference": {
            "core_research_question": _strip_placeholder(parsed["project"]["core_research_question"]),
            "current_focus": _strip_placeholder(parsed["project"]["current_focus"]),
            "project_md_updated": parsed["project"]["project_md_updated"],
        },
        "position": {
            "current_phase": _strip_placeholder(parsed["position"]["current_phase"]),
            "current_phase_name": _strip_placeholder(parsed["position"]["current_phase_name"]),
            "total_phases": parsed["position"]["total_phases"],
            "current_plan": _strip_placeholder(parsed["position"]["current_plan"]),
            "total_plans_in_phase": parsed["position"]["total_plans_in_phase"],
            "status": _strip_placeholder(parsed["position"]["status"]),
            "last_activity": _strip_placeholder(parsed["position"]["last_activity"]),
            "last_activity_desc": _strip_placeholder(parsed["position"]["last_activity_desc"]),
            "progress_percent": parsed["position"]["progress_percent"],
            "paused_at": _strip_placeholder(parsed["position"]["paused_at"]),
        },
        "session": session,
        "continuation": continuation,
        "decisions": parsed["decisions"],
        "blockers": parsed["blockers"],
        "performance_metrics": {"rows": parsed["metrics"]},
        "active_calculations": parsed["active_calculations"],
        "intermediate_results": parsed["intermediate_results"],
        "open_questions": parsed["open_questions"],
        "approximations": parsed["approximations"],
        "convention_lock": parsed["convention_lock"],
        "propagated_uncertainties": parsed["propagated_uncertainties"],
        "pending_todos": parsed["pending_todos"],
    }


# ─── Schema Enforcement ───────────────────────────────────────────────────────


def _coerce_position_identifiers(
    normalized: dict[str, object],
    integrity_issues: list[str],
) -> None:
    """Coerce legacy integer position identifiers without dropping the section."""

    position = normalized.get("position")
    if not isinstance(position, dict):
        return

    current_phase = position.get("current_phase")
    if isinstance(current_phase, int) and not isinstance(current_phase, bool):
        position["current_phase"] = str(current_phase)
        integrity_issues.append('schema normalization: coerced "position.current_phase" integer to string')

    current_plan = position.get("current_plan")
    if isinstance(current_plan, int) and not isinstance(current_plan, bool):
        position["current_plan"] = str(current_plan)
        integrity_issues.append('schema normalization: coerced "position.current_plan" integer to string')


def _normalize_state_schema(
    raw: dict | None,
    *,
    allow_project_contract_salvage: bool = True,
    project_root: Path | None = None,
) -> tuple[dict, list[str]]:
    """Normalize a raw state dict and capture integrity-affecting coercions."""
    if raw is None:
        return default_state_dict(), []
    if not raw:  # {} case — emit sentinel to trigger backup recovery
        return default_state_dict(), [
            "schema normalization: irrecoverable validation failure; reset to defaults"
        ]
    if not isinstance(raw, dict):
        return default_state_dict(), [f"state root must be an object, got {type(raw).__name__}"]

    normalized = copy.deepcopy(raw)
    integrity_issues: list[str] = []

    defaults = default_state_dict()
    for key, default_val in defaults.items():
        if key in normalized and normalized[key] is not None:
            if isinstance(default_val, list) and not isinstance(normalized[key], list):
                integrity_issues.append(
                    f'schema normalization: dropped "{key}" because expected list, got {type(normalized[key]).__name__}'
                )
                del normalized[key]
            elif isinstance(default_val, dict) and not isinstance(normalized[key], dict):
                if key == "continuation":
                    integrity_issues.append(
                        f"schema normalization: continuation requires salvage because expected object, got {type(normalized[key]).__name__}"
                    )
                else:
                    integrity_issues.append(
                        f'schema normalization: dropped "{key}" because expected object, got {type(normalized[key]).__name__}'
                    )
                    del normalized[key]

    _coerce_position_identifiers(normalized, integrity_issues)
    normalized = _salvage_state_sections(
        normalized,
        integrity_issues,
        allow_project_contract_salvage=allow_project_contract_salvage,
        project_root=project_root,
    )

    validation_findings: list[str] = []
    removed_validation_paths: set[tuple[object, ...]] = set()
    removed_top_level_keys: set[str] = set()
    while True:
        try:
            removed_validation_paths = set()
            validated = ResearchState.model_validate(normalized).model_dump()
            integrity_issues.extend(validation_findings)
            return _mirror_continuation_state(validated), integrity_issues
        except PydanticValidationError as exc:
            nested_removed = False
            top_level_keys: set[str] = set()
            for err in exc.errors():
                loc = tuple(err.get("loc", ()))
                message = str(err.get("msg", "validation failed")).strip() or "validation failed"
                if len(loc) > 1 and loc not in removed_validation_paths:
                    if _remove_validation_error_path(normalized, loc):
                        removed_validation_paths.add(loc)
                        issue = (
                            f'schema normalization: dropped malformed "{_format_validation_location(loc)}": {message}'
                        )
                        if issue not in validation_findings:
                            validation_findings.append(issue)
                        nested_removed = True
                        continue
                    # Nested field removal failed (e.g. missing required field).
                    # If the error path traverses a list, remove the entire
                    # malformed list element instead of letting it cascade to
                    # top-level section removal.
                    list_parent_loc = _find_list_parent_loc(normalized, loc)
                    if list_parent_loc is not None and list_parent_loc not in removed_validation_paths:
                        if _remove_validation_error_path(normalized, list_parent_loc):
                            removed_validation_paths.add(list_parent_loc)
                            removed_validation_paths.add(loc)
                            issue = (
                                f'schema normalization: dropped malformed list entry '
                                f'"{_format_validation_location(list_parent_loc)}": {message}'
                            )
                            if issue not in validation_findings:
                                validation_findings.append(issue)
                            nested_removed = True
                            continue
                if loc:
                    top_level_keys.add(str(loc[0]))

            if nested_removed:
                continue

            removed_now = sorted(
                key for key in top_level_keys if key not in removed_top_level_keys and key in normalized
            )
            if removed_now:
                validation_findings.append(
                    "schema normalization: removed invalid top-level sections "
                    + ", ".join(f'"{key}"' for key in removed_now)
                )
                for key in removed_now:
                    removed_top_level_keys.add(key)
                    normalized.pop(key, None)
                continue

            logger.warning("state.json had irrecoverable schema errors; resetting to defaults")
            integrity_issues.extend(validation_findings)
            integrity_issues.append("schema normalization: irrecoverable validation failure; reset to defaults")
            return _mirror_continuation_state(default_state_dict()), integrity_issues


def _normalize_state_schema_with_backup_project_contract(
    raw: dict | None,
    backup_raw: dict | None,
    *,
    allow_project_contract_salvage: bool = True,
    project_root: Path | None = None,
) -> tuple[dict, list[str], bool, bool, bool, bool]:
    """Normalize state and recover backup state when the primary root is unreadable."""

    normalized, integrity_issues = _normalize_state_schema(
        raw,
        allow_project_contract_salvage=allow_project_contract_salvage,
        project_root=project_root,
    )
    recovered_root_from_backup = False
    recovered_position_from_backup = False
    recovered_continuation_from_backup = False
    recovered_session_from_backup = False

    backup_normalized: dict | None = None
    backup_issues: list[str] = []
    if isinstance(backup_raw, dict):
        backup_normalized, backup_issues = _normalize_state_schema(
            backup_raw,
            allow_project_contract_salvage=allow_project_contract_salvage,
            project_root=project_root,
        )

    def _state_reset_issue_present(issues: list[str]) -> bool:
        return "schema normalization: irrecoverable validation failure; reset to defaults" in issues

    if (
        backup_normalized is not None
        and not _state_reset_issue_present(backup_issues)
        and (not isinstance(raw, dict) or _state_reset_issue_present(integrity_issues))
    ):
        normalized = backup_normalized
        integrity_issues = list(backup_issues)
        recovered_root_from_backup = True
        logger.warning("Recovered state.json from state.json.bak after primary state.json required normalization")
    else:
        primary_position_issues = [
            issue
            for issue in integrity_issues
            if issue.startswith('schema normalization: dropped "position" because expected object, got ')
            or issue == 'schema normalization: removed invalid top-level sections "position"'
        ]
        primary_continuation_issues = [
            issue
            for issue in integrity_issues
            if issue.startswith('schema normalization: dropped "continuation" because expected object, got ')
            or issue.startswith("schema normalization: continuation requires salvage because expected object, got ")
            or issue.startswith('schema normalization: dropped malformed "continuation" because expected object, got ')
            or issue == 'schema normalization: removed invalid top-level sections "continuation"'
        ]
        if (
            isinstance(raw, dict)
            and backup_normalized is not None
            and not recovered_root_from_backup
            and primary_position_issues
            and isinstance(backup_normalized.get("position"), dict)
        ):
            normalized = copy.deepcopy(normalized)
            normalized["position"] = copy.deepcopy(backup_normalized["position"])
            integrity_issues = [issue for issue in integrity_issues if issue not in primary_position_issues]
            recovered_position_from_backup = True
        if (
            isinstance(raw, dict)
            and backup_normalized is not None
            and not recovered_root_from_backup
            and primary_continuation_issues
            and _continuation_payload_has_values(backup_normalized.get("continuation"))
        ):
            normalized = copy.deepcopy(normalized)
            normalized["continuation"] = copy.deepcopy(backup_normalized["continuation"])
            integrity_issues = [issue for issue in integrity_issues if issue not in primary_continuation_issues]
            recovered_continuation_from_backup = True
    normalized = _mirror_continuation_state(normalized)
    return (
        normalized,
        integrity_issues,
        recovered_root_from_backup,
        recovered_position_from_backup,
        recovered_continuation_from_backup,
        recovered_session_from_backup,
    )


def _format_validation_location(loc: tuple[object, ...]) -> str:
    return ".".join(str(part) for part in loc)


def _find_list_parent_loc(payload: object, loc: tuple[object, ...]) -> tuple[object, ...] | None:
    """Find the nearest ancestor loc whose terminal step is a list index.

    For loc ``('approximations', 1, 'name')``, returns ``('approximations', 1)``
    because ``payload['approximations']`` is a list and index 1 identifies the
    element to remove.

    Returns ``None`` when *loc* does not traverse through any list.
    """
    container: object = payload
    for i, part in enumerate(loc[:-1]):
        if isinstance(container, dict):
            if part not in container:
                return None
            container = container[part]
        elif isinstance(container, list):
            if isinstance(part, int) and 0 <= part < len(container):
                # This is a list index -- the loc up to and including this index
                # would remove the list element.
                return loc[: i + 1]
            return None
        else:
            return None
    return None


def _remove_validation_error_path(payload: object, loc: tuple[object, ...]) -> bool:
    """Remove one nested validation target from a mutable payload."""

    if not loc:
        return False

    container: object = payload
    for part in loc[:-1]:
        if isinstance(container, dict):
            if part not in container:
                return False
            container = container[part]
            continue
        if isinstance(container, list):
            if not isinstance(part, int) or part < 0 or part >= len(container):
                return False
            container = container[part]
            continue
        return False

    terminal = loc[-1]
    if isinstance(container, dict):
        if terminal not in container:
            return False
        del container[terminal]
        return True
    if isinstance(container, list):
        if not isinstance(terminal, int) or terminal < 0 or terminal >= len(container):
            return False
        del container[terminal]
        return True
    return False


def _first_validation_issue(exc: PydanticValidationError) -> str:
    first = exc.errors()[0] if exc.errors() else {}
    location = _format_validation_location(tuple(first.get("loc", ())))
    message = str(first.get("msg", "validation failed"))
    return f"{location}: {message}" if location else message


def _integrity_issue_from_contract_error(error: str) -> str:
    extra_inputs_marker = ": Extra inputs are not permitted"

    if error.startswith("project_contract."):
        return f"schema normalization: {error}"
    if extra_inputs_marker in error:
        path = error.split(extra_inputs_marker, 1)[0].strip()
        return f'schema normalization: dropped unknown "project_contract.{path}"'
    if " must be an object, not " in error:
        path, actual = error.split(" must be an object, not ", 1)
        return f'schema normalization: normalized "project_contract.{path}" because expected object, got {actual}'
    if " must be a list, not " in error:
        path, actual = error.split(" must be a list, not ", 1)
        return f'schema normalization: normalized "project_contract.{path}" because expected list, got {actual}'
    if error.endswith(" is required"):
        normalized_error = error.replace("scope.", "project_contract.scope.", 1)
        return f"schema normalization: {normalized_error}"
    if ":" in error:
        path, detail = error.split(":", 1)
        return f'schema normalization: dropped malformed "project_contract.{path.strip()}": {detail.strip()}'
    path_match = re.match(
        r"^(schema_version|[A-Za-z_][A-Za-z0-9_]*(?:\.\d+|\.[A-Za-z_][A-Za-z0-9_]*)*)\s+(.*)$",
        error,
    )
    if path_match is not None:
        path, detail = path_match.groups()
        return f"schema normalization: project_contract.{path} {detail}"
    return f"schema normalization: {error}"


def _normalize_project_contract_section(
    value: object,
    integrity_issues: list[str],
    *,
    allow_project_contract_salvage: bool,
    project_root: Path | None = None,
) -> object:
    if value is None or not isinstance(value, dict):
        return value

    list_shape_drift_errors = _collect_list_shape_drift_errors(value)
    list_member_errors = _collect_project_contract_list_member_errors(value)
    normalized_contract, errors = salvage_project_contract(value)
    combined_errors = list(dict.fromkeys(errors))
    normalized_contract_dump = normalized_contract.model_dump() if normalized_contract is not None else None
    if list_shape_drift_errors:
        integrity_issues.extend(_integrity_issue_from_contract_error(error) for error in list_shape_drift_errors)
    if list_member_errors:
        integrity_issues.extend(_integrity_issue_from_contract_error(error) for error in list_member_errors)
    if normalized_contract is None:
        if combined_errors:
            integrity_issues.extend(_integrity_issue_from_contract_error(error) for error in combined_errors)
            if _has_authoritative_scalar_schema_findings(combined_errors):
                integrity_issues.append(
                    'schema normalization: dropped "project_contract" because authoritative scalar fields required normalization'
                )
            else:
                integrity_issues.append(
                    'schema normalization: dropped "project_contract" because contract schema required normalization'
                )
        return None
    if combined_errors:
        # Run contract salvage before any direct Pydantic acceptance so coercive
        # scalar drift is surfaced as an integrity issue instead of silently
        # canonicalized by field validators or bool/int coercion.
        integrity_issues.extend(_integrity_issue_from_contract_error(error) for error in combined_errors)
        if _has_authoritative_scalar_schema_findings(combined_errors):
            integrity_issues.append(
                'schema normalization: dropped "project_contract" because authoritative scalar fields required normalization'
            )
            return None
        _schema_warnings, schema_errors = split_project_contract_schema_findings(
            combined_errors,
            allow_case_drift_recovery=allow_project_contract_salvage,
        )
        if schema_errors:
            integrity_issues.append(
                'schema normalization: dropped "project_contract" because contract schema required normalization'
            )
            return None
    draft_validation = validate_project_contract(normalized_contract, mode="draft", project_root=project_root)
    if not draft_validation.valid:
        for error in draft_validation.errors:
            issue = f"project_contract: {error}"
            if issue not in integrity_issues:
                integrity_issues.append(issue)
        integrity_issues.append(
            'schema normalization: dropped "project_contract" because contract failed draft scoping validation'
        )
        return None
    return normalized_contract_dump


def _normalize_intermediate_results_section(value: object, integrity_issues: list[str]) -> object:
    if value is None or not isinstance(value, list):
        return value

    normalized_results: list[object] = []
    changed = False
    for index, item in enumerate(value):
        if isinstance(item, str):
            normalized_results.append(item)
            continue
        if not isinstance(item, dict):
            integrity_issues.append(
                f'schema normalization: dropped "intermediate_results[{index}]" because expected object or string, got {type(item).__name__}'
            )
            changed = True
            continue

        candidate = copy.deepcopy(item)
        try:
            normalized_results.append(IntermediateResult.model_validate(candidate).model_dump())
            continue
        except PydanticValidationError:
            pass

        records = candidate.get("verification_records")
        if isinstance(records, list):
            normalized_records: list[dict[str, object]] = []
            for record_index, record in enumerate(records):
                if not isinstance(record, dict):
                    integrity_issues.append(
                        "schema normalization: dropped "
                        f'"intermediate_results[{index}].verification_records[{record_index}]" '
                        f"because expected object, got {type(record).__name__}"
                    )
                    changed = True
                    continue
                try:
                    normalized_records.append(VerificationEvidence.model_validate(record).model_dump())
                except PydanticValidationError as exc:
                    detail = _first_validation_issue(exc)
                    integrity_issues.append(
                        "schema normalization: dropped malformed "
                        f'"intermediate_results[{index}].verification_records[{record_index}]": {detail}'
                    )
                    changed = True
            candidate["verification_records"] = normalized_records

        try:
            normalized_results.append(IntermediateResult.model_validate(candidate).model_dump())
            changed = True
        except PydanticValidationError as exc:
            detail = _first_validation_issue(exc)
            integrity_issues.append(
                f'schema normalization: dropped malformed "intermediate_results[{index}]": {detail}'
            )
            changed = True

    return normalized_results if changed else value


def _salvage_state_sections(
    normalized: dict[str, object],
    integrity_issues: list[str],
    *,
    allow_project_contract_salvage: bool,
    project_root: Path | None = None,
) -> dict[str, object]:
    if normalized.get("project_contract") is not None:
        normalized["project_contract"] = _normalize_project_contract_section(
            normalized.get("project_contract"),
            integrity_issues,
            allow_project_contract_salvage=allow_project_contract_salvage,
            project_root=project_root,
        )
    if normalized.get("intermediate_results") is not None:
        normalized["intermediate_results"] = _normalize_intermediate_results_section(
            normalized.get("intermediate_results"),
            integrity_issues,
        )
    if normalized.get("continuation") is not None:
        continuation_payload, continuation_issues = _normalize_continuation_payload_with_issues(
            normalized.get("continuation"),
            project_root=project_root,
        )
        normalized["continuation"] = continuation_payload
        for issue in continuation_issues:
            if issue not in integrity_issues:
                integrity_issues.append(issue)
    return normalized


def ensure_state_schema(raw: dict | None) -> dict:
    """Merge a (possibly incomplete) state dict with defaults so every field exists.

    Uses Pydantic model_validate to populate missing fields from ResearchState defaults.
    Type-mismatched fields (e.g. string where list expected) are dropped so Pydantic
    fills them with defaults.

    If validation still fails after top-level type fixup (e.g. wrong types inside nested
    objects), the offending top-level keys are progressively removed until validation
    succeeds. This guarantees the function never raises on any input dict.
    """
    normalized, _issues = _normalize_state_schema(raw)
    return normalized


def _normalize_state_for_persistence(raw: dict | None, *, project_root: Path | None = None) -> dict:
    """Normalize state for writes without silently salvaging malformed contracts."""
    normalized, integrity_issues = _normalize_state_schema(
        raw,
        allow_project_contract_salvage=False,
        project_root=project_root,
    )
    normalized = copy.deepcopy(normalized)
    normalized["session"] = _session_from_continuation_payload(normalized.get("continuation"))
    if any("project_contract" in issue for issue in integrity_issues):
        logger.warning(
            "state.json persistence normalized project_contract with issue(s): %s", "; ".join(integrity_issues)
        )
    return normalized


# ─── Markdown Generator ───────────────────────────────────────────────────────

# Convention field labels — reuse from conventions.py (derived from ConventionLock model).
from gpd.core.conventions import CONVENTION_LABELS as _CONVENTION_LABELS  # noqa: E402


def _escape_pipe(v: object) -> str:
    """Escape pipe characters for markdown tables."""
    return str(v).replace("|", "\\|")


def _safe_esc(v: object) -> str:
    """Escape pipe chars, defaulting None to '-'."""
    return _escape_pipe("-" if v is None else v)


def _item_text(item: object) -> str:
    """Convert a list item (string or dict) to display text."""
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return item.get("text") or item.get("description") or item.get("question") or json.dumps(item)
    return str(item)


def _merge_intermediate_results_from_markdown(existing: object, parsed_items: list[object]) -> list[object]:
    """Preserve JSON-only result provenance when syncing from markdown.

    STATE.md is a lossy human-readable view of intermediate results. When we
    sync it back into state.json, preserve existing structured result objects
    whenever a markdown bullet still references the same `[RESULT-ID]`.
    """
    if not parsed_items:
        return []

    existing_by_id: dict[str, object] = {}
    if isinstance(existing, list):
        for item in existing:
            if isinstance(item, dict) and item.get("id"):
                existing_by_id[str(item["id"])] = item

    merged: list[object] = []
    for item in parsed_items:
        if isinstance(item, str):
            match = re.match(r"^\[([^\]]+)\]", item)
            if match:
                existing_item = existing_by_id.get(match.group(1))
                if existing_item is not None:
                    merged.append(_merge_intermediate_result_markdown_text(existing_item, item))
                    continue
        merged.append(item)
    return merged


def _merge_intermediate_result_markdown_text(existing_item: object, markdown_item: str) -> object:
    """Merge markdown-editable result fields onto an existing structured result."""

    if not isinstance(existing_item, dict):
        return existing_item

    match = re.match(r"^\[(?P<id>[^\]]+)\]\s*(?P<body>.*)$", markdown_item.strip())
    if match is None:
        return existing_item

    body = match.group("body").strip()
    deps: list[str] = []
    deps_match = re.search(r"\s*\[deps:\s*(?P<deps>[^\]]*)\]\s*$", body)
    if deps_match is not None:
        body = body[: deps_match.start()].rstrip()
        raw_deps = deps_match.group("deps").strip()
        if raw_deps and raw_deps.casefold() != "none":
            deps = [dep.strip() for dep in raw_deps.split(",") if dep.strip()]

    metadata_tokens: list[str] = []
    metadata_match = re.search(r"\s*\((?P<meta>[^()]*)\)\s*$", body)
    if metadata_match is not None:
        body = body[: metadata_match.start()].rstrip()
        metadata_tokens = [token.strip() for token in metadata_match.group("meta").split(",") if token.strip()]

    description = body
    equation = None
    equation_match = re.match(r"^(?P<description>.*?)(?::\s*`(?P<equation>[^`]*)`)?\s*$", body)
    if equation_match is not None:
        description = equation_match.group("description").strip()
        equation = equation_match.group("equation")

    merged_item = dict(existing_item)
    merged_item.update(
        {
            "description": description or None,
            "equation": equation or None,
            "units": None,
            "validity": None,
            "phase": None,
            "depends_on": deps,
        }
    )

    for token in metadata_tokens:
        lowered = token.casefold()
        if lowered.startswith("units:"):
            merged_item["units"] = token.partition(":")[2].strip() or None
        elif lowered.startswith("valid:"):
            merged_item["validity"] = token.partition(":")[2].strip() or None
        elif lowered.startswith("phase "):
            merged_item["phase"] = token[6:].strip() or None

    return merged_item


def _integrity_status_from(issues: list[str], warnings: list[str], mode: str) -> str:
    """Map validation findings to a coarse integrity status."""
    if issues:
        return "blocked" if mode == "review" else "degraded"
    if warnings:
        return "warning"
    return "healthy"


_STATE_MD_MIRRORED_FIELDS: dict[str, tuple[str, ...] | None] = {
    "project_reference": ("core_research_question", "current_focus", "project_md_updated"),
    "position": (
        "current_phase",
        "current_phase_name",
        "total_phases",
        "current_plan",
        "total_plans_in_phase",
        "status",
        "last_activity",
        "last_activity_desc",
        "progress_percent",
        "paused_at",
    ),
    "session": ("last_date", "hostname", "platform", "stopped_at", "resume_file", "last_result_id"),
    "decisions": None,
    "blockers": None,
    "performance_metrics": ("rows",),
    "active_calculations": None,
    "open_questions": None,
    "approximations": None,
    "convention_lock": None,
    "propagated_uncertainties": None,
    "pending_todos": None,
}


def _state_md_comparison_payload(section: str, value: object) -> object:
    """Return the STATE.md-mirrored comparison payload for one top-level section."""

    if section == "convention_lock" and isinstance(value, dict):
        normalized = {
            key: item
            for key, item in value.items()
            if key == "custom_conventions" or (key in KNOWN_CONVENTIONS and not is_bogus_value(item))
        }
        if not normalized.get("custom_conventions"):
            normalized.pop("custom_conventions", None)
        return normalized

    mirrored_fields = _STATE_MD_MIRRORED_FIELDS.get(section)
    if mirrored_fields is None or not isinstance(value, dict):
        return value

    payload = {field: value.get(field) for field in mirrored_fields}
    if section == "position":
        for field in ("current_phase", "current_phase_name"):
            current = payload.get(field)
            if current is not None:
                payload[field] = phase_normalize(str(current))
    return payload


def _state_md_mirror_mismatches(state_json: dict[str, object], state_md: dict[str, object]) -> list[str]:
    """Return mismatches between ``state.json`` and the editable ``STATE.md`` mirror."""

    mismatches: list[str] = []
    for section in _STATE_MD_MIRRORED_FIELDS:
        json_value = _state_md_comparison_payload(section, state_json.get(section))
        md_value = _state_md_comparison_payload(section, state_md.get(section))
        if json_value is None or md_value is None:
            continue

        if json.dumps(json_value, sort_keys=True, ensure_ascii=False) != json.dumps(
            md_value,
            sort_keys=True,
            ensure_ascii=False,
        ):
            mismatches.append(f"{section} mismatch between state.json and STATE.md")

    return mismatches


def generate_state_markdown(raw: dict) -> str:
    """Generate STATE.md content from a state dict."""
    s = ensure_state_schema(raw)
    lines: list[str] = []

    def p(line: str) -> None:
        lines.append(line)

    p("# Research State")
    p("")
    p("## Project Reference")
    p("")
    pr = s["project_reference"]
    if pr.get("project_md_updated"):
        p(f"See: {PLANNING_DIR_NAME}/{PROJECT_FILENAME} (updated {pr['project_md_updated']})")
    else:
        p(f"See: {PLANNING_DIR_NAME}/{PROJECT_FILENAME}")
    p("")
    p(f"**Machine-readable scoping contract:** `{PLANNING_DIR_NAME}/{STATE_JSON_FILENAME}` field `project_contract`")
    p("")
    p(f"**Core research question:** {pr.get('core_research_question') or '[Not set]'}")
    p(f"**Current focus:** {pr.get('current_focus') or '[Not set]'}")
    p("")
    p("## Current Position")
    p("")

    pos = s["position"]
    p(f"**Current Phase:** {pos.get('current_phase') or EM_DASH}")
    p(f"**Current Phase Name:** {pos.get('current_phase_name') or EM_DASH}")
    p(f"**Total Phases:** {pos['total_phases'] if pos.get('total_phases') is not None else EM_DASH}")
    p(f"**Current Plan:** {pos.get('current_plan') or EM_DASH}")
    p(
        f"**Total Plans in Phase:** {pos['total_plans_in_phase'] if pos.get('total_plans_in_phase') is not None else EM_DASH}"
    )
    p(f"**Status:** {pos.get('status') or EM_DASH}")
    p(f"**Last Activity:** {pos.get('last_activity') or EM_DASH}")
    if pos.get("last_activity_desc"):
        p(f"**Last Activity Description:** {pos['last_activity_desc']}")
    if pos.get("paused_at"):
        p(f"**Paused At:** {pos['paused_at']}")
    p("")

    pct = pos.get("progress_percent")
    if pct is not None:
        try:
            pct = int(pct)
        except (TypeError, ValueError):
            pct = None
    if pct is not None:
        bar_width = 10
        filled = max(0, min(bar_width, round((pct / 100) * bar_width)))
        bar = "\u2588" * filled + "\u2591" * (bar_width - filled)
        p(f"**Progress:** [{bar}] {pct}%")
    p("")

    p("## Active Calculations")
    p("")
    if not s["active_calculations"]:
        p("None yet.")
    else:
        for c in s["active_calculations"]:
            p(f"- {_item_text(c)}")
    p("")

    p("## Intermediate Results")
    p("")
    if not s["intermediate_results"]:
        p("None yet.")
    else:
        for r in s["intermediate_results"]:
            if isinstance(r, str):
                p(f"- {r}")
                continue
            rd = r if isinstance(r, dict) else {}
            id_tag = f"[{rd['id']}]" if rd.get("id") else ""
            desc = rd.get("description") or "Untitled result"
            eqn = f": `{rd['equation']}`" if rd.get("equation") else ""
            parts = []
            if rd.get("units"):
                parts.append(f"units: {rd['units']}")
            if rd.get("validity"):
                parts.append(f"valid: {rd['validity']}")
            if rd.get("phase") is not None:
                parts.append(f"phase {rd['phase']}")
            if rd.get("verified"):
                parts.append("\u2713")
            record_count = len(rd.get("verification_records") or [])
            if record_count:
                parts.append(f"evidence: {record_count}")
            meta = f" ({', '.join(parts)})" if parts else ""
            deps_list = rd.get("depends_on") or []
            deps = f" [deps: {', '.join(deps_list)}]" if deps_list else ""
            line = f"- {id_tag} {desc}{eqn}{meta}{deps}"
            p(re.sub(r"\s+", " ", line).strip())
    p("")

    p("## Open Questions")
    p("")
    if not s["open_questions"]:
        p("None yet.")
    else:
        for q in s["open_questions"]:
            p(f"- {_item_text(q)}")
    p("")

    resolved = s.get("resolved_questions") or []
    if resolved:
        p("## Resolved Questions")
        p("")
        for rq in resolved:
            if isinstance(rq, dict):
                q_text = rq.get("question", "")
                a_text = rq.get("answer", "")
                p(f"- **Q:** {q_text}")
                if a_text:
                    p(f"  **A:** {a_text}")
            else:
                p(f"- {rq}")
        p("")

    p("## Performance Metrics")
    p("")
    p("| Label | Duration | Tasks | Files |")
    p("| ----- | -------- | ----- | ----- |")
    pm = s.get("performance_metrics") or {}
    pm_rows = pm.get("rows", []) if isinstance(pm, dict) else []
    if not pm_rows:
        p("| -     | -        | -     | -     |")
    else:
        for row in pm_rows:
            rd = row if isinstance(row, dict) else {}
            p(
                f"| {_escape_pipe(rd.get('label', '-'))} "
                f"| {_escape_pipe(rd.get('duration', '-'))} "
                f"| {_escape_pipe(rd.get('tasks') or '-')} tasks "
                f"| {_escape_pipe(rd.get('files') or '-')} files |"
            )
    p("")

    p("## Accumulated Context")
    p("")
    p("### Decisions")
    p("")
    if not s["decisions"]:
        p("None yet.")
    else:
        for d in s["decisions"]:
            dd = d if isinstance(d, dict) else {}
            rat = f" \u2014 {dd['rationale']}" if dd.get("rationale") else ""
            p(f"- [Phase {dd.get('phase') or '—'}]: {dd.get('summary', '')}{rat}")
    p("")

    p("### Active Approximations")
    p("")
    if not s["approximations"]:
        p("None yet.")
    else:
        p("| Approximation | Validity Range | Controlling Parameter | Current Value | Status |")
        p("| ------------- | -------------- | --------------------- | ------------- | ------ |")
        for a in s["approximations"]:
            ad = a if isinstance(a, dict) else {}
            p(
                f"| {_safe_esc(ad.get('name'))} | {_safe_esc(ad.get('validity_range'))} "
                f"| {_safe_esc(ad.get('controlling_param'))} | {_safe_esc(ad.get('current_value'))} "
                f"| {_safe_esc(ad.get('status'))} |"
            )
    p("")

    p("**Convention Lock:**")
    p("")
    cl = s.get("convention_lock") or {}

    set_conventions = [(k, label) for k, label in _CONVENTION_LABELS.items() if not is_bogus_value(cl.get(k))]

    # Collect custom conventions
    custom_convs = cl.get("custom_conventions") or {}
    custom_entries: list[tuple[str, str, object]] = []
    for key, value in custom_convs.items():
        if not is_bogus_value(value):
            label = key.replace("_", " ").title()
            custom_entries.append((key, label, value))

    # Also collect custom flat keys not covered by the standard labels
    for key, value in cl.items():
        if key not in _CONVENTION_LABELS and key != "custom_conventions" and not is_bogus_value(value):
            if not any(k == key for k, _, _ in custom_entries):
                label = key.replace("_", " ").title()
                custom_entries.append((key, label, value))

    if not set_conventions and not custom_entries:
        p("No conventions locked yet.")
    else:
        for key, label in set_conventions:
            p(f"- {label}: {cl[key]}")
        if custom_entries:
            if set_conventions:
                p("")
            p("*Custom conventions:*")
            for _, label, value in custom_entries:
                p(f"- {label}: {value}")
    p("")

    p("### Propagated Uncertainties")
    p("")
    if not s["propagated_uncertainties"]:
        p("None yet.")
    else:
        p("| Quantity | Current Value | Uncertainty | Last Updated (Phase) | Method |")
        p("| ------- | ------------- | ----------- | -------------------- | ------ |")
        for u in s["propagated_uncertainties"]:
            ud = u if isinstance(u, dict) else {}
            p(
                f"| {_safe_esc(ud.get('quantity'))} | {_safe_esc(ud.get('value'))} "
                f"| {_safe_esc(ud.get('uncertainty'))} | {_safe_esc(ud.get('phase'))} "
                f"| {_safe_esc(ud.get('method'))} |"
            )
    p("")

    p("### Pending Todos")
    p("")
    if not s["pending_todos"]:
        p("None yet.")
    else:
        for t in s["pending_todos"]:
            p(f"- {_item_text(t)}")
    p("")

    p("### Blockers/Concerns")
    p("")
    if not s["blockers"]:
        p("None")
    else:
        for b in s["blockers"]:
            p(f"- {_item_text(b)}")
    p("")

    p("## Session Continuity")
    p("")
    sess = s.get("session") or {}
    p(f"**Last session:** {sess.get('last_date') or EM_DASH}")
    p(f"**Stopped at:** {sess.get('stopped_at') or EM_DASH}")
    p(f"**Resume file:** {sess.get('resume_file') or EM_DASH}")
    p(f"**Last result ID:** {sess.get('last_result_id') or EM_DASH}")
    p(f"**Hostname:** {sess.get('hostname') or EM_DASH}")
    p(f"**Platform:** {sess.get('platform') or EM_DASH}")
    p("")

    return "\n".join(lines)


# ─── Dual-Write Engine ─────────────────────────────────────────────────────────


def _planning_dir(cwd: Path) -> Path:
    return ProjectLayout(cwd).gpd


def _state_json_path(cwd: Path) -> Path:
    return ProjectLayout(cwd).state_json


def _state_md_path(cwd: Path) -> Path:
    return ProjectLayout(cwd).state_md


def _intent_path(cwd: Path) -> Path:
    return ProjectLayout(cwd).state_intent


_STATE_LOCK_TIMEOUT_SECONDS = 30.0


def _state_lock(cwd: Path, timeout: float = _STATE_LOCK_TIMEOUT_SECONDS):
    """Return the canonical lock for all dual-file state operations."""
    return file_lock(_state_json_path(cwd), timeout=timeout)


def _recover_intent_locked(cwd: Path) -> None:
    """Recover from interrupted dual-file write (intent marker left behind)."""
    intent_file = _intent_path(cwd)
    json_path = _state_json_path(cwd)
    md_path = _state_md_path(cwd)

    try:
        intent_raw = intent_file.read_text(encoding="utf-8")
    except FileNotFoundError:
        return
    except OSError:
        # Intent file exists but unreadable — remove
        try:
            intent_file.unlink(missing_ok=True)
        except OSError:
            pass
        return

    parts = intent_raw.strip().split("\n")
    json_tmp = Path(parts[0]) if parts else None
    md_tmp = Path(parts[1]) if len(parts) > 1 else None

    json_tmp_exists = json_tmp is not None and json_tmp.exists()
    md_tmp_exists = md_tmp is not None and md_tmp.exists()

    # Validate temp file content before promoting
    json_valid = False
    if json_tmp_exists:
        try:
            json.loads(json_tmp.read_text(encoding="utf-8"))
            json_valid = True
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            pass

    try:
        md_valid = md_tmp_exists and md_tmp.stat().st_size > 0
    except OSError:
        md_valid = False

    conflict_with_current = False
    if json_tmp_exists and md_tmp_exists:
        try:
            current_json_is_newer = json_path.exists() and json_path.stat().st_mtime_ns > json_tmp.stat().st_mtime_ns
        except OSError:
            current_json_is_newer = False
        try:
            current_md_is_newer = md_path.exists() and md_path.stat().st_mtime_ns > md_tmp.stat().st_mtime_ns
        except OSError:
            current_md_is_newer = False
        conflict_with_current = current_json_is_newer or current_md_is_newer

    if json_tmp_exists and md_tmp_exists and json_valid and md_valid and not conflict_with_current:
        # Both temp files ready and valid — complete the interrupted write
        _replace_with_retry(json_tmp, json_path)
        _replace_with_retry(md_tmp, md_path)
    else:
        if conflict_with_current:
            logger.warning("Ignoring stale state write intent because current state files are newer than temp files")
        # Partial or corrupt — rollback by cleaning up temp files
        if json_tmp_exists:
            try:
                json_tmp.unlink()
            except OSError:
                pass
        if md_tmp_exists:
            try:
                md_tmp.unlink()
            except OSError:
                pass

    try:
        intent_file.unlink(missing_ok=True)
    except OSError:
        pass


def _build_state_from_markdown(
    cwd: Path,
    md_content: str,
    *,
    recover_intent: bool = True,
    import_session_continuation_from_markdown: bool = False,
) -> dict:
    """Merge markdown-derived state into the existing JSON state."""
    json_path = _state_json_path(cwd)
    backup_path = json_path.parent / STATE_JSON_BACKUP_FILENAME
    parsed = parse_state_to_json(
        md_content,
        import_legacy_session=import_session_continuation_from_markdown,
    )
    has_convention_lock = _has_bold_block(md_content, "Convention Lock")
    has_approximations = _has_subsection(md_content, "Active Approximations")
    has_uncertainties = _has_subsection(md_content, "Propagated Uncertainties")
    has_pending_todos = _has_subsection(md_content, "Pending Todos")
    if recover_intent:
        _recover_intent_locked(cwd)

    existing = None
    primary_unreadable = False
    try:
        existing = json.loads(json_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        primary_unreadable = True
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        logger.warning("state.json is unreadable during markdown merge; ignoring existing JSON state: %s", e)
        primary_unreadable = True

    if existing is not None and not isinstance(existing, dict):
        logger.warning(
            "state.json root is not an object during markdown merge; treating existing JSON state as unreadable: %s",
            type(existing).__name__,
        )
        existing = None
        primary_unreadable = True

    if primary_unreadable:
        try:
            backup_existing = json.loads(backup_path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
            backup_existing = None
        if isinstance(backup_existing, dict):
            existing = copy.deepcopy(backup_existing)
            existing_continuation = existing.get("continuation")
            if _continuation_payload_has_values(existing_continuation):
                existing["session"] = _session_from_continuation_payload(existing_continuation)
            else:
                existing["session"] = _blank_session_payload()

    if existing and isinstance(existing, dict):
        if primary_unreadable and existing.get("project_contract") is not None:
            existing = copy.deepcopy(existing)
            existing["project_contract"] = None
        project_contract = existing.get("project_contract")
        if project_contract is not None:
            preserved_contract = _preserved_visible_project_contract_from_raw_state(
                cwd,
                source_path=backup_path if primary_unreadable else json_path,
                raw_state=existing,
            )
            if preserved_contract is None:
                existing = copy.deepcopy(existing)
                existing["project_contract"] = None
            else:
                existing = copy.deepcopy(existing)
                existing["project_contract"] = preserved_contract
        merged = {**existing}
        merged["_version"] = parsed["_version"]
        merged["_synced_at"] = parsed["_synced_at"]
        existing_session = (
            {**_blank_session_payload(), **existing["session"]}
            if isinstance(existing.get("session"), dict)
            else _blank_session_payload()
        )
        parsed_session = (
            {**_blank_session_payload(), **parsed["session"]}
            if isinstance(parsed.get("session"), dict)
            else _blank_session_payload()
        )
        parsed_session_has_values = _session_payload_has_values(parsed_session)
        if parsed.get("project_reference"):
            merged["project_reference"] = {**(merged.get("project_reference") or {}), **parsed["project_reference"]}

        if parsed.get("position"):
            merged["position"] = {**(merged.get("position") or {}), **parsed["position"]}
        merged["session"] = parsed_session if parsed_session_has_values else existing_session

        if parsed.get("decisions") is not None:
            merged["decisions"] = parsed["decisions"]
        if parsed.get("blockers") is not None:
            merged["blockers"] = parsed["blockers"]

        if parsed.get("performance_metrics") is not None:
            merged["performance_metrics"] = parsed["performance_metrics"]

        if has_convention_lock and parsed.get("convention_lock") is not None:
            merged["convention_lock"] = parsed["convention_lock"]

        for field in ("active_calculations", "intermediate_results", "open_questions"):
            if field in parsed:
                if field == "intermediate_results":
                    merged[field] = _merge_intermediate_results_from_markdown(
                        merged.get(field),
                        parsed.get(field) or [],
                    )
                else:
                    merged[field] = parsed.get(field) or []
        structured_fields = (
            ("approximations", has_approximations),
            ("propagated_uncertainties", has_uncertainties),
            ("pending_todos", has_pending_todos),
        )
        for field, markdown_has_field in structured_fields:
            if markdown_has_field and field in parsed:
                merged[field] = parsed.get(field) or []

        if "continuation" in existing:
            merged["continuation"] = copy.deepcopy(existing.get("continuation"))
    else:
        merged = parsed

    return _normalize_state_for_persistence(merged, project_root=cwd)


def _preserved_visible_project_contract_from_raw_state(
    cwd: Path,
    *,
    source_path: Path,
    raw_state: object,
) -> dict[str, object] | None:
    """Return the visible normalized contract when state already exposes it."""

    if not isinstance(raw_state, dict):
        return None

    raw_contract = raw_state.get("project_contract")
    if not isinstance(raw_contract, dict):
        return None

    visible_contract, load_info = _classify_project_contract_payload(
        cwd=cwd,
        source_path=source_path,
        raw_contract=raw_contract,
    )
    if visible_contract is None:
        return None

    if load_info.get("status") not in {
        "loaded",
        "loaded_with_schema_normalization",
        "loaded_with_approval_blockers",
        "blocked_integrity",
    }:
        return None

    return visible_contract.model_dump(mode="python")


def _preserved_visible_project_contract_from_state_file(
    cwd: Path,
    *,
    state_path: Path,
) -> dict[str, object] | None:
    """Return the visible normalized project contract preserved from one state JSON file."""

    try:
        raw_state = json.loads(state_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    if not isinstance(raw_state, dict):
        return None
    return _preserved_visible_project_contract_from_raw_state(
        cwd,
        source_path=state_path,
        raw_state=raw_state,
    )


def _write_state_pair_locked(
    cwd: Path,
    *,
    state_obj: dict,
    md_content: str,
    preserve_raw_project_contract: object = None,
) -> dict:
    """Atomically persist state.json + STATE.md under the canonical state lock."""
    planning = _planning_dir(cwd)
    planning.mkdir(parents=True, exist_ok=True)
    json_path = _state_json_path(cwd)
    md_path = _state_md_path(cwd)
    backup_path = json_path.parent / STATE_JSON_BACKUP_FILENAME
    intent_file = _intent_path(cwd)
    temp_suffix = f"{os.getpid()}.{uuid4().hex}"
    json_tmp = json_path.with_suffix(f".json.tmp.{temp_suffix}")
    md_tmp = md_path.with_suffix(f".md.tmp.{temp_suffix}")

    json_backup = safe_read_file(json_path)
    md_backup = safe_read_file(md_path)

    normalized = _normalize_state_for_persistence(state_obj, project_root=cwd)
    if isinstance(preserve_raw_project_contract, dict):
        normalized = copy.deepcopy(normalized)
        normalized["project_contract"] = copy.deepcopy(preserve_raw_project_contract)

    json_rendered = json.dumps(normalized, indent=2) + "\n"
    backup_rendered = json_rendered

    try:
        atomic_write(json_tmp, json_rendered)
        atomic_write(md_tmp, md_content)

        intent_file.write_text(f"{json_tmp}\n{md_tmp}\n", encoding="utf-8")
        _replace_with_retry(json_tmp, json_path)
        _replace_with_retry(md_tmp, md_path)
        try:
            intent_file.unlink(missing_ok=True)
        except OSError:
            pass

        atomic_write(backup_path, backup_rendered)
    except Exception:
        for f in (intent_file, json_tmp, md_tmp):
            try:
                f.unlink(missing_ok=True)
            except OSError:
                pass
        if json_backup is not None:
            try:
                atomic_write(json_path, json_backup)
            except OSError:
                pass
        if md_backup is not None:
            try:
                atomic_write(md_path, md_backup)
            except OSError:
                pass
        raise

    _refresh_recent_project_projection(cwd, normalized)
    return normalized


def _write_state_markdown_locked(cwd: Path, content: str) -> dict:
    """Write STATE.md and sync state.json while holding the canonical state lock."""
    return save_state_markdown_locked(cwd, content)


def _raw_persisted_project_contract(cwd: Path) -> object | None:
    """Return the raw persisted project-contract payload from state.json."""

    layout = ProjectLayout(cwd)
    try:
        raw_state = json.loads(layout.state_json.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    if not isinstance(raw_state, dict):
        return None
    return raw_state.get("project_contract")


def sync_state_json_core(cwd: Path, md_content: str) -> dict:
    """Core sync logic: parse STATE.md -> merge into state.json.

    Caller MUST hold the state.json lock.
    """
    json_path = _state_json_path(cwd)
    backup_path = json_path.parent / STATE_JSON_BACKUP_FILENAME
    _recover_intent_locked(cwd)
    preserved_contract = _preserved_project_contract_for_markdown_save(cwd)
    merged = _build_state_from_markdown(
        cwd,
        md_content,
        # Session Continuity is a compatibility mirror; markdown edits must
        # not mint canonical continuation authority on their own.
        import_session_continuation_from_markdown=False,
    )
    if merged.get("project_contract") is None and isinstance(preserved_contract, dict):
        merged = copy.deepcopy(merged)
        merged["project_contract"] = copy.deepcopy(preserved_contract)

    json_content = json.dumps(merged, indent=2) + "\n"
    prior_json = safe_read_file(json_path)
    prior_backup = safe_read_file(backup_path)
    try:
        atomic_write(json_path, json_content)
        atomic_write(backup_path, json_content)
    except Exception:
        if prior_json is None:
            try:
                json_path.unlink(missing_ok=True)
            except OSError:
                pass
        else:
            try:
                atomic_write(json_path, prior_json)
            except OSError:
                pass
        if prior_backup is None:
            try:
                backup_path.unlink(missing_ok=True)
            except OSError:
                pass
        else:
            try:
                atomic_write(backup_path, prior_backup)
            except OSError:
                pass
        raise

    _refresh_recent_project_projection(cwd, merged)
    return merged


@instrument_gpd_function("state.sync")
def sync_state_json(cwd: Path, md_content: str) -> dict:
    """Parse STATE.md and sync into state.json (with locking)."""
    with _state_lock(cwd):
        return sync_state_json_core(cwd, md_content)


def _load_state_json_with_integrity_issues(
    cwd: Path,
    *,
    integrity_mode: str = "standard",
    persist_recovery: bool = True,
    recover_intent: bool = True,
    import_session_continuation_from_markdown: bool = False,
    surface_blocked_project_contract: bool = False,
    acquire_lock: bool = True,
) -> tuple[dict | None, list[str], str | None]:
    """Load state.json and return the normalized state, integrity issues, and source."""
    json_path = _state_json_path(cwd)
    bak_path = json_path.parent / STATE_JSON_BACKUP_FILENAME

    lock_context = _state_lock(cwd) if acquire_lock else nullcontext()
    with lock_context:
        if recover_intent:
            _recover_intent_locked(cwd)
        # Read paths must not silently default malformed singleton contract sections.
        allow_project_contract_salvage = False
        parse_issue: str | None = None

        try:
            raw = json_path.read_text(encoding="utf-8")
            parsed = json.loads(raw)
            if not isinstance(parsed, dict):
                raise TypeError(f"state root must be an object, got {type(parsed).__name__}")
            backup_parsed: dict | None = None
            try:
                bak_raw = bak_path.read_text(encoding="utf-8")
                bak_parsed = json.loads(bak_raw)
            except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
                bak_parsed = None
            if isinstance(bak_parsed, dict):
                backup_parsed = bak_parsed
            (
                normalized,
                integrity_issues,
                recovered_root_from_backup,
                recovered_position_from_backup,
                recovered_continuation_from_backup,
                recovered_session_from_backup,
            ) = _normalize_state_schema_with_backup_project_contract(
                parsed,
                backup_parsed,
                allow_project_contract_salvage=allow_project_contract_salvage,
                project_root=cwd,
            )
            if surface_blocked_project_contract:
                normalized, restored_contract_findings = _restore_visible_project_contract(
                    normalized,
                    parsed.get("project_contract"),
                    project_root=cwd,
                )
                for finding in restored_contract_findings:
                    if finding not in integrity_issues:
                        integrity_issues.append(finding)
            state_source = "state.json.bak" if recovered_root_from_backup else "state.json"
            if recovered_root_from_backup:
                integrity_issues.append(
                    "state.json root was recovered from state.json.bak after primary state.json required normalization"
                )
            if recovered_position_from_backup:
                integrity_issues.append(
                    "state.json position was recovered from state.json.bak after primary position required normalization"
                )
            if recovered_continuation_from_backup and integrity_mode != "review":
                integrity_issues.append(
                    "state.json continuation was recovered from state.json.bak after primary continuation required normalization"
                )
            if recovered_session_from_backup and integrity_mode != "review":
                integrity_issues.append(
                    "state.json session was recovered from state.json.bak after primary session required normalization"
                )
            if integrity_mode == "review" and integrity_issues:
                logger.warning("state.json failed review-mode integrity checks: %s", "; ".join(integrity_issues))
            if persist_recovery and (
                state_source != "state.json"
                or recovered_position_from_backup
                or recovered_continuation_from_backup
                or recovered_session_from_backup
            ):
                preserved_contract = _preserved_visible_project_contract_from_raw_state(
                    cwd,
                    source_path=json_path,
                    raw_state=parsed,
                )
                _write_state_pair_locked(
                    cwd,
                    state_obj=normalized,
                    md_content=generate_state_markdown(normalized),
                    preserve_raw_project_contract=preserved_contract,
                )
            return normalized, integrity_issues, state_source
        except FileNotFoundError:
            restored, integrity_issues = _load_state_json_from_backup(
                bak_path,
                integrity_mode=integrity_mode,
                allow_project_contract_salvage=allow_project_contract_salvage,
                surface_blocked_project_contract=surface_blocked_project_contract,
                project_root=cwd,
            )
            if restored is not None:
                integrity_issues.append(
                    "state.json root was recovered from state.json.bak after primary state.json was missing"
                )
                if persist_recovery:
                    preserved_contract = _preserved_visible_project_contract_from_state_file(
                        cwd,
                        state_path=bak_path,
                    )
                    _write_state_pair_locked(
                        cwd,
                        state_obj=restored,
                        md_content=generate_state_markdown(restored),
                        preserve_raw_project_contract=preserved_contract,
                    )
                return restored, integrity_issues, "state.json.bak"
        except TypeError as e:
            if os.environ.get(ENV_GPD_DEBUG):
                logger.debug("state.json structural error: %s", e)
            structural_issue = f"state.json structural error: {e}"
            restored, integrity_issues = _load_state_json_from_backup(
                bak_path,
                integrity_mode=integrity_mode,
                allow_project_contract_salvage=allow_project_contract_salvage,
                surface_blocked_project_contract=surface_blocked_project_contract,
                project_root=cwd,
            )
            if restored is not None:
                integrity_issues.append(
                    "state.json root was recovered from state.json.bak after primary state.json was unavailable or unreadable"
                )
                if persist_recovery:
                    preserved_contract = _preserved_visible_project_contract_from_state_file(
                        cwd,
                        state_path=bak_path,
                    )
                    _write_state_pair_locked(
                        cwd,
                        state_obj=restored,
                        md_content=generate_state_markdown(restored),
                        preserve_raw_project_contract=preserved_contract,
                    )
                return restored, integrity_issues, "state.json.bak"
            if os.environ.get(ENV_GPD_DEBUG):
                logger.debug("state.json.bak restore failed after structural error")
            if integrity_mode == "review":
                logger.warning("state.json structural error blocks review-mode loading: %s", e)
                return None, [structural_issue], None
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            if os.environ.get(ENV_GPD_DEBUG):
                logger.debug("state.json parse error: %s", e)
            parse_issue = f"state.json parse error: {e}"
            # Try backup
            restored, integrity_issues = _load_state_json_from_backup(
                bak_path,
                integrity_mode=integrity_mode,
                allow_project_contract_salvage=allow_project_contract_salvage,
                surface_blocked_project_contract=surface_blocked_project_contract,
                project_root=cwd,
            )
            if restored is not None:
                integrity_issues.insert(0, parse_issue)
                integrity_issues.append(
                    "state.json root was recovered from state.json.bak after primary state.json was unavailable or unreadable"
                )
                if persist_recovery:
                    preserved_contract = _preserved_visible_project_contract_from_state_file(
                        cwd,
                        state_path=bak_path,
                    )
                    _write_state_pair_locked(
                        cwd,
                        state_obj=restored,
                        md_content=generate_state_markdown(restored),
                        preserve_raw_project_contract=preserved_contract,
                    )
                return restored, integrity_issues, "state.json.bak"
            if os.environ.get(ENV_GPD_DEBUG):
                logger.debug("state.json.bak restore failed")
            if integrity_mode == "review":
                logger.warning("state.json parse error blocks review-mode loading: %s", e)
                return None, [parse_issue], None

        # Fall back to STATE.md
        md_path = _state_md_path(cwd)
        try:
            if integrity_mode == "review":
                logger.warning("STATE.md fallback is disabled in review integrity mode")
                return None, [], None
            content = md_path.read_text(encoding="utf-8")
            state_from_md = _build_state_from_markdown(
                cwd,
                content,
                recover_intent=recover_intent,
                import_session_continuation_from_markdown=import_session_continuation_from_markdown,
            )
            integrity_issues = [
                "state.json root was recovered from STATE.md after primary state.json was unavailable or unreadable"
            ]
            if parse_issue is not None:
                integrity_issues.insert(0, parse_issue)
            if persist_recovery:
                _write_state_pair_locked(
                    cwd,
                    state_obj=state_from_md,
                    md_content=content,
                    preserve_raw_project_contract=state_from_md.get("project_contract"),
                )
            return state_from_md, integrity_issues, "STATE.md"
        except (FileNotFoundError, OSError, UnicodeDecodeError):
            if os.environ.get(ENV_GPD_DEBUG):
                logger.debug("STATE.md fallback failed")
            return None, [], None


def peek_state_json(
    cwd: Path,
    integrity_mode: str = "standard",
    *,
    recover_intent: bool = True,
    surface_blocked_project_contract: bool = False,
    acquire_lock: bool = True,
) -> tuple[dict | None, list[str], str | None]:
    """Load state without persisting recovery writes.

    Callers that are only probing recoverability may set ``acquire_lock=False``
    to avoid creating lockfiles on sandboxed or read-only recent-project roots.
    """
    return _load_state_json_with_integrity_issues(
        cwd,
        integrity_mode=integrity_mode,
        persist_recovery=False,
        recover_intent=recover_intent,
        import_session_continuation_from_markdown=False,
        surface_blocked_project_contract=surface_blocked_project_contract,
        acquire_lock=acquire_lock,
    )


def _restore_visible_project_contract(
    state_obj: dict,
    raw_project_contract: object,
    *,
    project_root: Path | None = None,
) -> tuple[dict, list[str]]:
    """Restore a load-time contract that should remain visible despite load blockers."""

    if state_obj.get("project_contract") is not None or not isinstance(raw_project_contract, dict):
        return state_obj, []

    parsed = parse_project_contract_data_salvage(raw_project_contract)
    if parsed.contract is None:
        return state_obj, []

    local_grounding_errors = _collect_project_local_grounding_integrity_errors(
        parsed.contract,
        project_root=project_root,
    )

    integrity_errors = set(collect_contract_integrity_errors(parsed.contract))
    schema_blockers = [error for error in parsed.blocking_errors if error not in integrity_errors]
    if schema_blockers:
        return state_obj, []

    restored_state = dict(state_obj)
    restored_state["project_contract"] = parsed.contract.model_dump(mode="python")
    surfaced_findings = [*local_grounding_errors, *parsed.recoverable_errors, *parsed.blocking_errors]
    return restored_state, list(dict.fromkeys(surfaced_findings))


def _load_state_json_from_backup(
    bak_path: Path,
    *,
    integrity_mode: str,
    allow_project_contract_salvage: bool,
    surface_blocked_project_contract: bool,
    project_root: Path | None = None,
) -> tuple[dict | None, list[str]]:
    try:
        bak_raw = bak_path.read_text(encoding="utf-8")
        bak_parsed = json.loads(bak_raw)
        if not isinstance(bak_parsed, dict):
            raise TypeError(f"state root must be an object, got {type(bak_parsed).__name__}")
        (
            restored,
            integrity_issues,
            _recovered_root_from_backup,
            _recovered_position_from_backup,
            _recovered_continuation_from_backup,
            _recovered_session_from_backup,
        ) = _normalize_state_schema_with_backup_project_contract(
            bak_parsed,
            None,
            allow_project_contract_salvage=allow_project_contract_salvage,
            project_root=project_root,
        )
        if surface_blocked_project_contract:
            restored, restored_contract_findings = _restore_visible_project_contract(
                restored,
                bak_parsed.get("project_contract"),
                project_root=project_root,
            )
            for finding in restored_contract_findings:
                if finding not in integrity_issues:
                    integrity_issues.append(finding)
        if integrity_mode == "review" and integrity_issues:
            logger.warning("state.json backup failed review-mode integrity checks: %s", "; ".join(integrity_issues))
            return None, integrity_issues
        return restored, integrity_issues
    except (FileNotFoundError, TypeError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None, []


def _project_contract_runtime_payload_for_state(
    cwd: Path,
    *,
    state_obj: dict | None,
    state_source: str | None,
    preloaded_contract: ResearchContract | None = None,
    preloaded_load_info: dict[str, object] | None = None,
) -> tuple[dict[str, object], dict[str, object] | None, dict[str, object]]:
    """Build shared project-contract diagnostics for state-facing read paths."""

    layout = ProjectLayout(cwd)
    if state_source == "state.json":
        source_path = layout.state_json
    elif state_source == "state.json.bak":
        source_path = layout.state_json_backup
    elif state_source == "STATE.md":
        source_path = layout.state_md
    else:
        source_path = layout.state_json

    if preloaded_load_info is None:
        raw_contract: object = None
        if source_path.name in {STATE_JSON_FILENAME, STATE_JSON_BACKUP_FILENAME}:
            try:
                parsed = json.loads(source_path.read_text(encoding="utf-8"))
                if isinstance(parsed, dict):
                    raw_contract = parsed.get("project_contract")
            except (FileNotFoundError, TypeError, json.JSONDecodeError, OSError, UnicodeDecodeError):
                raw_contract = None

        contract, load_info = _classify_project_contract_payload(
            cwd=cwd,
            source_path=source_path,
            raw_contract=raw_contract,
            provenance="raw",
        )
        if contract is None and isinstance(state_obj, dict) and state_obj.get("project_contract") is not None:
            contract, load_info = _classify_project_contract_payload(
                cwd=cwd,
                source_path=source_path,
                raw_contract=state_obj.get("project_contract"),
                provenance="fallback",
            )
    else:
        contract = preloaded_contract
        load_info = {
            "status": preloaded_load_info.get("status"),
            "source_path": preloaded_load_info.get("source_path"),
            "provenance": preloaded_load_info.get("provenance"),
            "raw_project_contract_classified": bool(preloaded_load_info.get("raw_project_contract_classified")),
            "errors": list(preloaded_load_info.get("errors") or []),
            "warnings": list(preloaded_load_info.get("warnings") or []),
        }
        if isinstance(preloaded_load_info.get("approval_validation"), dict):
            load_info["approval_validation"] = dict(preloaded_load_info["approval_validation"])

    if contract is not None:
        from gpd.core.context import (
            _canonicalize_project_contract,
            _merge_active_references,
            _merge_reference_intake,
            _serialize_active_references,
        )

        active_references = _merge_active_references(_serialize_active_references(contract), [])
        effective_reference_intake = _merge_reference_intake(
            contract,
            {
                "must_read_refs": [],
                "must_include_prior_outputs": [],
                "user_asserted_anchors": [],
                "known_good_baselines": [],
                "context_gaps": [],
                "crucial_inputs": [],
            },
            active_references,
        )
        contract, canonicalization_warnings = _canonicalize_project_contract(
            contract,
            active_references=active_references,
            effective_reference_intake=effective_reference_intake,
        )
        if canonicalization_warnings:
            load_info = {
                **load_info,
                "warnings": list(dict.fromkeys([*list(load_info.get("warnings") or []), *canonicalization_warnings])),
            }

    return _finalize_project_contract_gate(cwd, contract, load_info)


@instrument_gpd_function("state.load_json")
def load_state_json(cwd: Path, integrity_mode: str = "standard") -> dict | None:
    """Load state.json with intent recovery and fallback to STATE.md.

    Returns the state dict, or None if no state exists.
    """
    state_obj, integrity_issues, _state_source = _load_state_json_with_integrity_issues(
        cwd,
        integrity_mode=integrity_mode,
        persist_recovery=True,
        import_session_continuation_from_markdown=True,
        surface_blocked_project_contract=True,
    )
    if integrity_mode == "review" and integrity_issues:
        return None
    return state_obj


def load_state_json_readonly(cwd: Path, integrity_mode: str = "standard") -> dict | None:
    """Load visible state without recovery writes or lockfile creation.

    This is the non-mutating probe path for read-only callers that need the
    same visibility as ``load_state_json`` but must not create lockfiles,
    recover intent markers, or persist normalized fallback content.
    """

    state_obj, integrity_issues, _state_source = peek_state_json(
        cwd,
        integrity_mode=integrity_mode,
        recover_intent=False,
        surface_blocked_project_contract=True,
        acquire_lock=False,
    )
    if integrity_mode == "review" and integrity_issues:
        return None
    return state_obj


def save_state_json_locked(
    cwd: Path,
    state_obj: dict,
    *,
    preserve_visible_project_contract: bool = True,
) -> None:
    """Core write logic: write state.json + regenerate STATE.md atomically.

    Caller MUST hold the canonical state lock.
    """
    _recover_intent_locked(cwd)
    normalized = _normalize_state_for_persistence(state_obj, project_root=cwd)
    preserved_contract = (
        _preserved_visible_project_contract_for_json_save(cwd, state_obj=state_obj)
        if preserve_visible_project_contract
        else None
    )
    _write_state_pair_locked(
        cwd,
        state_obj=normalized,
        md_content=generate_state_markdown(normalized),
        preserve_raw_project_contract=preserved_contract,
    )


def _preserved_visible_project_contract_for_json_save(cwd: Path, *, state_obj: dict) -> dict[str, object] | None:
    """Preserve an already-persisted visible contract across routine JSON saves.

    This guards the `load_state_json` -> mutate unrelated fields -> `save_state_json`
    path from erasing a visible-but-non-authoritative contract. Fresh writes and
    markdown-only resyncs still fail closed on malformed raw contract payloads.
    """

    candidate = state_obj.get("project_contract")
    if not isinstance(candidate, dict):
        return None

    raw_contract = _raw_persisted_project_contract(cwd)
    if not isinstance(raw_contract, dict):
        return None

    layout = ProjectLayout(cwd)
    visible_contract, load_info = _classify_project_contract_payload(
        cwd=cwd,
        source_path=layout.state_json,
        raw_contract=raw_contract,
    )
    if visible_contract is None:
        return None

    if load_info.get("status") not in {
        "blocked_integrity",
        "loaded_with_schema_normalization",
        "loaded_with_approval_blockers",
    }:
        return None

    candidate_contract, candidate_schema_findings = salvage_project_contract(candidate)
    if candidate_contract is None:
        return None
    _, candidate_schema_errors = split_project_contract_schema_findings(
        candidate_schema_findings,
        allow_case_drift_recovery=True,
    )
    if candidate_schema_errors:
        return None

    # Compare semantic contract content instead of raw dict shape so callers
    # that still hold the persisted raw payload (for example with omitted
    # defaulted arrays/scalars) do not spuriously look "changed".
    if candidate_contract.model_dump(mode="python") != visible_contract.model_dump(mode="python"):
        return None

    return visible_contract.model_dump(mode="python")


def _preserved_project_contract_for_markdown_save(
    cwd: Path,
    *,
    allow_backup_fallback_on_primary_failure: bool = True,
) -> dict[str, object] | None:
    """Return the raw persisted contract when a markdown-only save should keep it visible."""

    layout = ProjectLayout(cwd)
    try:
        existing = json.loads(layout.state_json.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        existing = None
    if isinstance(existing, dict):
        preserved = _preserved_visible_project_contract_from_raw_state(
            cwd,
            source_path=layout.state_json,
            raw_state=existing,
        )
        if preserved is not None:
            return preserved
        if existing.get("project_contract") is not None:
            return None
    elif not allow_backup_fallback_on_primary_failure:
        return None

    try:
        backup_existing = json.loads(layout.state_json_backup.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
        return None
    if not isinstance(backup_existing, dict):
        return None
    return _preserved_visible_project_contract_from_raw_state(
        cwd,
        source_path=layout.state_json_backup,
        raw_state=backup_existing,
    )


def _canonicalize_session_continuity_section(md_content: str, state_obj: dict[str, object]) -> str:
    """Rewrite the session continuity section from canonical continuation state."""

    canonical_match = re.search(
        r"(##\s*Session Continuity\s*\n[\s\S]*?)(?=\n##|$)",
        generate_state_markdown(state_obj),
        re.IGNORECASE,
    )
    if canonical_match is None:
        return md_content

    section_pattern = re.compile(
        r"(##\s*Session Continuity\s*\n)([\s\S]*?)(?=\n##|$)",
        re.IGNORECASE,
    )
    if section_pattern.search(md_content):
        return section_pattern.sub(canonical_match.group(1), md_content, count=1)
    return md_content.rstrip() + "\n\n" + canonical_match.group(1).rstrip() + "\n"


def save_state_markdown_locked(cwd: Path, md_content: str) -> dict:
    """Atomically write markdown-derived state while holding the canonical state lock."""
    _recover_intent_locked(cwd)
    preserved_contract = _preserved_project_contract_for_markdown_save(cwd)
    merged = _build_state_from_markdown(
        cwd,
        md_content,
        # Session Continuity is a compatibility mirror; markdown edits must
        # not mint canonical continuation authority on their own.
        import_session_continuation_from_markdown=False,
    )
    normalized_md_content = _canonicalize_session_continuity_section(md_content, merged)
    return _write_state_pair_locked(
        cwd,
        state_obj=merged,
        md_content=normalized_md_content,
        preserve_raw_project_contract=preserved_contract,
    )


@instrument_gpd_function("state.save")
def save_state_json(
    cwd: Path,
    state_obj: dict,
    *,
    preserve_visible_project_contract: bool = True,
) -> None:
    """Save state.json + STATE.md atomically (with locking)."""
    with _state_lock(cwd):
        save_state_json_locked(
            cwd,
            state_obj,
            preserve_visible_project_contract=preserve_visible_project_contract,
        )


@instrument_gpd_function("state.save_markdown")
def save_state_markdown(cwd: Path, md_content: str) -> dict:
    """Save STATE.md + state.json atomically from markdown content."""
    with _state_lock(cwd):
        return save_state_markdown_locked(cwd, md_content)


# ─── State Commands ────────────────────────────────────────────────────────────


@instrument_gpd_function("state.load")
def state_load(cwd: Path, integrity_mode: str = "standard") -> StateLoadResult:
    """Load full state with config and file-existence metadata."""
    preloaded_project_contract, preloaded_project_contract_load_info = _load_project_contract_for_runtime_context(cwd)
    state_obj, load_integrity_issues, state_source = _load_state_json_with_integrity_issues(
        cwd,
        integrity_mode=integrity_mode,
        persist_recovery=True,
        import_session_continuation_from_markdown=True,
        surface_blocked_project_contract=True,
    )
    validation = state_validate(cwd, integrity_mode=integrity_mode)
    combined_issues: list[str] = []
    for issue in [*load_integrity_issues, *validation.issues]:
        if issue not in combined_issues:
            combined_issues.append(issue)
    integrity_issues = list(combined_issues)
    if integrity_mode == "standard" and validation.warnings:
        for warning in validation.warnings:
            if warning not in integrity_issues:
                integrity_issues.append(warning)
    integrity_status = _integrity_status_from(
        combined_issues if integrity_mode == "review" else validation.issues,
        [*load_integrity_issues, *validation.warnings] if integrity_mode == "standard" else validation.warnings,
        integrity_mode,
    )

    layout = ProjectLayout(cwd)
    state_raw = safe_read_file(layout.state_md) or ""
    project_contract_load_info, project_contract_validation, project_contract_gate = (
        _project_contract_runtime_payload_for_state(
            cwd,
            state_obj=state_obj,
            state_source=state_source,
            preloaded_contract=preloaded_project_contract,
            preloaded_load_info=preloaded_project_contract_load_info,
        )
    )

    return StateLoadResult(
        state=state_obj or {},
        state_raw=state_raw,
        state_exists=state_obj is not None,
        roadmap_exists=layout.roadmap.exists(),
        config_exists=layout.config_json.exists(),
        integrity_mode=integrity_mode,
        integrity_status=integrity_status,
        integrity_issues=integrity_issues,
        state_source=state_source,
        project_contract_load_info=project_contract_load_info,
        project_contract_validation=project_contract_validation,
        project_contract_gate=project_contract_gate,
    )


@instrument_gpd_function("state.get")
def state_get(cwd: Path, section: str | None = None) -> StateGetResult:
    """Get full STATE.md content or a specific field/section."""
    md_path = _state_md_path(cwd)
    with _state_lock(cwd):
        content = _load_or_rebuild_state_markdown_locked(cwd)
        if content is None:
            raise StateError(f"STATE.md not found at {md_path}. Run 'gpd init' to create the project state file.")

    if not section:
        return StateGetResult(content=content)

    section_norm = section.replace("_", " ").strip()
    if section_norm.casefold() in {"session", "continuation", "handoff"}:
        state_obj = load_state_json_readonly(cwd)
        if isinstance(state_obj, dict):
            canonical_value: object | None
            if section_norm.casefold() == "session":
                canonical_value = state_obj.get("session")
            elif section_norm.casefold() == "continuation":
                canonical_value = state_obj.get("continuation")
            else:
                continuation = state_obj.get("continuation")
                canonical_value = continuation.get("handoff") if isinstance(continuation, dict) else None
            if canonical_value is not None:
                return StateGetResult(
                    value=json.dumps(canonical_value, indent=2),
                    section_name=section,
                )

    # Try **field:** value
    field_escaped = re.escape(section_norm)
    field_match = re.search(rf"\*\*{field_escaped}:\*\*\s*(.*)", content, re.IGNORECASE)
    if field_match:
        return StateGetResult(value=field_match.group(1).strip(), section_name=section)

    # Try ## Section
    section_match = re.search(rf"##\s*{field_escaped}\s*\n([\s\S]*?)(?=\n##|$)", content, re.IGNORECASE)
    if section_match:
        return StateGetResult(value=section_match.group(1).strip(), section_name=section)

    return StateGetResult(error=f'Section or field "{section}" not found')


@instrument_gpd_function("state.update")
def state_update(cwd: Path, field: str, value: str) -> StateUpdateResult:
    """Update a single **Field:** in STATE.md."""
    if not field or value is None:
        raise StateError(
            f"Both field and value are required for state update, got field={field!r}, value={value!r}. "
            "Usage: state_update(cwd, field='Status', value='in-progress')"
        )

    # Validate status values
    if field.lower() == "status" and not is_valid_status(value):
        return StateUpdateResult(
            updated=False,
            reason=f'Invalid status: "{value}". Valid: {", ".join(VALID_STATUSES)}',
        )

    with _state_lock(cwd):
        _recover_intent_locked(cwd)
        content = _load_or_rebuild_state_markdown_locked(cwd)
        if content is None:
            return StateUpdateResult(updated=False, reason="STATE.md not found")
        field_norm = field.replace("_", " ")  # TODO(FULL-017): Apply dot-notation stripping here too

        # Validate state transitions
        if field_norm.lower() == "status":
            current_status = state_extract_field(content, "Status")
            if current_status:
                err = validate_state_transition(current_status, value)
                if err:
                    return StateUpdateResult(updated=False, reason=err)

        if not state_has_field(content, field_norm):
            return StateUpdateResult(updated=False, reason=f'Field "{field}" not found in STATE.md')

        new_content = state_replace_field(content, field_norm, value)
        if new_content == content:
            return StateUpdateResult(updated=False, reason=f'Field "{field}" already has the requested value')

        _write_state_markdown_locked(cwd, new_content)
        return StateUpdateResult(updated=True)


@instrument_gpd_function("state.patch")
def state_patch(cwd: Path, patches: dict[str, str]) -> StatePatchResult:
    """Batch-update multiple **Field:** values in STATE.md."""
    md_path = _state_md_path(cwd)

    with _state_lock(cwd):
        _recover_intent_locked(cwd)
        content = _load_or_rebuild_state_markdown_locked(cwd)
        if content is None:
            raise StateError(
                f"STATE.md not found at {md_path}. Run 'gpd init' to create the project state file before patching."
            )
        updated: list[str] = []
        failed: list[str] = []
        failure_reasons: dict[str, str] = {}

        # Session Continuity fields are non-authoritative mirrors in STATE.md —
        # save_state_markdown_locked() regenerates this section from state.json,
        # so patching these fields via markdown replacement is silently a no-op.
        # Keep in sync with generate_state_markdown() L2716-2724.
        _session_mirror = frozenset({
            "last session", "stopped at", "resume file",
            "last result id", "hostname", "platform",
        })

        for field, value in patches.items():
            # --- Three-phase field resolution ---
            # Phase 1: try the raw input exactly as given
            field_norm = field
            found = state_has_field(content, field_norm)
            also_tried: list[str] = []

            # Phase 2: try underscore → space normalization
            if not found:
                underscore_form = field.replace("_", " ")
                if underscore_form != field:
                    also_tried.append(underscore_form)
                    found = state_has_field(content, underscore_form)
                    if found:
                        field_norm = underscore_form

            # Phase 3: dot-prefix stripping (on the best candidate so far)
            if not found and "." in field:
                # Strip from the raw field first (preserves underscores)
                stripped_raw = field.rsplit(".", 1)[-1]
                also_tried.append(stripped_raw)
                found = state_has_field(content, stripped_raw)
                if found:
                    field_norm = stripped_raw
                else:
                    # Also try underscore-replaced + stripped
                    stripped_norm = field.replace("_", " ").rsplit(".", 1)[-1]
                    if stripped_norm != stripped_raw:
                        also_tried.append(stripped_norm)
                        found = state_has_field(content, stripped_norm)
                        if found:
                            field_norm = stripped_norm

            # Guard: reject Session Continuity mirror fields — they are
            # regenerated from state.json on save, so markdown patches are no-ops.
            if found and field_norm.lower() in _session_mirror:
                failed.append(field)
                failure_reasons[field] = (
                    f'Field "{field_norm}" is a Session Continuity mirror field '
                    f"that is regenerated from state.json on save. "
                    f"Use the continuation API to update session state."
                )
                continue

            if field_norm.lower() == "status" and not is_valid_status(value):
                failed.append(field)
                failure_reasons[field] = (
                    f'Invalid status: "{value}". Valid: {", ".join(VALID_STATUSES)}'
                )
                continue

            if field_norm.lower() == "status":
                current_status = state_extract_field(content, "Status")
                if current_status:
                    err = validate_state_transition(current_status, value)
                    if err:
                        failed.append(field)
                        failure_reasons[field] = err
                        continue

            if found:
                content = state_replace_field(content, field_norm, value)
                updated.append(field)
            else:
                failed.append(field)
                if also_tried:
                    tried_str = ", ".join(f'"{t}"' for t in also_tried)
                    failure_reasons[field] = (
                        f'Field "{field}" not found in STATE.md'
                        f" (also tried {tried_str})"
                    )
                else:
                    failure_reasons[field] = f'Field "{field}" not found in STATE.md'

        if updated:
            _write_state_markdown_locked(cwd, content)

    return StatePatchResult(updated=updated, failed=failed, failure_reasons=failure_reasons)


@instrument_gpd_function("state.set_project_contract")
def state_set_project_contract(cwd: Path, contract_data: dict[str, object] | ResearchContract) -> StateUpdateResult:
    """Persist the canonical project contract to ``state.json``.

    This is a JSON-only state field, so it bypasses ``STATE.md`` field patching and
    writes through the authoritative structured state path instead. Unlike
    ``ensure_state_schema()``, this write path rejects authored schema
    normalization drift instead of silently salvaging it. Draft-valid contracts
    that still fail approval validation are persisted with explicit warnings so
    downstream runtime/init loaders can surface them as visible but
    non-authoritative. Read/repair flows can still canonicalize historical
    state through ``ensure_state_schema()`` and the backup recovery path.
    """
    warning_messages: list[str] = []

    def _failure(reason: str, *, schema_reference: str = "templates/project-contract-schema.md") -> StateUpdateResult:
        return StateUpdateResult(
            updated=False,
            reason=reason,
            warnings=list(warning_messages),
            schema_reference=schema_reference,
        )

    try:
        # Treat model instances like serialized payloads so schema drift is
        # checked through the same strict path as JSON/dict input.
        if isinstance(contract_data, ResearchContract):
            contract_payload = contract_data.model_dump(mode="python", warnings=False)
        elif isinstance(contract_data, dict):
            contract_payload = contract_data
        else:
            return _failure("Invalid project contract schema: project contract must be a JSON object")
        strict_result: ProjectContractParseResult = parse_project_contract_data_strict(contract_payload)
        if strict_result.errors:
            return _failure(
                "Invalid project contract schema: " + "; ".join(strict_result.errors),
                schema_reference=_project_contract_schema_reference_for_errors(strict_result.errors),
            )
        parsed = strict_result.contract
        if parsed is None:
            return _failure("Invalid project contract schema: project contract could not be normalized")
    except PydanticValidationError as exc:
        first_error = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(part) for part in first_error.get("loc", ())) or "project_contract"
        message = first_error.get("msg", "validation failed")
        return _failure(f"Invalid project contract at {location}: {message}")

    draft_validation = validate_project_contract(parsed, mode="draft", project_root=cwd)
    if not draft_validation.valid:
        for warning in draft_validation.warnings:
            if warning not in warning_messages:
                warning_messages.append(warning)
        return _failure(
            "Project contract failed scoping validation: " + "; ".join(draft_validation.errors),
            schema_reference=_project_contract_schema_reference_for_errors(draft_validation.errors),
        )
    for warning in draft_validation.warnings:
        if warning not in warning_messages:
            warning_messages.append(warning)

    approval_validation = validate_project_contract(parsed, mode="approved", project_root=cwd)
    if not approval_validation.valid:
        for warning in approval_validation.warnings:
            if warning not in warning_messages:
                warning_messages.append(warning)
        warning_messages.extend(
            f"approval blocker: {error}"
            for error in approval_validation.errors
            if f"approval blocker: {error}" not in warning_messages
        )
    for warning in approval_validation.warnings:
        if warning not in warning_messages:
            warning_messages.append(warning)

    contract_payload = parsed.model_dump()
    if _raw_persisted_project_contract(cwd) == contract_payload:
        return StateUpdateResult(
            updated=False,
            unchanged=True,
            reason="Project contract already matches requested value",
            warnings=warning_messages,
        )

    with _state_lock(cwd):
        _recover_intent_locked(cwd)
        state_obj = _load_state_snapshot_for_mutation(cwd, recover_intent=False)

        state_obj["project_contract"] = contract_payload

        unresolved = [
            question.strip() for question in parsed.scope.unresolved_questions if question and question.strip()
        ]
        if unresolved:
            existing_questions = {
                item.strip() for item in state_obj.get("open_questions", []) if isinstance(item, str) and item.strip()
            }
            for question in unresolved:
                if question not in existing_questions:
                    state_obj.setdefault("open_questions", []).append(question)
                    existing_questions.add(question)

        save_state_json_locked(cwd, state_obj, preserve_visible_project_contract=False)
        return StateUpdateResult(updated=True, warnings=warning_messages)


@instrument_gpd_function("state.set_continuation_bounded_segment")
def state_set_continuation_bounded_segment(
    cwd: Path,
    bounded_segment: dict[str, object] | ContinuationBoundedSegment,
) -> StateUpdateResult:
    """Persist the canonical continuation bounded_segment to state.json only."""
    if isinstance(bounded_segment, ContinuationBoundedSegment):
        bounded_segment_payload = bounded_segment.model_dump(mode="python")
    elif isinstance(bounded_segment, dict):
        bounded_segment_payload = bounded_segment
    else:
        return StateUpdateResult(
            updated=False,
            reason="Invalid continuation bounded_segment schema: bounded_segment must be a JSON object",
        )

    normalized_segment, normalization_issues = normalize_continuation_bounded_segment_with_issues(
        cwd,
        bounded_segment_payload,
    )
    if normalization_issues:
        return StateUpdateResult(
            updated=False,
            reason="Invalid continuation bounded_segment schema: " + "; ".join(dict.fromkeys(normalization_issues)),
        )
    if normalized_segment is None or normalized_segment.is_empty:
        return StateUpdateResult(
            updated=False,
            reason="Invalid continuation bounded_segment schema: bounded_segment must include at least one non-empty field",
        )

    with _state_lock(cwd):
        _recover_intent_locked(cwd)
        state_obj = _load_state_snapshot_for_mutation(cwd, recover_intent=False)
        current_continuation = normalize_continuation(cwd, state_obj.get("continuation")).model_dump(mode="python")
        desired_continuation = normalize_continuation(
            cwd,
            {
                **current_continuation,
                "bounded_segment": normalized_segment.model_dump(mode="python"),
            },
        ).model_dump(mode="python")

        if current_continuation.get("bounded_segment") == desired_continuation.get("bounded_segment"):
            return StateUpdateResult(
                updated=False, reason="Continuation bounded_segment already matches requested value"
            )

        state_obj["continuation"] = desired_continuation
        save_state_json_locked(cwd, state_obj)
        return StateUpdateResult(updated=True)


@instrument_gpd_function("state.carry_forward_continuation_last_result_id")
def state_carry_forward_continuation_last_result_id(
    cwd: Path,
    last_result_id: str,
    *,
    state_obj: dict[str, object] | None = None,
) -> StateUpdateResult:
    """Carry a canonical result ID into continuation state without session-boundary metadata."""

    requested_last_result_id = _optional_state_text(last_result_id)
    if requested_last_result_id is None:
        return StateUpdateResult(updated=False, reason="last_result_id must be a non-empty string when provided")

    def _apply(loaded_state_obj: dict[str, object]) -> StateUpdateResult:
        if not _state_has_canonical_result_id(loaded_state_obj, requested_last_result_id):
            return StateUpdateResult(
                updated=False,
                reason=(
                    f'last_result_id "{requested_last_result_id}" does not match any canonical result in '
                    "intermediate_results"
                ),
            )

        current_continuation = normalize_continuation(
            cwd,
            loaded_state_obj.get("continuation"),
        ).model_dump(mode="python")
        current_handoff = current_continuation.get("handoff")
        current_bounded_segment = current_continuation.get("bounded_segment")
        if not isinstance(current_handoff, dict):
            current_handoff = {}
        if not isinstance(current_bounded_segment, dict):
            return StateUpdateResult(updated=False, reason="Canonical continuation bounded_segment not found")

        desired_continuation = normalize_continuation(
            cwd,
            {
                **current_continuation,
                "handoff": {
                    **current_handoff,
                    "last_result_id": requested_last_result_id,
                },
                "bounded_segment": {
                    **current_bounded_segment,
                    "last_result_id": requested_last_result_id,
                },
            },
        ).model_dump(mode="python")

        if current_continuation == desired_continuation:
            return StateUpdateResult(
                updated=False,
                reason="Continuation last_result_id already matches requested value",
            )

        loaded_state_obj["continuation"] = desired_continuation
        loaded_state_obj["session"] = _session_from_continuation_payload(desired_continuation)
        return StateUpdateResult(updated=True)

    if state_obj is not None:
        return _apply(state_obj)

    with _state_lock(cwd):
        _recover_intent_locked(cwd)
        loaded_state_obj = _load_state_snapshot_for_mutation(cwd, recover_intent=False)
        result = _apply(loaded_state_obj)
        if result.updated:
            save_state_json_locked(cwd, loaded_state_obj)
        return result


@instrument_gpd_function("state.clear_continuation_bounded_segment")
def state_clear_continuation_bounded_segment(cwd: Path) -> StateUpdateResult:
    """Clear the canonical continuation bounded_segment in state.json only."""

    with _state_lock(cwd):
        _recover_intent_locked(cwd)
        state_obj = _load_state_snapshot_for_mutation(cwd, recover_intent=False)
        current_continuation = normalize_continuation(cwd, state_obj.get("continuation")).model_dump(mode="python")

        if current_continuation.get("bounded_segment") is None:
            return StateUpdateResult(updated=False, reason="Continuation bounded_segment already clear")

        desired_continuation = normalize_continuation(
            cwd,
            {
                **current_continuation,
                "bounded_segment": None,
            },
        ).model_dump(mode="python")
        state_obj["continuation"] = desired_continuation
        state_obj["session"] = _session_from_continuation_payload(desired_continuation)
        save_state_json_locked(cwd, state_obj)
        return StateUpdateResult(updated=True)


@instrument_gpd_function("state.advance_plan")
def state_advance_plan(cwd: Path) -> AdvancePlanResult:
    """Advance to the next plan, or mark phase complete if on last plan."""
    with _state_lock(cwd):
        _recover_intent_locked(cwd)
        content = _load_or_rebuild_state_markdown_locked(cwd)
        if content is None:
            return AdvancePlanResult(advanced=False, error="STATE.md not found")
        current_plan_raw = state_extract_field(content, "Current Plan")
        total_plans_raw = state_extract_field(content, "Total Plans in Phase")

        current_plan = safe_parse_int(current_plan_raw, None)
        total_plans = safe_parse_int(total_plans_raw, None)

        if current_plan is None or total_plans is None:
            return AdvancePlanResult(
                advanced=False, error="Cannot parse Current Plan or Total Plans in Phase from STATE.md"
            )

        today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        current_status = state_extract_field(content, "Status") or ""

        if current_plan >= total_plans:
            transition_error = validate_state_transition(current_status, "Phase complete \u2014 ready for verification")
            if transition_error:
                return AdvancePlanResult(advanced=False, error=transition_error)
            content = state_replace_field(content, "Status", "Phase complete \u2014 ready for verification")
            content = state_replace_field(content, "Last Activity", today)
            _write_state_markdown_locked(cwd, content)
            return AdvancePlanResult(
                advanced=False,
                reason="last_plan",
                current_plan=current_plan,
                total_plans_in_phase=total_plans,
                status="ready_for_verification",
            )

        new_plan = current_plan + 1
        content = state_replace_field(content, "Current Plan", str(new_plan))
        transition_error = validate_state_transition(current_status, "Ready to execute")
        if transition_error:
            return AdvancePlanResult(advanced=False, error=transition_error)
        content = state_replace_field(content, "Status", "Ready to execute")
        content = state_replace_field(content, "Last Activity", today)
        _write_state_markdown_locked(cwd, content)
        return AdvancePlanResult(
            advanced=True,
            previous_plan=current_plan,
            current_plan=new_plan,
            total_plans_in_phase=total_plans,
        )


@instrument_gpd_function("state.record_metric")
def state_record_metric(
    cwd: Path,
    *,
    phase: str | None = None,
    plan: str | None = None,
    duration: str | None = None,
    tasks: str | None = None,
    files: str | None = None,
) -> RecordMetricResult:
    """Record a performance metric in STATE.md."""
    if not phase or not plan or not duration:
        return RecordMetricResult(recorded=False, error="phase, plan, and duration required")

    with _state_lock(cwd):
        _recover_intent_locked(cwd)
        content = _load_or_rebuild_state_markdown_locked(cwd)
        if content is None:
            return RecordMetricResult(recorded=False, error="STATE.md not found")

        pattern = re.compile(
            r"(##\s*Performance Metrics[\s\S]*?\n\|[^\n]+\n\|[-|\s]+\n)([\s\S]*?)(?=\n##|\n$|$)",
            re.IGNORECASE,
        )
        match = pattern.search(content)

        if not match:
            return RecordMetricResult(recorded=False, reason="Performance Metrics section not found in STATE.md")

        table_header = match.group(1)
        table_body = match.group(2).rstrip()
        new_row = f"| Phase {phase} P{plan} | {duration} | {tasks or '-'} tasks | {files or '-'} files |"

        if not table_body.strip() or "None yet" in table_body or re.match(r"^\|\s*-\s*\|", table_body.strip()):
            table_body = new_row
        else:
            table_body = table_body + "\n" + new_row

        new_content = pattern.sub(lambda _: f"{table_header}{table_body}\n", content, count=1)
        _write_state_markdown_locked(cwd, new_content)
        return RecordMetricResult(recorded=True, phase=phase, plan=plan, duration=duration)


@instrument_gpd_function("state.update_progress")
def state_update_progress(cwd: Path) -> UpdateProgressResult:
    """Recalculate progress from plan/summary counts across all phases."""
    with _state_lock(cwd):
        _recover_intent_locked(cwd)
        content = _load_or_rebuild_state_markdown_locked(cwd)
        if content is None:
            return UpdateProgressResult(updated=False, error="STATE.md not found")

        phases_dir = ProjectLayout(cwd).phases_dir
        total_plans = 0
        total_completed = 0

        if phases_dir.exists():
            for phase_dir in phases_dir.iterdir():
                if not phase_dir.is_dir():
                    continue
                phase_files = [f.name for f in phase_dir.iterdir() if f.is_file()]
                phase_plans = [f for f in phase_files if f.endswith("-PLAN.md") or f == "PLAN.md"]
                phase_summaries = [f for f in phase_files if f.endswith("-SUMMARY.md") or f == "SUMMARY.md"]
                total_plans += len(phase_plans)
                total_completed += matching_phase_artifact_count(phase_plans, phase_summaries)

        percent = min(100, round((total_completed / total_plans) * 100)) if total_plans > 0 else 0
        bar_width = 10
        filled = max(0, min(bar_width, round((percent / 100) * bar_width)))
        bar = "\u2588" * filled + "\u2591" * (bar_width - filled)
        progress_str = f"[{bar}] {percent}%"

        progress_pattern = re.compile(r"(\*\*Progress:\*\*\s*)(.*)", re.IGNORECASE)
        if progress_pattern.search(content):
            new_content = progress_pattern.sub(lambda m: m.group(1) + progress_str, content, count=1)
            _write_state_markdown_locked(cwd, new_content)
            return UpdateProgressResult(
                updated=True,
                percent=percent,
                completed=total_completed,
                total=total_plans,
                bar=progress_str,
            )

        return UpdateProgressResult(updated=False, reason="Progress field not found in STATE.md")


@instrument_gpd_function("state.add_decision")
def state_add_decision(
    cwd: Path,
    *,
    summary: str | None = None,
    phase: str | None = None,
    rationale: str | None = None,
) -> AddDecisionResult:
    """Add a decision to STATE.md."""
    if not summary:
        return AddDecisionResult(added=False, error="summary required")

    summary_clean = summary.replace("\n", " ").strip()
    rat_str = f" \u2014 {rationale.replace(chr(10), ' ').strip()}" if rationale else ""
    entry = f"- [Phase {phase or '?'}]: {summary_clean}{rat_str}"

    with _state_lock(cwd):
        _recover_intent_locked(cwd)
        content = _load_or_rebuild_state_markdown_locked(cwd)
        if content is None:
            return AddDecisionResult(added=False, error="STATE.md not found")
        pattern = re.compile(
            r"(###?\s*Decisions\s*\n)([\s\S]*?)(?=\n###?|\n##[^#]|$)",
            re.IGNORECASE,
        )
        match = pattern.search(content)

        if not match:
            return AddDecisionResult(added=False, reason="Decisions section not found in STATE.md")

        section_body = match.group(2)
        section_body = re.sub(r"^None yet\.?\s*$", "", section_body, flags=re.MULTILINE | re.IGNORECASE)
        section_body = section_body.rstrip() + "\n" + entry + "\n"

        new_content = pattern.sub(lambda _: f"{match.group(1)}{section_body}", content, count=1)
        _write_state_markdown_locked(cwd, new_content)
        return AddDecisionResult(added=True, decision=entry)


@instrument_gpd_function("state.add_blocker")
def state_add_blocker(cwd: Path, text: str) -> AddBlockerResult:
    """Add a blocker to STATE.md."""
    if not text:
        return AddBlockerResult(added=False, error="text required")

    text_clean = text.replace("\n", " ").strip()
    entry = f"- {text_clean}"

    with _state_lock(cwd):
        _recover_intent_locked(cwd)
        content = _load_or_rebuild_state_markdown_locked(cwd)
        if content is None:
            return AddBlockerResult(added=False, error="STATE.md not found")
        pattern = re.compile(
            r"(###?\s*Blockers/Concerns\s*\n)([\s\S]*?)(?=\n###?|\n##[^#]|$)",
            re.IGNORECASE,
        )
        match = pattern.search(content)

        if not match:
            return AddBlockerResult(added=False, reason="Blockers section not found in STATE.md")

        section_body = match.group(2)
        section_body = re.sub(r"^None\.?\s*$", "", section_body, flags=re.MULTILINE | re.IGNORECASE)
        section_body = re.sub(r"^None yet\.?\s*$", "", section_body, flags=re.MULTILINE | re.IGNORECASE)
        section_body = section_body.rstrip() + "\n" + entry + "\n"

        new_content = pattern.sub(lambda _: f"{match.group(1)}{section_body}", content, count=1)
        _write_state_markdown_locked(cwd, new_content)
        return AddBlockerResult(added=True, blocker=text)


@instrument_gpd_function("state.resolve_blocker")
def state_resolve_blocker(cwd: Path, text: str) -> ResolveBlockerResult:
    """Resolve (remove) a blocker from STATE.md."""
    if not text:
        return ResolveBlockerResult(resolved=False, error="text required")
    if len(text) < 3:
        return ResolveBlockerResult(
            resolved=False, error="search text must be at least 3 characters to avoid accidental matches"
        )

    with _state_lock(cwd):
        _recover_intent_locked(cwd)
        content = _load_or_rebuild_state_markdown_locked(cwd)
        if content is None:
            return ResolveBlockerResult(resolved=False, error="STATE.md not found")
        pattern = re.compile(
            r"(###?\s*Blockers/Concerns\s*\n)([\s\S]*?)(?=\n###?|\n##[^#]|$)",
            re.IGNORECASE,
        )
        match = pattern.search(content)

        if not match:
            return ResolveBlockerResult(resolved=False, reason="Blockers section not found in STATE.md")

        section_lines = match.group(2).split("\n")
        text_lower = text.lower()

        # Find matching blocker: exact match first, then word-boundary regex
        remove_idx = -1
        for i, line in enumerate(section_lines):
            if not line.startswith("- "):
                continue
            bullet_text = line[2:].strip()
            if bullet_text.lower() == text_lower:
                remove_idx = i
                break

        if remove_idx == -1:
            escaped = re.escape(text)
            word_pattern = re.compile(rf"\b{escaped}(?=\s|[),;:\]!?]|$)", re.IGNORECASE)
            for i, line in enumerate(section_lines):
                if not line.startswith("- "):
                    continue
                if word_pattern.search(line):
                    remove_idx = i
                    break

        if remove_idx != -1:
            section_lines.pop(remove_idx)

        new_body = "\n".join(section_lines)
        if not new_body.strip() or "- " not in new_body:
            new_body = "None\n"

        new_content = pattern.sub(lambda _: f"{match.group(1)}{new_body}", content, count=1)

        if remove_idx != -1:
            _write_state_markdown_locked(cwd, new_content)
            return ResolveBlockerResult(resolved=True, blocker=text)

        return ResolveBlockerResult(resolved=False, blocker=text, reason="no match found")


def _normalize_session_resume_file(cwd: Path, resume_file: str | None) -> str | None:
    """Normalize project-local absolute resume pointers back to repo-relative form."""
    if resume_file is None:
        return None

    normalized = resume_file.strip()
    if (
        not normalized
        or normalized == EM_DASH
        or normalized == "[Not set]"
        or normalized.casefold() in {"none", "null"}
    ):
        return None
    return normalize_continuation_reference(cwd, normalized)


@instrument_gpd_function("state.record_session")
def state_record_session(
    cwd: Path,
    *,
    stopped_at: str | None = None,
    resume_file: str | None = None,
    last_result_id: str | None = None,
    clear_resume_file: bool = False,
    clear_last_result_id: bool = False,
) -> RecordSessionResult:
    """Record session continuity through canonical continuation state."""
    with _state_lock(cwd):
        _recover_intent_locked(cwd)
        state_obj, _integrity_issues, state_source = _load_state_json_with_integrity_issues(
            cwd,
            persist_recovery=False,
            recover_intent=False,
            import_session_continuation_from_markdown=True,
            acquire_lock=False,
        )
        if not isinstance(state_obj, dict) or state_source is None:
            return RecordSessionResult(recorded=False, error="State not found")
        now = datetime.now(tz=UTC).isoformat()
        machine = _current_machine_identity()
        current_continuation = normalize_continuation(
            cwd,
            state_obj.get("continuation"),
        )
        existing_handoff = current_continuation.handoff
        existing_machine = current_continuation.machine
        normalized_existing_resume_file = _normalize_session_resume_file(cwd, existing_handoff.resume_file)
        normalized_resume_file = (
            None
            if clear_resume_file
            else (
                normalized_existing_resume_file
                if resume_file is None
                else _normalize_session_resume_file(cwd, resume_file)
            )
        )
        if (
            not clear_resume_file
            and
            resume_file is not None
            and normalized_resume_file is None
            and resume_file.strip()
            and resume_file.strip() not in {EM_DASH, "[Not set]"}
            and resume_file.strip().casefold() not in {"none", "null"}
        ):
            raise StateError("resume_file must be a repo-relative path inside the project root")
        requested_last_result_id = (
            None
            if clear_last_result_id
            else (_optional_state_text(last_result_id) if last_result_id is not None else None)
        )
        if last_result_id is not None:
            if requested_last_result_id is None:
                raise StateError("last_result_id must be a non-empty string when provided")
            if not _state_has_canonical_result_id(state_obj, requested_last_result_id):
                raise StateError(
                    f'last_result_id "{requested_last_result_id}" does not match any canonical result in intermediate_results'
                )
        current_bounded_segment = current_continuation.bounded_segment
        bounded_segment_last_result_id = (
            _optional_state_text(current_bounded_segment.last_result_id)
            if current_bounded_segment is not None
            else None
        )
        if bounded_segment_last_result_id is not None and not _state_has_canonical_result_id(
            state_obj, bounded_segment_last_result_id
        ):
            bounded_segment_last_result_id = None
        updated: list[str] = []

        updated.append("Last session")
        if machine["hostname"] != existing_machine.hostname:
            updated.append("Hostname")
        if machine["platform"] != existing_machine.platform:
            updated.append("Platform")
        desired_stopped_at = stopped_at if stopped_at is not None else existing_handoff.stopped_at
        desired_last_result_id = (
            None
            if clear_last_result_id
            else (
                requested_last_result_id
                if last_result_id is not None
                else bounded_segment_last_result_id or _optional_state_text(existing_handoff.last_result_id)
            )
        )
        if desired_stopped_at != existing_handoff.stopped_at:
            updated.append("Stopped at")
        if (normalized_resume_file or EM_DASH) != (existing_handoff.resume_file or EM_DASH):
            updated.append("Resume file")
        if (desired_last_result_id or EM_DASH) != (existing_handoff.last_result_id or EM_DASH):
            updated.append("Last result ID")

        if updated:
            updated_continuation = current_continuation.model_copy(
                update={
                    "handoff": current_continuation.handoff.model_copy(
                        update={
                            "recorded_at": now,
                            "stopped_at": desired_stopped_at,
                            "resume_file": normalized_resume_file,
                            "last_result_id": desired_last_result_id,
                            "recorded_by": "state_record_session",
                        }
                    ),
                    "machine": current_continuation.machine.model_copy(
                        update={
                            "recorded_at": now,
                            "hostname": machine["hostname"],
                            "platform": machine["platform"],
                        }
                    ),
                }
            ).model_dump(mode="python")
            state_obj["continuation"] = updated_continuation
            state_obj["session"] = _session_from_continuation_payload(updated_continuation)
            save_state_json_locked(cwd, state_obj)
            with gpd_span(
                "session.continuity.recorded",
                cwd=str(cwd),
                updated_fields=",".join(updated),
                stopped_at=desired_stopped_at or "",
                resume_file=normalized_resume_file or EM_DASH,
                last_result_id=desired_last_result_id or EM_DASH,
                hostname=machine["hostname"] or EM_DASH,
                platform=machine["platform"] or EM_DASH,
            ):
                pass
            return RecordSessionResult(recorded=True, updated=updated)

        with gpd_span(
            "session.continuity.noop",
            cwd=str(cwd),
            stopped_at=stopped_at or "",
            resume_file=normalized_resume_file or EM_DASH,
            last_result_id=desired_last_result_id or EM_DASH,
            hostname=machine["hostname"] or EM_DASH,
            platform=machine["platform"] or EM_DASH,
        ):
            pass
        return RecordSessionResult(recorded=False, reason="No session fields found in STATE.md")


@instrument_gpd_function("state.snapshot")
def state_snapshot(cwd: Path) -> StateSnapshotResult:
    """Fast snapshot of state for progress/routing commands."""
    state_obj, _issues, _state_source = peek_state_json(cwd, recover_intent=False)
    if state_obj is None:
        return StateSnapshotResult(error="STATE.md not found")

    pos = state_obj.get("position")
    if not isinstance(pos, dict):
        pos = {}
    cp = pos.get("current_phase")
    return StateSnapshotResult(
        current_phase=phase_normalize(str(cp)) if cp is not None else None,
        current_phase_name=pos.get("current_phase_name"),
        total_phases=pos.get("total_phases"),
        current_plan=str(pos["current_plan"]) if pos.get("current_plan") is not None else None,
        total_plans_in_phase=pos.get("total_plans_in_phase"),
        status=pos.get("status"),
        progress_percent=pos.get("progress_percent"),
        last_activity=pos.get("last_activity"),
        last_activity_desc=pos.get("last_activity_desc"),
        decisions=state_obj.get("decisions"),
        blockers=state_obj.get("blockers"),
        paused_at=pos.get("paused_at"),
        session=state_obj.get("session"),
    )


# ─── Validate ──────────────────────────────────────────────────────────────────


@instrument_gpd_function("state.validate")
def state_validate(
    cwd: Path,
    integrity_mode: str = "standard",
    *,
    recover_intent: bool = True,
) -> StateValidateResult:
    """Validate state consistency between state.json and STATE.md."""
    from gpd.core.contract_validation import validate_project_contract

    md_path = _state_md_path(cwd)
    issues: list[str] = []
    warnings: list[str] = []

    state_json, normalization_issues, state_source = peek_state_json(
        cwd,
        integrity_mode=integrity_mode,
        recover_intent=recover_intent,
    )
    if normalization_issues:
        parse_issues = [issue for issue in normalization_issues if issue.startswith("state.json parse error:")]
        other_issues = [issue for issue in normalization_issues if not issue.startswith("state.json parse error:")]
        if parse_issues:
            parse_target = warnings if integrity_mode == "standard" and state_source == "state.json.bak" else issues
            parse_target.extend(parse_issues)
        if other_issues:
            target = issues if integrity_mode == "review" else warnings
            target.extend(other_issues)
    elif state_json is None:
        issues.append("state.json not found")

    # Load and parse STATE.md
    state_md = None
    try:
        content = md_path.read_text(encoding="utf-8")
        issues.extend(_state_markdown_structure_issues(content))
        state_md = parse_state_to_json(content, import_legacy_session=False)
    except FileNotFoundError:
        issues.append("STATE.md not found")
    except (OSError, UnicodeDecodeError) as e:
        issues.append(f"STATE.md parse error: {e}")

    if not state_json and not state_md:
        return StateValidateResult(
            valid=False,
            issues=issues,
            warnings=warnings,
            integrity_mode=integrity_mode,
            integrity_status=_integrity_status_from(issues, warnings, integrity_mode),
            state_source=state_source,
        )

    if isinstance(state_json, dict) and state_json.get("project_contract") is not None:
        contract_payload = state_json.get("project_contract")
        contract_validation_mode = "approved" if integrity_mode == "review" else "draft"
        contract_validation = validate_project_contract(
            contract_payload,
            mode=contract_validation_mode,
            project_root=cwd,
        )
        if contract_validation.errors:
            issues.extend(f"project_contract: {error}" for error in contract_validation.errors)
        if contract_validation.warnings:
            warnings.extend(f"project_contract: {warning}" for warning in contract_validation.warnings)
        if integrity_mode != "review":
            approval_validation = validate_project_contract(contract_payload, mode="approved", project_root=cwd)
            for error in approval_validation.errors:
                warning = f"project_contract: {error}"
                if warning not in warnings and warning not in issues:
                    warnings.append(warning)
            for warning_text in approval_validation.warnings:
                warning = f"project_contract: {warning_text}"
                if warning not in warnings:
                    warnings.append(warning)

    if isinstance(state_json, dict) and isinstance(state_md, dict) and state_source != "state.json.bak":
        issues.extend(_state_md_mirror_mismatches(state_json, state_md))

    json_pos = state_json.get("position") if isinstance(state_json, dict) else None

    # Convention lock completeness
    if state_json and isinstance(state_json.get("convention_lock"), dict):
        cl = state_json["convention_lock"]
        set_fields = [k for k in KNOWN_CONVENTIONS if not is_bogus_value(cl.get(k))]
        unset = [k for k in KNOWN_CONVENTIONS if is_bogus_value(cl.get(k))]
        if set_fields and unset:
            warnings.append(f"convention_lock: {len(unset)} conventions unset ({', '.join(unset)})")

    # NaN in numeric fields
    if isinstance(json_pos, dict):
        for field in ("total_phases", "total_plans_in_phase", "progress_percent"):
            val = json_pos.get(field)
            if val is not None and isinstance(val, float) and val != val:
                issues.append(f"position.{field} is NaN")

    # Status vocabulary
    if isinstance(json_pos, dict) and json_pos.get("status"):
        if not is_valid_status(str(json_pos["status"])):
            warnings.append(f'position.status "{json_pos["status"]}" is not a recognized status')

    # Schema completeness
    if state_json:
        if "position" not in state_json:
            issues.append('schema: missing required section "position" in state.json')
        for section in (
            "decisions",
            "blockers",
            "session",
            "continuation",
            "convention_lock",
            "approximations",
            "propagated_uncertainties",
        ):
            if section not in state_json:
                warnings.append(f'schema: missing section "{section}" in state.json (will be auto-created)')

    # Phase range validation
    if isinstance(json_pos, dict):
        cp = json_pos.get("current_phase")
        tp = json_pos.get("total_phases")
        if cp is not None and tp is not None:
            current_num = safe_parse_int(cp, None)
            total_num = safe_parse_int(tp, None)
            if current_num is not None and total_num is not None:
                if current_num > total_num:
                    issues.append(f"position: current_phase ({cp}) exceeds total_phases ({tp})")
                if current_num < 0:
                    issues.append(f"position: current_phase ({cp}) is negative")

    # Result ID uniqueness
    if state_json and isinstance(state_json.get("intermediate_results"), list):
        seen: set[str] = set()
        existing_ids: set[str] = set()
        for r in state_json["intermediate_results"]:
            if isinstance(r, dict) and r.get("id"):
                if r["id"] in seen:
                    issues.append(f'intermediate_results: duplicate result ID "{r["id"]}"')
                seen.add(r["id"])
                existing_ids.add(str(r["id"]))

        for r in state_json["intermediate_results"]:
            if not isinstance(r, dict):
                continue
            rid = r.get("id") or "<missing-id>"
            depends_on = r.get("depends_on") or []
            for dep_id in depends_on:
                if dep_id not in existing_ids:
                    issues.append(f'intermediate_results[{rid}]: missing dependency "{dep_id}"')

            records = r.get("verification_records") or []
            if r.get("verified") and not records:
                target = issues if integrity_mode == "review" else warnings
                target.append(f"intermediate_results[{rid}]: verified=true but no verification_records present")
            if records and not r.get("verified"):
                warnings.append(f"intermediate_results[{rid}]: verification_records present while verified=false")

            for index, record in enumerate(records):
                if not isinstance(record, dict):
                    issues.append(f"intermediate_results[{rid}]: verification_records[{index}] is not an object")
                    continue
                evidence_path = record.get("evidence_path")
                if evidence_path:
                    evidence_file = Path(cwd) / str(evidence_path)
                    if not evidence_file.exists():
                        target = issues if integrity_mode == "review" else warnings
                        target.append(f'intermediate_results[{rid}]: evidence_path "{evidence_path}" does not exist')

    # Cross-check: phase directory exists
    current_phase = json_pos.get("current_phase") if isinstance(json_pos, dict) else None
    if current_phase is not None:
        phases_dir = ProjectLayout(cwd).phases_dir
        if phases_dir.exists():
            normalized = phase_normalize(str(current_phase))
            matching = [
                d.name
                for d in phases_dir.iterdir()
                if d.is_dir()
                and (
                    d.name == normalized
                    or d.name.startswith(f"{normalized}-")
                    or (d.name.startswith(f"{normalized}.") and d.name[len(normalized) + 1 :].split("-")[0].isdigit())
                )
            ]
            if not matching:
                issues.append(
                    f'filesystem: current_phase "{current_phase}" has no matching directory in {PLANNING_DIR_NAME}/{PHASES_DIR_NAME}/'
                )
        else:
            issues.append(
                f'filesystem: {PLANNING_DIR_NAME}/{PHASES_DIR_NAME}/ directory does not exist but current_phase is "{current_phase}"'
            )

    integrity_status = _integrity_status_from(issues, warnings, integrity_mode)
    valid = len(issues) == 0
    return StateValidateResult(
        valid=valid,
        issues=issues,
        warnings=warnings,
        integrity_mode=integrity_mode,
        integrity_status=integrity_status,
        state_source=state_source,
    )


# ─── Compact ───────────────────────────────────────────────────────────────────


@instrument_gpd_function("state.compact")
def state_compact(cwd: Path) -> StateCompactResult:
    """Compact STATE.md by archiving old decisions, blockers, metrics, and sessions."""
    with _state_lock(cwd):
        _recover_intent_locked(cwd)
        content = _load_or_rebuild_state_markdown_locked(cwd)
        if content is None:
            return StateCompactResult(compacted=False, error="STATE.md not found")
        lines = content.split("\n")
        total_lines = len(lines)
        warn_threshold = STATE_LINES_TARGET
        line_budget = STATE_LINES_BUDGET

        if total_lines <= warn_threshold:
            return StateCompactResult(compacted=False, reason="within_budget", lines=total_lines, warn=False)

        soft_mode = total_lines < line_budget

        # Determine current phase
        loaded_state = _load_state_snapshot_for_mutation(cwd, recover_intent=False)
        state_obj = ensure_state_schema(loaded_state) if isinstance(loaded_state, dict) else None

        current_phase = state_obj["position"].get("current_phase") if state_obj and state_obj.get("position") else None

        # Compute keep thresholds
        keep_phase_min = None
        metrics_phase_min = None
        if current_phase is not None:
            segs = str(current_phase).split(".")
            try:
                first_seg = int(segs[0])
                dec_segs = list(segs)
                dec_segs[0] = str(max(1, first_seg - 1))
                keep_phase_min = ".".join(dec_segs)
                met_segs = list(segs)
                met_segs[0] = str(max(0, first_seg - 1))
                metrics_phase_min = ".".join(met_segs)
            except ValueError:
                pass

        planning = _planning_dir(cwd)
        archive_path = planning / STATE_ARCHIVE_FILENAME
        archive_date = datetime.now(tz=UTC).strftime("%Y-%m-%d")
        archive_entries: list[str] = []
        working = content

        # 1. Archive decisions older than keep threshold
        if keep_phase_min is not None:
            dec_pattern = re.compile(
                r"(###?\s*Decisions\s*\n)([\s\S]*?)(?=\n###?|\n##[^#]|$)",
                re.IGNORECASE,
            )
            dec_match = dec_pattern.search(working)
            if dec_match:
                dec_lines = dec_match.group(2).split("\n")
                kept: list[str] = []
                archived: list[str] = []
                for line in dec_lines:
                    pm = re.match(r"^\s*-\s*\[Phase\s+([\d.]+)", line, re.IGNORECASE)
                    if pm:
                        if compare_phase_numbers(pm.group(1), keep_phase_min) < 0:
                            archived.append(line)
                        else:
                            kept.append(line)
                    else:
                        kept.append(line)
                if archived:
                    archive_entries.append(f"### Decisions (phases < {keep_phase_min})\n\n" + "\n".join(archived))
                    working = dec_pattern.sub(lambda _: f"{dec_match.group(1)}" + "\n".join(kept), working, count=1)

        # 2. Archive resolved blockers
        blk_pattern = re.compile(
            r"(###?\s*Blockers/Concerns\s*\n)([\s\S]*?)(?=\n###?|\n##[^#]|$)",
            re.IGNORECASE,
        )
        blk_match = blk_pattern.search(working)
        if blk_match:
            blk_lines = blk_match.group(2).split("\n")
            kept_b: list[str] = []
            archived_b: list[str] = []
            for line in blk_lines:
                if line.startswith("- ") and (
                    re.search(r"\[resolved\]", line, re.IGNORECASE) or re.search(r"~~.*?~~", line)
                ):
                    archived_b.append(line)
                else:
                    kept_b.append(line)
            if archived_b:
                archive_entries.append("### Resolved Blockers\n\n" + "\n".join(archived_b))
                working = blk_pattern.sub(lambda _: f"{blk_match.group(1)}" + "\n".join(kept_b), working, count=1)

        # 3. Archive old metrics (full mode only)
        if not soft_mode and metrics_phase_min is not None:
            met_pattern = re.compile(
                r"(##\s*Performance Metrics[\s\S]*?\n\|[^\n]+\n\|[-|\s]+\n)([\s\S]*?)(?=\n##|\n$|$)",
                re.IGNORECASE,
            )
            met_match = met_pattern.search(working)
            if met_match:
                met_rows = [r for r in met_match.group(2).split("\n") if r.strip()]
                kept_m: list[str] = []
                archived_m: list[str] = []
                for row in met_rows:
                    pm = re.search(r"Phase\s+([\d.]+)", row, re.IGNORECASE)
                    if pm:
                        if compare_phase_numbers(pm.group(1), metrics_phase_min) < 0:
                            archived_m.append(row)
                        else:
                            kept_m.append(row)
                    else:
                        kept_m.append(row)
                if archived_m:
                    archive_entries.append(
                        "### Performance Metrics\n\n"
                        "| Label | Duration | Tasks | Files |\n"
                        "| ----- | -------- | ----- | ----- |\n" + "\n".join(archived_m)
                    )
                    working = met_pattern.sub(
                        lambda _: f"{met_match.group(1)}" + "\n".join(kept_m) + "\n", working, count=1
                    )

        # 4. Archive session records (full mode only, keep last 3)
        if not soft_mode:
            sess_pattern = re.compile(
                r"(##\s*Session Continuity\s*\n)([\s\S]*?)(?=\n##|$)",
                re.IGNORECASE,
            )
            sess_match = sess_pattern.search(working)
            if sess_match:
                sess_lines = sess_match.group(2).split("\n")
                session_blocks: list[list[str]] = []
                current_block: list[str] = []
                for line in sess_lines:
                    if re.search(r"\*\*Last (?:session|Date):\*\*", line, re.IGNORECASE) and current_block:
                        session_blocks.append(current_block)
                        current_block = []
                    current_block.append(line)
                if current_block:
                    session_blocks.append(current_block)

                if len(session_blocks) > 3:
                    archived_s = session_blocks[:-3]
                    kept_s = session_blocks[-3:]
                    archive_entries.append("### Session Records\n\n" + "\n\n".join("\n".join(b) for b in archived_s))
                    working = sess_pattern.sub(
                        lambda _: f"{sess_match.group(1)}" + "\n".join("\n".join(b) for b in kept_s) + "\n",
                        working,
                        count=1,
                    )

        if not archive_entries:
            return StateCompactResult(compacted=False, reason="nothing_to_archive", lines=total_lines, warn=soft_mode)

        # Write archive
        archive_header = f"## Archived {archive_date} (from phase {current_phase or '?'})\n\n"
        archive_block = archive_header + "\n\n".join(archive_entries) + "\n\n"

        if archive_path.exists():
            existing = archive_path.read_text(encoding="utf-8")
            atomic_write(archive_path, existing + "\n" + archive_block)
        else:
            atomic_write(
                archive_path,
                "# STATE Archive\n\nHistorical state entries archived from STATE.md.\n\n" + archive_block,
            )

        # Write compacted STATE.md + sync
        _write_state_markdown_locked(cwd, working)

        new_lines = len(working.split("\n"))
        return StateCompactResult(
            compacted=True,
            original_lines=total_lines,
            new_lines=new_lines,
            archived_lines=total_lines - new_lines,
            soft_mode=soft_mode,
        )
