"""Dual-write state management for GPD research projects.

The state engine maintains two files in sync:
- STATE.md  — human-readable, editable markdown
- state.json — machine-readable, authoritative for structured data

Atomic writes with intent-marker crash recovery keep both in sync.
File locking via fcntl.flock() prevents concurrent modification.
"""

from __future__ import annotations

import json
import logging
import os
import re
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from gpd.contracts import ConventionLock
from gpd.core.constants import (
    PHASES_DIR_NAME,
    PLAN_SUFFIX,
    PLANNING_DIR_NAME,
    PROJECT_FILENAME,
    STANDALONE_PLAN,
    STANDALONE_SUMMARY,
    STATE_LINES_BUDGET,
    STATE_LINES_TARGET,
    ENV_GPD_DEBUG,
    SUMMARY_SUFFIX,
    ProjectLayout,
)
from gpd.core.errors import StateError
from gpd.core.extras import Approximation
from gpd.core.extras import Uncertainty as PropagatedUncertainty
from gpd.core.observability import instrument_gpd_function
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

    updated: bool
    error: str | None = None
    reason: str | None = None
    percent: int = 0
    completed: int = 0
    total: int = 0
    bar: str = ""


class AddDecisionResult(BaseModel):
    """Returned by :func:`state_add_decision`."""

    added: bool
    error: str | None = None
    reason: str | None = None
    decision: str | None = None


class AddBlockerResult(BaseModel):
    """Returned by :func:`state_add_blocker`."""

    added: bool
    error: str | None = None
    reason: str | None = None
    blocker: str | None = None


class ResolveBlockerResult(BaseModel):
    """Returned by :func:`state_resolve_blocker`."""

    resolved: bool
    error: str | None = None
    reason: str | None = None
    blocker: str | None = None


class RecordSessionResult(BaseModel):
    """Returned by :func:`state_record_session`."""

    recorded: bool
    error: str | None = None
    reason: str | None = None
    updated: list[str] = Field(default_factory=list)


class StateSnapshotResult(BaseModel):
    """Returned by :func:`state_snapshot`."""

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
    "Phase complete",
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
    "ready to plan": ["planning", "researching", "paused", "blocked", "not started"],
    "planning": ["ready to execute", "researching", "paused", "blocked", "ready to plan", "not started"],
    "researching": ["planning", "ready to execute", "paused", "blocked", "ready to plan", "not started"],
    "ready to execute": ["executing", "planning", "researching", "paused", "blocked", "not started"],
    "executing": [
        "phase complete",
        "phase complete \u2014 ready for verification",
        "planning",
        "researching",
        "ready to execute",
        "paused",
        "blocked",
    ],
    "phase complete": [
        "verifying",
        "phase complete \u2014 ready for verification",
        "not started",
        "planning",
        "executing",
    ],
    "phase complete \u2014 ready for verification": [
        "verifying",
        "not started",
        "planning",
        "executing",
        "paused",
    ],
    "verifying": ["complete", "phase complete \u2014 ready for verification", "planning", "blocked", "paused"],
    "complete": ["not started", "planning", "milestone complete"],
    "milestone complete": ["not started", "planning"],
    "paused": None,
    "blocked": None,
}


def is_valid_status(value: str) -> bool:
    """Check if a status value is recognized (case-insensitive prefix match)."""
    lower = value.lower()
    return any(lower.startswith(s.lower()) for s in VALID_STATUSES)


def validate_state_transition(current_status: str, new_status: str) -> str | None:
    """Validate a state transition. Returns None if valid, or an error message."""
    current_lower = current_status.lower()
    new_lower = new_status.lower()

    if current_lower == new_lower:
        return None

    matched_key = None
    for key in VALID_TRANSITIONS:
        if current_lower.startswith(key):
            matched_key = key
            break

    # Unknown current status — allow transition
    if matched_key is None:
        return None

    allowed = VALID_TRANSITIONS[matched_key]

    # None means any transition valid (recovery states)
    if allowed is None:
        return None

    if any(new_lower.startswith(target) for target in allowed):
        return None

    return f'Invalid transition: "{current_status}" \u2192 "{new_status}". Valid targets: {", ".join(allowed)}'


# ─── STATE.md Field Helpers ────────────────────────────────────────────────────


def _escape_regex(s: str) -> str:
    """Escape special regex characters in a string."""
    return re.escape(s)


def state_extract_field(content: str, field_name: str) -> str | None:
    """Extract a **Field:** value from STATE.md content."""
    escaped = _escape_regex(field_name)
    pattern = re.compile(rf"\*\*{escaped}:\*\*\s*(.+)", re.IGNORECASE)
    match = pattern.search(content)
    return match.group(1).strip() if match else None


def state_replace_field(content: str, field_name: str, new_value: str) -> str:
    """Replace a **Field:** value in STATE.md content.

    Returns the updated content if the field was found, or original content unchanged.
    """
    escaped = _escape_regex(field_name)
    pattern = re.compile(rf"(\*\*{escaped}:\*\*\s*)(.*)", re.IGNORECASE)
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
    escaped = _escape_regex(field_name)
    return bool(re.search(rf"\*\*{escaped}:\*\*", content, re.IGNORECASE))


# ─── STATE.md Parser ──────────────────────────────────────────────────────────


