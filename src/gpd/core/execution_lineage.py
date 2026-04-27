"""Append-only execution lineage storage and derived head helpers.

The lineage stream is a history/audit surface only. The derived head is a cache
projection for later observability integration and compatibility surfaces. It
does not replace canonical continuation authority in ``state.json``.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from enum import StrEnum
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from gpd.core.constants import (
    EXECUTION_LINEAGE_HEAD_FILENAME,
    EXECUTION_LINEAGE_LEDGER_FILENAME,
    EXECUTION_LINEAGE_REDUCER_VERSION,
    EXECUTION_LINEAGE_SCHEMA_VERSION,
    LINEAGE_DIR_NAME,
    ProjectLayout,
)
from gpd.core.continuation import ContinuationBoundedSegment
from gpd.core.utils import atomic_write, phase_normalize, safe_read_file

__all__ = [
    "ExecutionHeadEffect",
    "ExecutionLineageEntry",
    "ExecutionLineageHead",
    "build_execution_lineage_entry",
    "clear_execution_lineage_head",
    "derive_execution_lineage_head",
    "execution_lineage_head_path",
    "execution_lineage_ledger_path",
    "execution_lineage_root",
    "load_execution_lineage_entries",
    "load_execution_lineage_head",
    "project_execution_lineage_head",
    "rebuild_execution_lineage_head",
    "write_execution_lineage_head",
]


class ExecutionHeadEffect(StrEnum):
    """How one lineage entry changes the derived execution head."""

    SEED = "seed"
    REPLACE = "replace"
    CLEAR = "clear"
    NOOP = "noop"


class ExecutionLineageEntry(BaseModel):
    """One append-only execution lineage record."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    schema_version: int = EXECUTION_LINEAGE_SCHEMA_VERSION
    seq: int = 0
    event_id: str
    recorded_at: str
    kind: str
    reducer_version: str = EXECUTION_LINEAGE_REDUCER_VERSION
    session_id: str | None = None
    phase: str | None = None
    plan: str | None = None
    segment_id: str | None = None
    parent_segment_id: str | None = None
    prev_event_id: str | None = None
    causation_event_id: str | None = None
    source_category: str | None = None
    source_name: str | None = None
    source_action: str | None = None
    head_effect: ExecutionHeadEffect = ExecutionHeadEffect.REPLACE
    head_after: dict[str, object] | None = None
    bounded_segment_after: ContinuationBoundedSegment | None = None
    data: dict[str, object] = Field(default_factory=dict)

    @field_validator(
        "event_id",
        "recorded_at",
        "kind",
        "reducer_version",
        "session_id",
        "phase",
        "plan",
        "segment_id",
        "parent_segment_id",
        "prev_event_id",
        "causation_event_id",
        "source_category",
        "source_name",
        "source_action",
        mode="before",
    )
    @classmethod
    def _normalize_text_fields(cls, value: object) -> str | None:
        return _normalize_optional_text(value)

    @field_validator("phase", "plan", mode="before")
    @classmethod
    def _normalize_phase_like_fields(cls, value: object) -> object:
        return _normalize_phase_like(value)

    @field_validator("seq", mode="before")
    @classmethod
    def _normalize_sequence(cls, value: object) -> int:
        if isinstance(value, bool):
            return 0
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return 0
            try:
                return int(stripped)
            except ValueError:
                return 0
        return 0

    @field_validator("data", mode="before")
    @classmethod
    def _normalize_data(cls, value: object) -> dict[str, object]:
        return _mapping(value)

    @property
    def is_seed(self) -> bool:
        return self.head_effect == ExecutionHeadEffect.SEED


class ExecutionLineageHead(BaseModel):
    """Derived latest-view execution head projection."""

    model_config = ConfigDict(frozen=True, extra="ignore")

    schema_version: int = EXECUTION_LINEAGE_SCHEMA_VERSION
    reducer_version: str = EXECUTION_LINEAGE_REDUCER_VERSION
    last_applied_seq: int | None = None
    last_applied_event_id: str | None = None
    recorded_at: str | None = None
    execution: dict[str, object] | None = None
    bounded_segment: ContinuationBoundedSegment | None = None

    @field_validator("reducer_version", "last_applied_event_id", "recorded_at", mode="before")
    @classmethod
    def _normalize_text_fields(cls, value: object) -> str | None:
        return _normalize_optional_text(value)

    @field_validator("last_applied_seq", mode="before")
    @classmethod
    def _normalize_sequence(cls, value: object) -> int | None:
        if isinstance(value, bool):
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                return None
            try:
                return int(stripped)
            except ValueError:
                return None
        return None

    @field_validator("execution", mode="before")
    @classmethod
    def _normalize_execution(cls, value: object) -> dict[str, object] | None:
        return _as_mapping(value)

    @field_validator("bounded_segment", mode="before")
    @classmethod
    def _normalize_bounded_segment(
        cls, value: object
    ) -> dict[str, object] | ContinuationBoundedSegment | None:
        if value is None:
            return None
        if isinstance(value, ContinuationBoundedSegment):
            return value
        mapping = _as_mapping(value)
        return mapping if mapping is not None else None

    @property
    def is_empty(self) -> bool:
        return self.execution is None and self.bounded_segment is None and self.last_applied_event_id is None


