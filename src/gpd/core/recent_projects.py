"""Machine-local recent-project index helpers for cross-project recovery.

The recent-project index is advisory only. It lives outside any single project
under the resolved GPD data root and helps users find likely repos to reopen.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic import ValidationError as PydanticValidationError

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


def _strict_bool_value(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    return None


def _normalize_recent_projects_index_payload(value: object) -> dict[str, object]:
    if value is None:
        return {"rows": []}
    if not isinstance(value, dict):
        raise ValueError("recent-project index must be a JSON object with only rows")
    if not value:
        return {"rows": []}
    if set(value) != {"rows"}:
        raise ValueError("recent-project index must contain only rows")
    rows = value.get("rows")
    if rows is None:
        return {"rows": []}
    if not isinstance(rows, list):
        raise ValueError("recent-project index rows must be a list")
    return {"rows": rows}


class RecentProjectEntry(BaseModel):
    """One machine-local recent-project record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: int = Field(default=1)
    project_root: str
    last_session_at: str | None = None
    last_seen_at: str | None = None
    stopped_at: str | None = None
    resume_file: str | None = None
    last_result_id: str | None = None
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
        "last_result_id",
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

    @field_validator("schema_version", mode="before")
    @classmethod
    def _normalize_schema_version(cls, value: object) -> int:
        if value is None:
            return 1
        if type(value) is not int or value != 1:
            raise ValueError("schema_version must be the integer 1")
        return value

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

    model_config = ConfigDict(frozen=True, extra="forbid")

    rows: list[RecentProjectEntry] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _normalize_payload(cls, value: object) -> object:
        return _normalize_recent_projects_index_payload(value)


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
    """Resolve canonical recovery fields from explicit row metadata."""

    resume_target_kind = _normalize_resume_target_kind(_row_value(row, "resume_target_kind"))
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
    if available_value is None:
        available = True
    else:
        available = _strict_bool_value(available_value) is True
    resume_file = _normalize_recent_text(_row_value(row, "resume_file"))
    resume_file_available = _strict_bool_value(_row_value(row, "resume_file_available"))

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


def _parse_recent_project_rows(raw_rows: list[object]) -> list[RecentProjectEntry]:
    parsed_rows: list[RecentProjectEntry] = []
    for raw_row in raw_rows:
        try:
            parsed_rows.append(RecentProjectEntry.model_validate(raw_row))
        except PydanticValidationError:
            continue
    return parsed_rows


def load_recent_projects_index(data_root: Path | None = None) -> RecentProjectIndex:
    index_path = recent_projects_index_path(data_root)
    return _load_recent_projects_index_from_path(index_path)


def _load_recent_projects_index_from_path(index_path: Path) -> RecentProjectIndex:
    content = safe_read_file(index_path)
    if content is None:
        return RecentProjectIndex()
    try:
        raw_payload = json.loads(content)
        normalized_payload = _normalize_recent_projects_index_payload(raw_payload)
    except (ValueError, json.JSONDecodeError) as exc:
        raise RecentProjectsError(f"Malformed recent-project index at {index_path}: {exc}") from exc
    rows = _parse_recent_project_rows(list(normalized_payload["rows"]))
    annotated_rows = [_annotate_availability(row) for row in _dedupe_rows(_sort_rows(rows))]
    return RecentProjectIndex(rows=annotated_rows)

def record_recent_project(
    project_root: Path,
    *,
    session_data: dict[str, object],
    store_root: Path | None = None,
) -> RecentProjectEntry:
    """Insert or update one recent-project row."""
    resolved_root = project_root.expanduser().resolve(strict=False)
    data_root = store_root
    index_path = recent_projects_index_path(data_root)
    with file_lock(index_path):
        current = _load_recent_projects_index_from_path(index_path)
        existing = next((row for row in current.rows if row.project_root == resolved_root.as_posix()), None)
        last_session_at = _updated_text(
            session_data,
            existing.last_session_at if existing is not None else None,
            "last_date",
            "last_session_at",
        )
        last_seen_at = _updated_text(
            session_data,
            existing.last_seen_at if existing is not None else last_session_at,
            "last_seen_at",
            "last_date",
            "last_session_at",
        )
        normalized_resume_file = _updated_text(
            session_data,
            existing.resume_file if existing is not None else None,
            "resume_file",
        )
        normalized_last_result_id = _updated_text(
            session_data,
            existing.last_result_id if existing is not None else None,
            "last_result_id",
        )
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
        source_kind = _updated_text(
            session_data,
            existing.source_kind if existing is not None else None,
            "source_kind",
            "provenance_kind",
        )
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
        if normalized_resume_file is not None and resume_target_kind is None:
            resume_target_kind = "handoff"
        if (
            normalized_resume_file is not None
            and resume_target_recorded_at is None
            and resume_target_kind in _RECENT_PROJECT_TARGET_KINDS
        ):
            resume_target_recorded_at = source_recorded_at or last_session_at or last_seen_at
        if "resume_file" in session_data and normalized_resume_file is None:
            normalized_last_result_id = None
            resume_target_kind = None
            resume_target_recorded_at = None
            source_kind = None
            source_session_id = None
            source_segment_id = None
            source_transition_id = None
            source_event_id = None
            source_recorded_at = None
            recovery_phase = None
            recovery_plan = None
        updated_entry = RecentProjectEntry(
            project_root=resolved_root.as_posix(),
            last_session_at=last_session_at,
            last_seen_at=last_seen_at,
            stopped_at=_updated_text(session_data, existing.stopped_at if existing is not None else None, "stopped_at"),
            resume_file=normalized_resume_file,
            last_result_id=normalized_last_result_id,
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

        atomic_write(index_path, RecentProjectIndex(rows=_dedupe_rows(_sort_rows(rows))).model_dump_json(indent=2) + "\n")
    return _annotate_availability(updated_entry)


def list_recent_projects(store_root: Path | None = None, *, last: int | None = None) -> list[RecentProjectEntry]:
    """Return recent-project rows sorted newest-first with availability annotations.

    ``last`` is a hard limit: ``None`` returns the full index, positive values
    return that many rows, and zero or negative values return an empty list.
    """
    if last is not None and last <= 0:
        return []
    current = load_recent_projects_index(store_root)
    rows = [_annotate_availability(entry) for entry in _dedupe_rows(_sort_rows(list(current.rows)))]
    if last is not None:
        rows = rows[:last]
    return rows