def _unescape_pipe(v: str) -> str:
    return v.replace("\\|", "|")


def _extract_field(content: str, field_name: str) -> str | None:
    """Extract a **Field:** value from content (internal parser helper)."""
    escaped = _escape_regex(field_name)
    pattern = re.compile(rf"\*\*{escaped}:\*\*\s*(.+)", re.IGNORECASE)
    match = pattern.search(content)
    return match.group(1).strip() if match else None


def _extract_bullets(content: str, section_name: str) -> list[str]:
    """Extract bullet list items from a ## Section."""
    escaped = _escape_regex(section_name)
    pattern = re.compile(rf"##\s*{escaped}\s*\n([\s\S]*?)(?=\n##|$)", re.IGNORECASE)
    match = pattern.search(content)
    if not match:
        return []
    bullets = re.findall(r"^-\s+(.+)$", match.group(1), re.MULTILINE)
    return [b.strip() for b in bullets if b.strip() and not re.match(r"^none", b.strip(), re.IGNORECASE)]


def parse_state_md(content: str) -> dict:
    """Parse STATE.md into a structured dict.

    This is the canonical parser — used by parse_state_to_json, migrate, and snapshot.
    """
    # Position fields
    current_phase_raw = _extract_field(content, "Current Phase")
    total_phases_raw = _extract_field(content, "Total Phases")
    total_plans_raw = _extract_field(content, "Total Plans in Phase")
    progress_raw = _extract_field(content, "Progress")

    position = {
        "current_phase": current_phase_raw,
        "current_phase_name": _extract_field(content, "Current Phase Name"),
        "total_phases": safe_parse_int(total_phases_raw, None) if total_phases_raw else None,
        "current_plan": _extract_field(content, "Current Plan"),
        "total_plans_in_phase": safe_parse_int(total_plans_raw, None) if total_plans_raw else None,
        "status": _extract_field(content, "Status"),
        "last_activity": _extract_field(content, "Last Activity"),
        "last_activity_desc": _extract_field(content, "Last Activity Description"),
        "progress_raw": progress_raw,
        "progress_percent": None,
        "paused_at": _extract_field(content, "Paused At"),
    }
    if progress_raw:
        m = re.search(r"(\d+)%", progress_raw)
        if m:
            position["progress_percent"] = int(m.group(1))

    # Project fields
    project = {
        "core_question": _extract_field(content, "Core research question"),
        "current_focus": _extract_field(content, "Current focus"),
        "project_md_updated": None,
    }
    see_match = re.search(r"See:.*PROJECT\.md\s*\(updated\s+([^)]+)\)", content, re.IGNORECASE)
    if see_match:
        project["project_md_updated"] = see_match.group(1).strip()

    # Decisions — table format OR bullet format
    decisions: list[dict] = []
    dec_table_match = re.search(
        r"#{2,3}\s*Decisions(?:\s+Made)?[\s\S]*?\n\|[^\n]+\n\|[-|\s]+\n([\s\S]*?)(?=\n##|\n$|$)",
        content,
        re.IGNORECASE,
    )
    if dec_table_match:
        rows = [r for r in dec_table_match.group(1).strip().split("\n") if "|" in r]
        for row in rows:
            # Split on unescaped pipes
            cells = [_unescape_pipe(c.strip()) for c in re.split(r"(?<!\\)\|", row) if c.strip()]
            if len(cells) >= 3:
                decisions.append({"phase": cells[0], "summary": cells[1], "rationale": cells[2]})

    if not decisions:
        dec_bullet_match = re.search(
            r"###?\s*(?:Decisions|Decisions Made|Accumulated.*Decisions)\s*\n([\s\S]*?)(?=\n###?|\n##[^#]|$)",
            content,
            re.IGNORECASE,
        )
        if dec_bullet_match:
            items = re.findall(r"^-\s+(.+)$", dec_bullet_match.group(1), re.MULTILINE)
            for item in items:
                text = item.strip()
                if not text or re.match(r"^none", text, re.IGNORECASE):
                    continue
                phase_match = re.match(r"^\[Phase\s+([^\]]+)\]:\s*(.*)", text, re.IGNORECASE)
                if phase_match:
                    parts = phase_match.group(2).split(" \u2014 ")
                    decisions.append(
                        {
                            "phase": phase_match.group(1),
                            "summary": parts[0].strip(),
                            "rationale": parts[1].strip() if len(parts) > 1 else None,
                        }
                    )
                else:
                    decisions.append({"phase": None, "summary": text, "rationale": None})

    # Blockers
    blockers: list[str] = []
    blockers_match = re.search(
        r"###?\s*(?:Blockers|Blockers/Concerns|Concerns)\s*\n([\s\S]*?)(?=\n###?|\n##[^#]|$)",
        content,
        re.IGNORECASE,
    )
    if blockers_match:
        items = re.findall(r"^-\s+(.+)$", blockers_match.group(1), re.MULTILINE)
        for item in items:
            text = item.strip()
            if text and not re.match(r"^none", text, re.IGNORECASE):
                blockers.append(text)

    # Session
    session = {"last_date": None, "stopped_at": None, "resume_file": None}
    session_match = re.search(
        r"##\s*Session(?:\s+Continuity)?\s*\n([\s\S]*?)(?=\n##|$)",
        content,
        re.IGNORECASE,
    )
    if session_match:
        sec = session_match.group(1)
        ld = re.search(r"\*\*Last (?:session|Date):\*\*\s*(.+)", sec, re.IGNORECASE)
        sa = re.search(r"\*\*Stopped [Aa]t:\*\*\s*(.+)", sec)
        rf = re.search(r"\*\*Resume [Ff]ile:\*\*\s*(.+)", sec)
        if ld:
            session["last_date"] = ld.group(1).strip()
        if sa:
            session["stopped_at"] = sa.group(1).strip()
        if rf:
            session["resume_file"] = rf.group(1).strip()
    if not session["last_date"]:
        ls = _extract_field(content, "Last session") or _extract_field(content, "Last Date")
        if ls:
            session["last_date"] = ls
    if not session["stopped_at"]:
        sa = _extract_field(content, "Stopped At") or _extract_field(content, "Stopped at")
        if sa:
            session["stopped_at"] = sa
    if not session["resume_file"]:
        rf = _extract_field(content, "Resume File") or _extract_field(content, "Resume file")
        if rf:
            session["resume_file"] = rf

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
    }


