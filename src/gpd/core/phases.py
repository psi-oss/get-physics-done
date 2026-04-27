"""Phase lifecycle and roadmap management for GPD research projects.

Handles phase discovery, ROADMAP.md parsing, wave validation, dependency graph analysis,
milestone management, and progress rendering.

Most public functions are instrumented with local observability spans via ``gpd_span``.
All return types are Pydantic models — no raw dicts cross module boundaries.
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import tempfile
from collections import deque
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from gpd.core.checkpoints import sync_phase_checkpoints
from gpd.core.constants import (
    CONTEXT_SUFFIX,
    MILESTONES_DIR_NAME,
    MILESTONES_FILENAME,
    PHASES_DIR_NAME,
    PLAN_SUFFIX,
    PLANNING_DIR_NAME,
    REQUIREMENTS_FILENAME,
    RESEARCH_SUFFIX,
    STANDALONE_CONTEXT,
    STANDALONE_PLAN,
    STANDALONE_RESEARCH,
    STANDALONE_SUMMARY,
    STANDALONE_VALIDATION,
    SUMMARY_SUFFIX,
    VALIDATION_SUFFIX,
    VERIFICATION_SUFFIX,
    ProjectLayout,
)
from gpd.core.errors import GPDError
from gpd.core.frontmatter import FrontmatterParseError
from gpd.core.observability import gpd_span
from gpd.core.utils import (
    atomic_write,
    compare_phase_numbers,
    file_lock,
    generate_slug,
    is_phase_complete,
    matching_phase_artifact_count,
    phase_artifact_display_name,
    phase_artifact_id,
    phase_normalize,
    phase_unpad,
    safe_read_file,
    strict_parse_int,
)
from gpd.core.utils import phase_sort_key as _phase_sort_key

logger = logging.getLogger(__name__)

__all__ = [
    # Errors
    "PhaseError",
    "PhaseNotFoundError",
    "PhaseAmbiguityError",
    "PhaseValidationError",
    "PhaseIncompleteError",
    "RoadmapNotFoundError",
    "MilestoneIncompleteError",
    # Models
    "PhaseInfo",
    "WaveValidation",
    "RoadmapPhase",
    "MilestoneInfo",
    "RoadmapAnalysis",
    "PlanEntry",
    "PhasePlanIndex",
    "PhaseListResult",
    "PhaseFilesResult",
    "RoadmapPhaseResult",
    "NextDecimalResult",
    "PhaseAddResult",
    "PhaseInsertResult",
    "RenameEntry",
    "PhaseRemoveResult",
    "PhaseCompleteResult",
    "ArchiveStatus",
    "MilestoneCompleteResult",
    "PhaseProgress",
    "ProgressJsonResult",
    "ProgressBarResult",
    "ProgressTableResult",
    "PhaseWaveValidationResult",
    # Functions
    "find_phase",
    "get_milestone_info",
    "list_phases",
    "list_phase_files",
    "roadmap_get_phase",
    "next_decimal_phase",
    "validate_waves",
    "validate_phase_waves",
    "phase_plan_index",
    "roadmap_analyze",
    "phase_add",
    "phase_insert",
    "phase_remove",
    "phase_complete",
    "milestone_complete",
    "progress_render",
]


# ─── Error Hierarchy ───────────────────────────────────────────────────────────


class PhaseError(GPDError):
    """Base error for all phase operations."""


class PhaseNotFoundError(PhaseError):
    """Raised when a phase identifier doesn't match any directory."""

    def __init__(self, phase: str) -> None:
        self.phase = phase
        super().__init__(f"Phase {phase} not found")


class PhaseValidationError(PhaseError):
    """Raised when a phase number or input fails validation."""


class PhaseAmbiguityError(PhaseValidationError):
    """Raised when a phase identifier maps to multiple phase directories."""

    def __init__(self, phase: str, matches: list[str]) -> None:
        self.phase = phase
        self.matches = matches
        super().__init__(
            f"Phase {phase} is ambiguous; matching directories: {', '.join(matches)}. "
            "Use the exact phase directory name to disambiguate."
        )


class PhaseIncompleteError(PhaseError):
    """Raised when an operation requires a complete phase but it isn't."""

    def __init__(self, phase: str, summary_count: int, plan_count: int) -> None:
        self.phase = phase
        self.summary_count = summary_count
        self.plan_count = plan_count
        super().__init__(
            f"Phase {phase} has {summary_count}/{plan_count} plans completed. "
            f"All plans must have summaries before marking complete."
        )


class RoadmapNotFoundError(PhaseError):
    """Raised when ROADMAP.md is missing and required."""


class MilestoneIncompleteError(PhaseError):
    """Raised when attempting to complete a milestone with incomplete phases."""

    def __init__(self, incomplete: int, total: int) -> None:
        self.incomplete = incomplete
        self.total = total
        super().__init__(
            f"Cannot complete milestone: {incomplete} of {total} phases are incomplete. Complete all phases first."
        )


# ─── Lazy Imports (break circular dep with frontmatter.py / state.py) ────────


def _extract_frontmatter(content: str) -> dict:
    """Lazy-load extract_frontmatter from frontmatter module and return metadata only."""
    from gpd.core.frontmatter import extract_frontmatter

    meta, _body = extract_frontmatter(content)
    return meta


def _save_state_markdown_locked(cwd: Path, state_content: str) -> None:
    """Persist STATE.md-derived content while the canonical state lock is already held."""
    from gpd.core.state import save_state_markdown_locked

    save_state_markdown_locked(cwd, state_content)


def _parse_plan_wave(value: object) -> int:
    """Return a canonical wave number from frontmatter without coercive drift."""
    if value is None:
        return 1
    wave = strict_parse_int(value, None)
    if wave is None:
        raise PhaseValidationError(f"wave must be an integer, got {value!r}")
    return wave


def _update_state_markdown_locked(cwd: Path, update_state_content: Callable[[str], str]) -> bool:
    """Rewrite STATE.md through the canonical state lock and locked writer path."""
    from gpd.core.state import _load_or_rebuild_state_markdown_locked

    state_json_path = ProjectLayout(cwd).state_json
    with file_lock(state_json_path):
        state_content = _load_or_rebuild_state_markdown_locked(cwd)
        if state_content is None:
            return False
        _save_state_markdown_locked(cwd, update_state_content(state_content))
    return True


def _restore_text_file(path: Path, previous_content: str | None) -> None:
    """Restore one text file to its previous on-disk state."""
    if previous_content is None:
        if path.exists():
            path.unlink()
        return
    atomic_write(path, previous_content)


def _backup_directory_tree(path: Path) -> tuple[Path | None, Path | None]:
    """Copy *path* to a temporary backup tree for rollback."""
    if not path.exists():
        return None, None
    backup_root = Path(tempfile.mkdtemp(prefix=f"gpd-{path.name}-backup-"))
    backup_path = backup_root / path.name
    shutil.copytree(path, backup_path)
    return backup_root, backup_path


def _restore_directory_tree(path: Path, backup_path: Path | None) -> None:
    """Restore *path* from *backup_path* when rollback is required."""
    if path.exists():
        shutil.rmtree(path)
    if backup_path is not None and backup_path.exists():
        shutil.copytree(backup_path, path)


def _state_content_with_total_phases(state_content: str, *, total_phases: int) -> str:
    """Rewrite total-phase counters in STATE.md content."""
    updated = re.sub(
        r"(\*\*Total Phases:\*\*\s*)(?:\d+|[—\-]+)",
        rf"\g<1>{total_phases}",
        state_content,
    )
    return re.sub(
        r"(\bof\s+)\d+(\s*(?:\(|phases?))",
        rf"\g<1>{total_phases}\2",
        updated,
        flags=re.IGNORECASE,
    )


def _phase_remove_state_content(
    cwd: Path,
    state_content: str,
    *,
    target_phase: str,
    updated_roadmap: RoadmapAnalysis,
) -> str:
    """Rewrite STATE.md after removing a phase."""
    total_phases = updated_roadmap.phase_count

    state_content = _state_content_with_total_phases(state_content, total_phases=total_phases)
    current_phase_before = _extract_state_field(state_content, "Current Phase")
    mapped_phase = _remap_phase_after_removal(
        current_phase_before,
        target_phase,
        [phase.number for phase in updated_roadmap.phases],
    )
    mapped_phase_name = None
    if mapped_phase is not None:
        mapped_phase_entry = _get_roadmap_phase_by_number(cwd, mapped_phase)
        mapped_phase_name = mapped_phase_entry.name if mapped_phase_entry else None

    from gpd.core.state import INACTIVE_FIELD_SENTINEL

    replacement_phase = mapped_phase or INACTIVE_FIELD_SENTINEL
    replacement_name = mapped_phase_name or INACTIVE_FIELD_SENTINEL
    state_content = _replace_state_field(state_content, "Current Phase", replacement_phase)
    state_content = _replace_state_field(state_content, "Current Phase Name", replacement_name)

    current_was_removed = _phase_in_subtree(current_phase_before, target_phase)
    if current_was_removed:
        state_content = _replace_state_field(state_content, "Current Plan", INACTIVE_FIELD_SENTINEL)

    if mapped_phase is not None:
        mapped_info = find_phase(cwd, mapped_phase)
        plan_total = len(mapped_info.plans) if mapped_info else 0
        total_plans_value = str(plan_total) if plan_total else INACTIVE_FIELD_SENTINEL
    else:
        total_plans_value = INACTIVE_FIELD_SENTINEL
    return _replace_state_field(state_content, "Total Plans in Phase", total_plans_value)


def _phase_complete_state_content(
    cwd: Path,
    state_content: str,
    *,
    phase_num: str,
    next_phase_num: str | None,
    next_phase_name: str | None,
    today: str,
    is_last_phase: bool,
) -> str:
    """Rewrite STATE.md after completing a phase."""
    from gpd.core.state import INACTIVE_FIELD_SENTINEL

    new_status = "Milestone complete" if is_last_phase else "Ready to plan"
    current_status = _extract_state_field(state_content, "Status") or ""
    _validate_transition(current_status, new_status)

    if is_last_phase:
        state_content = _replace_state_field(state_content, "Current Phase", INACTIVE_FIELD_SENTINEL)
        state_content = _replace_state_field(state_content, "Current Phase Name", INACTIVE_FIELD_SENTINEL)
    else:
        state_content = _replace_state_field(state_content, "Current Phase", next_phase_num or phase_num)
        phase_name_display = (
            next_phase_name.replace("-", " ")
            if next_phase_name
            else (next_phase_num or INACTIVE_FIELD_SENTINEL)
        )
        state_content = _replace_state_field(state_content, "Current Phase Name", phase_name_display)

    state_content = _replace_state_field(state_content, "Status", new_status)
    state_content = _replace_state_field(state_content, "Current Plan", INACTIVE_FIELD_SENTINEL)

    if next_phase_num and not is_last_phase:
        next_info = find_phase(cwd, next_phase_num)
        next_plan_count = len(next_info.plans) if next_info else 0
        replacement = str(next_plan_count) if next_plan_count else INACTIVE_FIELD_SENTINEL
        state_content = _replace_state_field(state_content, "Total Plans in Phase", replacement)
    else:
        state_content = _replace_state_field(state_content, "Total Plans in Phase", INACTIVE_FIELD_SENTINEL)

    state_content = _replace_state_field(state_content, "Last Activity", today)

    transition_msg = f"Phase {phase_num} complete"
    if next_phase_num:
        transition_msg += f", transitioned to Phase {next_phase_num}"
    return _replace_state_field(state_content, "Last Activity Description", transition_msg)


def _milestone_complete_state_content(state_content: str, *, today: str, version: str) -> str:
    """Rewrite STATE.md after completing a milestone.

    Clears Current Phase / Current Phase Name / Current Plan / Total Plans in
    Phase to the inactive sentinel so end-of-milestone state is a real "no
    active work" snapshot rather than a half-filled template.
    """
    from gpd.core.state import INACTIVE_FIELD_SENTINEL

    current_status = _extract_state_field(state_content, "Status") or ""
    _validate_transition(current_status, "Milestone complete")
    state_content = _replace_state_field(state_content, "Status", "Milestone complete")
    state_content = _replace_state_field(state_content, "Current Phase", INACTIVE_FIELD_SENTINEL)
    state_content = _replace_state_field(state_content, "Current Phase Name", INACTIVE_FIELD_SENTINEL)
    state_content = _replace_state_field(state_content, "Current Plan", INACTIVE_FIELD_SENTINEL)
    state_content = _replace_state_field(state_content, "Total Plans in Phase", INACTIVE_FIELD_SENTINEL)
    state_content = _replace_state_field(state_content, "Last Activity", today)
    return _replace_state_field(
        state_content, "Last Activity Description", f"{version} milestone completed and archived"
    )


def _replace_state_field(state_content: str, field_name: str, new_value: str) -> str:
    """Lazy-load the canonical STATE.md field replacer."""
    from gpd.core.state import state_replace_field

    return state_replace_field(state_content, field_name, new_value)


