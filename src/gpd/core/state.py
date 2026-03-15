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
import re
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from gpd.contracts import (
    ConventionLock,
    ResearchContract,
    VerificationEvidence,
)
from gpd.core.constants import (
    ENV_GPD_DEBUG,
    PHASES_DIR_NAME,
    PLAN_SUFFIX,
    PLANNING_DIR_NAME,
    PROJECT_FILENAME,
    STANDALONE_PLAN,
    STANDALONE_SUMMARY,
    STATE_ARCHIVE_FILENAME,
    STATE_JSON_BACKUP_FILENAME,
    STATE_LINES_BUDGET,
    STATE_LINES_TARGET,
    SUMMARY_SUFFIX,
    ProjectLayout,
)
from gpd.core.contract_validation import salvage_project_contract, validate_project_contract
from gpd.core.conventions import KNOWN_CONVENTIONS, is_bogus_value
from gpd.core.errors import StateError
from gpd.core.extras import Approximation
from gpd.core.extras import Uncertainty as PropagatedUncertainty
from gpd.core.observability import gpd_span, instrument_gpd_function
from gpd.core.results import IntermediateResult
from gpd.core.utils import (
    atomic_write,
    compare_phase_numbers,
    file_lock,
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
    "state_resolve_blocker",
    "state_snapshot",
    "state_update",
    "state_update_progress",
    "state_validate",
    "sync_state_json",
    "validate_state_transition",
]

EM_DASH = "\u2014"

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
    stopped_at: str | None = None
    resume_file: str | None = None


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
    performance_metrics: PerformanceMetrics = Field(default_factory=PerformanceMetrics)
    decisions: list[Decision] = Field(default_factory=list)
    approximations: list[Approximation] = Field(default_factory=list)
    convention_lock: ConventionLock = Field(default_factory=ConventionLock)
    propagated_uncertainties: list[PropagatedUncertainty] = Field(default_factory=list)
    pending_todos: list[str | dict] = Field(default_factory=list)
    blockers: list[str | dict] = Field(default_factory=list)
    session: SessionInfo = Field(default_factory=SessionInfo)

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


class StateUpdateResult(BaseModel):
    """Returned by :func:`state_update`."""

    model_config = ConfigDict(frozen=True)

    updated: bool
    reason: str | None = None


class StatePatchResult(BaseModel):
    """Returned by :func:`state_patch`."""

    model_config = ConfigDict(frozen=True)

    updated: list[str] = Field(default_factory=list)
    failed: list[str] = Field(default_factory=list)


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
    """Returned by :func:`state_update_progress`."""

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
    if value == "\u2014":
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
    session = {"last_date": None, "stopped_at": None, "resume_file": None}
    session_match = re.search(
        r"##\s*Session Continuity\s*\n([\s\S]*?)(?=\n##|$)",
        content,
        re.IGNORECASE,
    )
    if session_match:
        sec = session_match.group(1)
        ld = re.search(r"\*\*Last session:\*\*\s*(.+)", sec)
        sa = re.search(r"\*\*Stopped at:\*\*\s*(.+)", sec)
        rf = re.search(r"\*\*Resume file:\*\*\s*(.+)", sec)
        if ld:
            session["last_date"] = ld.group(1).strip()
        if sa:
            session["stopped_at"] = sa.group(1).strip()
        if rf:
            session["resume_file"] = rf.group(1).strip()

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
    """Return None if *value* is a markdown placeholder (EM_DASH or '[Not set]')."""
    if value is None:
        return None
    stripped = value.strip()
    if stripped == "\u2014" or stripped.lower() == "[not set]":
        return None
    return stripped


def parse_state_to_json(content: str) -> dict:
    """Parse STATE.md content into JSON-sidecar format."""
    parsed = parse_state_md(content)

    last_date = _strip_placeholder(parsed["session"]["last_date"])
    stopped_at = _strip_placeholder(parsed["session"]["stopped_at"])
    resume_file = _strip_placeholder(parsed["session"]["resume_file"])
    session: dict[str, str | None] = {
        "last_date": last_date,
        "stopped_at": stopped_at,
        "resume_file": resume_file,
    }

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


