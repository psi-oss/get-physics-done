"""Canonical application of durable child-return effects.

This module turns a validated ``gpd_return`` envelope into durable project
state mutations where that is explicitly supported. It keeps the contract
fail-closed:

- artifacts and status stay workflow-owned
- supported shared-state operations are mapped onto existing state helpers
- unsupported or malformed child-return updates are rejected before mutation
- workflow-local payloads such as ``contract_updates`` are surfaced back to the
  caller rather than silently persisted to global state
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from gpd.core.constants import ProjectLayout
from gpd.core.continuation import (
    normalize_continuation_bounded_segment_with_issues,
    normalize_continuation_reference,
)
from gpd.core.recent_projects import recent_projects_index_path
from gpd.core.results import state_has_canonical_result_id
from gpd.core.return_contract import (
    GpdReturnContinuationBoundedSegment,
    GpdReturnContinuationUpdate,
    GpdReturnEnvelope,
)
from gpd.core.state import (
    StateUpdateResult,
    load_state_json_readonly,
    state_add_blocker,
    state_add_decision,
    state_advance_plan,
    state_clear_continuation_bounded_segment,
    state_record_metric,
    state_record_session,
    state_set_continuation_bounded_segment,
    state_update_progress,
)
from gpd.core.utils import atomic_write, file_lock

__all__ = [
    "ApplyChildReturnResult",
    "SUPPORTED_CONTINUATION_UPDATE_FIELDS",
    "SUPPORTED_STATE_UPDATE_FIELDS",
    "apply_child_return_updates",
]


# Explicit supported update surfaces for the canonical child-return applicator.
SUPPORTED_STATE_UPDATE_FIELDS: tuple[str, ...] = ("advance_plan", "update_progress", "record_metric")
SUPPORTED_CONTINUATION_UPDATE_FIELDS: tuple[str, ...] = ("handoff", "bounded_segment")
_CHILD_RETURN_BOUNDED_SEGMENT_RECORDED_BY = "apply_child_return_updates"


@dataclass(frozen=True)
class _FileSnapshot:
    path: Path
    existed: bool
    content: bytes | None


class _RecordMetricPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    phase: str
    plan: str
    duration: str | int | float
    tasks: str | int | None = None
    files: str | int | None = None


class _StateUpdatesPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    advance_plan: bool = False
    update_progress: bool = False
    record_metric: _RecordMetricPayload | None = None


class _DecisionPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    summary: str
    phase: str | None = None
    rationale: str | None = None


class _BlockerPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    text: str


class ApplyChildReturnResult(BaseModel):
    """Outcome of applying the durable subset of one child return."""

    passed: bool
    status: str
    files_written: list[str] = Field(default_factory=list)
    applied_state_operations: list[str] = Field(default_factory=list)
    applied_continuation_operations: list[str] = Field(default_factory=list)
    applied_decisions: int = 0
    applied_blockers: int = 0
    contract_updates: dict[str, object] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


def apply_child_return_updates(cwd: Path, envelope: GpdReturnEnvelope) -> ApplyChildReturnResult:
    """Apply the durable shared-state subset of a validated child return."""

    errors: list[str] = []
    warnings: list[str] = []
    applied_state_operations: list[str] = []
    applied_continuation_operations: list[str] = []
    applied_decisions = 0
    applied_blockers = 0

    state_updates = _validate_state_updates(envelope.state_updates, errors)
    decisions = _validate_decisions(envelope.decisions, errors)
    blockers = _validate_blockers(envelope.blockers, errors)
    continuation_update = _validate_continuation_update(envelope.continuation_update, errors)
    _validate_continuation_update_semantics(cwd, continuation_update, errors)
    contract_updates = dict(envelope.contract_updates or {})

    if errors:
        return ApplyChildReturnResult(
            passed=False,
            status="failed",
            files_written=list(envelope.files_written),
            contract_updates=contract_updates,
            errors=errors,
        )

    state_snapshot = _capture_state_mutation_snapshot(cwd)
    recent_projects_snapshot = _capture_recent_projects_mutation_snapshot()
    expected_state_snapshot = state_snapshot
    expected_recent_projects_snapshot = recent_projects_snapshot
    current_operation = "apply_child_return_updates"

    def _refresh_mutation_expectations() -> None:
        nonlocal expected_state_snapshot, expected_recent_projects_snapshot
        expected_state_snapshot = _capture_state_mutation_snapshot(cwd)
        expected_recent_projects_snapshot = _capture_recent_projects_mutation_snapshot()

    try:
        if state_updates is not None:
            if state_updates.advance_plan:
                current_operation = "advance_plan"
                result = state_advance_plan(cwd)
                advance_mutated = bool(getattr(result, "state_mutated", result.advanced))
                _record_advance_plan_result(
                    result.advanced,
                    state_mutated=advance_mutated,
                    error=getattr(result, "error", None),
                    reason=getattr(result, "reason", None),
                    errors=errors,
                    warnings=warnings,
                    applied=applied_state_operations,
                )
                if advance_mutated:
                    _refresh_mutation_expectations()
            if state_updates.update_progress:
                current_operation = "update_progress"
                result = state_update_progress(cwd)
                _record_bool_result(
                    result.updated,
                    error=result.error,
                    reason=result.reason,
                    operation="update_progress",
                    errors=errors,
                    warnings=warnings,
                    applied=applied_state_operations,
                )
                if result.updated:
                    _refresh_mutation_expectations()
            if state_updates.record_metric is not None:
                current_operation = "record_metric"
                metric = state_updates.record_metric
                result = state_record_metric(
                    cwd,
                    phase=str(metric.phase),
                    plan=str(metric.plan),
                    duration=str(metric.duration),
                    tasks=None if metric.tasks is None else str(metric.tasks),
                    files=None if metric.files is None else str(metric.files),
                )
                _record_bool_result(
                    result.recorded,
                    error=result.error,
                    reason=result.reason,
                    operation="record_metric",
                    errors=errors,
                    warnings=warnings,
                    applied=applied_state_operations,
                )
                if result.recorded:
                    _refresh_mutation_expectations()

        for decision in decisions:
            current_operation = "add_decision"
            result = state_add_decision(
                cwd,
                phase=decision.phase,
                summary=decision.summary,
                rationale=decision.rationale,
            )
            _record_bool_result(
                result.added,
                error=result.error,
                reason=result.reason,
                operation="add_decision",
                errors=errors,
                warnings=warnings,
                applied=None,
            )
            if result.added:
                applied_decisions += 1
                _refresh_mutation_expectations()

        for blocker in blockers:
            current_operation = "add_blocker"
            result = state_add_blocker(cwd, blocker.text)
            _record_bool_result(
                result.added,
                error=result.error,
                reason=result.reason,
                operation="add_blocker",
                errors=errors,
                warnings=warnings,
                applied=None,
            )
            if result.added:
                applied_blockers += 1
                _refresh_mutation_expectations()

        if continuation_update is not None:
            if continuation_update.handoff is not None:
                current_operation = "record_session"
                handoff = continuation_update.handoff
                result = state_record_session(
                    cwd,
                    stopped_at=handoff.stopped_at,
                    resume_file=handoff.resume_file,
                    last_result_id=handoff.last_result_id,
                    clear_resume_file="resume_file" in handoff.model_fields_set and handoff.resume_file is None,
                    clear_last_result_id="last_result_id" in handoff.model_fields_set and handoff.last_result_id is None,
                )
                _record_bool_result(
                    result.recorded,
                    error=result.error,
                    reason=result.reason,
                    operation="record_session",
                    errors=errors,
                    warnings=warnings,
                    applied=applied_continuation_operations,
                )
                if result.recorded:
                    _refresh_mutation_expectations()

            if "bounded_segment" in continuation_update.model_fields_set:
                bounded_segment = continuation_update.bounded_segment
                if bounded_segment is None:
                    current_operation = "clear_bounded_segment"
                    result = state_clear_continuation_bounded_segment(cwd)
                    _record_state_update_result(
                        result,
                        operation="clear_bounded_segment",
                        errors=errors,
                        warnings=warnings,
                        applied=applied_continuation_operations,
                    )
                    if result.updated:
                        _refresh_mutation_expectations()
                else:
                    current_operation = "set_bounded_segment"
                    result = state_set_continuation_bounded_segment(
                        cwd,
                        _with_applicator_owned_bounded_segment_metadata(bounded_segment),
                    )
                    _record_state_update_result(
                        result,
                        operation="set_bounded_segment",
                        errors=errors,
                        warnings=warnings,
                        applied=applied_continuation_operations,
                    )
                    if result.updated:
                        _refresh_mutation_expectations()
    except Exception as exc:
        errors.append(f"{current_operation}: {exc}")

    if errors:
        rollback_errors = _restore_state_mutation_snapshot(
            state_snapshot,
            expected_current_snapshots=expected_state_snapshot,
        )
        rollback_errors.extend(
            _restore_recent_projects_mutation_snapshot(
                recent_projects_snapshot,
                expected_current_snapshot=expected_recent_projects_snapshot,
            )
        )
        if rollback_errors:
            errors.extend(rollback_errors)
        elif applied_state_operations or applied_continuation_operations or applied_decisions or applied_blockers:
            warnings.append("rolled back partial child-return state updates after failure")
        applied_state_operations = []
        applied_continuation_operations = []
        applied_decisions = 0
        applied_blockers = 0

    passed = not errors
    return ApplyChildReturnResult(
        passed=passed,
        status=envelope.status if passed else "failed",
        files_written=list(envelope.files_written),
        applied_state_operations=applied_state_operations,
        applied_continuation_operations=applied_continuation_operations,
        applied_decisions=applied_decisions,
        applied_blockers=applied_blockers,
        contract_updates=contract_updates,
        errors=errors,
        warnings=warnings,
    )


def _validate_state_updates(raw: object, errors: list[str]) -> _StateUpdatesPayload | None:
    if raw is None:
        return None
    try:
        return _StateUpdatesPayload.model_validate(raw)
    except PydanticValidationError as exc:
        errors.extend(_format_validation_errors(exc, prefix="state_updates"))
        return None


def _validate_decisions(raw: object, errors: list[str]) -> list[_DecisionPayload]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        errors.append("decisions must be a list")
        return []

    normalized: list[_DecisionPayload] = []
    for index, item in enumerate(raw):
        payload: object = item
        if isinstance(item, str):
            payload = {"summary": item}
        try:
            normalized.append(_DecisionPayload.model_validate(payload))
        except PydanticValidationError as exc:
            errors.extend(_format_validation_errors(exc, prefix=f"decisions[{index}]"))
    return normalized


def _validate_blockers(raw: object, errors: list[str]) -> list[_BlockerPayload]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        errors.append("blockers must be a list")
        return []

    normalized: list[_BlockerPayload] = []
    for index, item in enumerate(raw):
        payload: object = item
        if isinstance(item, str):
            payload = {"text": item}
        try:
            normalized.append(_BlockerPayload.model_validate(payload))
        except PydanticValidationError as exc:
            errors.extend(_format_validation_errors(exc, prefix=f"blockers[{index}]"))
    return normalized


def _validate_continuation_update(raw: object, errors: list[str]) -> GpdReturnContinuationUpdate | None:
    if raw is None:
        return None
    try:
        return GpdReturnContinuationUpdate.model_validate(raw)
    except PydanticValidationError as exc:
        errors.extend(_format_validation_errors(exc, prefix="continuation_update"))
        return None


def _with_applicator_owned_bounded_segment_metadata(
    bounded_segment: GpdReturnContinuationBoundedSegment,
) -> GpdReturnContinuationBoundedSegment:
    return bounded_segment.model_copy(
        update={
            "updated_at": datetime.now(UTC).isoformat(),
            "recorded_by": _CHILD_RETURN_BOUNDED_SEGMENT_RECORDED_BY,
        }
    )


def _validate_continuation_update_semantics(
    cwd: Path,
    continuation_update: GpdReturnContinuationUpdate | None,
    errors: list[str],
) -> None:
    if continuation_update is None:
        return

    if continuation_update.handoff is not None:
        handoff = continuation_update.handoff
        if handoff.resume_file is not None and normalize_continuation_reference(cwd, handoff.resume_file) is None:
            errors.append("record_session: resume_file must be a repo-relative path inside the project root")
        if handoff.last_result_id is not None:
            state_obj = load_state_json_readonly(cwd)
            if not isinstance(state_obj, dict):
                errors.append("record_session: State not found")
            elif not state_has_canonical_result_id(state_obj, handoff.last_result_id):
                errors.append(
                    f'record_session: last_result_id "{handoff.last_result_id}" does not match any canonical result '
                    "in intermediate_results"
                )

    if "bounded_segment" not in continuation_update.model_fields_set:
        return

    bounded_segment = continuation_update.bounded_segment
    if bounded_segment is None:
        return

    normalized_segment, normalization_issues = normalize_continuation_bounded_segment_with_issues(
        cwd,
        bounded_segment,
    )
    if normalization_issues:
        errors.append(
            "set_bounded_segment: Invalid continuation bounded_segment schema: "
            + "; ".join(dict.fromkeys(normalization_issues))
        )
    elif normalized_segment is None or normalized_segment.is_empty:
        errors.append(
            "set_bounded_segment: Invalid continuation bounded_segment schema: "
            "bounded_segment must include at least one non-empty field"
        )
    elif normalized_segment.last_result_id is not None:
        state_obj = load_state_json_readonly(cwd)
        if not isinstance(state_obj, dict):
            errors.append("set_bounded_segment: State not found")
        elif not state_has_canonical_result_id(state_obj, normalized_segment.last_result_id):
            errors.append(
                f'set_bounded_segment: last_result_id "{normalized_segment.last_result_id}" does not match any '
                "canonical result in intermediate_results"
            )


def _capture_state_mutation_snapshot(cwd: Path) -> tuple[_FileSnapshot, ...]:
    layout = ProjectLayout(cwd)
    return tuple(
        _capture_file_snapshot(path)
        for path in (layout.state_json, layout.state_md, layout.state_json_backup, layout.state_intent)
    )


def _capture_recent_projects_mutation_snapshot() -> _FileSnapshot:
    return _capture_file_snapshot(recent_projects_index_path())


def _capture_file_snapshot(path: Path) -> _FileSnapshot:
    try:
        return _FileSnapshot(path=path, existed=True, content=path.read_bytes())
    except FileNotFoundError:
        return _FileSnapshot(path=path, existed=False, content=None)


def _restore_state_mutation_snapshot(
    snapshots: tuple[_FileSnapshot, ...],
    *,
    expected_current_snapshots: tuple[_FileSnapshot, ...] | None = None,
) -> list[str]:
    if not snapshots:
        return []
    try:
        with file_lock(snapshots[0].path):
            return _restore_file_snapshots(snapshots, expected_current_snapshots=expected_current_snapshots)
    except OSError as exc:
        return [f"rollback failed for {snapshots[0].path}: {exc}"]
    except TimeoutError as exc:
        return [f"rollback failed for {snapshots[0].path}: {exc}"]


def _restore_file_snapshots(
    snapshots: tuple[_FileSnapshot, ...],
    *,
    expected_current_snapshots: tuple[_FileSnapshot, ...] | None = None,
) -> list[str]:
    errors: list[str] = []
    if expected_current_snapshots is not None:
        changed_paths = [
            expected.path
            for expected in expected_current_snapshots
            if not _current_file_matches_snapshot(expected)
        ]
        if changed_paths:
            changed = ", ".join(str(path) for path in changed_paths)
            return [f"rollback skipped because file(s) changed after child-return mutation: {changed}"]

    for snapshot in snapshots:
        try:
            if snapshot.existed:
                snapshot.path.parent.mkdir(parents=True, exist_ok=True)
                atomic_write(snapshot.path, (snapshot.content or b"").decode("utf-8"))
            else:
                snapshot.path.unlink(missing_ok=True)
        except (OSError, UnicodeDecodeError) as exc:
            errors.append(f"rollback failed for {snapshot.path}: {exc}")
    return errors


def _current_file_matches_snapshot(snapshot: _FileSnapshot) -> bool:
    try:
        current = snapshot.path.read_bytes()
    except FileNotFoundError:
        return not snapshot.existed
    except OSError:
        return False
    return snapshot.existed and current == (snapshot.content or b"")


def _restore_recent_projects_mutation_snapshot(
    snapshot: _FileSnapshot,
    *,
    expected_current_snapshot: _FileSnapshot | None = None,
) -> list[str]:
    try:
        with file_lock(snapshot.path):
            expected = None if expected_current_snapshot is None else (expected_current_snapshot,)
            return _restore_file_snapshots((snapshot,), expected_current_snapshots=expected)
    except OSError as exc:
        return [f"rollback failed for {snapshot.path}: {exc}"]
    except TimeoutError as exc:
        return [f"rollback failed for {snapshot.path}: {exc}"]


def _record_bool_result(
    succeeded: bool,
    *,
    error: str | None,
    reason: str | None,
    operation: str,
    errors: list[str],
    warnings: list[str],
    applied: list[str] | None,
) -> None:
    if error:
        errors.append(f"{operation}: {error}")
        return
    if succeeded:
        if applied is not None:
            applied.append(operation)
        return

    if _is_noop_reason(reason):
        if applied is not None:
            applied.append(f"{operation}:noop")
        if reason:
            warnings.append(f"{operation}: {reason}")
        return

    errors.append(f"{operation}: {reason or 'operation failed'}")


def _record_advance_plan_result(
    advanced: bool,
    *,
    state_mutated: bool,
    error: str | None,
    reason: str | None,
    errors: list[str],
    warnings: list[str],
    applied: list[str],
) -> None:
    if error:
        errors.append(f"advance_plan: {error}")
        return
    if advanced:
        applied.append("advance_plan")
        return
    if state_mutated:
        applied.append("advance_plan:last_plan")
        if reason:
            warnings.append(f"advance_plan: {reason}")
        return
    if _is_noop_reason(reason):
        applied.append("advance_plan:noop")
        if reason:
            warnings.append(f"advance_plan: {reason}")
        return
    errors.append(f"advance_plan: {reason or 'operation failed'}")


def _record_state_update_result(
    result: StateUpdateResult,
    *,
    operation: str,
    errors: list[str],
    warnings: list[str],
    applied: list[str],
) -> None:
    if result.updated:
        applied.append(operation)
        return
    if result.unchanged or _is_noop_reason(result.reason):
        applied.append(f"{operation}:noop")
        if result.reason:
            warnings.append(f"{operation}: {result.reason}")
        return
    errors.append(f"{operation}: {result.reason or 'operation failed'}")


def _is_noop_reason(reason: str | None) -> bool:
    if not reason:
        return False
    normalized = reason.casefold()
    return (
        "already" in normalized
        or "matches requested value" in normalized
        or "already clear" in normalized
        or normalized == "last_plan"
        or "no session fields found" in normalized
    )


def _format_validation_errors(exc: PydanticValidationError, *, prefix: str) -> list[str]:
    errors: list[str] = []
    for item in exc.errors():
        location = ".".join(str(part) for part in item.get("loc", ()))
        message = str(item.get("msg", "validation failed"))
        if location:
            errors.append(f"{prefix}.{location}: {message}")
        else:
            errors.append(f"{prefix}: {message}")
    return errors
