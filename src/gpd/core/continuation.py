"""Canonical continuation helpers for durable current-state authority.

This module keeps the durable continuation contract intentionally small:

- ``ContinuationState`` is the portable JSON-side schema
- ``resolve_continuation()`` returns the canonical state plus a normalized
  projection for resume/status callers
- when canonical ``state["continuation"]`` is absent, the resolver synthesizes
  that state from legacy ``session`` plus the current execution snapshot

Only portable repo-local references survive into the canonical continuation
state. File existence remains a read-time concern surfaced by the projection.
"""

from __future__ import annotations

from collections.abc import Mapping
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from gpd.core.utils import phase_normalize

__all__ = [
    "ContinuationBoundedSegment",
    "ContinuationHandoff",
    "ContinuationMachine",
    "ContinuationProjection",
    "ContinuationResumeSource",
    "ContinuationSource",
    "ContinuationState",
    "RESUMABLE_SEGMENT_STATUSES",
    "canonical_bounded_segment_from_execution_snapshot",
    "normalize_continuation",
    "normalize_continuation_reference",
    "resolve_continuation",
    "synthesize_legacy_continuation",
]

EM_DASH = "\u2014"
_CLEAR_VALUES = frozenset({"none", "null"})
RESUMABLE_SEGMENT_STATUSES = frozenset({"paused", "awaiting_user", "ready_to_continue", "waiting_review", "blocked"})


def _normalize_optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or stripped == EM_DASH or stripped.casefold() in _CLEAR_VALUES:
        return None
    return stripped


def _normalize_optional_bool(value: object) -> object:
    if value is None:
        return False
    return value


def _project_root_path(project_root: Path | str) -> Path:
    root = project_root if isinstance(project_root, Path) else Path(project_root)
    expanded = root.expanduser()
    try:
        return expanded.resolve(strict=False)
    except OSError:
        return expanded


def _as_mapping(value: Mapping[str, object] | BaseModel | None) -> dict[str, object] | None:
    if value is None:
        return None
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return dict(value)
    return None


class ContinuationSource(StrEnum):
    """Where the resolved continuation state came from."""

    CANONICAL = "canonical"
    LEGACY = "legacy"
    EMPTY = "empty"


class ContinuationResumeSource(StrEnum):
    """Which continuation pointer is currently active."""

    BOUNDED_SEGMENT = "bounded_segment"
    HANDOFF = "handoff"


class ContinuationHandoff(BaseModel):
    """Portable handoff pointer recorded when a session pauses."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    resume_file: str | None = None
    stopped_at: str | None = None
    last_result_id: str | None = None
    recorded_at: str | None = None
    recorded_by: str | None = None

    @field_validator("resume_file", "stopped_at", "last_result_id", "recorded_at", "recorded_by", mode="before")
    @classmethod
    def _normalize_text_fields(cls, value: object) -> str | None:
        return _normalize_optional_text(value)

    @property
    def is_empty(self) -> bool:
        return not any((self.resume_file, self.stopped_at, self.last_result_id, self.recorded_at, self.recorded_by))


class ContinuationMachine(BaseModel):
    """Advisory machine metadata for non-blocking portability notices."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    recorded_at: str | None = None
    hostname: str | None = None
    platform: str | None = None

    @field_validator("recorded_at", "hostname", "platform", mode="before")
    @classmethod
    def _normalize_text_fields(cls, value: object) -> str | None:
        return _normalize_optional_text(value)

    @property
    def is_empty(self) -> bool:
        return not any((self.recorded_at, self.hostname, self.platform))


