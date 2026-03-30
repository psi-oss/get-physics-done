"""Machine-local recent-project index helpers for cross-project recovery.

The recent-project index is advisory only. It lives outside any single project
under the resolved GPD data root and helps users find likely repos to reopen.
"""

from __future__ import annotations

import os
from pathlib import Path

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from gpd.core.constants import (
    ENV_DATA_DIR,
    HOME_DATA_DIR_NAME,
    RECENT_PROJECTS_DIR_NAME,
    RECENT_PROJECTS_INDEX_FILENAME,
)
from gpd.core.utils import atomic_write, file_lock, safe_read_file

__all__ = [
    "RecentProjectEntry",
    "RecentProjectRecoveryClassification",
    "RecentProjectIndex",
    "RecentProjectsError",
    "classify_recent_project_recovery",
    "list_recent_projects",
    "load_recent_projects_index",
    "recent_projects_index_path",
    "recent_projects_root",
    "record_recent_project",
]

_RECENT_PROJECT_TARGET_KINDS = {"bounded_segment", "handoff"}


class RecentProjectsError(ValueError):
    """Raised when the recent-project advisory cache cannot be parsed."""


class RecentProjectEntry(BaseModel):
    """One machine-local recent-project record."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    schema_version: int = Field(default=1, ge=1)
    project_root: str = Field(validation_alias=AliasChoices("project_root", "workspace_root", "cwd", "path"))
    last_session_at: str | None = None
    last_seen_at: str | None = None
    stopped_at: str | None = None
    resume_file: str | None = None
    resume_target_kind: str | None = None
    resume_target_recorded_at: str | None = None
    resume_file_available: bool | None = None
    resume_file_reason: str | None = None
    hostname: str | None = None
    platform: str | None = None
    source_kind: str | None = None
    source_session_id: str | None = None
    source_segment_id: str | None = None
    source_transition_id: str | None = None
    source_event_id: str | None = None
    source_recorded_at: str | None = None
    recovery_phase: str | None = None
    recovery_plan: str | None = None
    resumable: bool = False
    available: bool = True
    availability_reason: str | None = None

    @field_validator(
        "last_session_at",
        "last_seen_at",
        "stopped_at",
        "resume_file",
        "resume_target_recorded_at",
        "resume_file_reason",
        "hostname",
        "platform",
        "source_kind",
        "source_session_id",
        "source_segment_id",
        "source_transition_id",
        "source_event_id",
        "source_recorded_at",
        "recovery_phase",
        "recovery_plan",
        "availability_reason",
        mode="before",
    )
    @classmethod
    def _normalize_optional_text(cls, value: object) -> str | None:
        return _normalize_recent_text(value)

    @field_validator("project_root", mode="before")
    @classmethod
    def _normalize_project_root(cls, value: object) -> str:
        normalized = _normalize_recent_text(value)
        if normalized is None:
            raise ValueError("project_root is required")
        return Path(normalized).expanduser().resolve(strict=False).as_posix()

    @field_validator("resume_target_kind", mode="before")
    @classmethod
    def _normalize_resume_target_kind(cls, value: object) -> str | None:
        return _normalize_resume_target_kind(value)

    @model_validator(mode="before")
    @classmethod
    def _backfill_recovery_fields(cls, value: object) -> object:
        if isinstance(value, RecentProjectEntry):
            payload: object = value.model_dump(mode="python")
        elif isinstance(value, dict):
            payload = dict(value)
        else:
            return value

        payload_dict = payload if isinstance(payload, dict) else {}
        resume_target_kind, resume_target_recorded_at = _backfill_recent_project_recovery_fields(payload_dict)

        payload_dict["resume_target_kind"] = resume_target_kind
        payload_dict["resume_target_recorded_at"] = resume_target_recorded_at
        return payload_dict


class RecentProjectRecoveryClassification(BaseModel):
    """Shared recent-project recovery classification for ranking and explanations."""

    model_config = ConfigDict(frozen=True)

    resume_target_kind: str | None = None
    resume_target_recorded_at: str | None = None
    has_recorded_target: bool = False
    has_concrete_target: bool = False
    target_priority: int = 0

    def candidate_reason(self, *, recoverable: bool) -> str:
        if self.has_concrete_target:
            if self.resume_target_kind == "bounded_segment":
                return "recent project cache entry with confirmed bounded segment resume target"
            if self.resume_target_kind == "handoff":
                return "recent project cache entry with projected continuity handoff"
            return "recent project cache entry with confirmed resume target"
        if recoverable:
            if self.has_recorded_target:
                if self.resume_target_kind == "bounded_segment":
                    return "recent project cache entry with recoverable project state and a recorded bounded segment target"
                if self.resume_target_kind == "handoff":
                    return "recent project cache entry with recoverable project state and a recorded continuity handoff"
                return "recent project cache entry with recoverable project state and a recorded resume target"
            return "recent project cache entry with recoverable project state"
        if self.has_recorded_target:
            if self.resume_target_kind == "bounded_segment":
                return "recent project cache entry with a recorded bounded segment target but without recoverable project state"
            if self.resume_target_kind == "handoff":
                return "recent project cache entry with a recorded continuity handoff but without recoverable project state"
            return "recent project cache entry with a recorded resume target but without recoverable project state"
        return "recent project cache entry without recoverable project state"


class RecentProjectIndex(BaseModel):
    """Persisted recent-project advisory index."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    rows: list[RecentProjectEntry] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_payload(cls, value: object) -> object:
        if value is None:
            return {"rows": []}
        if isinstance(value, dict) and not value:
            return {"rows": []}
        return {"rows": _extract_recent_project_rows(value)}