def _normalize_state_schema(raw: dict | None) -> tuple[dict, list[str]]:
    """Normalize a raw state dict and capture integrity-affecting coercions."""
    if not raw:
        return default_state_dict(), []
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
                integrity_issues.append(
                    f'schema normalization: dropped "{key}" because expected object, got {type(normalized[key]).__name__}'
                )
                del normalized[key]

    normalized = _salvage_state_sections(normalized, integrity_issues)

    try:
        return ResearchState.model_validate(normalized).model_dump(), integrity_issues
    except PydanticValidationError as exc:
        bad_keys: set[str] = set()
        for err in exc.errors():
            loc = err.get("loc", ())
            if loc:
                bad_keys.add(str(loc[0]))

        if bad_keys:
            integrity_issues.append(
                "schema normalization: removed invalid top-level sections "
                + ", ".join(sorted(f'"{key}"' for key in bad_keys))
            )
            for bad_key in bad_keys:
                normalized.pop(bad_key, None)
            try:
                return ResearchState.model_validate(normalized).model_dump(), integrity_issues
            except PydanticValidationError:
                pass

        logger.warning("state.json had irrecoverable schema errors; resetting to defaults")
        integrity_issues.append("schema normalization: irrecoverable validation failure; reset to defaults")
        result = default_state_dict()
        for key, value in normalized.items():
            if key not in result:
                result[key] = value
        return result, integrity_issues


def _format_validation_location(loc: tuple[object, ...]) -> str:
    return ".".join(str(part) for part in loc)


def _first_validation_issue(exc: PydanticValidationError) -> str:
    first = exc.errors()[0] if exc.errors() else {}
    location = _format_validation_location(tuple(first.get("loc", ())))
    message = str(first.get("msg", "validation failed"))
    return f"{location}: {message}" if location else message


def _integrity_issue_from_contract_error(error: str) -> str:
    if error.endswith(": Extra inputs are not permitted"):
        path = error.rsplit(":", 1)[0].strip()
        return f'schema normalization: dropped unknown "project_contract.{path}"'
    if " must be an object, not " in error:
        path, actual = error.split(" must be an object, not ", 1)
        return f'schema normalization: reset "project_contract.{path}" because expected object, got {actual}'
    if " must be a list, not " in error:
        path, actual = error.split(" must be a list, not ", 1)
        return f'schema normalization: reset "project_contract.{path}" because expected list, got {actual}'
    if error.endswith(" is required"):
        normalized_error = error.replace("scope.", "project_contract.scope.", 1)
        return f"schema normalization: {normalized_error}"
    if ":" in error:
        path, detail = error.split(":", 1)
        return f'schema normalization: dropped malformed "project_contract.{path.strip()}": {detail.strip()}'
    return f"schema normalization: {error}"


def _normalize_project_contract_section(value: object, integrity_issues: list[str]) -> object:
    if value is None or not isinstance(value, dict):
        return value

    try:
        return ResearchContract.model_validate(value).model_dump()
    except PydanticValidationError:
        pass

    normalized_contract, errors = salvage_project_contract(value)
    integrity_issues.extend(_integrity_issue_from_contract_error(error) for error in errors)
    return normalized_contract.model_dump() if normalized_contract is not None else None


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
            integrity_issues.append(f'schema normalization: dropped malformed "intermediate_results[{index}]": {detail}')
            changed = True

    return normalized_results if changed else value


def _salvage_state_sections(normalized: dict[str, object], integrity_issues: list[str]) -> dict[str, object]:
    if normalized.get("project_contract") is not None:
        normalized["project_contract"] = _normalize_project_contract_section(
            normalized.get("project_contract"),
            integrity_issues,
        )
    if normalized.get("intermediate_results") is not None:
        normalized["intermediate_results"] = _normalize_intermediate_results_section(
            normalized.get("intermediate_results"),
            integrity_issues,
        )
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
        metadata_tokens = [
            token.strip()
            for token in metadata_match.group("meta").split(",")
            if token.strip()
        ]

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


def _state_lock(cwd: Path, timeout: float = 5.0):
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

    if json_tmp_exists and md_tmp_exists and json_valid and md_valid:
        # Both temp files ready and valid — complete the interrupted write
        os.rename(json_tmp, json_path)
        os.rename(md_tmp, md_path)
    else:
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