class ContinuationBoundedSegment(BaseModel):
    """Portable resumable bounded-segment reference and minimal gate state."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    resume_file: str | None = None
    phase: str | None = None
    plan: str | None = None
    segment_id: str | None = None
    segment_status: str | None = None
    checkpoint_reason: str | None = None
    waiting_reason: str | None = None
    blocked_reason: str | None = None
    waiting_for_review: bool = False
    first_result_gate_pending: bool = False
    pre_fanout_review_pending: bool = False
    pre_fanout_review_cleared: bool = False
    skeptical_requestioning_required: bool = False
    downstream_locked: bool = False
    skeptical_requestioning_summary: str | None = None
    weakest_unchecked_anchor: str | None = None
    disconfirming_observation: str | None = None
    transition_id: str | None = None
    last_result_id: str | None = None
    updated_at: str | None = None
    source_session_id: str | None = None
    recorded_by: str | None = None

    @field_validator(
        "resume_file",
        "segment_id",
        "segment_status",
        "checkpoint_reason",
        "waiting_reason",
        "blocked_reason",
        "skeptical_requestioning_summary",
        "weakest_unchecked_anchor",
        "disconfirming_observation",
        "transition_id",
        "last_result_id",
        "updated_at",
        "source_session_id",
        "recorded_by",
        mode="before",
    )
    @classmethod
    def _normalize_text_fields(cls, value: object) -> str | None:
        return _normalize_optional_text(value)

    @field_validator("phase", "plan", mode="before")
    @classmethod
    def _normalize_phase_like_fields(cls, value: object) -> object:
        if isinstance(value, int):
            return phase_normalize(str(value))
        if isinstance(value, str):
            stripped = value.strip()
            return phase_normalize(stripped) if stripped else None
        return value

    @field_validator(
        "waiting_for_review",
        "first_result_gate_pending",
        "pre_fanout_review_pending",
        "pre_fanout_review_cleared",
        "skeptical_requestioning_required",
        "downstream_locked",
        mode="before",
    )
    @classmethod
    def _normalize_bool_fields(cls, value: object) -> object:
        return _normalize_optional_bool(value)

    @property
    def is_resumable_status(self) -> bool:
        status = (self.segment_status or "").strip().lower()
        return status in RESUMABLE_SEGMENT_STATUSES

    @property
    def is_empty(self) -> bool:
        return not any(
            (
                self.resume_file,
                self.phase,
                self.plan,
                self.segment_id,
                self.segment_status,
                self.checkpoint_reason,
                self.waiting_reason,
                self.blocked_reason,
                self.waiting_for_review,
                self.first_result_gate_pending,
                self.pre_fanout_review_pending,
                self.pre_fanout_review_cleared,
                self.skeptical_requestioning_required,
                self.downstream_locked,
                self.skeptical_requestioning_summary,
                self.weakest_unchecked_anchor,
                self.disconfirming_observation,
                self.transition_id,
                self.last_result_id,
                self.updated_at,
                self.source_session_id,
                self.recorded_by,
            )
        )


class ContinuationState(BaseModel):
    """Canonical durable continuation payload stored in ``state.json``."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    schema_version: int = 1
    handoff: ContinuationHandoff = Field(default_factory=ContinuationHandoff)
    bounded_segment: ContinuationBoundedSegment | None = None
    machine: ContinuationMachine = Field(default_factory=ContinuationMachine)

    @property
    def is_empty(self) -> bool:
        return self.handoff.is_empty and (self.bounded_segment is None or self.bounded_segment.is_empty) and self.machine.is_empty


class ContinuationProjection(BaseModel):
    """Resolved continuation state plus caller-friendly active-pointer projection."""

    model_config = ConfigDict(frozen=True)

    source: ContinuationSource = ContinuationSource.EMPTY
    continuation: ContinuationState = Field(default_factory=ContinuationState)
    recorded_handoff_resume_file: str | None = None
    handoff_resume_file: str | None = None
    missing_handoff_resume_file: str | None = None
    bounded_segment_resume_file: str | None = None
    active_resume_file: str | None = None
    active_resume_source: ContinuationResumeSource | None = None
    resumable: bool = False