def _validate_transition(current_status: str, new_status: str) -> None:
    """Validate a state transition, raising PhaseValidationError if invalid."""
    from gpd.core.state import validate_state_transition

    error = validate_state_transition(current_status, new_status)
    if error is not None:
        raise PhaseValidationError(error)


def _extract_state_field(state_content: str, field_name: str) -> str | None:
    """Extract a `**Field:** value from STATE.md content."""
    match = re.search(rf"\*\*{re.escape(field_name)}:\*\*\s*(.+)", state_content, re.IGNORECASE)
    if not match:
        return None
    value = match.group(1).strip()
    if value == "\u2014" or value.lower() in {"none", "no", "not set", "[not set]"}:
        return None
    return value


_CHECKPOINT_TASK_RE = re.compile(r'<task\s+[^>]*?type=["\']?checkpoint', re.IGNORECASE)


_PLAN_CHECKBOX_RE = re.compile(
    r"^(?P<indent>\s*-\s*)\[\s\](?P<body>\s+(?P<plan>\d{1,3}(?:\.\d+)?-\d{1,3})\b[^\n]*)$",
    re.MULTILINE,
)


def _tick_completed_plan_checkboxes(cwd: Path, roadmap_content: str) -> str:
    """Tick ``- [ ] NN-KK`` rows whose plan has a SUMMARY.md on disk.

    Archive freezing requires the plan checklist to agree with the phase-level
    "complete" markers. The live ROADMAP.md is authored by agents and often
    carries stale unchecked rows. This reconciles them based on filesystem
    truth at milestone completion.
    """
    if "- [ ]" not in roadmap_content:
        return roadmap_content

    phases_dir = _phases_dir(cwd)
    if not phases_dir.exists():
        return roadmap_content

    completed_plans: set[str] = set()
    for phase_dir in phases_dir.iterdir():
        if not phase_dir.is_dir():
            continue
        for summary in phase_dir.glob("*-SUMMARY.md"):
            stem = summary.name[: -len("-SUMMARY.md")]
            # Canonicalize to the unpadded dotted-index form (e.g. "5-2", "05-02",
            # "5.1-03" all reconcile to the same key).
            m = re.match(r"^(\d+(?:\.\d+)?)-(\d+)$", stem)
            if not m:
                continue
            phase_part = m.group(1).lstrip("0") or "0"
            plan_part = str(int(m.group(2)))
            completed_plans.add(f"{phase_part}-{plan_part}")

    if not completed_plans:
        return roadmap_content

    def _normalize_plan_token(token: str) -> str:
        m = re.match(r"^(\d+(?:\.\d+)?)-(\d+)$", token)
        if not m:
            return token
        phase_part = m.group(1).lstrip("0") or "0"
        plan_part = str(int(m.group(2)))
        return f"{phase_part}-{plan_part}"

    def _replace(match: re.Match) -> str:
        token = _normalize_plan_token(match.group("plan"))
        if token in completed_plans:
            return f"{match.group('indent')}[x]{match.group('body')}"
        return match.group(0)

    return _PLAN_CHECKBOX_RE.sub(_replace, roadmap_content)


def _upsert_milestone_entry(existing: str, version: str, milestone_entry: str) -> str:
    """Replace or append a milestone entry keyed by version."""
    pattern = re.compile(
        rf"^##\s+{re.escape(version)}(?:\s|$)[\s\S]*?(?:\n---\n\n|\Z)",
        re.MULTILINE,
    )
    if pattern.search(existing):
        return pattern.sub(milestone_entry, existing, count=1)

    separator = "" if existing.endswith("\n\n") else ("\n" if existing.endswith("\n") else "\n\n")
    return existing + separator + milestone_entry


# ─── Pydantic Models ──────────────────────────────────────────────────────────


class PhaseInfo(BaseModel):
    """Information about a discovered phase directory."""

    found: bool
    directory: str  # Relative internal phase-record path: GPD/phases/XX-name
    phase_number: str
    phase_name: str | None
    phase_slug: str | None
    plans: list[str]
    summaries: list[str]
    incomplete_plans: list[str]
    has_research: bool = False
    has_context: bool = False
    has_verification: bool = False
    has_validation: bool = False


class WaveValidation(BaseModel):
    """Result of validating wave dependencies in a phase."""

    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class RoadmapPhase(BaseModel):
    """Phase entry parsed from ROADMAP.md."""

    number: str
    name: str
    goal: str | None = None
    depends_on: str | None = None
    plan_count: int = 0
    summary_count: int = 0
    has_context: bool = False
    has_research: bool = False
    contract_advances: list[str] = Field(default_factory=list)
    contract_anchor_coverage: list[str] = Field(default_factory=list)
    contract_forbidden_proxies: list[str] = Field(default_factory=list)
    has_contract_coverage: bool = False
    disk_status: str  # no_directory|empty|discussed|researched|planned|partial|complete
    roadmap_complete: bool = False


class MilestoneInfo(BaseModel):
    """Milestone version and name from ROADMAP.md."""

    version: str
    name: str


class RoadmapAnalysis(BaseModel):
    """Full analysis of a ROADMAP.md file."""

    milestones: list[dict[str, str]] = Field(default_factory=list)
    phases: list[RoadmapPhase] = Field(default_factory=list)
    phase_count: int = 0
    completed_phases: int = 0
    total_plans: int = 0
    total_summaries: int = 0
    progress_percent: int = 0
    current_phase: str | None = None
    next_phase: str | None = None


class PlanEntry(BaseModel):
    """A single plan entry with wave and dependency info."""

    id: str
    wave: int = 1
    depends_on: list[str] = Field(default_factory=list)
    files_modified: list[str] = Field(default_factory=list)
    interactive: bool = False
    objective: str | None = None
    task_count: int = 0
    has_summary: bool = False


class PhasePlanIndex(BaseModel):
    """Index of plans in a phase with wave grouping and validation."""

    phase: str
    plans: list[PlanEntry] = Field(default_factory=list)
    waves: dict[str, list[str]] = Field(default_factory=dict)
    incomplete: list[str] = Field(default_factory=list)
    has_checkpoints: bool = False
    validation: WaveValidation = Field(default_factory=lambda: WaveValidation(valid=True))


class PhaseListResult(BaseModel):
    """Result of listing phase directories."""

    directories: list[str] = Field(default_factory=list)
    count: int = 0


class PhaseFilesResult(BaseModel):
    """Result of listing phase files by type."""

    files: list[str] = Field(default_factory=list)
    count: int = 0
    phase_dir: str | None = None
    phase_directory: str | None = None
    files_by_phase: dict[str, list[str]] = Field(default_factory=dict)
    error: str | None = None


class RoadmapPhaseResult(BaseModel):
    """Result of looking up a single phase in ROADMAP.md."""

    found: bool
    phase_number: str | None = None
    phase_name: str | None = None
    goal: str | None = None
    section: str | None = None
    error: str | None = None


class NextDecimalResult(BaseModel):
    """Result of computing the next decimal sub-phase number."""

    found: bool
    base_phase: str
    next: str
    existing: list[str] = Field(default_factory=list)


class PhaseAddResult(BaseModel):
    """Result of adding a new phase."""

    phase_number: int
    padded: str
    name: str
    slug: str | None
    directory: str


class PhaseInsertResult(BaseModel):
    """Result of inserting a decimal sub-phase."""

    phase_number: str
    after_phase: str
    name: str
    slug: str | None
    directory: str


class RenameEntry(BaseModel):
    """A single directory or file rename."""

    from_name: str = Field(alias="from")
    to_name: str = Field(alias="to")

    model_config = {"populate_by_name": True}


class PhaseRemoveResult(BaseModel):
    """Result of removing a phase."""

    removed: str
    directory_deleted: str | None = None
    renamed_directories: list[RenameEntry] = Field(default_factory=list)
    renamed_files: list[RenameEntry] = Field(default_factory=list)
    roadmap_updated: bool = False
    state_updated: bool = False


class PhaseCompleteResult(BaseModel):
    """Result of marking a phase complete."""

    completed_phase: str
    phase_name: str | None = None
    plans_executed: str
    all_plans_complete: bool
    next_phase: str | None = None
    next_phase_name: str | None = None
    is_last_phase: bool = True
    date: str
    roadmap_updated: bool = False
    state_updated: bool = False


class ArchiveStatus(BaseModel):
    """Status of archived milestone files."""

    roadmap: bool = False
    requirements: bool = False
    audit: bool = False


class MilestoneCompleteResult(BaseModel):
    """Result of completing and archiving a milestone."""

    version: str
    name: str
    date: str
    phases: int = 0
    plans: int = 0
    tasks: int = 0
    accomplishments: list[str] = Field(default_factory=list)
    archived: ArchiveStatus = Field(default_factory=ArchiveStatus)
    milestones_updated: bool = False
    state_updated: bool = False


class PhaseProgress(BaseModel):
    """Progress data for a single phase."""

    number: str
    name: str
    plans: int
    summaries: int
    status: str


class ProgressLiveExecution(BaseModel):
    """Live execution telemetry surfaced next to static milestone progress.

    Populated from ``derive_execution_visibility`` so ``gpd:progress`` can
    answer "any idea of progress?" during long-running multi-plan executions.
    """

    model_config = ConfigDict(extra="forbid")

    phase: str | None = None
    plan: str | None = None
    wave: str | None = None
    current_task: str | None = None
    current_task_index: int | None = None
    current_task_total: int | None = None
    segment_status: str | None = None
    waiting_reason: str | None = None
    last_result_label: str | None = None
    last_artifact_path: str | None = None
    last_updated_age_label: str | None = None
    strict_wait: bool = False
    never_interrupt_running_workers: bool = False
    never_auto_close_child_agents: bool = False


class ProgressJsonResult(BaseModel):
    """Progress data in JSON format."""

    model_config = ConfigDict(extra="forbid")

    milestone_version: str
    milestone_name: str
    phases: list[PhaseProgress] = Field(default_factory=list)
    total_plans: int = 0
    total_summaries: int = 0
    percent: int = 0
    state_progress_percent: int | None = None
    diverged: bool = False
    warnings: list[str] = Field(default_factory=list)
    live_execution: ProgressLiveExecution | None = None


class ProgressBarResult(BaseModel):
    """Progress data as a text bar."""

    bar: str
    percent: int
    completed: int
    total: int


class ProgressTableResult(BaseModel):
    """Progress data as a rendered markdown table."""

    rendered: str


class PhaseWaveValidationResult(BaseModel):
    """Result of validating waves for a specific phase."""

    phase: str
    validation: WaveValidation
    error: str | None = None


# ─── Internal Helpers ──────────────────────────────────────────────────────────


def _sorted_phases(dirs: list[str]) -> list[str]:
    """Sort phase directory names by numeric segments."""
    return sorted(dirs, key=lambda name: (_phase_sort_key(name), name))


def _phase_dir_number(dir_name: str) -> str | None:
    """Return the normalized phase number encoded by a phase directory name."""
    match = re.match(r"^(\d+(?:\.\d+)*)(?:-|$)", dir_name)
    if match is None:
        return None
    return phase_normalize(match.group(1))


def _phase_dir_immediate_descendant_of(dir_name: str, normalized_phase: str) -> bool:
    """Return whether *dir_name* is an immediate decimal descendant of a phase."""
    prefix = normalized_phase + "."
    if not dir_name.startswith(prefix):
        return False
    rest = dir_name[len(prefix) :]
    return re.match(r"^\d+(?:-|$)", rest) is not None and re.match(r"^\d+\.", rest) is None


def _matching_phase_dir(phase: str, dirs: list[str]) -> str | None:
    """Resolve a phase query to exactly one directory or raise on ambiguity."""
    normalized = phase_normalize(phase)
    if normalized in dirs:
        return normalized

    exact_number_matches = [d for d in dirs if _phase_dir_number(d) == normalized]
    if len(exact_number_matches) > 1:
        raise PhaseAmbiguityError(phase, exact_number_matches)
    if len(exact_number_matches) == 1:
        return exact_number_matches[0]

    descendant_matches = [d for d in dirs if _phase_dir_immediate_descendant_of(d, normalized)]
    if len(descendant_matches) > 1:
        raise PhaseAmbiguityError(phase, descendant_matches)
    if len(descendant_matches) == 1:
        return descendant_matches[0]

    return None


@dataclass(frozen=True, slots=True)
class _MilestoneCompletionSnapshot:
    """Internal milestone-level completion summary shared across workflows."""

    phase_numbers: tuple[str, ...]
    phase_count: int
    completed_phases: int
    total_plans: int
    all_phases_complete: bool