def _build_state_from_markdown(cwd: Path, md_content: str) -> dict:
    """Merge markdown-derived state into the existing JSON state."""
    json_path = _state_json_path(cwd)
    parsed = parse_state_to_json(md_content)
    has_convention_lock = _has_bold_block(md_content, "Convention Lock")
    has_approximations = _has_subsection(md_content, "Active Approximations")
    has_uncertainties = _has_subsection(md_content, "Propagated Uncertainties")
    has_pending_todos = _has_subsection(md_content, "Pending Todos")

    existing = None
    try:
        existing = json.loads(json_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        logger.warning("state.json is corrupt, attempting backup restore: %s", e)
        bak_path = json_path.parent / STATE_JSON_BACKUP_FILENAME
        try:
            existing = json.loads(bak_path.read_text(encoding="utf-8"))
            logger.info("Restored from state.json.bak")
        except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
            if os.environ.get(ENV_GPD_DEBUG):
                logger.debug("state.json.bak also unavailable")

    if existing and isinstance(existing, dict):
        merged = {**existing}
        merged["_version"] = parsed["_version"]
        merged["_synced_at"] = parsed["_synced_at"]

        if parsed.get("project_reference"):
            merged["project_reference"] = {**(merged.get("project_reference") or {}), **parsed["project_reference"]}

        if parsed.get("position"):
            merged["position"] = {**(merged.get("position") or {}), **parsed["position"]}

        if parsed.get("session") is not None:
            merged["session"] = {**(merged.get("session") or {}), **parsed["session"]}

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
    else:
        merged = parsed

    return ensure_state_schema(merged)


def _write_state_pair_locked(cwd: Path, *, state_obj: dict, md_content: str) -> dict:
    """Atomically persist state.json + STATE.md under the canonical state lock."""
    planning = _planning_dir(cwd)
    planning.mkdir(parents=True, exist_ok=True)
    json_path = _state_json_path(cwd)
    md_path = _state_md_path(cwd)
    intent_file = _intent_path(cwd)
    temp_suffix = f"{os.getpid()}.{uuid4().hex}"
    json_tmp = json_path.with_suffix(f".json.tmp.{temp_suffix}")
    md_tmp = md_path.with_suffix(f".md.tmp.{temp_suffix}")

    json_backup = safe_read_file(json_path)
    md_backup = safe_read_file(md_path)

    normalized = ensure_state_schema(state_obj)
    json_rendered = json.dumps(normalized, indent=2) + "\n"

    try:
        atomic_write(json_tmp, json_rendered)
        atomic_write(md_tmp, md_content)

        intent_file.write_text(f"{json_tmp}\n{md_tmp}\n", encoding="utf-8")
        os.rename(json_tmp, json_path)
        os.rename(md_tmp, md_path)
        try:
            intent_file.unlink(missing_ok=True)
        except OSError:
            pass

        try:
            atomic_write(json_path.parent / STATE_JSON_BACKUP_FILENAME, json_rendered)
        except OSError:
            if os.environ.get(ENV_GPD_DEBUG):
                logger.debug("Failed to write state.json backup")
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

    return normalized


def _write_state_markdown_locked(cwd: Path, content: str) -> dict:
    """Write STATE.md and sync state.json while holding the canonical state lock."""
    return save_state_markdown_locked(cwd, content)


def sync_state_json_core(cwd: Path, md_content: str) -> dict:
    """Core sync logic: parse STATE.md -> merge into state.json.

    Caller MUST hold the state.json lock.
    """
    json_path = _state_json_path(cwd)
    merged = _build_state_from_markdown(cwd, md_content)

    json_content = json.dumps(merged, indent=2) + "\n"
    atomic_write(json_path, json_content)
    # Create backup
    try:
        atomic_write(json_path.parent / STATE_JSON_BACKUP_FILENAME, json_content)
    except OSError:
        if os.environ.get(ENV_GPD_DEBUG):
            logger.debug("sync_state_json backup write failed")

    return merged


@instrument_gpd_function("state.sync")
def sync_state_json(cwd: Path, md_content: str) -> dict:
    """Parse STATE.md and sync into state.json (with locking)."""
    with _state_lock(cwd):
        return sync_state_json_core(cwd, md_content)


@instrument_gpd_function("state.load_json")
def load_state_json(cwd: Path, integrity_mode: str = "standard") -> dict | None:
    """Load state.json with intent recovery and fallback to STATE.md.

    Returns the state dict, or None if no state exists.
    """
    json_path = _state_json_path(cwd)
    bak_path = json_path.parent / STATE_JSON_BACKUP_FILENAME

    with _state_lock(cwd):
        _recover_intent_locked(cwd)

        try:
            raw = json_path.read_text(encoding="utf-8")
            normalized, integrity_issues = _normalize_state_schema(json.loads(raw))
            if integrity_mode == "review" and integrity_issues:
                logger.warning("state.json failed review-mode integrity checks: %s", "; ".join(integrity_issues))
                return None
            return normalized
        except FileNotFoundError:
            pass
        except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
            if os.environ.get(ENV_GPD_DEBUG):
                logger.debug("state.json parse error: %s", e)
            if integrity_mode == "review":
                logger.warning("state.json parse error blocks review-mode loading: %s", e)
                return None
            # Try backup
            try:
                bak_raw = bak_path.read_text(encoding="utf-8")
                restored, integrity_issues = _normalize_state_schema(json.loads(bak_raw))
                if integrity_mode == "review" and integrity_issues:
                    logger.warning("state.json backup failed review-mode integrity checks: %s", "; ".join(integrity_issues))
                    return None
                atomic_write(json_path, json.dumps(restored, indent=2) + "\n")
                return restored
            except (FileNotFoundError, json.JSONDecodeError, OSError, UnicodeDecodeError):
                if os.environ.get(ENV_GPD_DEBUG):
                    logger.debug("state.json.bak restore failed")

        # Fall back to STATE.md
        md_path = _state_md_path(cwd)
        try:
            if integrity_mode == "review":
                logger.warning("STATE.md fallback is disabled in review integrity mode")
                return None
            content = md_path.read_text(encoding="utf-8")
            return sync_state_json_core(cwd, content)
        except (FileNotFoundError, OSError, UnicodeDecodeError):
            if os.environ.get(ENV_GPD_DEBUG):
                logger.debug("STATE.md fallback failed")
            return None


def save_state_json_locked(cwd: Path, state_obj: dict) -> None:
    """Core write logic: write state.json + regenerate STATE.md atomically.

    Caller MUST hold the canonical state lock.
    """
    normalized = ensure_state_schema(state_obj)
    _write_state_pair_locked(cwd, state_obj=normalized, md_content=generate_state_markdown(normalized))


def save_state_markdown_locked(cwd: Path, md_content: str) -> dict:
    """Atomically write markdown-derived state while holding the canonical state lock."""
    merged = _build_state_from_markdown(cwd, md_content)
    return _write_state_pair_locked(cwd, state_obj=merged, md_content=md_content)


@instrument_gpd_function("state.save")
def save_state_json(cwd: Path, state_obj: dict) -> None:
    """Save state.json + STATE.md atomically (with locking)."""
    with _state_lock(cwd):
        save_state_json_locked(cwd, state_obj)


@instrument_gpd_function("state.save_markdown")
def save_state_markdown(cwd: Path, md_content: str) -> dict:
    """Save STATE.md + state.json atomically from markdown content."""
    with _state_lock(cwd):
        return save_state_markdown_locked(cwd, md_content)


# ─── State Commands ────────────────────────────────────────────────────────────


@instrument_gpd_function("state.load")
def state_load(cwd: Path, integrity_mode: str = "standard") -> StateLoadResult:
    """Load full state with config and file-existence metadata."""
    state_obj = load_state_json(cwd, integrity_mode=integrity_mode)
    validation = state_validate(cwd, integrity_mode=integrity_mode)

    layout = ProjectLayout(cwd)
    state_raw = safe_read_file(layout.state_md) or ""

    return StateLoadResult(
        state=state_obj or {},
        state_raw=state_raw,
        state_exists=state_obj is not None or len(state_raw) > 0,
        roadmap_exists=layout.roadmap.exists(),
        config_exists=layout.config_json.exists(),
        integrity_mode=integrity_mode,
        integrity_status=validation.integrity_status,
        integrity_issues=list(validation.issues),
    )


@instrument_gpd_function("state.get")
def state_get(cwd: Path, section: str | None = None) -> StateGetResult:
    """Get full STATE.md content or a specific field/section."""
    md_path = _state_md_path(cwd)
    content = safe_read_file(md_path)
    if content is None:
        raise StateError(
            f"STATE.md not found at {md_path}. "
            "Run 'gpd init' to create the project state file."
        )

    if not section:
        return StateGetResult(content=content)

    # Normalize snake_case → space-separated (e.g. "current_phase" → "current phase")
    section_norm = section.replace("_", " ")

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

    md_path = _state_md_path(cwd)
    if not md_path.exists():
        return StateUpdateResult(updated=False, reason="STATE.md not found")

    with _state_lock(cwd):
        content = md_path.read_text(encoding="utf-8")
        field_norm = field.replace("_", " ")

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
    if not md_path.exists():
        raise StateError(
            f"STATE.md not found at {md_path}. "
            "Run 'gpd init' to create the project state file before patching."
        )

    with _state_lock(cwd):
        content = md_path.read_text(encoding="utf-8")
        updated: list[str] = []
        failed: list[str] = []

        for field, value in patches.items():
            # Normalize snake_case → Title Case (e.g. "current_plan" → "Current Plan")
            field_norm = field.replace("_", " ")

            if field_norm.lower() == "status" and not is_valid_status(value):
                failed.append(field)
                continue

            if field_norm.lower() == "status":
                current_status = state_extract_field(content, "Status")
                if current_status:
                    err = validate_state_transition(current_status, value)
                    if err:
                        failed.append(field)
                        continue

            if state_has_field(content, field_norm):
                content = state_replace_field(content, field_norm, value)
                updated.append(field)
            else:
                failed.append(field)

        if updated:
            _write_state_markdown_locked(cwd, content)

    return StatePatchResult(updated=updated, failed=failed)


@instrument_gpd_function("state.set_project_contract")
def state_set_project_contract(cwd: Path, contract_data: dict[str, object] | ResearchContract) -> StateUpdateResult:
    """Persist the canonical project contract to ``state.json``.

    This is a JSON-only state field, so it bypasses ``STATE.md`` field patching and
    writes through the authoritative structured state path instead.
    """
    from pydantic import ValidationError

    try:
        if isinstance(contract_data, ResearchContract):
            parsed = contract_data
        else:
            normalized_contract, _errors = salvage_project_contract(contract_data)
            candidate = normalized_contract.model_dump() if normalized_contract is not None else contract_data
            parsed = ResearchContract.model_validate(candidate)
    except ValidationError as exc:
        first_error = exc.errors()[0] if exc.errors() else {}
        location = ".".join(str(part) for part in first_error.get("loc", ())) or "project_contract"
        message = first_error.get("msg", "validation failed")
        return StateUpdateResult(updated=False, reason=f"Invalid project contract at {location}: {message}")

    validation = validate_project_contract(parsed, mode="approved")
    if not validation.valid:
        return StateUpdateResult(
            updated=False,
            reason="Project contract failed scoping validation: " + "; ".join(validation.errors),
        )

    state_obj = load_state_json(cwd) or default_state_dict()
    contract_payload = parsed.model_dump()
    if state_obj.get("project_contract") == contract_payload:
        return StateUpdateResult(updated=False, reason="Project contract already matches requested value")

    state_obj["project_contract"] = contract_payload

    unresolved = [question.strip() for question in parsed.scope.unresolved_questions if question and question.strip()]
    if unresolved:
        existing_questions = {
            item.strip()
            for item in state_obj.get("open_questions", [])
            if isinstance(item, str) and item.strip()
        }
        for question in unresolved:
            if question not in existing_questions:
                state_obj.setdefault("open_questions", []).append(question)
                existing_questions.add(question)

    save_state_json(cwd, state_obj)
    return StateUpdateResult(updated=True)


@instrument_gpd_function("state.advance_plan")
def state_advance_plan(cwd: Path) -> AdvancePlanResult:
    """Advance to the next plan, or mark phase complete if on last plan."""
    md_path = _state_md_path(cwd)
    if not md_path.exists():
        return AdvancePlanResult(advanced=False, error="STATE.md not found")

    with _state_lock(cwd):
        content = md_path.read_text(encoding="utf-8")
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
    md_path = _state_md_path(cwd)
    if not md_path.exists():
        return RecordMetricResult(recorded=False, error="STATE.md not found")

    if not phase or not plan or not duration:
        return RecordMetricResult(recorded=False, error="phase, plan, and duration required")

    with _state_lock(cwd):
        content = md_path.read_text(encoding="utf-8")

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
    md_path = _state_md_path(cwd)
    if not md_path.exists():
        return UpdateProgressResult(updated=False, error="STATE.md not found")

    with _state_lock(cwd):
        content = md_path.read_text(encoding="utf-8")

        phases_dir = ProjectLayout(cwd).phases_dir
        total_plans = 0
        total_completed = 0

        if phases_dir.exists():
            for phase_dir in phases_dir.iterdir():
                if not phase_dir.is_dir():
                    continue
                phase_files = [f.name for f in phase_dir.iterdir() if f.is_file()]
                phase_plans = sum(1 for f in phase_files if f.endswith(PLAN_SUFFIX) or f == STANDALONE_PLAN)
                phase_summaries = sum(1 for f in phase_files if f.endswith(SUMMARY_SUFFIX) or f == STANDALONE_SUMMARY)
                total_plans += phase_plans
                total_completed += min(phase_plans, phase_summaries)

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
                updated=True, percent=percent, completed=total_completed, total=total_plans, bar=progress_str
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
    md_path = _state_md_path(cwd)
    if not md_path.exists():
        return AddDecisionResult(added=False, error="STATE.md not found")
    if not summary:
        return AddDecisionResult(added=False, error="summary required")

    summary_clean = summary.replace("\n", " ").strip()
    rat_str = f" \u2014 {rationale.replace(chr(10), ' ').strip()}" if rationale else ""
    entry = f"- [Phase {phase or '?'}]: {summary_clean}{rat_str}"

    with _state_lock(cwd):
        content = md_path.read_text(encoding="utf-8")
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
    md_path = _state_md_path(cwd)
    if not md_path.exists():
        return AddBlockerResult(added=False, error="STATE.md not found")
    if not text:
        return AddBlockerResult(added=False, error="text required")

    text_clean = text.replace("\n", " ").strip()
    entry = f"- {text_clean}"

    with _state_lock(cwd):
        content = md_path.read_text(encoding="utf-8")
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
    md_path = _state_md_path(cwd)
    if not md_path.exists():
        return ResolveBlockerResult(resolved=False, error="STATE.md not found")
    if not text:
        return ResolveBlockerResult(resolved=False, error="text required")
    if len(text) < 3:
        return ResolveBlockerResult(
            resolved=False, error="search text must be at least 3 characters to avoid accidental matches"
        )

    with _state_lock(cwd):
        content = md_path.read_text(encoding="utf-8")
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


@instrument_gpd_function("state.record_session")
def state_record_session(
    cwd: Path,
    *,
    stopped_at: str | None = None,
    resume_file: str | None = None,
) -> RecordSessionResult:
    """Record session info in STATE.md."""
    md_path = _state_md_path(cwd)
    if not md_path.exists():
        with gpd_span(
            "session.continuity.missing_state",
            cwd=str(cwd),
            stopped_at=stopped_at or "",
            resume_file=resume_file or EM_DASH,
        ):
            pass
        return RecordSessionResult(recorded=False, error="STATE.md not found")

    with _state_lock(cwd):
        content = md_path.read_text(encoding="utf-8")
        now = datetime.now(tz=UTC).isoformat()
        updated: list[str] = []

        new_content = state_replace_field(content, "Last session", now)
        if new_content != content:
            content = new_content
            updated.append("Last session")

        if stopped_at:
            new_content = state_replace_field(content, "Stopped at", stopped_at)
            if new_content != content:
                content = new_content
                updated.append("Stopped at")

        resume = resume_file or EM_DASH
        new_content = state_replace_field(content, "Resume file", resume)
        if new_content != content:
            content = new_content
            updated.append("Resume file")

        if updated:
            _write_state_markdown_locked(cwd, content)
            with gpd_span(
                "session.continuity.recorded",
                cwd=str(cwd),
                updated_fields=",".join(updated),
                stopped_at=stopped_at or "",
                resume_file=resume,
            ):
                pass
            return RecordSessionResult(recorded=True, updated=updated)

        with gpd_span(
            "session.continuity.noop",
            cwd=str(cwd),
            stopped_at=stopped_at or "",
            resume_file=resume,
        ):
            pass
        return RecordSessionResult(recorded=False, reason="No session fields found in STATE.md")


@instrument_gpd_function("state.snapshot")
def state_snapshot(cwd: Path) -> StateSnapshotResult:
    """Fast snapshot of state for progress/routing commands."""
    state_obj = load_state_json(cwd)
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
def state_validate(cwd: Path, integrity_mode: str = "standard") -> StateValidateResult:
    """Validate state consistency between state.json and STATE.md."""
    from gpd.core.contract_validation import validate_project_contract

    json_path = _state_json_path(cwd)
    md_path = _state_md_path(cwd)
    issues: list[str] = []
    warnings: list[str] = []

    # Load state.json
    state_json = None
    try:
        raw_state_json = json.loads(json_path.read_text(encoding="utf-8"))
        if not isinstance(raw_state_json, dict):
            issues.append(
                f"state.json root must be an object, got {type(raw_state_json).__name__}; validating normalized fallback"
            )
        state_json, normalization_issues = _normalize_state_schema(raw_state_json)
        if normalization_issues:
            target = issues if integrity_mode == "review" else warnings
            target.extend(normalization_issues)
        if isinstance(raw_state_json, dict):
            raw_version = raw_state_json.get("_version")
            if raw_version not in (None, 1):
                target = issues if integrity_mode == "review" else warnings
                target.append(f"state.json version drift: expected 1, found {raw_version}")
    except FileNotFoundError:
        issues.append("state.json not found")
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        issues.append(f"state.json parse error: {e}")

    # Load and parse STATE.md
    state_md = None
    try:
        content = md_path.read_text(encoding="utf-8")
        issues.extend(_state_markdown_structure_issues(content))
        state_md = parse_state_to_json(content)
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
        )

    if isinstance(state_json, dict) and state_json.get("project_contract") is not None:
        contract_validation = validate_project_contract(state_json.get("project_contract"), mode="approved")
        if contract_validation.errors:
            target = issues if integrity_mode == "review" else warnings
            target.extend(f"project_contract: {error}" for error in contract_validation.errors)
        if contract_validation.warnings:
            warnings.extend(f"project_contract: {warning}" for warning in contract_validation.warnings)

    # Cross-check position fields
    json_pos = state_json.get("position") if isinstance(state_json, dict) else None
    md_pos = state_md.get("position") if isinstance(state_md, dict) else None
    if isinstance(json_pos, dict) and isinstance(md_pos, dict):
        pos_fields = [
            "current_phase",
            "current_phase_name",
            "status",
            "current_plan",
            "total_phases",
            "total_plans_in_phase",
            "last_activity",
            "last_activity_desc",
            "paused_at",
        ]
        phase_fields = {"current_phase", "current_phase_name"}
        for field in pos_fields:
            json_val = json_pos.get(field)
            md_val = md_pos.get(field)
            if json_val is not None and md_val is not None:
                if field in phase_fields:
                    j_str = phase_normalize(str(json_val))
                    m_str = phase_normalize(str(md_val))
                else:
                    j_str = str(json_val)
                    m_str = str(md_val)
                if j_str != m_str:
                    issues.append(f'position.{field} mismatch: json="{json_val}" vs md="{md_val}"')

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
                target.append(f'intermediate_results[{rid}]: verified=true but no verification_records present')
            if records and not r.get("verified"):
                warnings.append(f'intermediate_results[{rid}]: verification_records present while verified=false')

            for index, record in enumerate(records):
                if not isinstance(record, dict):
                    issues.append(f"intermediate_results[{rid}]: verification_records[{index}] is not an object")
                    continue
                evidence_path = record.get("evidence_path")
                if evidence_path:
                    evidence_file = Path(cwd) / str(evidence_path)
                    if not evidence_file.exists():
                        target = issues if integrity_mode == "review" else warnings
                        target.append(
                            f'intermediate_results[{rid}]: evidence_path "{evidence_path}" does not exist'
                        )

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
    )


# ─── Compact ───────────────────────────────────────────────────────────────────


@instrument_gpd_function("state.compact")
def state_compact(cwd: Path) -> StateCompactResult:
    """Compact STATE.md by archiving old decisions, blockers, metrics, and sessions."""
    md_path = _state_md_path(cwd)
    if not md_path.exists():
        return StateCompactResult(compacted=False, error="STATE.md not found")

    with _state_lock(cwd):
        _recover_intent_locked(cwd)
        content = md_path.read_text(encoding="utf-8")
        lines = content.split("\n")
        total_lines = len(lines)
        warn_threshold = STATE_LINES_TARGET
        line_budget = STATE_LINES_BUDGET

        if total_lines <= warn_threshold:
            return StateCompactResult(compacted=False, reason="within_budget", lines=total_lines, warn=False)

        soft_mode = total_lines < line_budget

        # Determine current phase
        state_obj = None
        try:
            state_obj = ensure_state_schema(json.loads(_state_json_path(cwd).read_text(encoding="utf-8")))
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass

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