def normalize_continuation_reference(
    project_root: Path | str,
    reference: object,
    *,
    require_exists: bool = False,
) -> str | None:
    """Return one portable repo-local continuation reference or ``None``."""

    normalized = _normalize_optional_text(reference)
    if normalized is None:
        return None

    resolved_root = _project_root_path(project_root)
    candidate = Path(normalized).expanduser()
    if candidate.is_absolute():
        try:
            normalized = candidate.resolve(strict=False).relative_to(resolved_root).as_posix()
        except (OSError, ValueError):
            return None
        candidate = Path(normalized)

    if candidate.is_absolute():
        return None

    try:
        resolved_target = (resolved_root / candidate).resolve(strict=False)
        resolved_target.relative_to(resolved_root)
    except (OSError, ValueError):
        return None

    if require_exists and not resolved_target.exists():
        return None

    return candidate.as_posix()


def normalize_continuation(
    project_root: Path | str,
    continuation: ContinuationState | Mapping[str, object],
) -> ContinuationState:
    """Validate and normalize a canonical continuation payload."""

    model = continuation if isinstance(continuation, ContinuationState) else ContinuationState.model_validate(continuation)
    normalized_handoff = model.handoff.model_copy(
        update={
            "resume_file": normalize_continuation_reference(project_root, model.handoff.resume_file),
        }
    )
    normalized_segment = model.bounded_segment
    if normalized_segment is not None:
        normalized_segment = normalized_segment.model_copy(
            update={
                "resume_file": normalize_continuation_reference(project_root, normalized_segment.resume_file),
            }
        )
    return model.model_copy(update={"handoff": normalized_handoff, "bounded_segment": normalized_segment})


def synthesize_legacy_continuation(
    project_root: Path | str,
    *,
    session: Mapping[str, object] | BaseModel | None = None,
    current_execution: Mapping[str, object] | BaseModel | None = None,
) -> ContinuationState:
    """Build canonical continuation state from legacy ``session`` plus live execution."""

    session_payload = _as_mapping(session) or {}
    current_execution_payload = _as_mapping(current_execution) or {}

    last_seen_at = _normalize_optional_text(session_payload.get("last_date"))
    handoff_resume_file = normalize_continuation_reference(project_root, session_payload.get("resume_file"))
    handoff_stopped_at = _normalize_optional_text(session_payload.get("stopped_at"))
    handoff_recorded_by = (
        "legacy_session" if any((handoff_resume_file, handoff_stopped_at, last_seen_at)) else None
    )
    normalized_handoff = ContinuationHandoff(
        resume_file=handoff_resume_file,
        stopped_at=handoff_stopped_at,
        recorded_at=last_seen_at,
        recorded_by=handoff_recorded_by,
    )
    machine = ContinuationMachine(
        recorded_at=last_seen_at,
        hostname=session_payload.get("hostname"),
        platform=session_payload.get("platform"),
    )

    segment = canonical_bounded_segment_from_execution_snapshot(project_root, current_execution_payload)
    bounded_segment = segment if segment is not None and segment.resume_file and segment.is_resumable_status else None

    return ContinuationState(
        handoff=normalized_handoff,
        bounded_segment=bounded_segment,
        machine=machine,
    )


def canonical_bounded_segment_from_execution_snapshot(
    project_root: Path | str,
    execution_snapshot: Mapping[str, object] | BaseModel | None,
) -> ContinuationBoundedSegment | None:
    """Derive a canonical bounded segment from a normalized execution snapshot."""

    execution_payload = _as_mapping(execution_snapshot) or {}
    if not execution_payload:
        return None

    segment = ContinuationBoundedSegment(
        resume_file=normalize_continuation_reference(
            project_root,
            execution_payload.get("resume_file"),
            require_exists=True,
        ),
        phase=execution_payload.get("phase"),
        plan=execution_payload.get("plan"),
        segment_id=execution_payload.get("segment_id"),
        segment_status=execution_payload.get("segment_status"),
        checkpoint_reason=execution_payload.get("checkpoint_reason"),
        waiting_reason=execution_payload.get("waiting_reason"),
        blocked_reason=execution_payload.get("blocked_reason"),
        waiting_for_review=execution_payload.get("waiting_for_review"),
        first_result_gate_pending=execution_payload.get("first_result_gate_pending"),
        pre_fanout_review_pending=execution_payload.get("pre_fanout_review_pending"),
        pre_fanout_review_cleared=execution_payload.get("pre_fanout_review_cleared"),
        skeptical_requestioning_required=execution_payload.get("skeptical_requestioning_required"),
        downstream_locked=execution_payload.get("downstream_locked"),
        skeptical_requestioning_summary=execution_payload.get("skeptical_requestioning_summary"),
        weakest_unchecked_anchor=execution_payload.get("weakest_unchecked_anchor"),
        disconfirming_observation=execution_payload.get("disconfirming_observation"),
        transition_id=execution_payload.get("transition_id"),
        last_result_id=execution_payload.get("last_result_id"),
        updated_at=execution_payload.get("updated_at"),
        source_session_id=execution_payload.get("session_id"),
        recorded_by="legacy_current_execution",
    )
    return segment if segment.resume_file and segment.is_resumable_status else None