def _milestone_completion_snapshot(cwd: Path) -> _MilestoneCompletionSnapshot:
    """Return roadmap-plus-disk milestone completion state."""

    roadmap = roadmap_analyze(cwd)
    roadmap_phase_map = {phase_normalize(phase.number): phase for phase in roadmap.phases}
    disk_phase_numbers = {
        phase_normalize(match.group(1))
        for phase_dir in _list_phase_dirs(cwd)
        if (match := re.match(r"^(\d+(?:\.\d+)*)", phase_dir))
    }

    phase_numbers = tuple(sorted(set(roadmap_phase_map) | disk_phase_numbers, key=_phase_sort_key))
    completed_phases = 0
    total_plans = 0

    for phase_number in phase_numbers:
        roadmap_phase = roadmap_phase_map.get(phase_number)
        phase_info = find_phase(cwd, phase_number)

        if roadmap_phase is not None:
            total_plans += roadmap_phase.plan_count
        elif phase_info is not None:
            total_plans += len(phase_info.plans)

        if phase_info is None:
            continue

        if is_phase_complete(len(phase_info.plans), matching_phase_artifact_count(phase_info.plans, phase_info.summaries)):
            completed_phases += 1

    phase_count = len(phase_numbers)
    return _MilestoneCompletionSnapshot(
        phase_numbers=phase_numbers,
        phase_count=phase_count,
        completed_phases=completed_phases,
        total_plans=total_plans,
        all_phases_complete=phase_count > 0 and completed_phases == phase_count,
    )


def _planning_path(cwd: Path) -> Path:
    return ProjectLayout(cwd).gpd


def _phases_dir(cwd: Path) -> Path:
    return ProjectLayout(cwd).phases_dir


def _roadmap_path(cwd: Path) -> Path:
    return ProjectLayout(cwd).roadmap


def _list_phase_dirs(cwd: Path) -> list[str]:
    """List phase directories sorted by phase number."""
    phases_dir = _phases_dir(cwd)
    if not phases_dir.is_dir():
        return []
    dirs = [d.name for d in phases_dir.iterdir() if d.is_dir()]
    return _sorted_phases(dirs)


def _list_phase_dirs_raw(phases_dir: Path) -> list[str]:
    """List and sort phase directories from a phases_dir Path."""
    return _sorted_phases([d.name for d in phases_dir.iterdir() if d.is_dir()])