def recent_projects_root(explicit_data_dir: Path | None = None) -> Path:
    """Resolve the machine-local recent-project root.

    Precedence: explicit data dir > ``GPD_DATA_DIR`` env > ``~/.gpd/recent-projects``.
    """
    if explicit_data_dir is not None:
        return explicit_data_dir.expanduser() / RECENT_PROJECTS_DIR_NAME

    data_dir = os.environ.get(ENV_DATA_DIR, "").strip()
    if data_dir:
        return Path(data_dir).expanduser() / RECENT_PROJECTS_DIR_NAME
    return Path.home() / HOME_DATA_DIR_NAME / RECENT_PROJECTS_DIR_NAME


def recent_projects_index_path(data_root: Path | None = None) -> Path:
    """Return the index.json path for the recent-project cache."""
    base = recent_projects_root(data_root)
    return base / RECENT_PROJECTS_INDEX_FILENAME


def _sort_rows(rows: list[RecentProjectEntry]) -> list[RecentProjectEntry]:
    return sorted(
        rows,
        key=lambda row: (_recent_project_sort_stamp(row), row.project_root),
        reverse=True,
    )


def _dedupe_rows(rows: list[RecentProjectEntry]) -> list[RecentProjectEntry]:
    unique_rows: list[RecentProjectEntry] = []
    seen_roots: set[str] = set()
    for row in rows:
        if row.project_root in seen_roots:
            continue
        seen_roots.add(row.project_root)
        unique_rows.append(row)
    return unique_rows


def _recent_project_sort_stamp(row: RecentProjectEntry) -> str:
    return row.resume_target_recorded_at or row.last_session_at or row.last_seen_at or row.source_recorded_at or ""


def _availability_for(project_root: str) -> tuple[bool, str | None]:
    root = Path(project_root).expanduser()
    if not root.exists():
        return False, "project root missing"
    return root.is_dir(), None if root.is_dir() else "project root is not a directory"


def _resume_file_availability(project_root: str, resume_file: str | None) -> tuple[bool | None, str | None]:
    if not isinstance(resume_file, str) or not resume_file.strip():
        return None, None

    root = Path(project_root).expanduser()
    if not root.exists() or not root.is_dir():
        return None, None

    resolved_root = root.resolve(strict=False)
    candidate = Path(resume_file).expanduser()
    if candidate.is_absolute():
        resolved_target = candidate.resolve(strict=False)
    else:
        resolved_target = (root / candidate).resolve(strict=False)

    try:
        resolved_target.relative_to(resolved_root)
    except ValueError:
        return False, "resume file outside project root"

    if not resolved_target.exists():
        return False, "resume file missing"
    if not resolved_target.is_file():
        return False, "resume file is not a file"
    return True, None


def _normalize_recent_text(value: object) -> str | None:
    if isinstance(value, Path):
        value = value.as_posix()
    elif not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or stripped in {"—", "[Not set]"} or stripped.casefold() in {"none", "null"}:
        return None
    return stripped


def _normalize_resume_target_kind(value: object) -> str | None:
    normalized = _normalize_recent_text(value)
    if normalized is None:
        return None
    if normalized == "continuity_handoff":
        return "handoff"
    if normalized in _RECENT_PROJECT_TARGET_KINDS:
        return normalized
    return None