def _project_continuation(
    project_root: Path | str,
    *,
    source: ContinuationSource,
    continuation: ContinuationState,
) -> ContinuationProjection:
    recorded_handoff_resume_file = normalize_continuation_reference(project_root, continuation.handoff.resume_file)
    handoff_resume_file = normalize_continuation_reference(
        project_root,
        continuation.handoff.resume_file,
        require_exists=True,
    )
    missing_handoff_resume_file = (
        recorded_handoff_resume_file if recorded_handoff_resume_file and handoff_resume_file is None else None
    )

    bounded_segment_resume_file = None
    resumable = False
    if continuation.bounded_segment is not None:
        bounded_segment_resume_file = normalize_continuation_reference(
            project_root,
            continuation.bounded_segment.resume_file,
            require_exists=True,
        )
        resumable = bool(bounded_segment_resume_file and continuation.bounded_segment.is_resumable_status)

    if resumable:
        active_resume_file = bounded_segment_resume_file
        active_resume_source = ContinuationResumeSource.BOUNDED_SEGMENT
    elif handoff_resume_file is not None:
        active_resume_file = handoff_resume_file
        active_resume_source = ContinuationResumeSource.HANDOFF
    else:
        active_resume_file = None
        active_resume_source = None

    return ContinuationProjection(
        source=source,
        continuation=continuation,
        recorded_handoff_resume_file=recorded_handoff_resume_file,
        handoff_resume_file=handoff_resume_file,
        missing_handoff_resume_file=missing_handoff_resume_file,
        bounded_segment_resume_file=bounded_segment_resume_file,
        active_resume_file=active_resume_file,
        active_resume_source=active_resume_source,
        resumable=resumable,
    )


def resolve_continuation(
    project_root: Path | str,
    *,
    state: Mapping[str, object] | BaseModel | None = None,
    current_execution: Mapping[str, object] | BaseModel | None = None,
) -> ContinuationProjection:
    """Resolve canonical continuation and project active pointers for callers.

    If ``state["continuation"]`` exists, it is authoritative and validated as
    the canonical schema. Otherwise the projection synthesizes a canonical
    continuation from the legacy ``session`` block and the live execution
    snapshot.
    """

    state_payload = _as_mapping(state) or {}
    raw_continuation = state_payload.get("continuation")
    if raw_continuation is not None:
        continuation = normalize_continuation(project_root, raw_continuation)
        if not continuation.is_empty:
            if continuation.bounded_segment is None:
                overlay_segment = canonical_bounded_segment_from_execution_snapshot(project_root, current_execution)
                if overlay_segment is not None:
                    continuation = continuation.model_copy(update={"bounded_segment": overlay_segment})
            return _project_continuation(project_root, source=ContinuationSource.CANONICAL, continuation=continuation)

    legacy = synthesize_legacy_continuation(
        project_root,
        session=state_payload.get("session"),
        current_execution=current_execution,
    )
    source = ContinuationSource.LEGACY if not legacy.is_empty else ContinuationSource.EMPTY
    return _project_continuation(project_root, source=source, continuation=legacy)