def _strip_placeholder(value: str | None) -> str | None:
    """Return None if *value* is a markdown placeholder (EM_DASH, '[Not set]', literal 'None')."""
    if value is None:
        return None
    stripped = value.strip()
    if stripped in ("\u2014", "None") or stripped.lower() == "[not set]":
        return None
    return value


def parse_state_to_json(content: str) -> dict:
    """Parse STATE.md content into JSON-sidecar format."""
    parsed = parse_state_md(content)

    session: dict = {}
    last_date = _strip_placeholder(parsed["session"]["last_date"])
    stopped_at = _strip_placeholder(parsed["session"]["stopped_at"])
    resume_file = _strip_placeholder(parsed["session"]["resume_file"])
    if last_date:
        session["last_session"] = last_date
        session["last_date"] = last_date
    if stopped_at:
        session["stopped_at"] = stopped_at
    if resume_file:
        session["resume_file"] = resume_file

    return {
        "_version": 1,
        "_synced_at": datetime.now(tz=UTC).isoformat(),
        "project": {
            "core_question": _strip_placeholder(parsed["project"]["core_question"]),
            "current_focus": _strip_placeholder(parsed["project"]["current_focus"]),
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
        "metrics": parsed["metrics"],
        "active_calculations": parsed["active_calculations"],
        "intermediate_results": parsed["intermediate_results"],
        "open_questions": parsed["open_questions"],
    }


# ─── Schema Enforcement ───────────────────────────────────────────────────────


def _normalize_legacy_keys(raw: dict) -> dict:
    """Map legacy state keys to current schema before Pydantic validation."""
    if "project" in raw and "project_reference" not in raw:
        project = raw.pop("project")
        raw["project_reference"] = {
            "project_md_updated": project.get("project_md_updated") if isinstance(project, dict) else None,
            "core_research_question": (project.get("core_research_question") or project.get("core_question"))
            if isinstance(project, dict)
            else None,
            "current_focus": project.get("current_focus") if isinstance(project, dict) else None,
        }
    return raw


def ensure_state_schema(raw: dict | None) -> dict:
    """Merge a (possibly incomplete) state dict with defaults so every field exists.

    Uses Pydantic model_validate to populate missing fields from ResearchState defaults
    and map legacy keys. Type-mismatched fields (e.g. string where list expected) are
    dropped so Pydantic fills them with defaults.

    If validation still fails after top-level type fixup (e.g. wrong types inside nested
    objects), the offending top-level keys are progressively removed until validation
    succeeds. This guarantees the function never raises on any input dict.
    """
    from pydantic import ValidationError

    if not raw or not isinstance(raw, dict):
        return default_state_dict()

    normalized = _normalize_legacy_keys(dict(raw))  # shallow copy to avoid mutating input

    # Drop fields with wrong types to let Pydantic fill defaults (backward compat).
    defaults = default_state_dict()
    for key, default_val in defaults.items():
        if key in normalized and normalized[key] is not None:
            if isinstance(default_val, list) and not isinstance(normalized[key], list):
                del normalized[key]
            elif isinstance(default_val, dict) and not isinstance(normalized[key], dict):
                del normalized[key]

    try:
        return ResearchState.model_validate(normalized).model_dump()
    except ValidationError as exc:
        # Extract the top-level field names that caused validation errors and
        # progressively remove them so Pydantic fills defaults instead.
        bad_keys: set[str] = set()
        for err in exc.errors():
            loc = err.get("loc", ())
            if loc:
                bad_keys.add(str(loc[0]))

        if bad_keys:
            for bk in bad_keys:
                normalized.pop(bk, None)
            try:
                return ResearchState.model_validate(normalized).model_dump()
            except ValidationError:
                pass

        # Last resort: return clean defaults (preserving any extra keys that
        # the caller stored via ``extra = "allow"``).
        logger.warning("state.json had irrecoverable schema errors; resetting to defaults")
        result = default_state_dict()
        for k, v in normalized.items():
            if k not in result:
                result[k] = v
        return result


# ─── Markdown Generator ───────────────────────────────────────────────────────

# Convention field labels — reuse from conventions.py (derived from ConventionLock model).
from gpd.core.conventions import CONVENTION_LABELS as _CONVENTION_LABELS  # noqa: E402


def _is_bogus_value(v: object) -> bool:
    """Check if a convention value is effectively unset.

    Delegates to :func:`gpd.core.conventions.is_bogus_value` for consistency.
    """
    from gpd.core.conventions import is_bogus_value

    return is_bogus_value(v)


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
            p(f"- [Phase {dd.get('phase') or '?'}]: {dd.get('summary', '')}{rat}")
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

    set_conventions = [(k, label) for k, label in _CONVENTION_LABELS.items() if not _is_bogus_value(cl.get(k))]

    # Collect custom conventions
    custom_convs = cl.get("custom_conventions") or {}
    custom_entries: list[tuple[str, str, object]] = []
    for key, value in custom_convs.items():
        if not _is_bogus_value(value):
            label = key.replace("_", " ").title()
            custom_entries.append((key, label, value))

    # Also collect legacy flat keys not in standard labels
    for key, value in cl.items():
        if key not in _CONVENTION_LABELS and key != "custom_conventions" and not _is_bogus_value(value):
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
    p(f"**Resume file:** {sess.get('resume_file') or 'None'}")
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


def _recover_intent(cwd: Path) -> None:
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

    if json_tmp_exists and md_tmp_exists:
        # Both temp files ready — complete the interrupted write
        os.rename(json_tmp, json_path)
        os.rename(md_tmp, md_path)
    else:
        # Partial — rollback by cleaning up temp files
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


def sync_state_json_core(cwd: Path, md_content: str) -> dict:
    """Core sync logic: parse STATE.md -> merge into state.json.

    Caller MUST hold the state.json lock.
    """
    json_path = _state_json_path(cwd)
    parsed = parse_state_to_json(md_content)

    # Load existing JSON to preserve JSON-only fields
    existing = None
    try:
        existing = json.loads(json_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("state.json is corrupt, attempting backup restore: %s", e)
        bak_path = json_path.with_suffix(".json.bak")
        try:
            existing = json.loads(bak_path.read_text(encoding="utf-8"))
            logger.info("Restored from state.json.bak")
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            if os.environ.get(ENV_GPD_DEBUG):
                logger.debug("state.json.bak also unavailable")

    if existing and isinstance(existing, dict):
        merged = {**existing}
        merged["_version"] = parsed["_version"]
        merged["_synced_at"] = parsed["_synced_at"]

        # Merge project -> project_reference
        if parsed.get("project"):
            if "project_reference" not in merged:
                merged["project_reference"] = {
                    "project_md_updated": None,
                    "core_research_question": None,
                    "current_focus": None,
                }
            cq = parsed["project"].get("core_question")
            if cq is not None and str(cq).strip().lower() != "[not set]":
                merged["project_reference"]["core_research_question"] = cq
            cf = parsed["project"].get("current_focus")
            if cf is not None and str(cf).strip().lower() != "[not set]":
                merged["project_reference"]["current_focus"] = cf

        # Merge position
        if parsed.get("position"):
            if "position" not in merged:
                merged["position"] = {}
            for key, val in parsed["position"].items():
                if val is not None and val != EM_DASH:
                    merged["position"][key] = val

        # Merge session (filter out placeholder values)
        if parsed.get("session") and parsed["session"]:
            filtered_session = {
                k: v for k, v in parsed["session"].items() if v is not None and v != EM_DASH
            }
            if filtered_session:
                merged["session"] = {**(merged.get("session") or {}), **filtered_session}

        # Replace decisions and blockers (fully represented in markdown)
        if parsed.get("decisions") is not None:
            merged["decisions"] = parsed["decisions"]
        if parsed.get("blockers") is not None:
            merged["blockers"] = parsed["blockers"]

        # Metrics
        if parsed.get("metrics") and len(parsed["metrics"]) > 0:
            merged["performance_metrics"] = {"rows": parsed["metrics"]}

        # Bullet sections are fully represented in markdown, so markdown wins.
        for field in ("active_calculations", "intermediate_results", "open_questions"):
            if field in parsed:
                merged[field] = parsed.get(field) or []
    else:
        merged = ensure_state_schema(parsed)

    json_content = json.dumps(merged, indent=2)
    atomic_write(json_path, json_content)
    # Create backup
    try:
        atomic_write(json_path.with_suffix(".json.bak"), json_content + "\n")
    except OSError:
        if os.environ.get(ENV_GPD_DEBUG):
            logger.debug("sync_state_json backup write failed")

    return merged


@instrument_gpd_function("state.sync")
def sync_state_json(cwd: Path, md_content: str) -> dict:
    """Parse STATE.md and sync into state.json (with locking)."""
    with file_lock(_state_json_path(cwd)):
        return sync_state_json_core(cwd, md_content)


@instrument_gpd_function("state.load_json")
def load_state_json(cwd: Path) -> dict | None:
    """Load state.json with intent recovery and fallback to STATE.md.

    Returns the state dict, or None if no state exists.
    """
    json_path = _state_json_path(cwd)
    bak_path = json_path.with_suffix(".json.bak")

    # Recover from interrupted writes
    _recover_intent(cwd)

    try:
        raw = json_path.read_text(encoding="utf-8")
        return ensure_state_schema(json.loads(raw))
    except FileNotFoundError:
        pass
    except (json.JSONDecodeError, OSError) as e:
        if os.environ.get(ENV_GPD_DEBUG):
            logger.debug("state.json parse error: %s", e)
        # Try backup
        try:
            bak_raw = bak_path.read_text(encoding="utf-8")
            restored = ensure_state_schema(json.loads(bak_raw))
            atomic_write(json_path, bak_raw)
            return restored
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            if os.environ.get(ENV_GPD_DEBUG):
                logger.debug("state.json.bak restore failed")

    # Fall back to STATE.md
    md_path = _state_md_path(cwd)
    try:
        content = md_path.read_text(encoding="utf-8")
        return ensure_state_schema(sync_state_json_core(cwd, content))
    except (FileNotFoundError, OSError):
        if os.environ.get(ENV_GPD_DEBUG):
            logger.debug("STATE.md fallback failed")
        return None


def save_state_json_locked(cwd: Path, state_obj: dict) -> None:
    """Core write logic: write state.json + regenerate STATE.md atomically.

    Caller MUST hold the lock on state.json.
    """
    planning = _planning_dir(cwd)
    planning.mkdir(parents=True, exist_ok=True)
    json_path = _state_json_path(cwd)
    md_path = _state_md_path(cwd)
    intent_file = _intent_path(cwd)
    pid = os.getpid()
    json_tmp = json_path.with_suffix(f".json.tmp.{pid}")
    md_tmp = md_path.with_suffix(f".md.tmp.{pid}")

    # Read existing for rollback
    json_backup = safe_read_file(json_path)
    md_backup = safe_read_file(md_path)

    try:
        # Phase 1: Write both temp files
        json_tmp.write_text(json.dumps(state_obj, indent=2) + "\n", encoding="utf-8")
        md_tmp.write_text(generate_state_markdown(state_obj), encoding="utf-8")

        # Phase 2: Write intent marker, then rename both
        intent_file.write_text(f"{json_tmp}\n{md_tmp}\n", encoding="utf-8")
        os.rename(json_tmp, json_path)
        os.rename(md_tmp, md_path)
        try:
            intent_file.unlink(missing_ok=True)
        except OSError:
            pass

        # Backup
        try:
            atomic_write(json_path.with_suffix(".json.bak"), json.dumps(state_obj, indent=2) + "\n")
        except OSError:
            if os.environ.get(ENV_GPD_DEBUG):
                logger.debug("Failed to write state.json backup")
    except Exception:
        # Cleanup temp files and intent
        for f in (intent_file, json_tmp, md_tmp):
            try:
                f.unlink(missing_ok=True)
            except OSError:
                pass
        # Restore backups
        if json_backup is not None:
            try:
                json_path.write_text(json_backup, encoding="utf-8")
            except OSError:
                pass
        if md_backup is not None:
            try:
                md_path.write_text(md_backup, encoding="utf-8")
            except OSError:
                pass
        raise


@instrument_gpd_function("state.save")
def save_state_json(cwd: Path, state_obj: dict) -> None:
    """Save state.json + STATE.md atomically (with locking)."""
    with file_lock(_state_json_path(cwd)):
        save_state_json_locked(cwd, state_obj)


# ─── State Commands ────────────────────────────────────────────────────────────


@instrument_gpd_function("state.load")
def state_load(cwd: Path) -> StateLoadResult:
    """Load full state with config and file-existence metadata."""
    state_obj = load_state_json(cwd)

    layout = ProjectLayout(cwd)
    state_raw = safe_read_file(layout.state_md) or ""

    return StateLoadResult(
        state=state_obj or {},
        state_raw=state_raw,
        state_exists=len(state_raw) > 0,
        roadmap_exists=layout.roadmap.exists(),
        config_exists=layout.config_json.exists(),
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

    # Normalize snake_case → Title Case (e.g. "current_phase" → "Current Phase")
    section_norm = section.replace("_", " ")

    # Try **field:** value
    field_escaped = _escape_regex(section_norm)
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

    with file_lock(md_path):
        content = md_path.read_text(encoding="utf-8")
        field_norm = field.replace("_", " ")

        # Validate state transitions
        if field_norm.lower() == "status":
            current_status = state_extract_field(content, "Status")
            if current_status:
                err = validate_state_transition(current_status, value)
                if err:
                    return StateUpdateResult(updated=False, reason=err)

        new_content = state_replace_field(content, field_norm, value)
        if new_content != content:
            atomic_write(md_path, new_content)
            sync_state_json(cwd, new_content)
            return StateUpdateResult(updated=True)

        return StateUpdateResult(updated=False, reason=f'Field "{field}" not found in STATE.md')


@instrument_gpd_function("state.patch")
def state_patch(cwd: Path, patches: dict[str, str]) -> StatePatchResult:
    """Batch-update multiple **Field:** values in STATE.md."""
    md_path = _state_md_path(cwd)
    if not md_path.exists():
        raise StateError(
            f"STATE.md not found at {md_path}. "
            "Run 'gpd init' to create the project state file before patching."
        )

    with file_lock(md_path):
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

            escaped = _escape_regex(field_norm)
            pattern = re.compile(rf"(\*\*{escaped}:\*\*\s*)(.*)", re.IGNORECASE)
            if pattern.search(content):
                safe_val = str(value)

                def _rep(m: re.Match, sv: str = safe_val) -> str:
                    return m.group(1) + sv

                content = pattern.sub(_rep, content, count=1)
                updated.append(field)
            else:
                failed.append(field)

        if updated:
            atomic_write(md_path, content)
            sync_state_json(cwd, content)

    return StatePatchResult(updated=updated, failed=failed)


@instrument_gpd_function("state.advance_plan")
def state_advance_plan(cwd: Path) -> AdvancePlanResult:
    """Advance to the next plan, or mark phase complete if on last plan."""
    md_path = _state_md_path(cwd)
    if not md_path.exists():
        return AdvancePlanResult(advanced=False, error="STATE.md not found")

    with file_lock(md_path):
        content = md_path.read_text(encoding="utf-8")
        current_plan_raw = state_extract_field(content, "Current Plan")
        total_plans_raw = state_extract_field(content, "Total Plans in Phase")

        current_plan = safe_parse_int(current_plan_raw, None)
        total_plans = safe_parse_int(total_plans_raw, None)

        if current_plan is None or total_plans is None:
            return AdvancePlanResult(
                advanced=False, error="Cannot parse Current Plan or Total Plans in Phase from STATE.md"
            )

        if not state_has_field(content, "Current Plan"):
            return AdvancePlanResult(
                advanced=False, error="STATE.md is missing **Current Plan:** field \u2014 cannot advance"
            )

        today = datetime.now(tz=UTC).strftime("%Y-%m-%d")

        if current_plan >= total_plans:
            content = state_replace_field(content, "Status", "Phase complete \u2014 ready for verification")
            content = state_replace_field(content, "Last Activity", today)
            atomic_write(md_path, content)
            sync_state_json(cwd, content)
            return AdvancePlanResult(
                advanced=False,
                reason="last_plan",
                current_plan=current_plan,
                total_plans_in_phase=total_plans,
                status="ready_for_verification",
            )

        new_plan = current_plan + 1
        content = state_replace_field(content, "Current Plan", str(new_plan))
        content = state_replace_field(content, "Status", "Ready to execute")
        content = state_replace_field(content, "Last Activity", today)
        atomic_write(md_path, content)
        sync_state_json(cwd, content)
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

    with file_lock(md_path):
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
        atomic_write(md_path, new_content)
        sync_state_json(cwd, new_content)
        return RecordMetricResult(recorded=True, phase=phase, plan=plan, duration=duration)


@instrument_gpd_function("state.update_progress")
def state_update_progress(cwd: Path) -> UpdateProgressResult:
    """Recalculate progress from plan/summary counts across all phases."""
    md_path = _state_md_path(cwd)
    if not md_path.exists():
        return UpdateProgressResult(updated=False, error="STATE.md not found")

    with file_lock(md_path):
        content = md_path.read_text(encoding="utf-8")

        phases_dir = ProjectLayout(cwd).phases_dir
        total_plans = 0
        total_summaries = 0

        if phases_dir.exists():
            for phase_dir in phases_dir.iterdir():
                if not phase_dir.is_dir():
                    continue
                phase_files = [f.name for f in phase_dir.iterdir() if f.is_file()]
                total_plans += sum(1 for f in phase_files if f.endswith(PLAN_SUFFIX) or f == STANDALONE_PLAN)
                total_summaries += sum(1 for f in phase_files if f.endswith(SUMMARY_SUFFIX) or f == STANDALONE_SUMMARY)

        percent = round((total_summaries / total_plans) * 100) if total_plans > 0 else 0
        bar_width = 10
        filled = max(0, min(bar_width, round((percent / 100) * bar_width)))
        bar = "\u2588" * filled + "\u2591" * (bar_width - filled)
        progress_str = f"[{bar}] {percent}%"

        progress_pattern = re.compile(r"(\*\*Progress:\*\*\s*)(.*)", re.IGNORECASE)
        if progress_pattern.search(content):
            new_content = progress_pattern.sub(lambda m: m.group(1) + progress_str, content, count=1)
            atomic_write(md_path, new_content)
            sync_state_json(cwd, new_content)
            return UpdateProgressResult(
                updated=True, percent=percent, completed=total_summaries, total=total_plans, bar=progress_str
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

    rat_str = f" \u2014 {rationale}" if rationale else ""
    entry = f"- [Phase {phase or '?'}]: {summary}{rat_str}"

    with file_lock(md_path):
        content = md_path.read_text(encoding="utf-8")
        pattern = re.compile(
            r"(###?\s*(?:Decisions|Decisions Made|Accumulated.*Decisions)\s*\n)([\s\S]*?)(?=\n###?|\n##[^#]|$)",
            re.IGNORECASE,
        )
        match = pattern.search(content)

        if not match:
            return AddDecisionResult(added=False, reason="Decisions section not found in STATE.md")

        section_body = match.group(2)
        section_body = re.sub(r"^None yet\.?\s*$", "", section_body, flags=re.MULTILINE | re.IGNORECASE)
        section_body = re.sub(r"^No decisions yet\.?\s*$", "", section_body, flags=re.MULTILINE | re.IGNORECASE)
        section_body = section_body.rstrip() + "\n" + entry + "\n"

        new_content = pattern.sub(lambda _: f"{match.group(1)}{section_body}", content, count=1)
        atomic_write(md_path, new_content)
        sync_state_json(cwd, new_content)
        return AddDecisionResult(added=True, decision=entry)


@instrument_gpd_function("state.add_blocker")
def state_add_blocker(cwd: Path, text: str) -> AddBlockerResult:
    """Add a blocker to STATE.md."""
    md_path = _state_md_path(cwd)
    if not md_path.exists():
        return AddBlockerResult(added=False, error="STATE.md not found")
    if not text:
        return AddBlockerResult(added=False, error="text required")

    entry = f"- {text}"

    with file_lock(md_path):
        content = md_path.read_text(encoding="utf-8")
        pattern = re.compile(
            r"(###?\s*(?:Blockers|Blockers/Concerns|Concerns)\s*\n)([\s\S]*?)(?=\n###?|\n##[^#]|$)",
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
        atomic_write(md_path, new_content)
        sync_state_json(cwd, new_content)
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

    with file_lock(md_path):
        content = md_path.read_text(encoding="utf-8")
        pattern = re.compile(
            r"(###?\s*(?:Blockers|Blockers/Concerns|Concerns)\s*\n)([\s\S]*?)(?=\n###?|\n##[^#]|$)",
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
            word_pattern = re.compile(rf"\b{escaped}\b", re.IGNORECASE)
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
            atomic_write(md_path, new_content)
            sync_state_json(cwd, new_content)
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
        return RecordSessionResult(recorded=False, error="STATE.md not found")

    with file_lock(md_path):
        content = md_path.read_text(encoding="utf-8")
        now = datetime.now(tz=UTC).isoformat()
        updated: list[str] = []

        new_content = state_replace_field(content, "Last session", now)
        if new_content != content:
            content = new_content
            updated.append("Last session")
        new_content = state_replace_field(content, "Last Date", now)
        if new_content != content:
            content = new_content
            updated.append("Last Date")

        if stopped_at:
            new_content = state_replace_field(content, "Stopped At", stopped_at)
            if new_content == content:
                new_content = state_replace_field(content, "Stopped at", stopped_at)
            if new_content != content:
                content = new_content
                updated.append("Stopped At")

        resume = resume_file or "None"
        new_content = state_replace_field(content, "Resume File", resume)
        if new_content == content:
            new_content = state_replace_field(content, "Resume file", resume)
        if new_content != content:
            content = new_content
            updated.append("Resume File")

        if updated:
            atomic_write(md_path, content)
            sync_state_json(cwd, content)
            return RecordSessionResult(recorded=True, updated=updated)

        return RecordSessionResult(recorded=False, reason="No session fields found in STATE.md")


@instrument_gpd_function("state.snapshot")
def state_snapshot(cwd: Path) -> StateSnapshotResult:
    """Fast snapshot of state for progress/routing commands."""
    json_path = _state_json_path(cwd)
    if json_path.exists():
        try:
            state_obj = json.loads(json_path.read_text(encoding="utf-8"))
            pos = state_obj.get("position") or {}
            progress_pct = pos.get("progress_percent")
            if progress_pct is None:
                progress_str = pos.get("progress")
                if progress_str:
                    m = re.search(r"(\d+)%", str(progress_str))
                    progress_pct = int(m.group(1)) if m else None
            cp = pos.get("current_phase")
            return StateSnapshotResult(
                current_phase=phase_normalize(str(cp)) if cp is not None else None,
                current_phase_name=pos.get("current_phase_name"),
                total_phases=pos.get("total_phases"),
                current_plan=str(pos["current_plan"]) if pos.get("current_plan") is not None else None,
                total_plans_in_phase=pos.get("total_plans_in_phase"),
                status=pos.get("status"),
                progress_percent=progress_pct,
                last_activity=pos.get("last_activity"),
                last_activity_desc=pos.get("last_activity_desc"),
                decisions=state_obj.get("decisions"),
                blockers=state_obj.get("blockers"),
                paused_at=pos.get("paused_at"),
                session=state_obj.get("session"),
            )
        except (json.JSONDecodeError, OSError):
            if os.environ.get(ENV_GPD_DEBUG):
                logger.debug("state.json read failed, falling back")

    # Fall back to parsing STATE.md
    md_path = _state_md_path(cwd)
    if not md_path.exists():
        return StateSnapshotResult(error="STATE.md not found")

    content = md_path.read_text(encoding="utf-8")
    parsed = parse_state_md(content)
    cp = parsed["position"]["current_phase"]
    return StateSnapshotResult(
        current_phase=phase_normalize(str(cp)) if cp is not None else None,
        current_phase_name=parsed["position"]["current_phase_name"],
        total_phases=parsed["position"]["total_phases"],
        current_plan=parsed["position"]["current_plan"],
        total_plans_in_phase=parsed["position"]["total_plans_in_phase"],
        status=parsed["position"]["status"],
        progress_percent=parsed["position"]["progress_percent"],
        last_activity=parsed["position"]["last_activity"],
        last_activity_desc=parsed["position"]["last_activity_desc"],
        decisions=parsed["decisions"],
        blockers=parsed["blockers"],
        paused_at=parsed["position"]["paused_at"],
        session=parsed["session"],
    )


# ─── Validate ──────────────────────────────────────────────────────────────────


@instrument_gpd_function("state.validate")
def state_validate(cwd: Path) -> StateValidateResult:
    """Validate state consistency between state.json and STATE.md."""
    json_path = _state_json_path(cwd)
    md_path = _state_md_path(cwd)
    issues: list[str] = []
    warnings: list[str] = []

    # Load state.json
    state_json = None
    try:
        state_json = json.loads(json_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        issues.append("state.json not found")
    except (json.JSONDecodeError, OSError) as e:
        issues.append(f"state.json parse error: {e}")

    # Load and parse STATE.md
    state_md = None
    try:
        content = md_path.read_text(encoding="utf-8")
        state_md = parse_state_to_json(content)
    except FileNotFoundError:
        issues.append("STATE.md not found")
    except OSError as e:
        issues.append(f"STATE.md parse error: {e}")

    if not state_json and not state_md:
        return StateValidateResult(valid=False, issues=issues, warnings=warnings)

    # Cross-check position fields
    if state_json and state_md and state_json.get("position") and state_md.get("position"):
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
            json_val = state_json["position"].get(field)
            md_val = state_md["position"].get(field)
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
    if state_json and state_json.get("convention_lock"):
        cl = state_json["convention_lock"]
        unset = [k for k, v in cl.items() if v is None and k != "custom_conventions"]
        if unset:
            issues.append(f"convention_lock: {len(unset)} conventions unset ({', '.join(unset)})")

    # NaN in numeric fields
    if state_json and state_json.get("position"):
        for field in ("total_phases", "total_plans_in_phase", "progress_percent"):
            val = state_json["position"].get(field)
            if val is not None and isinstance(val, float) and val != val:
                issues.append(f"position.{field} is NaN")

    # Status vocabulary
    if state_json and state_json.get("position") and state_json["position"].get("status"):
        if not is_valid_status(state_json["position"]["status"]):
            warnings.append(f'position.status "{state_json["position"]["status"]}" is not a recognized status')

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
    if state_json and state_json.get("position"):
        cp = state_json["position"].get("current_phase")
        tp = state_json["position"].get("total_phases")
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
        for r in state_json["intermediate_results"]:
            if isinstance(r, dict) and r.get("id"):
                if r["id"] in seen:
                    issues.append(f'intermediate_results: duplicate result ID "{r["id"]}"')
                seen.add(r["id"])

    # Cross-check: phase directory exists
    current_phase = state_json["position"].get("current_phase") if state_json and state_json.get("position") else None
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

    valid = len(issues) == 0
    return StateValidateResult(valid=valid, issues=issues, warnings=warnings)


# ─── Compact ───────────────────────────────────────────────────────────────────


@instrument_gpd_function("state.compact")
def state_compact(cwd: Path) -> StateCompactResult:
    """Compact STATE.md by archiving old decisions, blockers, metrics, and sessions."""
    md_path = _state_md_path(cwd)
    if not md_path.exists():
        return StateCompactResult(compacted=False, error="STATE.md not found")

    with file_lock(md_path):
        with file_lock(_state_json_path(cwd)):
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
                state_obj = json.loads(_state_json_path(cwd).read_text(encoding="utf-8"))
            except (FileNotFoundError, json.JSONDecodeError, OSError):
                pass

            current_phase = (
                state_obj["position"].get("current_phase") if state_obj and state_obj.get("position") else None
            )

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
            archive_path = planning / "STATE-ARCHIVE.md"
            archive_date = datetime.now(tz=UTC).strftime("%Y-%m-%d")
            archive_entries: list[str] = []
            working = content

            # 1. Archive decisions older than keep threshold
            if keep_phase_min is not None:
                dec_pattern = re.compile(
                    r"(###?\s*(?:Decisions|Decisions Made|Accumulated.*Decisions)\s*\n)([\s\S]*?)(?=\n###?|\n##[^#]|$)",
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
                r"(###?\s*(?:Blockers|Blockers/Concerns|Concerns)\s*\n)([\s\S]*?)(?=\n###?|\n##[^#]|$)",
                re.IGNORECASE,
            )
            blk_match = blk_pattern.search(working)
            if blk_match:
                blk_lines = blk_match.group(2).split("\n")
                kept_b: list[str] = []
                archived_b: list[str] = []
                for line in blk_lines:
                    if line.startswith("- ") and (
                        re.search(r"\[resolved\]", line, re.IGNORECASE) or re.search(r"~~.*~~", line)
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
                    r"(##\s*Session(?:\s+Continuity)?\s*\n)([\s\S]*?)(?=\n##|$)",
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
                        archive_entries.append(
                            "### Session Records\n\n" + "\n\n".join("\n".join(b) for b in archived_s)
                        )
                        working = sess_pattern.sub(
                            lambda _: f"{sess_match.group(1)}" + "\n".join("\n".join(b) for b in kept_s) + "\n",
                            working,
                            count=1,
                        )

            if not archive_entries:
                return StateCompactResult(
                    compacted=False, reason="nothing_to_archive", lines=total_lines, warn=soft_mode
                )

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
            atomic_write(md_path, working)
            sync_state_json_core(cwd, working)

            new_lines = len(working.split("\n"))
            return StateCompactResult(
                compacted=True,
                original_lines=total_lines,
                new_lines=new_lines,
                archived_lines=total_lines - new_lines,
                soft_mode=soft_mode,
            )