def _backfill_recent_project_recovery_fields(row: object) -> tuple[str | None, str | None]:
    """Resolve canonical recovery fields from normalized or legacy row data."""

    resume_target_kind = _normalize_resume_target_kind(_row_value(row, "resume_target_kind"))
    if resume_target_kind is None:
        resume_target_kind = infer_recent_project_resume_target_kind(row)

    resume_target_recorded_at = _normalize_recent_text(_row_value(row, "resume_target_recorded_at"))
    if resume_target_recorded_at is None and resume_target_kind in _RECENT_PROJECT_TARGET_KINDS:
        resume_target_recorded_at = (
            _normalize_recent_text(_row_value(row, "source_recorded_at"))
            or _normalize_recent_text(_row_value(row, "last_session_at"))
            or _normalize_recent_text(_row_value(row, "last_seen_at"))
        )

    return resume_target_kind, resume_target_recorded_at


def _row_value(row: object, field: str) -> object:
    if isinstance(row, dict):
        return row.get(field)
    return getattr(row, field, None)


def _legacy_recent_project_resume_target_kind(row: object) -> str | None:
    resume_file = _normalize_recent_text(_row_value(row, "resume_file"))
    if resume_file is None:
        return None

    source_kind = _normalize_recent_text(_row_value(row, "source_kind"))
    if source_kind in {"continuation.bounded_segment", "bounded_segment"}:
        return "bounded_segment"
    if source_kind in {"continuation.handoff", "handoff", "legacy_session"}:
        return "handoff"
    if isinstance(source_kind, str) and source_kind.startswith("segment."):
        return "bounded_segment"

    source_segment_id = _normalize_recent_text(_row_value(row, "source_segment_id"))
    source_transition_id = _normalize_recent_text(_row_value(row, "source_transition_id"))
    if source_segment_id is not None or source_transition_id is not None:
        return "bounded_segment"

    return "handoff"


def infer_recent_project_resume_target_kind(row: object) -> str | None:
    """Infer one additive resume target classification for a recent-project row."""

    explicit = _normalize_resume_target_kind(_row_value(row, "resume_target_kind"))
    if explicit is not None:
        return explicit
    return _legacy_recent_project_resume_target_kind(row)