def _now_iso() -> str:
    from datetime import UTC, datetime

    return datetime.now(UTC).isoformat()


def _normalize_optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _normalize_phase_like(value: object) -> object:
    if isinstance(value, int):
        return phase_normalize(str(value))
    if isinstance(value, str):
        stripped = value.strip()
        return phase_normalize(stripped) if stripped else None
    return value


def _as_mapping(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return dict(value)
    return None


def _mapping(value: object) -> dict[str, object]:
    mapping = _as_mapping(value)
    return mapping if mapping is not None else {}


def _coerce_bounded_segment(value: object) -> ContinuationBoundedSegment | None:
    if value is None:
        return None
    if isinstance(value, ContinuationBoundedSegment):
        return value
    mapping = _as_mapping(value)
    if mapping is None:
        return None
    try:
        return ContinuationBoundedSegment.model_validate(mapping)
    except Exception:
        return None


def _layout(project_root: Path | str | ProjectLayout) -> ProjectLayout:
    if isinstance(project_root, ProjectLayout):
        return project_root
    root = project_root if isinstance(project_root, Path) else Path(project_root)
    return ProjectLayout(root.expanduser().resolve(strict=False))


def execution_lineage_root(project_root: Path | str | ProjectLayout) -> Path:
    """Return the lineage directory for one project root."""
    layout = _layout(project_root)
    return layout.gpd / LINEAGE_DIR_NAME


def execution_lineage_ledger_path(project_root: Path | str | ProjectLayout) -> Path:
    """Return the append-only execution lineage ledger path."""
    layout = _layout(project_root)
    return layout.lineage_dir / EXECUTION_LINEAGE_LEDGER_FILENAME


def execution_lineage_head_path(project_root: Path | str | ProjectLayout) -> Path:
    """Return the derived execution head cache path."""
    layout = _layout(project_root)
    return layout.lineage_dir / EXECUTION_LINEAGE_HEAD_FILENAME


def _read_json(path: Path) -> dict[str, object] | None:
    content = safe_read_file(path)
    if content is None:
        return None
    try:
        raw = json.loads(content)
    except Exception:
        return None
    return raw if isinstance(raw, dict) else None


def _read_jsonl(path: Path) -> list[dict[str, object]]:
    content = safe_read_file(path)
    if content is None:
        return []
    rows: list[dict[str, object]] = []
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        try:
            raw = json.loads(stripped)
        except Exception:
            continue
        if isinstance(raw, dict):
            rows.append(raw)
    return rows


def _entry_from_mapping(row: dict[str, object]) -> ExecutionLineageEntry | None:
    try:
        return ExecutionLineageEntry.model_validate(row)
    except Exception:
        return None


def load_execution_lineage_entries(project_root: Path | str | ProjectLayout) -> list[ExecutionLineageEntry]:
    """Load execution lineage entries oldest-first, skipping malformed rows."""
    ledger_path = execution_lineage_ledger_path(project_root)
    raw_rows = _read_jsonl(ledger_path)
    entries: list[ExecutionLineageEntry] = []
    for row in raw_rows:
        entry = _entry_from_mapping(row)
        if entry is not None:
            entries.append(entry)
    entries.sort(key=lambda item: (item.seq, item.recorded_at, item.event_id))
    return entries


def project_execution_lineage_head(
    execution: object | None = None,
    *,
    bounded_segment: object | None = None,
    last_applied_seq: int | None = None,
    last_applied_event_id: str | None = None,
    recorded_at: str | None = None,
    reducer_version: str = EXECUTION_LINEAGE_REDUCER_VERSION,
) -> ExecutionLineageHead:
    """Project one derived execution head from snapshot-like payloads."""
    return ExecutionLineageHead(
        reducer_version=_normalize_optional_text(reducer_version) or EXECUTION_LINEAGE_REDUCER_VERSION,
        last_applied_seq=last_applied_seq,
        last_applied_event_id=_normalize_optional_text(last_applied_event_id),
        recorded_at=_normalize_optional_text(recorded_at) or _now_iso(),
        execution=_as_mapping(execution),
        bounded_segment=_coerce_bounded_segment(bounded_segment),
    )


def derive_execution_lineage_head(
    entries: Sequence[ExecutionLineageEntry | Mapping[str, object] | BaseModel],
) -> ExecutionLineageHead | None:
    """Derive the latest execution head from one sequence of ledger entries."""
    normalized: list[ExecutionLineageEntry] = []
    for entry in entries:
        candidate = entry if isinstance(entry, ExecutionLineageEntry) else _entry_from_mapping(_as_mapping(entry) or {})
        if candidate is not None:
            normalized.append(candidate)
    if not normalized:
        return None

    latest = max(normalized, key=lambda item: (item.seq, item.recorded_at, item.event_id))
    if latest.head_effect == ExecutionHeadEffect.NOOP and latest.head_after is None and latest.bounded_segment_after is None:
        prior = [item for item in normalized if item.seq < latest.seq]
        if prior:
            latest = max(prior, key=lambda item: (item.seq, item.recorded_at, item.event_id))

    return project_execution_lineage_head(
        latest.head_after,
        bounded_segment=latest.bounded_segment_after,
        last_applied_seq=latest.seq,
        last_applied_event_id=latest.event_id,
        recorded_at=latest.recorded_at,
        reducer_version=latest.reducer_version,
    )


def _ledger_tail_entry(entries: Sequence[ExecutionLineageEntry]) -> ExecutionLineageEntry | None:
    if not entries:
        return None
    return max(entries, key=lambda item: (item.seq, item.recorded_at, item.event_id))


def _head_matches_ledger_tail(
    head: ExecutionLineageHead,
    tail: ExecutionLineageEntry | None,
) -> bool:
    if tail is None:
        return True
    return head.last_applied_seq == tail.seq and head.last_applied_event_id == tail.event_id


def _head_to_json(head: ExecutionLineageHead) -> str:
    return head.model_dump_json(indent=2)


def write_execution_lineage_head(
    project_root: Path | str | ProjectLayout,
    head: ExecutionLineageHead | Mapping[str, object] | BaseModel,
) -> ExecutionLineageHead:
    """Persist one derived execution head cache."""
    candidate = (
        head if isinstance(head, ExecutionLineageHead) else ExecutionLineageHead.model_validate(_as_mapping(head) or {})
    )
    path = execution_lineage_head_path(project_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write(path, _head_to_json(candidate))
    return candidate


def load_execution_lineage_head(project_root: Path | str | ProjectLayout) -> ExecutionLineageHead | None:
    """Load the cached head or derive it from the ledger if needed."""
    path = execution_lineage_head_path(project_root)
    entries: list[ExecutionLineageEntry] | None = None
    raw = _read_json(path)
    if raw is not None:
        try:
            cached = ExecutionLineageHead.model_validate(raw)
        except Exception:
            pass
        else:
            entries = load_execution_lineage_entries(project_root)
            if _head_matches_ledger_tail(cached, _ledger_tail_entry(entries)):
                return cached

    if entries is None:
        entries = load_execution_lineage_entries(project_root)
    derived = derive_execution_lineage_head(entries)
    if derived is None:
        return None
    return derived


def rebuild_execution_lineage_head(project_root: Path | str | ProjectLayout) -> ExecutionLineageHead | None:
    """Derive and persist the latest execution head from the append-only ledger."""
    derived = derive_execution_lineage_head(load_execution_lineage_entries(project_root))
    if derived is None:
        return None
    return write_execution_lineage_head(project_root, derived)


def clear_execution_lineage_head(project_root: Path | str | ProjectLayout) -> None:
    """Remove the derived head cache if present."""
    path = execution_lineage_head_path(project_root)
    try:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


def build_execution_lineage_entry(
    *,
    kind: str,
    event_id: str | None = None,
    recorded_at: str | None = None,
    session_id: str | None = None,
    phase: str | int | None = None,
    plan: str | int | None = None,
    segment_id: str | None = None,
    parent_segment_id: str | None = None,
    prev_event_id: str | None = None,
    causation_event_id: str | None = None,
    source_category: str | None = None,
    source_name: str | None = None,
    source_action: str | None = None,
    head_effect: ExecutionHeadEffect | str = ExecutionHeadEffect.REPLACE,
    head_after: object | None = None,
    bounded_segment_after: object | None = None,
    data: Mapping[str, object] | BaseModel | None = None,
    seq: int | None = None,
    reducer_version: str = EXECUTION_LINEAGE_REDUCER_VERSION,
) -> ExecutionLineageEntry:
    """Build one validated execution lineage entry from snapshot-like inputs."""
    return ExecutionLineageEntry(
        schema_version=EXECUTION_LINEAGE_SCHEMA_VERSION,
        seq=seq or 0,
        event_id=_normalize_optional_text(event_id) or uuid4().hex,
        recorded_at=_normalize_optional_text(recorded_at) or _now_iso(),
        kind=_normalize_optional_text(kind) or "unknown",
        reducer_version=_normalize_optional_text(reducer_version) or EXECUTION_LINEAGE_REDUCER_VERSION,
        session_id=_normalize_optional_text(session_id),
        phase=_normalize_phase_like(phase),
        plan=_normalize_phase_like(plan),
        segment_id=_normalize_optional_text(segment_id),
        parent_segment_id=_normalize_optional_text(parent_segment_id),
        prev_event_id=_normalize_optional_text(prev_event_id),
        causation_event_id=_normalize_optional_text(causation_event_id),
        source_category=_normalize_optional_text(source_category),
        source_name=_normalize_optional_text(source_name),
        source_action=_normalize_optional_text(source_action),
        head_effect=ExecutionHeadEffect(head_effect),
        head_after=_as_mapping(head_after),
        bounded_segment_after=_coerce_bounded_segment(bounded_segment_after),
        data=_mapping(data),
    )