def _ensure_list(value: object, *, field_name: str) -> list[str]:
    """Require a list-valued frontmatter field and normalize items to strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    raise PhaseValidationError(f"Frontmatter field '{field_name}' must be a list")


def _validate_phase_number(phase_num: str) -> None:
    """Raise PhaseValidationError if phase_num is not digits-and-dots."""
    if not re.match(r"^\d+(\.\d+)*$", str(phase_num)):
        raise PhaseValidationError(
            f'Invalid phase number format: "{phase_num}". Expected digits and dots (e.g., 3, 3.1, 3.1.2)'
        )


@contextmanager
def _null_context():
    """No-op context manager for conditional locking."""
    yield


# ─── Phase Discovery ──────────────────────────────────────────────────────────


def find_phase(cwd: Path, phase: str) -> PhaseInfo | None:
    """Find a phase directory matching the given phase identifier.

    Matches by exact name, prefix with hyphen, or decimal sub-phase.
    Returns None if no matching phase directory found.
    """
    if not phase:
        return None

    layout = ProjectLayout(cwd)
    phases_dir = layout.phases_dir
    normalized = phase_normalize(phase)

    if not phases_dir.is_dir():
        return None

    with gpd_span("phases.find", phase=phase):
        dirs = _list_phase_dirs(cwd)
        match_dir = _matching_phase_dir(phase, dirs)

        if match_dir is None:
            return None

        # Parse directory name
        dir_match = re.match(r"^(\d+(?:\.\d+)*)-?(.*)", match_dir)
        phase_number = dir_match.group(1) if dir_match else normalized
        phase_name = dir_match.group(2) if dir_match and dir_match.group(2) else None

        # List phase files
        phase_dir = phases_dir / match_dir
        phase_files = sorted(f.name for f in phase_dir.iterdir() if f.is_file())

        plans = sorted(f for f in phase_files if f.endswith(PLAN_SUFFIX) or f == STANDALONE_PLAN)
        summaries = sorted(f for f in phase_files if layout.is_summary_file(f))
        has_research = any(f.endswith(RESEARCH_SUFFIX) or f == STANDALONE_RESEARCH for f in phase_files)
        has_context = any(f.endswith(CONTEXT_SUFFIX) or f == STANDALONE_CONTEXT for f in phase_files)
        has_verification = any(f.endswith(VERIFICATION_SUFFIX) for f in phase_files)
        has_validation = any(f.endswith(VALIDATION_SUFFIX) or f == STANDALONE_VALIDATION for f in phase_files)

        # Determine incomplete plans (plans without matching summaries)
        completed_plan_ids = {phase_artifact_id(s, SUMMARY_SUFFIX, STANDALONE_SUMMARY) for s in summaries}
        incomplete_plans = [p for p in plans if phase_artifact_id(p, PLAN_SUFFIX, STANDALONE_PLAN) not in completed_plan_ids]

        # Build slug
        phase_slug = None
        if phase_name:
            phase_slug = re.sub(r"[^a-z0-9]+", "-", phase_name.lower()).strip("-") or None

        return PhaseInfo(
            found=True,
            directory=f"{PLANNING_DIR_NAME}/{PHASES_DIR_NAME}/{match_dir}",
            phase_number=phase_number,
            phase_name=phase_name,
            phase_slug=phase_slug,
            plans=plans,
            summaries=summaries,
            incomplete_plans=incomplete_plans,
            has_research=has_research,
            has_context=has_context,
            has_verification=has_verification,
            has_validation=has_validation,
        )


def get_milestone_info(cwd: Path) -> MilestoneInfo:
    """Extract milestone version and name from ROADMAP.md."""
    roadmap_path = _roadmap_path(cwd)
    content = safe_read_file(roadmap_path)
    if content is None:
        return MilestoneInfo(version="v1.0", name="milestone")

    version_match = re.search(r"v(\d+\.\d+)", content)
    name_match = re.search(r"## .*v\d+\.\d+[:\s]+([^\n(]+)", content)
    return MilestoneInfo(
        version=version_match.group(0) if version_match else "v1.0",
        name=name_match.group(1).strip() if name_match else "milestone",
    )


# ─── Phase Listing ─────────────────────────────────────────────────────────────


def list_phases(cwd: Path) -> PhaseListResult:
    """List all phase directories sorted by phase number."""
    with gpd_span("phases.list"):
        dirs = _list_phase_dirs(cwd)
        return PhaseListResult(directories=dirs, count=len(dirs))


def list_phase_files(cwd: Path, file_type: str, phase: str | None = None) -> PhaseFilesResult:
    """List files of a specific type across phases.

    Args:
        cwd: Project root directory.
        file_type: ``"plans"``, ``"summaries"``, or any other value (returns all files).
        phase: Optional phase filter.
    """
    with gpd_span("phases.list_files", file_type=file_type):
        layout = ProjectLayout(cwd)
        phases_dir = layout.phases_dir
        if not phases_dir.is_dir():
            return PhaseFilesResult()

        dirs = _list_phase_dirs(cwd)

        # Filter to specific phase if requested
        if phase:
            try:
                info = find_phase(cwd, phase)
            except PhaseAmbiguityError as exc:
                return PhaseFilesResult(error=str(exc))
            if not info:
                return PhaseFilesResult(error="Phase not found")
            match_dir = Path(info.directory).name
            dirs = [match_dir]

        files: list[str] = []
        files_by_phase: dict[str, list[str]] = {}
        for d in dirs:
            dir_path = phases_dir / d
            dir_files = sorted(f.name for f in dir_path.iterdir() if f.is_file())

            if file_type == "plans":
                filtered = [f for f in dir_files if f.endswith(PLAN_SUFFIX) or f == STANDALONE_PLAN]
            elif file_type == "summaries":
                filtered = [f for f in dir_files if layout.is_summary_file(f)]
            else:
                filtered = dir_files

            files_by_phase[d] = sorted(filtered)
            files.extend(files_by_phase[d])

        phase_dir_name = None
        phase_directory = None
        if phase and dirs:
            phase_dir_name = re.sub(r"^\d+(?:\.\d+)*-?", "", dirs[0])
            phase_directory = dirs[0]

        return PhaseFilesResult(
            files=files,
            count=len(files),
            phase_dir=phase_dir_name,
            phase_directory=phase_directory,
            files_by_phase=files_by_phase,
        )


# ─── Roadmap Get Phase ─────────────────────────────────────────────────────────


def roadmap_get_phase(cwd: Path, phase_num: str) -> RoadmapPhaseResult:
    """Extract a specific phase section from ROADMAP.md."""
    _validate_phase_number(phase_num)

    with gpd_span("roadmap.get_phase", phase=phase_num):
        roadmap_path = _roadmap_path(cwd)
        content = safe_read_file(roadmap_path)
        if content is None:
            return RoadmapPhaseResult(found=False, error="ROADMAP.md not found")

        heading = _find_roadmap_phase_heading(content, phase_num)
        if heading is None:
            return RoadmapPhaseResult(found=False, phase_number=phase_num)

        section_start, section_end = _roadmap_phase_section_bounds(content, heading)
        section = content[section_start:section_end].strip()

        goal_match = re.search(r"\*\*Goal:\*\*\s*([^\n]+)", section, re.IGNORECASE)
        goal = goal_match.group(1).strip() if goal_match else None

        return RoadmapPhaseResult(
            found=True,
            phase_number=heading.number,
            phase_name=heading.name,
            goal=goal,
            section=section,
        )


# ─── Phase Next Decimal ────────────────────────────────────────────────────────


def next_decimal_phase(cwd: Path, base_phase: str) -> NextDecimalResult:
    """Calculate the next decimal sub-phase number.

    E.g., if ``03.1`` and ``03.2`` exist, returns ``"03.3"``.
    """
    with gpd_span("phases.next_decimal", base_phase=base_phase):
        normalized = phase_normalize(base_phase)
        phases_dir = _phases_dir(cwd)

        if not phases_dir.is_dir():
            return NextDecimalResult(found=False, base_phase=normalized, next=f"{normalized}.1")

        dirs = [d.name for d in phases_dir.iterdir() if d.is_dir()]
        base_exists = any(d.startswith(normalized + "-") or d == normalized for d in dirs)

        escaped = re.escape(normalized)
        decimal_pattern = re.compile(rf"^{escaped}\.(\d+)")
        existing_decimals: list[str] = []
        for d in dirs:
            m = decimal_pattern.match(d)
            if m:
                existing_decimals.append(f"{normalized}.{m.group(1)}")

        existing_decimals = _sorted_phases(existing_decimals)

        if not existing_decimals:
            next_decimal = f"{normalized}.1"
        else:
            last = existing_decimals[-1]
            last_num = int(last.split(".")[-1])
            next_decimal = f"{normalized}.{last_num + 1}"

        return NextDecimalResult(
            found=base_exists,
            base_phase=normalized,
            next=next_decimal,
            existing=existing_decimals,
        )


# ─── Wave Validation ──────────────────────────────────────────────────────────


def validate_waves(plans: list[PlanEntry]) -> WaveValidation:
    """Validate wave dependencies, file overlaps, cycles, orphans, and numbering.

    Performs 6 checks:

    1. ``depends_on`` targets exist
    2. ``files_modified`` overlap within same wave (warning)
    3. No dependency on same or later wave
    4. Cycle detection via Kahn's algorithm
    5. Orphan detection (plans not depended upon, not in final wave)
    6. Wave numbering is consecutive starting from 1
    """
    with gpd_span("waves.validate", plan_count=len(plans)):
        errors: list[str] = []
        warnings: list[str] = []

        plan_ids = {p.id for p in plans}
        plan_by_id = {p.id: p for p in plans}

        # 1. depends_on target validation
        for plan in plans:
            for dep in plan.depends_on:
                if dep not in plan_ids:
                    errors.append(f'Plan {plan.id} depends_on "{dep}" which does not exist in this phase')

        # 2. files_modified overlap within same wave
        wave_groups: dict[int, list[PlanEntry]] = {}
        for plan in plans:
            wave_groups.setdefault(plan.wave, []).append(plan)

        for wave_key, wave_plans in wave_groups.items():
            for i in range(len(wave_plans)):
                for j in range(i + 1, len(wave_plans)):
                    a, b = wave_plans[i], wave_plans[j]
                    a_files = set(a.files_modified)
                    overlap = [f for f in b.files_modified if f in a_files]
                    if overlap:
                        warnings.append(f"Plans {a.id} and {b.id} both modify {', '.join(overlap)} in wave {wave_key}")

        # 3. Wave consistency: dependency must be in an earlier wave
        for plan in plans:
            for dep in plan.depends_on:
                dep_plan = plan_by_id.get(dep)
                if dep_plan and dep_plan.wave >= plan.wave:
                    errors.append(
                        f"Plan {plan.id} (wave {plan.wave}) depends on {dep} (wave {dep_plan.wave}); "
                        f"dependency must be in an earlier wave"
                    )

        # 4. Cycle detection via Kahn's algorithm (topological sort)
        in_degree: dict[str, int] = {p.id: 0 for p in plans}
        adj_list: dict[str, list[str]] = {p.id: [] for p in plans}
        for plan in plans:
            for dep in plan.depends_on:
                if dep in plan_ids:
                    adj_list[dep].append(plan.id)
                    in_degree[plan.id] += 1

        queue = deque(pid for pid, deg in in_degree.items() if deg == 0)
        visited = 0
        while queue:
            node = queue.popleft()
            visited += 1
            for neighbor in adj_list[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if visited < len(plans):
            cycle_nodes = [pid for pid, deg in in_degree.items() if deg > 0]
            errors.append(f"Circular dependency detected among plans: {', '.join(cycle_nodes)}")

        # 5. Orphan detection
        depended_upon: set[str] = set()
        for plan in plans:
            depended_upon.update(plan.depends_on)

        max_wave = max((p.wave for p in plans), default=0)
        for plan in plans:
            if plan.id not in depended_upon and plan.wave < max_wave:
                warnings.append(
                    f"Plan {plan.id} (wave {plan.wave}) is not depended upon by any other plan "
                    f"and is not in the final wave"
                )

        # 6. Wave numbering gap detection
        wave_numbers = sorted({p.wave for p in plans})
        if wave_numbers:
            if wave_numbers[0] != 1:
                errors.append(f"Wave numbering must start at 1, found {wave_numbers[0]}")
            for i in range(1, len(wave_numbers)):
                if wave_numbers[i] != wave_numbers[i - 1] + 1:
                    errors.append(
                        f"Gap in wave numbering: wave {wave_numbers[i - 1]} is followed by "
                        f"wave {wave_numbers[i]} (expected {wave_numbers[i - 1] + 1})"
                    )

        logger.info(
            "wave_validation_complete: valid=%s errors=%d warnings=%d",
            len(errors) == 0,
            len(errors),
            len(warnings),
        )
        return WaveValidation(valid=len(errors) == 0, errors=errors, warnings=warnings)


def validate_phase_waves(cwd: Path, phase: str) -> PhaseWaveValidationResult:
    """Validate wave dependencies for a specific phase."""
    normalized = phase_normalize(phase)
    try:
        phase_info = find_phase(cwd, phase)
    except PhaseAmbiguityError as exc:
        return PhaseWaveValidationResult(
            phase=normalized,
            error=str(exc),
            validation=WaveValidation(valid=False, errors=[str(exc)]),
        )

    if not phase_info:
        return PhaseWaveValidationResult(
            phase=normalized,
            error="Phase not found",
            validation=WaveValidation(valid=False, errors=["Phase not found"]),
        )

    with gpd_span("phases.validate_waves", phase=normalized):
        phase_dir = cwd / phase_info.directory

        plans: list[PlanEntry] = []
        errors: list[str] = []
        for plan_file in phase_info.plans:
            plan_key = phase_artifact_id(plan_file, PLAN_SUFFIX, STANDALONE_PLAN)
            plan_id = phase_artifact_display_name(plan_key, STANDALONE_PLAN)
            try:
                content = (phase_dir / plan_file).read_text(encoding="utf-8")
                fm = _extract_frontmatter(content)
                files_modified = _ensure_list(fm.get("files_modified"), field_name="files_modified")
                depends_on = _ensure_list(fm.get("depends_on"), field_name="depends_on")
                wave = _parse_plan_wave(fm.get("wave"))
            except (FrontmatterParseError, PhaseValidationError, OSError, UnicodeDecodeError) as exc:
                errors.append(f"{plan_file}: {exc}")
                continue

            plans.append(PlanEntry(id=plan_id, wave=wave, depends_on=depends_on, files_modified=files_modified))

        validation = validate_waves(plans)
        if errors:
            validation = validation.model_copy(update={"valid": False, "errors": [*errors, *validation.errors]})
        return PhaseWaveValidationResult(phase=normalized, validation=validation)


# ─── Phase Plan Index ──────────────────────────────────────────────────────────


def phase_plan_index(cwd: Path, phase: str) -> PhasePlanIndex:
    """Build an index of plans in a phase with wave grouping and validation."""
    normalized = phase_normalize(phase)
    try:
        phase_info = find_phase(cwd, phase)
    except PhaseAmbiguityError as exc:
        return PhasePlanIndex(
            phase=normalized,
            validation=WaveValidation(valid=False, errors=[str(exc)]),
        )

    if not phase_info:
        return PhasePlanIndex(phase=normalized)

    with gpd_span("phases.plan_index", phase=normalized):
        phase_dir = cwd / phase_info.directory

        completed_plan_ids = {phase_artifact_id(s, SUMMARY_SUFFIX, STANDALONE_SUMMARY) for s in phase_info.summaries}

        plans: list[PlanEntry] = []
        waves: dict[str, list[str]] = {}
        incomplete: list[str] = []
        has_checkpoints = False
        validation_errors: list[str] = []

        for plan_file in phase_info.plans:
            plan_key = phase_artifact_id(plan_file, PLAN_SUFFIX, STANDALONE_PLAN)
            plan_id = phase_artifact_display_name(plan_key, STANDALONE_PLAN)
            try:
                content = (phase_dir / plan_file).read_text(encoding="utf-8")
                fm = _extract_frontmatter(content)
                files_modified = _ensure_list(fm.get("files_modified"), field_name="files_modified")
                depends_on = _ensure_list(fm.get("depends_on"), field_name="depends_on")
                wave = _parse_plan_wave(fm.get("wave"))
            except (FrontmatterParseError, PhaseValidationError, OSError, UnicodeDecodeError) as exc:
                validation_errors.append(f"{plan_file}: {exc}")
                continue

            task_count = len(re.findall(r"##\s*Task\s*\d+", content, re.IGNORECASE))
            if task_count == 0:
                task_count = len(re.findall(r"<task\b", content, re.IGNORECASE))

            interactive = False
            if "interactive" in fm:
                interactive = fm["interactive"] in (True, "true")

            if interactive or _CHECKPOINT_TASK_RE.search(content):
                has_checkpoints = True

            has_summary = plan_key in completed_plan_ids
            if not has_summary:
                incomplete.append(plan_id)

            entry = PlanEntry(
                id=plan_id,
                wave=wave,
                interactive=interactive,
                objective=fm.get("objective"),
                depends_on=depends_on,
                files_modified=files_modified,
                task_count=task_count,
                has_summary=has_summary,
            )
            plans.append(entry)

            wave_key = str(wave)
            waves.setdefault(wave_key, []).append(plan_id)

        validation = validate_waves(plans)
        if validation_errors:
            validation = validation.model_copy(
                update={"valid": False, "errors": [*validation_errors, *validation.errors]}
            )

        return PhasePlanIndex(
            phase=normalized,
            plans=plans,
            waves=waves,
            incomplete=incomplete,
            has_checkpoints=has_checkpoints,
            validation=validation,
        )


# ─── Roadmap Analyze ───────────────────────────────────────────────────────────


def roadmap_analyze(cwd: Path) -> RoadmapAnalysis:
    """Analyze the full ROADMAP.md: phases, milestones, progress stats."""
    roadmap_path = _roadmap_path(cwd)
    content = safe_read_file(roadmap_path)
    if content is None:
        return RoadmapAnalysis()

    with gpd_span("roadmap.analyze"):
        layout = ProjectLayout(cwd)
        phases_dir = layout.phases_dir

        # Read phase directories once
        phase_dir_names: list[str] = []
        if phases_dir.is_dir():
            phase_dir_names = [d.name for d in phases_dir.iterdir() if d.is_dir()]

        # Extract all phase headings
        phases: list[RoadmapPhase] = []

        for heading in _roadmap_phase_headings(content):
            phase_num = heading.number
            phase_name = re.sub(r"\(INSERTED\)", "", heading.name, flags=re.IGNORECASE).strip()

            # Extract section text
            section_start, section_end = _roadmap_phase_section_bounds(content, heading)
            section = content[section_start:section_end]

            goal_match = re.search(r"\*\*Goal:\*\*\s*([^\n]+)", section, re.IGNORECASE)
            goal = goal_match.group(1).strip() if goal_match else None

            depends_match = re.search(r"\*\*Depends on:\*\*\s*([^\n]+)", section, re.IGNORECASE)
            depends_on = depends_match.group(1).strip() if depends_match else None

            def _coverage_items(section_text: str, label: str) -> list[str]:
                match = re.search(rf"-\s*{re.escape(label)}:\s*([^\n]+)", section_text, re.IGNORECASE)
                if match is None:
                    return []
                raw = match.group(1).strip()
                if not raw:
                    return []
                return [item.strip() for item in raw.split(",") if item.strip()]

            contract_advances = _coverage_items(section, "Advances")
            contract_anchor_coverage = _coverage_items(section, "Anchor coverage")
            contract_forbidden_proxies = _coverage_items(section, "Forbidden proxies")
            has_contract_coverage = bool(
                contract_advances or contract_anchor_coverage or contract_forbidden_proxies
            )

            # Check disk status
            normalized = phase_normalize(phase_num)
            disk_status = "no_directory"
            plan_count = 0
            summary_count = 0
            has_context = False
            has_research = False

            try:
                dir_match_name = _matching_phase_dir(phase_num, _sorted_phases(phase_dir_names))
            except PhaseAmbiguityError:
                dir_match_name = None
                disk_status = "ambiguous"

            if dir_match_name:
                phase_files = [f.name for f in (phases_dir / dir_match_name).iterdir() if f.is_file()]
                plans = [f for f in phase_files if f.endswith(PLAN_SUFFIX) or f == STANDALONE_PLAN]
                summaries = [f for f in phase_files if layout.is_summary_file(f)]
                plan_count = len(plans)
                summary_count = matching_phase_artifact_count(plans, summaries)
                has_context = any(f.endswith(CONTEXT_SUFFIX) or f == STANDALONE_CONTEXT for f in phase_files)
                has_research = any(f.endswith(RESEARCH_SUFFIX) or f == STANDALONE_RESEARCH for f in phase_files)

                if is_phase_complete(plan_count, summary_count):
                    disk_status = "complete"
                elif summary_count > 0:
                    disk_status = "partial"
                elif plan_count > 0:
                    disk_status = "planned"
                elif has_research:
                    disk_status = "researched"
                elif has_context:
                    disk_status = "discussed"
                else:
                    disk_status = "empty"

            # Check ROADMAP checkbox status
            roadmap_complete = False
            for checkbox_match in re.finditer(
                r"-\s*\[(x| )\]\s*.*?\bPhase\s+(\d+(?:\.\d+)*)(?=[:\s.\)\u2014]|$)",
                content,
                re.IGNORECASE,
            ):
                if phase_normalize(checkbox_match.group(2)) == normalized:
                    roadmap_complete = checkbox_match.group(1).lower() == "x"
                    break

            phases.append(
                RoadmapPhase(
                    number=phase_num,
                    name=phase_name,
                    goal=goal,
                    depends_on=depends_on,
                    plan_count=plan_count,
                    summary_count=summary_count,
                    has_context=has_context,
                    has_research=has_research,
                    contract_advances=contract_advances,
                    contract_anchor_coverage=contract_anchor_coverage,
                    contract_forbidden_proxies=contract_forbidden_proxies,
                    has_contract_coverage=has_contract_coverage,
                    disk_status=disk_status,
                    roadmap_complete=roadmap_complete,
                )
            )

        # Extract milestones
        milestones: list[dict[str, str]] = []
        milestone_pattern = re.compile(r"##\s*(.*v(\d+\.\d+)[^(\n]*)", re.IGNORECASE)
        for m in milestone_pattern.finditer(content):
            milestones.append({"heading": m.group(1).strip(), "version": f"v{m.group(2)}"})

        # Find current and next phase
        current_phase = next((p for p in phases if p.disk_status in ("planned", "partial")), None)
        if current_phase is None:
            state_content = safe_read_file(layout.state_md)
            if state_content is not None:
                state_phase = _extract_state_field(state_content, "Current Phase")
                if state_phase is not None:
                    try:
                        _validate_phase_number(state_phase)
                    except PhaseValidationError:
                        pass
                    else:
                        normalized_state_phase = phase_normalize(state_phase)
                        current_phase = next(
                            (
                                p
                                for p in phases
                                if compare_phase_numbers(phase_normalize(p.number), normalized_state_phase) == 0
                            ),
                            None,
                        )
        current_phase_number = current_phase.number if current_phase else None
        next_phase = next(
            (
                p
                for p in phases
                if p.disk_status in ("empty", "no_directory", "discussed", "researched")
                and (
                    current_phase_number is None
                    or compare_phase_numbers(phase_normalize(p.number), phase_normalize(current_phase_number)) != 0
                )
            ),
            None,
        )

        # Aggregate stats
        total_plans = sum(p.plan_count for p in phases)
        total_summaries = sum(p.summary_count for p in phases)
        completed = sum(1 for p in phases if p.disk_status == "complete")

        return RoadmapAnalysis(
            milestones=milestones,
            phases=phases,
            phase_count=len(phases),
            completed_phases=completed,
            total_plans=total_plans,
            total_summaries=total_summaries,
            progress_percent=min(100, round(total_summaries / total_plans * 100)) if total_plans > 0 else 0,
            current_phase=current_phase.number if current_phase else None,
            next_phase=next_phase.number if next_phase else None,
        )


def _normalize_phase_label(phase: str | None) -> str | None:
    """Normalize a roadmap or state phase identifier for comparisons/storage."""
    if phase is None:
        return None
    return phase_normalize(str(phase))


def _phase_in_subtree(candidate_phase: str | None, target_phase: str) -> bool:
    """Return whether *candidate_phase* is *target_phase* or one of its descendants."""
    normalized_candidate = _normalize_phase_label(candidate_phase)
    if normalized_candidate is None:
        return False
    normalized_target = phase_normalize(target_phase)
    return normalized_candidate == normalized_target or normalized_candidate.startswith(normalized_target + ".")


def _phase_dir_entry(dir_name: str) -> tuple[str, str]:
    """Split a phase directory name into its numeric prefix and optional slug."""
    match = re.match(r"^(\d+(?:\.\d+)*)(?:-(.*))?$", dir_name)
    if match is None:
        raise PhaseError(f'Invalid phase directory name: "{dir_name}"')
    return match.group(1), match.group(2) or ""


def _phase_dir_in_subtree(dir_name: str, target_phase: str) -> bool:
    """Return whether a phase directory belongs to the removed subtree."""
    try:
        prefix, _slug = _phase_dir_entry(dir_name)
    except PhaseError:
        return False
    return _phase_in_subtree(prefix, target_phase)


def _phase_number_parts(phase_ref: str) -> list[int] | None:
    """Return integer segments for a phase reference."""
    if not re.fullmatch(r"\d+(?:\.\d+)*", phase_ref):
        return None
    return [int(part) for part in phase_ref.split(".")]


def _shift_phase_reference_after_removal(
    phase_ref: str,
    removed_phase: str,
    *,
    normalize_output: bool = False,
) -> str:
    """Shift one surviving phase reference after removing a sibling or subtree phase."""
    phase_parts = _phase_number_parts(phase_unpad(phase_ref))
    removed_parts = _phase_number_parts(phase_unpad(removed_phase))
    if phase_parts is None or removed_parts is None:
        return phase_ref

    if len(removed_parts) == 1:
        if phase_parts[0] <= removed_parts[0]:
            return phase_ref
        shifted_parts = [phase_parts[0] - 1, *phase_parts[1:]]
    else:
        sibling_depth = len(removed_parts) - 1
        if len(phase_parts) <= sibling_depth or phase_parts[:sibling_depth] != removed_parts[:sibling_depth]:
            return phase_ref
        if phase_parts[sibling_depth] <= removed_parts[sibling_depth]:
            return phase_ref
        shifted_parts = [
            *phase_parts[:sibling_depth],
            phase_parts[sibling_depth] - 1,
            *phase_parts[sibling_depth + 1 :],
        ]

    shifted = ".".join(str(part) for part in shifted_parts)
    return phase_normalize(shifted) if normalize_output else shifted


def _get_roadmap_phase_sequence(cwd: Path) -> list[RoadmapPhase]:
    """Return roadmap phases in document order."""
    return roadmap_analyze(cwd).phases


def _get_next_roadmap_phase(cwd: Path, phase_num: str) -> RoadmapPhase | None:
    """Return the next roadmap phase after *phase_num*, even if no directory exists yet."""
    normalized = phase_normalize(phase_num)
    for phase in _get_roadmap_phase_sequence(cwd):
        phase_number = phase_normalize(phase.number)
        if compare_phase_numbers(phase_number, normalized) > 0:
            return phase
    return None


def _get_roadmap_phase_by_number(cwd: Path, phase_num: str | None) -> RoadmapPhase | None:
    """Return a roadmap phase by number using normalized comparison."""
    normalized = _normalize_phase_label(phase_num)
    if normalized is None:
        return None
    for phase in _get_roadmap_phase_sequence(cwd):
        if compare_phase_numbers(phase_normalize(phase.number), normalized) == 0:
            return phase
    return None
def _remap_phase_after_removal(current_phase: str | None, removed_phase: str, remaining: list[str]) -> str | None:
    """Map a stored current phase to the post-removal numbering scheme."""
    current_norm = _normalize_phase_label(current_phase)
    if current_norm is None:
        return None

    remaining_norm = sorted({_normalize_phase_label(p) for p in remaining if _normalize_phase_label(p)}, key=str)
    removed_norm = phase_normalize(removed_phase)

    def _phase_exists(candidate: str) -> bool:
        return any(compare_phase_numbers(candidate, p) == 0 for p in remaining_norm)

    def _closest_previous(target: str) -> str | None:
        previous = [p for p in remaining_norm if compare_phase_numbers(p, target) < 0]
        if not previous:
            return None
        return max(previous, key=lambda p: [int(part) for part in p.split(".")])

    if "." in removed_norm:
        removed_base, removed_decimal = removed_norm.split(".", 1)
        current_parts = current_norm.split(".")
        current_base = current_parts[0]
        if current_base != removed_base or len(current_parts) == 1:
            return current_norm if _phase_exists(current_norm) else _closest_previous(current_norm)
        if _phase_in_subtree(current_norm, removed_norm) and current_norm != removed_norm:
            return _closest_previous(removed_norm)

        # Only handle single-level decimals (e.g. "06.2"); multi-level
        # sub-phases like "06.1.2" are not subject to decimal renumbering.
        if len(current_parts) != 2 or "." in removed_decimal:
            return current_norm if _phase_exists(current_norm) else _closest_previous(current_norm)

        current_decimal = int(current_parts[1])
        removed_decimal_int = int(removed_decimal)
        if current_decimal < removed_decimal_int:
            return current_norm if _phase_exists(current_norm) else _closest_previous(current_norm)
        if current_decimal > removed_decimal_int:
            shifted = f"{removed_base}.{current_decimal - 1}"
            return phase_normalize(shifted) if _phase_exists(shifted) else _closest_previous(shifted)
        if _phase_exists(removed_norm):
            return removed_norm
        return _closest_previous(removed_norm)

    removed_int = int(removed_norm.split(".", 1)[0])
    current_parts = current_norm.split(".", 1)
    current_int = int(current_parts[0])
    decimal_suffix = f".{current_parts[1]}" if len(current_parts) > 1 else ""

    if current_int < removed_int:
        return current_norm if _phase_exists(current_norm) else _closest_previous(current_norm)
    if current_int > removed_int:
        shifted = f"{str(current_int - 1).zfill(2)}{decimal_suffix}"
        return phase_normalize(shifted) if _phase_exists(shifted) else _closest_previous(shifted)
    if _phase_exists(removed_norm):
        return removed_norm
    return _closest_previous(removed_norm)


# ─── Phase heading parsing / format detection ───────────────────────────────

_PHASE_HEADING_RE = re.compile(
    r"^(?P<indent>[ \t]*)(?P<level>#{2,4})[ \t]*Phase[ \t]+(?P<number>\d+(?:\.\d+)*)"
    r"(?P<separator>[ \t]*(?::|\u2014)[ \t]*)(?P<name>[^\n]*)",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass(frozen=True, slots=True)
class _RoadmapPhaseHeading:
    indent: str
    level: str
    number: str
    separator: str
    name: str
    start: int
    end: int


def _roadmap_phase_headings(content: str) -> list[_RoadmapPhaseHeading]:
    """Return parsed phase headings from ROADMAP.md in document order."""
    return [
        _RoadmapPhaseHeading(
            indent=match.group("indent"),
            level=match.group("level"),
            number=match.group("number"),
            separator=match.group("separator"),
            name=match.group("name").strip(),
            start=match.start(),
            end=match.end(),
        )
        for match in _PHASE_HEADING_RE.finditer(content)
    ]


def _find_roadmap_phase_heading(content: str, phase_num: str) -> _RoadmapPhaseHeading | None:
    """Find a roadmap heading by normalized phase identity."""
    normalized_query = phase_normalize(str(phase_num))
    for heading in _roadmap_phase_headings(content):
        if phase_normalize(heading.number) == normalized_query:
            return heading
    return None


def _roadmap_phase_section_bounds(content: str, heading: _RoadmapPhaseHeading) -> tuple[int, int]:
    """Return ``(start, end)`` bounds for a roadmap phase section."""
    next_heading = _PHASE_HEADING_RE.search(content, heading.end)
    return heading.start, next_heading.start() if next_heading else len(content)


def _remove_roadmap_phase_sections(content: str, phase_numbers: list[str]) -> str:
    """Remove phase sections matching *phase_numbers* by normalized identity."""
    targets = {phase_normalize(phase) for phase in phase_numbers}
    spans: list[tuple[int, int]] = []
    for heading in _roadmap_phase_headings(content):
        if phase_normalize(heading.number) not in targets:
            continue
        start, end = _roadmap_phase_section_bounds(content, heading)
        if start > 0 and content[start - 1] == "\n":
            start -= 1
        spans.append((start, end))

    merged_spans: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if not merged_spans or start > merged_spans[-1][1]:
            merged_spans.append((start, end))
            continue
        previous_start, previous_end = merged_spans[-1]
        merged_spans[-1] = (previous_start, max(previous_end, end))

    updated = content
    for start, end in reversed(merged_spans):
        updated = updated[:start] + updated[end:]
    return updated


def _phase_number_in_set(phase_num: str, phase_numbers: set[str]) -> bool:
    """Return whether *phase_num* matches one of *phase_numbers* after normalization."""
    normalized = phase_normalize(phase_num)
    return any(compare_phase_numbers(normalized, phase) == 0 for phase in phase_numbers)


def _remove_roadmap_phase_reference_lines(content: str, phase_numbers: list[str]) -> str:
    """Remove checklist/table rows that point at removed phases."""
    targets = {phase_normalize(phase) for phase in phase_numbers}
    if not targets:
        return content

    kept: list[str] = []
    for line in content.splitlines(keepends=True):
        stripped = line.lstrip()
        checkbox_match = re.match(
            r"-\s*\[[ x]\]\s*.*?\bPhase\s+(\d+(?:\.\d+)*)\b",
            stripped,
            re.IGNORECASE,
        )
        if checkbox_match and _phase_number_in_set(checkbox_match.group(1), targets):
            continue

        table_match = re.match(r"\|\s*(\d+(?:\.\d+)*)\.?\s", stripped)
        if table_match and _phase_number_in_set(table_match.group(1), targets):
            continue

        kept.append(line)
    return "".join(kept)


def _format_phase_display_num(num: int | str, pad_width: int) -> str:
    """Format a phase number for roadmap display."""
    s = str(num)
    if pad_width <= 0:
        return s
    parts = s.split(".")
    if parts and parts[0].isdigit():
        parts[0] = parts[0].zfill(pad_width)
    return ".".join(parts)


def _format_shifted_phase_reference(phase_ref: str, removed_phase: str, pad_width: int) -> str:
    """Shift a display phase reference and preserve roadmap padding style."""
    shifted = _shift_phase_reference_after_removal(phase_ref, removed_phase)
    if shifted == phase_ref:
        return phase_ref
    return _format_phase_display_num(shifted, pad_width)


def _renumber_roadmap_phase_headings(content: str, removed_phase: str, pad_width: int) -> str:
    """Renumber surviving roadmap phase headings after removal."""

    def _replace(match: re.Match[str]) -> str:
        number = _format_shifted_phase_reference(match.group("number"), removed_phase, pad_width)
        return f"{match.group('indent')}{match.group('level')} Phase {number}{match.group('separator')}{match.group('name')}"

    return _PHASE_HEADING_RE.sub(_replace, content)


def _renumber_roadmap_phase_references(content: str, removed_phase: str, pad_width: int) -> str:
    """Renumber non-heading roadmap phase references after removal."""
    content = re.sub(
        r"(^\s*-\s*\[[ x]\]\s*(?:\*\*)?Phase\s+)(\d+(?:\.\d+)*)",
        lambda m: f"{m.group(1)}{_format_shifted_phase_reference(m.group(2), removed_phase, pad_width)}",
        content,
        flags=re.MULTILINE | re.IGNORECASE,
    )
    content = re.sub(
        r"(\*\*Depends on:\*\*\s*Phase\s+)(\d+(?:\.\d+)*)\b",
        lambda m: f"{m.group(1)}{_format_shifted_phase_reference(m.group(2), removed_phase, pad_width)}",
        content,
        flags=re.IGNORECASE,
    )
    content = re.sub(
        r"(\|\s*)(\d+(?:\.\d+)*)(\.\s)",
        lambda m: f"{m.group(1)}{_format_shifted_phase_reference(m.group(2), removed_phase, pad_width)}{m.group(3)}",
        content,
    )
    return re.sub(
        r"(?<![\d.])(\d{2}(?:\.\d+)*)(?=-)",
        lambda m: _shift_phase_reference_after_removal(m.group(1), removed_phase, normalize_output=True),
        content,
    )


def _mark_roadmap_phase_complete(content: str, phase_num: str, today: str) -> str:
    """Mark a matching roadmap checklist row complete."""
    normalized = phase_normalize(phase_num)

    def _replace(match: re.Match[str]) -> str:
        if phase_normalize(match.group("number")) != normalized or match.group("mark").lower() == "x":
            return match.group(0)
        return f"{match.group('prefix')}x{match.group('suffix')} (completed {today})"

    return re.sub(
        r"(?m)^(?P<prefix>\s*-\s*\[)(?P<mark>[ xX])(?P<suffix>\]\s*.*?\bPhase\s+"
        r"(?P<number>\d+(?:\.\d+)*)[^\n]*)$",
        _replace,
        content,
    )


def _update_roadmap_phase_plan_count(content: str, phase_num: str, summary_count: int, plan_count: int) -> str:
    """Update the ``**Plans:**`` line within one roadmap phase section."""
    heading = _find_roadmap_phase_heading(content, phase_num)
    if heading is None:
        return content
    start, end = _roadmap_phase_section_bounds(content, heading)
    section = content[start:end]
    updated_section = re.sub(
        r"(\*\*Plans:\*\*\s*)[^\n]+",
        rf"\g<1>{summary_count}/{plan_count} plans complete",
        section,
        count=1,
        flags=re.IGNORECASE,
    )
    return content[:start] + updated_section + content[end:]


def _update_roadmap_phase_table_status(content: str, phase_num: str, today: str) -> str:
    """Update a progress-table row for one phase by normalized identity."""
    normalized = phase_normalize(phase_num)
    lines: list[str] = []
    for line in content.splitlines(keepends=True):
        newline = ""
        body = line
        if body.endswith("\n"):
            body = body[:-1]
            newline = "\n"
        cells = body.split("|")
        if len(cells) >= 5:
            phase_match = re.match(r"\s*(\d+(?:\.\d+)*)\.?\b", cells[1])
            if phase_match and phase_normalize(phase_match.group(1)) == normalized:
                cells[-3] = " Complete    "
                cells[-2] = f" {today} "
                body = "|".join(cells)
        lines.append(body + newline)
    return "".join(lines)


def _detect_phase_heading_format(content: str) -> tuple[str, int, str]:
    """Detect heading level, padding width, and separator from existing phase headings.

    Returns:
        (heading_prefix, pad_width, separator) where:
        - heading_prefix is e.g. ``"###"``
        - pad_width is 0 for no padding or N for ``zfill(N)``
        - separator is e.g. ``": "`` or ``" \\u2014 "``

    When no existing phases are found, returns defaults matching the
    ``new-project`` template: ``("###", 0, ": ")``.
    """
    matches = _roadmap_phase_headings(content)
    if not matches:
        return "###", 0, ": "

    # Prefer the first integer-only phase (no decimal) for heading level
    heading_level: str | None = None
    for m in matches:
        if "." not in m.number:
            heading_level = m.level
            break
    if heading_level is None:
        # All phases are decimal; use the first match
        heading_level = matches[0].level

    # Detect padding: check if any integer phase number has a leading zero
    pad_width = 0
    for m in matches:
        raw_num = m.number
        if "." in raw_num:
            continue  # skip decimal phases for padding detection
        if len(raw_num) > 1 and raw_num[0] == "0":
            pad_width = len(raw_num)
            break

    # Detect separator: colon vs em-dash
    separator = ": "  # default
    for m in matches:
        separator = m.separator
        break

    return heading_level, pad_width, separator


# ─── Phase Add ─────────────────────────────────────────────────────────────────


def phase_add(cwd: Path, description: str) -> PhaseAddResult:
    """Add a new phase to the end of the roadmap.

    Creates the phase directory and appends a section to ROADMAP.md.

    Raises:
        PhaseValidationError: If description is empty.
        RoadmapNotFoundError: If ROADMAP.md doesn't exist.
    """
    if not description:
        raise PhaseValidationError("description required for phase add")

    roadmap_path = _roadmap_path(cwd)
    if not roadmap_path.exists():
        raise RoadmapNotFoundError("ROADMAP.md not found")

    slug = generate_slug(description)

    with gpd_span("phases.add", description=description):
        with file_lock(roadmap_path):
            content = roadmap_path.read_text(encoding="utf-8")

            max_phase = 0
            for heading in _roadmap_phase_headings(content):
                num = int(phase_unpad(heading.number).split(".", 1)[0])
                if num > max_phase:
                    max_phase = num

            new_phase_num = max_phase + 1
            padded = str(new_phase_num).zfill(2)
            dir_name = f"{padded}-{slug}" if slug else padded
            dir_path = _phases_dir(cwd) / dir_name

            dir_path.mkdir(parents=True, exist_ok=True)

            heading_level, pad_width, separator = _detect_phase_heading_format(content)
            display_num = _format_phase_display_num(new_phase_num, pad_width)
            depends_display = _format_phase_display_num(max_phase, pad_width) if max_phase > 0 else None
            depends = f"Phase {depends_display}" if depends_display else "None"
            phase_entry = (
                f"\n{heading_level} Phase {display_num}{separator}{description}\n\n"
                f"**Goal:** [To be planned]\n"
                f"**Depends on:** {depends}\n"
                f"**Plans:** 0 plans\n\n"
                f"Plans:\n"
                f"- [ ] TBD (run plan-phase {new_phase_num} to break down)\n"
            )

            last_sep = content.rfind("\n---")
            if last_sep > 0:
                updated = content[:last_sep] + phase_entry + content[last_sep:]
            else:
                updated = content + phase_entry

            atomic_write(roadmap_path, updated)
            try:
                # Update STATE.md using the canonical state lock so the markdown
                # write stays coupled to the state.json write path.
                total_phases = roadmap_analyze(cwd).phase_count
                _update_state_markdown_locked(
                    cwd,
                    lambda state_content: _state_content_with_total_phases(
                        state_content,
                        total_phases=total_phases,
                    ),
                )
            except Exception:
                if dir_path.exists():
                    shutil.rmtree(dir_path)
                atomic_write(roadmap_path, content)
                raise

        return PhaseAddResult(
            phase_number=new_phase_num,
            padded=padded,
            name=description,
            slug=slug,
            directory=f"{PLANNING_DIR_NAME}/{PHASES_DIR_NAME}/{dir_name}",
        )


# ─── Phase Insert (Decimal) ───────────────────────────────────────────────────


def phase_insert(cwd: Path, after_phase: str, description: str) -> PhaseInsertResult:
    """Insert a decimal sub-phase after an existing phase.

    E.g., inserting after phase 3 creates phase 3.1 (or 3.2 if 3.1 exists).

    Raises:
        PhaseValidationError: If inputs are invalid or target phase not in ROADMAP.
        RoadmapNotFoundError: If ROADMAP.md doesn't exist.
    """
    if not after_phase or not description:
        raise PhaseValidationError("after_phase and description required for phase insert")

    after_phase = str(after_phase).strip()
    if not re.match(r"^\d+(\.\d+)*$", after_phase):
        raise PhaseValidationError(f'Invalid phase number: "{after_phase}". Must be numeric (e.g., "3" or "3.1")')

    roadmap_path = _roadmap_path(cwd)
    if not roadmap_path.exists():
        raise RoadmapNotFoundError("ROADMAP.md not found")

    slug = generate_slug(description)

    with gpd_span("phases.insert", after_phase=after_phase, description=description):
        with file_lock(roadmap_path):
            content = roadmap_path.read_text(encoding="utf-8")

            after_heading = _find_roadmap_phase_heading(content, after_phase)
            if after_heading is None:
                raise PhaseValidationError(f"Phase {after_phase} not found in ROADMAP.md")

            normalized_base = phase_normalize(after_phase)
            phases_dir = _phases_dir(cwd)
            existing_decimals: list[int] = []

            if phases_dir.is_dir():
                escaped_base = re.escape(normalized_base)
                dec_pattern = re.compile(rf"^{escaped_base}\.(\d+)")
                for d in phases_dir.iterdir():
                    if d.is_dir():
                        dm = dec_pattern.match(d.name)
                        if dm:
                            existing_decimals.append(int(dm.group(1)))

            next_decimal = 1 if not existing_decimals else max(existing_decimals) + 1
            decimal_phase = f"{normalized_base}.{next_decimal}"
            dir_name = f"{decimal_phase}-{slug}" if slug else decimal_phase

            heading_level, pad_width, separator = _detect_phase_heading_format(content)
            display_decimal_phase = _format_phase_display_num(f"{phase_unpad(normalized_base)}.{next_decimal}", pad_width)
            depends_display = _format_phase_display_num(phase_unpad(after_phase), pad_width)
            phase_entry = (
                f"\n{heading_level} Phase {display_decimal_phase}{separator}{description} (INSERTED)\n\n"
                f"**Goal:** [Urgent work - to be planned]\n"
                f"**Depends on:** Phase {depends_display}\n"
                f"**Plans:** 0 plans\n\n"
                f"Plans:\n"
                f"- [ ] TBD (run plan-phase {decimal_phase} to break down)\n"
            )

            _section_start, insert_idx = _roadmap_phase_section_bounds(content, after_heading)

            dir_path = phases_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)

            updated = content[:insert_idx] + phase_entry + content[insert_idx:]
            atomic_write(roadmap_path, updated)
            try:
                # Update STATE.md using the canonical state lock so the
                # markdown write stays coupled to the state.json write path.
                total_phases = roadmap_analyze(cwd).phase_count
                _update_state_markdown_locked(
                    cwd,
                    lambda state_content: _state_content_with_total_phases(
                        state_content,
                        total_phases=total_phases,
                    ),
                )
            except Exception:
                if dir_path.exists():
                    shutil.rmtree(dir_path)
                atomic_write(roadmap_path, content)
                raise

        return PhaseInsertResult(
            phase_number=decimal_phase,
            after_phase=after_phase,
            name=description,
            slug=slug,
            directory=f"{PLANNING_DIR_NAME}/{PHASES_DIR_NAME}/{dir_name}",
        )


# ─── Phase Remove ──────────────────────────────────────────────────────────────


def phase_remove(cwd: Path, target_phase: str, *, force: bool = False) -> PhaseRemoveResult:
    """Remove a phase: update ROADMAP.md, delete directory, renumber subsequent phases.

    For integer phases, renumbers all subsequent phases (8 -> 7, 9 -> 8, etc.).
    For decimal phases, renumbers sibling decimals (3.2 removed -> 3.3 becomes 3.2).

    Raises:
        PhaseValidationError: If phase number is invalid or has executed work without force.
        RoadmapNotFoundError: If ROADMAP.md doesn't exist.
    """
    target_phase = str(target_phase)
    _validate_phase_number(target_phase)

    roadmap_path = _roadmap_path(cwd)
    layout = ProjectLayout(cwd)
    phases_dir = layout.phases_dir

    if not roadmap_path.exists():
        raise RoadmapNotFoundError("ROADMAP.md not found")

    normalized = phase_normalize(target_phase)
    is_decimal = "." in target_phase

    with gpd_span("phases.remove", phase=target_phase, force=force):
        # Find the removed directory subtree.
        target_dirs: list[str] = []
        if phases_dir.is_dir():
            dirs = _list_phase_dirs(cwd)
            target_dirs = [d for d in dirs if _phase_dir_in_subtree(d, normalized)]
        target_dir = next(
            (dir_name for dir_name in target_dirs if phase_normalize(_phase_dir_entry(dir_name)[0]) == normalized),
            None,
        )

        renamed_dirs: list[RenameEntry] = []
        renamed_files: list[RenameEntry] = []

        with file_lock(roadmap_path):
            roadmap_before = roadmap_path.read_text(encoding="utf-8")
            removed_phase_numbers = [
                phase.number for phase in roadmap_analyze(cwd).phases if _phase_in_subtree(phase.number, normalized)
            ]
            if not target_dirs and not removed_phase_numbers:
                raise PhaseNotFoundError(target_phase)

            # Check for executed work (inside lock to avoid TOCTOU race)
            if target_dirs and not force:
                summaries: list[str] = []
                for dir_name in target_dirs:
                    target_path = phases_dir / dir_name
                    summaries.extend(f.name for f in target_path.iterdir() if layout.is_summary_file(f.name))
                if summaries:
                    raise PhaseValidationError(
                        f"Phase {target_phase} has {len(summaries)} executed plan(s). Use force=True to remove anyway."
                    )

            phases_backup_root: Path | None = None
            phases_backup_path: Path | None = None
            try:
                phases_backup_root, phases_backup_path = _backup_directory_tree(phases_dir)

                # Step 1: Update ROADMAP.md
                roadmap_content = roadmap_before
                if not removed_phase_numbers:
                    removed_phase_numbers = [phase_unpad(target_phase)]

                _heading_level, pad_width, _separator = _detect_phase_heading_format(roadmap_content)
                roadmap_content = _remove_roadmap_phase_sections(roadmap_content, removed_phase_numbers)
                roadmap_content = _remove_roadmap_phase_reference_lines(roadmap_content, removed_phase_numbers)
                roadmap_content = _renumber_roadmap_phase_headings(roadmap_content, normalized, pad_width)
                roadmap_content = _renumber_roadmap_phase_references(roadmap_content, normalized, pad_width)

                atomic_write(roadmap_path, roadmap_content)

                # Step 2: Filesystem operations
                for dir_name in target_dirs:
                    shutil.rmtree(phases_dir / dir_name)

                if is_decimal:
                    rd, rf_ = _renumber_decimal_phases(phases_dir, normalized)
                elif phases_dir.is_dir():
                    rd, rf_ = _renumber_integer_phases(phases_dir, int(normalized))
                else:
                    rd, rf_ = [], []
                renamed_dirs = rd
                renamed_files = rf_

                # Step 3: Update STATE.md through the canonical state lock path.
                updated_roadmap = roadmap_analyze(cwd)
                state_updated = _update_state_markdown_locked(
                    cwd,
                    lambda state_content: _phase_remove_state_content(
                        cwd,
                        state_content,
                        target_phase=target_phase,
                        updated_roadmap=updated_roadmap,
                    ),
                )
            except Exception:
                atomic_write(roadmap_path, roadmap_before)
                _restore_directory_tree(phases_dir, phases_backup_path)
                raise
            finally:
                if phases_backup_root is not None and phases_backup_root.exists():
                    shutil.rmtree(phases_backup_root, ignore_errors=True)

        result = PhaseRemoveResult(
            removed=target_phase,
            directory_deleted=target_dir,
            renamed_directories=renamed_dirs,
            renamed_files=renamed_files,
            roadmap_updated=True,
            state_updated=state_updated,
        )

    sync_phase_checkpoints(cwd)
    return result


def _renumber_decimal_phases(phases_dir: Path, normalized: str) -> tuple[list[RenameEntry], list[RenameEntry]]:
    """Renumber later sibling subtrees after removing a decimal phase.

    E.g., removing ``06.2`` shifts ``06.3`` -> ``06.2`` and
    ``06.3.1`` -> ``06.2.1`` while preserving deeper suffixes.
    """
    renamed_dirs: list[RenameEntry] = []
    renamed_files: list[RenameEntry] = []

    if not phases_dir.is_dir():
        return renamed_dirs, renamed_files

    dirs = _list_phase_dirs_raw(phases_dir)
    to_rename: list[dict[str, str]] = []
    for d in dirs:
        try:
            old_prefix, slug = _phase_dir_entry(d)
        except PhaseError:
            continue
        new_prefix = _shift_phase_reference_after_removal(old_prefix, normalized, normalize_output=True)
        if new_prefix == old_prefix:
            continue
        to_rename.append({"dir": d, "old_prefix": old_prefix, "new_prefix": new_prefix, "slug": slug})

    to_rename.sort(key=lambda item: [int(part) for part in phase_unpad(item["old_prefix"]).split(".")])

    # Dry-run validation
    planned_ops: list[tuple[dict[str, str], str]] = []
    for item in to_rename:
        new_dir_name = f"{item['new_prefix']}-{item['slug']}" if item["slug"] else item["new_prefix"]
        src = phases_dir / item["dir"]
        dest = phases_dir / new_dir_name
        if not src.exists():
            raise PhaseError(f'Renumber validation failed: source "{item["dir"]}" does not exist')
        if dest.exists() and not any(t["dir"] == new_dir_name for t in to_rename):
            raise PhaseError(f'Renumber validation failed: destination "{new_dir_name}" already exists')
        planned_ops.append((item, new_dir_name))

    # Execute with rollback tracking
    completed_dir_ops: list[tuple[str, str]] = []
    completed_file_ops: list[tuple[str, str, str]] = []
    try:
        for item, new_dir_name in planned_ops:
            (phases_dir / item["dir"]).rename(phases_dir / new_dir_name)
            completed_dir_ops.append((item["dir"], new_dir_name))
            renamed_dirs.append(RenameEntry(**{"from": item["dir"], "to": new_dir_name}))

            for f in sorted((phases_dir / new_dir_name).iterdir()):
                if f.is_file() and f.name.startswith(item["old_prefix"]):
                    new_file_name = item["new_prefix"] + f.name[len(item["old_prefix"]) :]
                    f.rename(phases_dir / new_dir_name / new_file_name)
                    completed_file_ops.append((new_dir_name, f.name, new_file_name))
                    renamed_files.append(RenameEntry(**{"from": f.name, "to": new_file_name}))
    except Exception:
        for dir_name, old_name, new_name in reversed(completed_file_ops):
            try:
                (phases_dir / dir_name / new_name).rename(phases_dir / dir_name / old_name)
            except OSError as e:
                logger.warning("Rollback failed renaming file %s -> %s: %s", new_name, old_name, e)
        for from_dir, to_dir in reversed(completed_dir_ops):
            try:
                (phases_dir / to_dir).rename(phases_dir / from_dir)
            except OSError as e:
                logger.warning("Rollback failed renaming dir %s -> %s: %s", to_dir, from_dir, e)
        raise

    return renamed_dirs, renamed_files


def _renumber_integer_phases(phases_dir: Path, removed_int: int) -> tuple[list[RenameEntry], list[RenameEntry]]:
    """Renumber subsequent integer phases after removing one.

    E.g., removing phase 5: 06 -> 05, 06.1 -> 05.1, 07 -> 06, etc.
    Sorts ascending so each rename lands on the slot just vacated by the
    previous rename (or the deleted phase), avoiding collisions when
    sibling directories share the same slug.  Validates before executing.
    """
    renamed_dirs: list[RenameEntry] = []
    renamed_files: list[RenameEntry] = []

    if not phases_dir.is_dir():
        return renamed_dirs, renamed_files

    dirs = _list_phase_dirs_raw(phases_dir)

    to_rename = []
    for d in dirs:
        dm = re.match(r"^(\d+)((?:\.\d+)*)-?(.*)$", d)
        if not dm:
            continue
        dir_int = int(dm.group(1))
        if dir_int > removed_int:
            to_rename.append(
                {
                    "dir": d,
                    "old_int": dir_int,
                    "decimal_suffix": dm.group(2) or "",
                    "slug": dm.group(3) or "",
                }
            )

    to_rename.sort(key=lambda x: x["old_int"])

    # Dry-run validation
    planned_ops = []
    for item in to_rename:
        new_int = item["old_int"] - 1
        new_padded = str(new_int).zfill(2)
        old_padded = str(item["old_int"]).zfill(2)
        old_prefix = f"{old_padded}{item['decimal_suffix']}"
        new_prefix = f"{new_padded}{item['decimal_suffix']}"
        new_dir_name = f"{new_prefix}-{item['slug']}" if item["slug"] else new_prefix

        src = phases_dir / item["dir"]
        dest = phases_dir / new_dir_name
        if not src.exists():
            raise PhaseError(f'Renumber validation failed: source "{item["dir"]}" does not exist')
        if dest.exists() and not any(t["dir"] == new_dir_name for t in to_rename):
            raise PhaseError(f'Renumber validation failed: destination "{new_dir_name}" already exists')
        planned_ops.append((item, old_prefix, new_prefix, new_dir_name))

    # Execute with rollback
    completed_dir_ops: list[tuple[str, str]] = []
    completed_file_ops: list[tuple[str, str, str]] = []
    try:
        for item, old_prefix, new_prefix, new_dir_name in planned_ops:
            (phases_dir / item["dir"]).rename(phases_dir / new_dir_name)
            completed_dir_ops.append((item["dir"], new_dir_name))
            renamed_dirs.append(RenameEntry(**{"from": item["dir"], "to": new_dir_name}))

            for f in sorted((phases_dir / new_dir_name).iterdir()):
                if f.is_file() and f.name.startswith(old_prefix):
                    new_file_name = new_prefix + f.name[len(old_prefix) :]
                    f.rename(phases_dir / new_dir_name / new_file_name)
                    completed_file_ops.append((new_dir_name, f.name, new_file_name))
                    renamed_files.append(RenameEntry(**{"from": f.name, "to": new_file_name}))
    except Exception:
        for dir_name, old_name, new_name in reversed(completed_file_ops):
            try:
                (phases_dir / dir_name / new_name).rename(phases_dir / dir_name / old_name)
            except OSError as e:
                logger.warning("Rollback failed renaming file %s -> %s: %s", new_name, old_name, e)
        for from_dir, to_dir in reversed(completed_dir_ops):
            try:
                (phases_dir / to_dir).rename(phases_dir / from_dir)
            except OSError as e:
                logger.warning("Rollback failed renaming dir %s -> %s: %s", to_dir, from_dir, e)
        raise

    return renamed_dirs, renamed_files


# ─── Phase Complete ────────────────────────────────────────────────────────────


def phase_complete(cwd: Path, phase_num: str) -> PhaseCompleteResult:
    """Mark a phase as complete and transition to the next phase.

    Updates ROADMAP.md (checkbox, progress table, plan count) and STATE.md
    (current phase, status, last activity).

    Raises:
        PhaseValidationError: If phase number format is invalid.
        PhaseNotFoundError: If the phase doesn't exist.
        PhaseIncompleteError: If not all plans have summaries.
    """
    phase_num = str(phase_num)
    _validate_phase_number(phase_num)

    roadmap_path = _roadmap_path(cwd)
    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")

    next_phase_num: str | None = None
    next_phase_name: str | None = None
    is_last_phase = True
    plan_count = 0
    summary_count = 0
    state_updated = False

    with gpd_span("phases.complete", phase=phase_num):
        with file_lock(roadmap_path) if roadmap_path.exists() else _null_context():
            phase_info = find_phase(cwd, phase_num)
            if not phase_info:
                raise PhaseNotFoundError(phase_num)
            if not phase_info.plans:
                raise PhaseValidationError(f"Phase {phase_num} has no plans. Run plan-phase {phase_num} first.")

            plan_count = len(phase_info.plans)
            summary_count = matching_phase_artifact_count(phase_info.plans, phase_info.summaries)

            if not is_phase_complete(plan_count, summary_count):
                raise PhaseIncompleteError(phase_num, summary_count, plan_count)

            # Update ROADMAP.md
            roadmap_before = roadmap_path.read_text(encoding="utf-8") if roadmap_path.exists() else None
            if roadmap_path.exists():
                roadmap_content = roadmap_before or ""
                roadmap_content = _mark_roadmap_phase_complete(roadmap_content, phase_num, today)
                roadmap_content = _update_roadmap_phase_table_status(roadmap_content, phase_num, today)
                roadmap_content = _update_roadmap_phase_plan_count(
                    roadmap_content,
                    phase_num,
                    summary_count,
                    plan_count,
                )
                atomic_write(roadmap_path, roadmap_content)

            try:
                # Find next phase from ROADMAP, even if no directory exists yet.
                next_phase = _get_next_roadmap_phase(cwd, phase_num)
                if next_phase is not None:
                    next_phase_num = phase_normalize(next_phase.number)
                    next_phase_name = next_phase.name or None
                    is_last_phase = False

                # Update STATE.md through the canonical state lock path.
                state_updated = _update_state_markdown_locked(
                    cwd,
                    lambda state_content: _phase_complete_state_content(
                        cwd,
                        state_content,
                        phase_num=phase_num,
                        next_phase_num=next_phase_num,
                        next_phase_name=next_phase_name,
                        today=today,
                        is_last_phase=is_last_phase,
                    ),
                )
            except Exception:
                if roadmap_before is not None:
                    atomic_write(roadmap_path, roadmap_before)
                raise

            # sync_phase_checkpoints() already degrades gracefully for malformed
            # or unreadable summaries. Let unexpected render/write failures
            # surface here instead of silently completing the lifecycle step.
            sync_phase_checkpoints(cwd)

        return PhaseCompleteResult(
            completed_phase=phase_num,
            phase_name=phase_info.phase_name,
            plans_executed=f"{summary_count}/{plan_count}",
            all_plans_complete=is_phase_complete(plan_count, summary_count),
            next_phase=next_phase_num,
            next_phase_name=next_phase_name,
            is_last_phase=is_last_phase,
            date=today,
            roadmap_updated=roadmap_path.exists(),
            state_updated=state_updated,
        )


# ─── Milestone Complete ────────────────────────────────────────────────────────


def milestone_complete(cwd: Path, version: str, *, name: str | None = None) -> MilestoneCompleteResult:
    """Complete and archive a milestone.

    Archives ROADMAP.md, REQUIREMENTS.md, and audit files.
    Creates/appends MILESTONES.md. Updates STATE.md.

    Raises:
        PhaseValidationError: If version is empty.
        MilestoneIncompleteError: If not all phases are complete.
    """
    if not version:
        raise PhaseValidationError("version required for milestone complete (e.g., v1.0)")

    roadmap_path = _roadmap_path(cwd)
    req_path = _planning_path(cwd) / REQUIREMENTS_FILENAME
    milestones_path = _planning_path(cwd) / MILESTONES_FILENAME
    archive_dir = _planning_path(cwd) / MILESTONES_DIR_NAME
    phases_dir = _phases_dir(cwd)
    today = datetime.now(tz=UTC).strftime("%Y-%m-%d")
    milestone_name = name or version

    state_updated = False

    with gpd_span("milestone.complete", version=version, milestone=milestone_name):
        # Gather stats from the union of roadmap phases and on-disk phase dirs so
        # milestone completion cannot ignore either unscaffolded roadmap entries
        # or real phase work that exists only on disk.
        total_tasks = 0
        accomplishments: list[str] = []

        completion_snapshot = _milestone_completion_snapshot(cwd)

        for phase_number in completion_snapshot.phase_numbers:
            phase_info = find_phase(cwd, phase_number)
            if phase_info is None:
                continue

            phase_dir = phases_dir / Path(phase_info.directory).name
            for summary_name in phase_info.summaries:
                try:
                    content = (phase_dir / summary_name).read_text(encoding="utf-8")
                    fm = _extract_frontmatter(content)
                except FrontmatterParseError as exc:
                    raise PhaseValidationError(f"{summary_name}: {exc}") from exc
                except (OSError, UnicodeDecodeError) as exc:
                    raise PhaseValidationError(f"{summary_name}: {exc}") from exc

                one_liner = fm.get("one-liner")
                if not one_liner:
                    body_match = re.search(
                        r"^---[\s\S]*?---\s*(?:#[^\n]*\n\s*)?\*\*(.+?)\*\*",
                        content,
                        re.MULTILINE,
                    )
                    if body_match:
                        one_liner = body_match.group(1)
                if one_liner:
                    accomplishments.append(one_liner)

                task_matches = re.findall(r"##\s*Task\s*\d+", content, re.IGNORECASE)
                total_tasks += len(task_matches)

        # Guard: all phases must be complete
        if completion_snapshot.phase_count > 0 and not completion_snapshot.all_phases_complete:
            raise MilestoneIncompleteError(
                completion_snapshot.phase_count - completion_snapshot.completed_phases,
                completion_snapshot.phase_count,
            )

        with file_lock(roadmap_path):
            milestones_before = milestones_path.read_text(encoding="utf-8") if milestones_path.exists() else None
            roadmap_archive_path = archive_dir / f"{version}-ROADMAP.md"
            requirements_archive_path = archive_dir / f"{version}-REQUIREMENTS.md"
            archived_audit_path = archive_dir / f"{version}-MILESTONE-AUDIT.md"
            audit_file = _planning_path(cwd) / f"{version}-MILESTONE-AUDIT.md"
            archive_dir.mkdir(parents=True, exist_ok=True)
            try:
                if roadmap_path.exists():
                    content = roadmap_path.read_text(encoding="utf-8")
                    # Reconcile plan-level checkboxes so the archived roadmap is
                    # self-consistent: "Phase complete" headers must agree with
                    # the plan checklist below them.
                    content = _tick_completed_plan_checkboxes(cwd, content)
                    atomic_write(roadmap_archive_path, content)

                if req_path.exists():
                    req_content = req_path.read_text(encoding="utf-8")
                    archive_header = (
                        f"# Requirements Archive: {version} {milestone_name}\n\n"
                        f"**Archived:** {today}\n"
                        f"**Status:** SHIPPED\n\n"
                        f"For current requirements, see `{PLANNING_DIR_NAME}/REQUIREMENTS.md`.\n\n---\n\n"
                    )
                    atomic_write(requirements_archive_path, archive_header + req_content)

                if audit_file.exists():
                    shutil.move(str(audit_file), str(archived_audit_path))

                acc_list = "\n".join(f"- {a}" for a in accomplishments) if accomplishments else "- (none recorded)"
                audit_line = (
                    f"- `GPD/milestones/{version}-MILESTONE-AUDIT.md`"
                    if archived_audit_path.exists()
                    else "- (audit file is opt-in; run `gpd:audit-milestone` before completion to include one)"
                )
                digest_path = archive_dir / version / "RESEARCH-DIGEST.md"
                digest_line = (
                    f"- `GPD/milestones/{version}/RESEARCH-DIGEST.md`"
                    if digest_path.exists()
                    else "- (no research digest archived for this milestone)"
                )
                evidence_block = (
                    "**Archived evidence:**\n"
                    f"- `GPD/milestones/{version}-ROADMAP.md`\n"
                    f"- `GPD/milestones/{version}-REQUIREMENTS.md`\n"
                    f"{digest_line}\n"
                    f"{audit_line}\n"
                )
                milestone_entry = (
                    f"## {version} {milestone_name} (Shipped: {today})\n\n"
                    f"**Phases completed:** {completion_snapshot.phase_count} phases, {completion_snapshot.total_plans} plans, {total_tasks} tasks\n\n"
                    f"**Key accomplishments:**\n{acc_list}\n\n"
                    f"{evidence_block}\n"
                    f"---\n\n"
                )

                if milestones_path.exists():
                    existing = milestones_path.read_text(encoding="utf-8")
                    atomic_write(milestones_path, _upsert_milestone_entry(existing, version, milestone_entry))
                else:
                    atomic_write(milestones_path, f"# Milestones\n\n{milestone_entry}")

                state_updated = _update_state_markdown_locked(
                    cwd,
                    lambda state_content: _milestone_complete_state_content(
                        state_content,
                        today=today,
                        version=version,
                    ),
                )
            except Exception:
                _restore_text_file(milestones_path, milestones_before)
                if archived_audit_path.exists() and not audit_file.exists():
                    shutil.move(str(archived_audit_path), str(audit_file))
                if roadmap_archive_path.exists():
                    roadmap_archive_path.unlink()
                if requirements_archive_path.exists():
                    requirements_archive_path.unlink()
                if archive_dir.exists() and not any(archive_dir.iterdir()):
                    archive_dir.rmdir()
                raise

            # sync_phase_checkpoints() already handles malformed or unreadable
            # summaries non-fatally. Let unexpected sync failures propagate.
            sync_phase_checkpoints(cwd)

        return MilestoneCompleteResult(
            version=version,
            name=milestone_name,
            date=today,
            phases=completion_snapshot.phase_count,
            plans=completion_snapshot.total_plans,
            tasks=total_tasks,
            accomplishments=accomplishments,
            archived=ArchiveStatus(
                roadmap=(archive_dir / f"{version}-ROADMAP.md").exists(),
                requirements=(archive_dir / f"{version}-REQUIREMENTS.md").exists(),
                audit=(archive_dir / f"{version}-MILESTONE-AUDIT.md").exists(),
            ),
            milestones_updated=True,
            state_updated=state_updated,
        )


# ─── Progress Rendering ───────────────────────────────────────────────────────


def progress_render(cwd: Path, fmt: str = "json") -> ProgressJsonResult | ProgressBarResult | ProgressTableResult:
    """Render project progress in various formats.

    Args:
        cwd: Project root directory.
        fmt: ``"json"`` (structured data), ``"bar"`` (text progress bar),
             or ``"table"`` (markdown table).
    """
    with gpd_span("progress.render", format=fmt):
        layout = ProjectLayout(cwd)
        phases_dir = layout.phases_dir
        milestone = get_milestone_info(cwd)

        phases: list[PhaseProgress] = []
        total_plans = 0
        total_summaries = 0

        if phases_dir.is_dir():
            dirs = _list_phase_dirs(cwd)
            for d in dirs:
                dm = re.match(r"^(\d+(?:\.\d+)*)-?(.*)", d)
                phase_num = dm.group(1) if dm else d
                phase_name = dm.group(2).replace("-", " ") if dm and dm.group(2) else ""

                phase_files = [f.name for f in (phases_dir / d).iterdir() if f.is_file()]
                plans = [f for f in phase_files if f.endswith(PLAN_SUFFIX) or f == STANDALONE_PLAN]
                summaries = [f for f in phase_files if layout.is_summary_file(f)]
                plan_count = len(plans)
                summary_count = matching_phase_artifact_count(plans, summaries)

                total_plans += plan_count
                total_summaries += summary_count

                if plan_count == 0:
                    status = "Pending"
                elif summary_count >= plan_count:
                    status = "Complete"
                elif summary_count > 0:
                    status = "In Progress"
                else:
                    status = "Planned"

                phases.append(
                    PhaseProgress(
                        number=phase_num,
                        name=phase_name,
                        plans=plan_count,
                        summaries=summary_count,
                        status=status,
                    )
                )

        percent = min(100, round(total_summaries / total_plans * 100)) if total_plans > 0 else 0

        if fmt == "table":
            bar_width = 10
            filled = max(0, min(bar_width, round(percent / 100 * bar_width)))
            bar = "\u2588" * filled + "\u2591" * (bar_width - filled)
            rendered = f"# {milestone.version} {milestone.name}\n\n"
            rendered += f"**Progress:** [{bar}] {total_summaries}/{total_plans} plans ({percent}%)\n\n"
            rendered += "| Phase | Name | Plans | Status |\n"
            rendered += "|-------|------|-------|--------|\n"
            for p in phases:
                rendered += f"| {p.number} | {p.name} | {p.summaries}/{p.plans} | {p.status} |\n"
            return ProgressTableResult(rendered=rendered)

        if fmt == "bar":
            bar_width = 20
            filled = max(0, min(bar_width, round(percent / 100 * bar_width)))
            bar = "\u2588" * filled + "\u2591" * (bar_width - filled)
            text = f"[{bar}] {total_summaries}/{total_plans} plans ({percent}%)"
            return ProgressBarResult(bar=text, percent=percent, completed=total_summaries, total=total_plans)

        # Advisory read of state.json to detect divergence (read-only, no lock).
        state_pct: int | None = None
        diverged = False
        progress_warnings: list[str] = []
        try:
            sj = layout.state_json
            if sj.is_file():
                raw = json.loads(sj.read_text(encoding="utf-8"))
                pos = raw.get("position") or {}
                val = pos.get("progress_percent")
                if val is not None:
                    state_pct = int(val)
                    if state_pct != percent:
                        diverged = True
                        progress_warnings.append(
                            f"state.json progress_percent ({state_pct}%) differs from "
                            f"filesystem progress ({percent}%). "
                            f"Run 'gpd state update-progress' to reconcile."
                        )
        except (FileNotFoundError, json.JSONDecodeError, OSError, KeyError, TypeError):
            logger.debug("state.json advisory read failed during progress render", exc_info=True)

        live_execution = _build_progress_live_execution(cwd)

        return ProgressJsonResult(
            milestone_version=milestone.version,
            milestone_name=milestone.name,
            phases=phases,
            total_plans=total_plans,
            total_summaries=total_summaries,
            percent=percent,
            state_progress_percent=state_pct,
            diverged=diverged,
            warnings=progress_warnings,
            live_execution=live_execution,
        )


def _build_progress_live_execution(cwd: Path) -> ProgressLiveExecution | None:
    """Assemble the live-execution block from execution-visibility state."""
    try:
        from gpd.core.observability import derive_execution_visibility
    except ImportError:  # pragma: no cover — defensive
        return None

    try:
        snapshot = derive_execution_visibility(cwd)
    except Exception:  # pragma: no cover — telemetry should never block progress
        logger.debug("derive_execution_visibility failed during progress render", exc_info=True)
        return None

    # Execution prefs: read from GPDProjectConfig.
    strict_wait = False
    never_interrupt = False
    never_auto_close = False
    try:
        from gpd.core.config import load_config

        cfg = load_config(cwd)
        exec_prefs = getattr(cfg, "execution_preferences", None)
        if exec_prefs is not None:
            strict_wait = bool(getattr(exec_prefs, "strict_wait", False))
            never_interrupt = bool(getattr(exec_prefs, "never_interrupt_running_workers", False))
            never_auto_close = bool(getattr(exec_prefs, "never_auto_close_child_agents", False))
    except Exception:  # pragma: no cover
        logger.debug("execution-preferences read failed during progress render", exc_info=True)

    if snapshot is None and not (strict_wait or never_interrupt or never_auto_close):
        return None

    if snapshot is None:
        return ProgressLiveExecution(
            strict_wait=strict_wait,
            never_interrupt_running_workers=never_interrupt,
            never_auto_close_child_agents=never_auto_close,
        )

    wave = snapshot.wave
    return ProgressLiveExecution(
        phase=snapshot.phase,
        plan=snapshot.plan,
        wave=str(wave) if wave is not None else None,
        current_task=snapshot.current_task,
        current_task_index=snapshot.current_task_index,
        current_task_total=snapshot.current_task_total,
        segment_status=snapshot.segment_status,
        waiting_reason=snapshot.waiting_reason_label or snapshot.waiting_reason,
        last_result_label=snapshot.last_result_label,
        last_artifact_path=snapshot.last_artifact_path,
        last_updated_age_label=snapshot.last_updated_age_label,
        strict_wait=strict_wait,
        never_interrupt_running_workers=never_interrupt,
        never_auto_close_child_agents=never_auto_close,
    )