def _extract_recent_project_rows(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    if not isinstance(value, dict):
        raise ValueError("recent-project index must be a mapping or list of rows")

    for key in ("rows", "projects"):
        if key in value:
            return _extract_recent_project_rows(value[key])

    if any(key in value for key in ("project_root", "workspace_root", "cwd", "path")):
        return [value]

    raise ValueError("recent-project index payload does not contain rows")


def _session_text(session_data: dict[str, object], *keys: str) -> str | None:
    for key in keys:
        if key in session_data:
            return _normalize_recent_text(session_data.get(key))
    return None


def _updated_text(
    session_data: dict[str, object],
    existing_value: str | None,
    *keys: str,
) -> str | None:
    updated = _session_text(session_data, *keys)
    return updated if updated is not None or any(key in session_data for key in keys) else existing_value


def classify_recent_project_recovery(row: object) -> RecentProjectRecoveryClassification:
    """Return one shared recovery classification for a recent-project row."""

    resume_target_kind, resume_target_recorded_at = _backfill_recent_project_recovery_fields(row)

    available_value = _row_value(row, "available")
    available = True if available_value is None else bool(available_value)
    resume_file = _normalize_recent_text(_row_value(row, "resume_file"))
    resume_file_available = _row_value(row, "resume_file_available")
    if not isinstance(resume_file_available, bool):
        resume_file_available = None

    has_recorded_target = resume_file is not None
    has_concrete_target = bool(has_recorded_target and available and resume_file_available is not False)
    if has_concrete_target and resume_target_kind == "bounded_segment":
        target_priority = 2
    elif has_concrete_target:
        target_priority = 1
    else:
        target_priority = 0

    return RecentProjectRecoveryClassification(
        resume_target_kind=resume_target_kind,
        resume_target_recorded_at=resume_target_recorded_at,
        has_recorded_target=has_recorded_target,
        has_concrete_target=has_concrete_target,
        target_priority=target_priority,
    )


def _annotate_availability(entry: RecentProjectEntry) -> RecentProjectEntry:
    available, reason = _availability_for(entry.project_root)
    resume_file_available, resume_file_reason = _resume_file_availability(entry.project_root, entry.resume_file)
    return entry.model_copy(
        update={
            "available": available,
            "availability_reason": reason,
            "resume_file_available": resume_file_available,
            "resume_file_reason": resume_file_reason,
            "resumable": bool(entry.resume_file) and available and resume_file_available is True,
        }
    )


def load_recent_projects_index(data_root: Path | None = None) -> RecentProjectIndex:
    index_path = recent_projects_index_path(data_root)
    content = safe_read_file(index_path)
    if content is None:
        return RecentProjectIndex()
    try:
        index = RecentProjectIndex.model_validate_json(content)
    except ValueError as exc:
        raise RecentProjectsError(f"Malformed recent-project index at {index_path}: {exc}") from exc
    return index.model_copy(update={"rows": [_annotate_availability(row) for row in _sort_rows(list(index.rows))]})


def _save_index(data_root: Path | None, index: RecentProjectIndex) -> None:
    index_path = recent_projects_index_path(data_root)
    with file_lock(index_path):
        atomic_write(index_path, index.model_dump_json(indent=2) + "\n")


def record_recent_project(
    project_root: Path,
    *,
    session_data: dict[str, object],
    store_root: Path | None = None,
) -> RecentProjectEntry:
    """Insert or update one recent-project row."""
    resolved_root = project_root.expanduser().resolve(strict=False)
    data_root = store_root
    current = load_recent_projects_index(data_root)
    existing = next((row for row in current.rows if row.project_root == resolved_root.as_posix()), None)
    last_session_at = _updated_text(session_data, existing.last_session_at if existing is not None else None, "last_date", "last_session_at")
    last_seen_at = _updated_text(
        session_data,
        existing.last_seen_at if existing is not None else last_session_at,
        "last_seen_at",
        "last_date",
        "last_session_at",
    )
    normalized_resume_file = _updated_text(session_data, existing.resume_file if existing is not None else None, "resume_file")
    resume_target_kind = _updated_text(
        session_data,
        existing.resume_target_kind if existing is not None else None,
        "resume_target_kind",
    )
    resume_target_recorded_at = _updated_text(
        session_data,
        existing.resume_target_recorded_at if existing is not None else None,
        "resume_target_recorded_at",
    )
    normalized_hostname = _updated_text(session_data, existing.hostname if existing is not None else None, "hostname")
    normalized_platform = _updated_text(session_data, existing.platform if existing is not None else None, "platform")
    source_kind = _updated_text(session_data, existing.source_kind if existing is not None else None, "source_kind", "provenance_kind")
    source_session_id = _updated_text(
        session_data,
        existing.source_session_id if existing is not None else None,
        "source_session_id",
        "session_id",
    )
    source_segment_id = _updated_text(
        session_data,
        existing.source_segment_id if existing is not None else None,
        "source_segment_id",
        "segment_id",
    )
    source_transition_id = _updated_text(
        session_data,
        existing.source_transition_id if existing is not None else None,
        "source_transition_id",
        "transition_id",
    )
    source_event_id = _updated_text(
        session_data,
        existing.source_event_id if existing is not None else None,
        "source_event_id",
        "event_id",
    )
    source_recorded_at = _updated_text(
        session_data,
        existing.source_recorded_at if existing is not None else None,
        "source_recorded_at",
        "recorded_at",
        "timestamp",
    )
    recovery_phase = _updated_text(
        session_data,
        existing.recovery_phase if existing is not None else None,
        "recovery_phase",
        "phase",
    )
    recovery_plan = _updated_text(
        session_data,
        existing.recovery_plan if existing is not None else None,
        "recovery_plan",
        "plan",
    )
    updated_entry = RecentProjectEntry(
        project_root=resolved_root.as_posix(),
        last_session_at=last_session_at,
        last_seen_at=last_seen_at,
        stopped_at=_updated_text(session_data, existing.stopped_at if existing is not None else None, "stopped_at"),
        resume_file=normalized_resume_file,
        resume_target_kind=resume_target_kind,
        resume_target_recorded_at=resume_target_recorded_at,
        hostname=normalized_hostname,
        platform=normalized_platform,
        source_kind=source_kind,
        source_session_id=source_session_id,
        source_segment_id=source_segment_id,
        source_transition_id=source_transition_id,
        source_event_id=source_event_id,
        source_recorded_at=source_recorded_at,
        recovery_phase=recovery_phase,
        recovery_plan=recovery_plan,
    )

    rows: list[RecentProjectEntry] = []
    replaced = False
    for current_row in current.rows:
        if current_row.project_root == updated_entry.project_root:
            rows.append(updated_entry)
            replaced = True
        else:
            rows.append(current_row)
    if not replaced:
        rows.append(updated_entry)

    _save_index(data_root, RecentProjectIndex(rows=_dedupe_rows(_sort_rows(rows))))
    return _annotate_availability(updated_entry)


def list_recent_projects(store_root: Path | None = None, *, last: int | None = None) -> list[RecentProjectEntry]:
    """Return recent-project rows sorted newest-first with availability annotations."""
    current = load_recent_projects_index(store_root)
    rows = [_annotate_availability(entry) for entry in _dedupe_rows(_sort_rows(list(current.rows)))]
    if last is not None and last > 0:
        rows = rows[:last]
    return rows
