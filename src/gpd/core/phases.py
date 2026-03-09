"""Phase lifecycle and roadmap management for GPD research projects.

Ported from experiments/get-physics-done/get-physics-done/src/phases.js (2094 lines).
Handles phase discovery, ROADMAP.md parsing, wave validation, dependency graph analysis,
milestone management, and progress rendering.

All public functions are instrumented with Logfire spans via ``gpd_span``.
All return types are Pydantic models — no raw dicts cross module boundaries.
"""

from __future__ import annotations

import logging
import re
import shutil
from contextlib import contextmanager
from datetime import date
from pathlib import Path

import logfire
from pydantic import BaseModel, Field

from gpd.core.constants import (
    PLAN_SUFFIX,
    STANDALONE_PLAN,
    STANDALONE_SUMMARY,
    SUMMARY_SUFFIX,
    VERIFICATION_SUFFIX,
    ProjectLayout,
)
from gpd.core.errors import GPDError
from gpd.core.observability import gpd_span
from gpd.core.utils import (
    atomic_write,
    compare_phase_numbers,
    file_lock,
    generate_slug,
    is_phase_complete,
    phase_normalize,
    phase_unpad,
    safe_parse_int,
    safe_read_file,
)

logger = logging.getLogger(__name__)

__all__ = [
    # Errors
    "PhaseError",
    "PhaseNotFoundError",
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
    """Lazy-load extract_frontmatter from frontmatter module.

    Returns just the metadata dict (discards body). On parse error, returns
    ``{"_parse_error": message}`` for compatibility with callers that check that key.
    """
    from gpd.core.frontmatter import FrontmatterParseError, extract_frontmatter

    try:
        meta, _body = extract_frontmatter(content)
        return meta
    except FrontmatterParseError as exc:
        return {"_parse_error": str(exc)}


def _sync_state_json(cwd: Path, state_content: str) -> None:
    """Lazy-load sync_state_json from state module."""
    from gpd.core.state import sync_state_json

    sync_state_json(cwd, state_content)


# ─── Pydantic Models ──────────────────────────────────────────────────────────


class PhaseInfo(BaseModel):
    """Information about a discovered phase directory."""

    found: bool
    directory: str  # Relative path: .planning/phases/XX-name
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
    autonomous: bool = True
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


class ProgressJsonResult(BaseModel):
    """Progress data in JSON format."""

    milestone_version: str
    milestone_name: str
    phases: list[PhaseProgress] = Field(default_factory=list)
    total_plans_in_phase: int = 0
    total_summaries: int = 0
    percent: int = 0


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


def _strip_suffix(name: str, suffix: str) -> str:
    """Strip a suffix from a string if present; return unchanged otherwise."""
    if name.endswith(suffix):
        return name[: -len(suffix)]
    return name


def _phase_sort_key(name: str) -> list[int]:
    """Sort key for phase directory names based on numeric segments."""
    match = re.match(r"^(\d+(?:\.\d+)*)", name)
    if not match:
        return [0]
    return [int(s) for s in match.group(1).split(".")]


def _sorted_phases(dirs: list[str]) -> list[str]:
    """Sort phase directory names by numeric segments."""
    return sorted(dirs, key=_phase_sort_key)


def _planning_path(cwd: Path) -> Path:
    return ProjectLayout(cwd).planning


def _phases_dir(cwd: Path) -> Path:
    return ProjectLayout(cwd).phases_dir


def _roadmap_path(cwd: Path) -> Path:
    return ProjectLayout(cwd).roadmap


def _state_path(cwd: Path) -> Path:
    return ProjectLayout(cwd).state_md


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


def _ensure_list(value: object) -> list[str]:
    """Coerce a value to a list of strings."""
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


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

    phases_dir = _phases_dir(cwd)
    normalized = phase_normalize(phase)

    if not phases_dir.is_dir():
        return None

    with gpd_span("phases.find", phase=phase):
        dirs = _list_phase_dirs(cwd)

        # Find matching directory
        match_dir: str | None = None
        for d in dirs:
            if d == normalized:
                match_dir = d
                break
            if d.startswith(normalized + "-"):
                match_dir = d
                break
            # Decimal sub-phase match: "03.1" matches "03.1-name" but not "03.10-name"
            if d.startswith(normalized + "."):
                rest = d[len(normalized) + 1 :]
                if re.match(r"^\d+(?:-|$)", rest) and not re.match(r"^\d+\.", rest):
                    match_dir = d
                    break

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
        summaries = sorted(f for f in phase_files if f.endswith(SUMMARY_SUFFIX) or f == STANDALONE_SUMMARY)
        has_research = any(f.endswith("-RESEARCH.md") or f == "RESEARCH.md" for f in phase_files)
        has_context = any(f.endswith("-CONTEXT.md") or f == "CONTEXT.md" for f in phase_files)
        has_verification = any(f.endswith(VERIFICATION_SUFFIX) or f == "VERIFICATION.md" for f in phase_files)
        has_validation = any(f.endswith("-VALIDATION.md") or f == "VALIDATION.md" for f in phase_files)

        # Determine incomplete plans (plans without matching summaries)
        completed_plan_ids = {_strip_suffix(_strip_suffix(s, SUMMARY_SUFFIX), STANDALONE_SUMMARY) for s in summaries}
        incomplete_plans = [
            p for p in plans if _strip_suffix(_strip_suffix(p, PLAN_SUFFIX), STANDALONE_PLAN) not in completed_plan_ids
        ]

        # Build slug
        phase_slug = None
        if phase_name:
            phase_slug = re.sub(r"[^a-z0-9]+", "-", phase_name.lower()).strip("-") or None

        return PhaseInfo(
            found=True,
            directory=f".planning/phases/{match_dir}",
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
        phases_dir = _phases_dir(cwd)
        if not phases_dir.is_dir():
            return PhaseFilesResult()

        dirs = _list_phase_dirs(cwd)

        # Filter to specific phase if requested
        if phase:
            info = find_phase(cwd, phase)
            if not info:
                return PhaseFilesResult(error="Phase not found")
            match_dir = Path(info.directory).name
            dirs = [match_dir]

        files: list[str] = []
        for d in dirs:
            dir_path = phases_dir / d
            dir_files = sorted(f.name for f in dir_path.iterdir() if f.is_file())

            if file_type == "plans":
                filtered = [f for f in dir_files if f.endswith(PLAN_SUFFIX) or f == STANDALONE_PLAN]
            elif file_type == "summaries":
                filtered = [f for f in dir_files if f.endswith(SUMMARY_SUFFIX) or f == STANDALONE_SUMMARY]
            else:
                filtered = dir_files

            files.extend(sorted(filtered))

        phase_dir_name = None
        if phase and dirs:
            phase_dir_name = re.sub(r"^\d+(?:\.\d+)*-?", "", dirs[0])

        return PhaseFilesResult(files=files, count=len(files), phase_dir=phase_dir_name)


# ─── Roadmap Get Phase ─────────────────────────────────────────────────────────


def roadmap_get_phase(cwd: Path, phase_num: str) -> RoadmapPhaseResult:
    """Extract a specific phase section from ROADMAP.md."""
    _validate_phase_number(phase_num)

    with gpd_span("roadmap.get_phase", phase=phase_num):
        roadmap_path = _roadmap_path(cwd)
        content = safe_read_file(roadmap_path)
        if content is None:
            return RoadmapPhaseResult(found=False, error="ROADMAP.md not found")

        escaped_phase = re.escape(str(phase_num))
        phase_pattern = re.compile(rf"###\s*Phase\s+{escaped_phase}:\s*([^\n]+)", re.IGNORECASE)
        header_match = phase_pattern.search(content)

        if not header_match:
            return RoadmapPhaseResult(found=False, phase_number=phase_num)

        phase_name = header_match.group(1).strip()
        header_index = header_match.start()

        rest_of_content = content[header_index:]
        next_header = re.search(r"\n###\s+Phase\s+\d", rest_of_content, re.IGNORECASE)
        section_end = header_index + next_header.start() if next_header else len(content)
        section = content[header_index:section_end].strip()

        goal_match = re.search(r"\*\*Goal:\*\*\s*([^\n]+)", section, re.IGNORECASE)
        goal = goal_match.group(1).strip() if goal_match else None

        return RoadmapPhaseResult(
            found=True,
            phase_number=phase_num,
            phase_name=phase_name,
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

        queue = [pid for pid, deg in in_degree.items() if deg == 0]
        visited = 0
        while queue:
            node = queue.pop(0)
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

        logfire.info(
            "wave_validation_complete",
            valid=len(errors) == 0,
            error_count=len(errors),
            warning_count=len(warnings),
        )
        return WaveValidation(valid=len(errors) == 0, errors=errors, warnings=warnings)


def validate_phase_waves(cwd: Path, phase: str) -> PhaseWaveValidationResult:
    """Validate wave dependencies for a specific phase."""
    normalized = phase_normalize(phase)
    phase_info = find_phase(cwd, phase)

    if not phase_info:
        return PhaseWaveValidationResult(
            phase=normalized,
            error="Phase not found",
            validation=WaveValidation(valid=False, errors=["Phase not found"]),
        )

    with gpd_span("phases.validate_waves", phase=normalized):
        phase_dir = cwd / phase_info.directory

        plans: list[PlanEntry] = []
        for plan_file in phase_info.plans:
            plan_id = _strip_suffix(_strip_suffix(plan_file, PLAN_SUFFIX), STANDALONE_PLAN)
            content = (phase_dir / plan_file).read_text(encoding="utf-8")
            fm = _extract_frontmatter(content)
            if fm.get("_parse_error"):
                continue

            wave = safe_parse_int(fm.get("wave"), 1)
            files_modified = _ensure_list(fm.get("files_modified") or fm.get("files-modified"))
            depends_on = _ensure_list(fm.get("depends_on") or fm.get("depends-on"))

            plans.append(PlanEntry(id=plan_id, wave=wave, depends_on=depends_on, files_modified=files_modified))

        validation = validate_waves(plans)
        return PhaseWaveValidationResult(phase=normalized, validation=validation)


# ─── Phase Plan Index ──────────────────────────────────────────────────────────


def phase_plan_index(cwd: Path, phase: str) -> PhasePlanIndex:
    """Build an index of plans in a phase with wave grouping and validation."""
    normalized = phase_normalize(phase)
    phase_info = find_phase(cwd, phase)

    if not phase_info:
        return PhasePlanIndex(phase=normalized)

    with gpd_span("phases.plan_index", phase=normalized):
        phase_dir = cwd / phase_info.directory

        completed_plan_ids = {
            _strip_suffix(_strip_suffix(s, SUMMARY_SUFFIX), STANDALONE_SUMMARY) for s in phase_info.summaries
        }

        plans: list[PlanEntry] = []
        waves: dict[str, list[str]] = {}
        incomplete: list[str] = []
        has_checkpoints = False

        for plan_file in phase_info.plans:
            plan_id = _strip_suffix(_strip_suffix(plan_file, PLAN_SUFFIX), STANDALONE_PLAN)
            content = (phase_dir / plan_file).read_text(encoding="utf-8")
            fm = _extract_frontmatter(content)
            if fm.get("_parse_error"):
                continue

            task_count = len(re.findall(r"##\s*Task\s*\d+", content, re.IGNORECASE))
            wave = safe_parse_int(fm.get("wave"), 1)

            autonomous = True
            if "autonomous" in fm:
                autonomous = fm["autonomous"] in (True, "true")

            if not autonomous:
                has_checkpoints = True

            files_modified = _ensure_list(fm.get("files_modified") or fm.get("files-modified"))
            depends_on = _ensure_list(fm.get("depends_on") or fm.get("depends-on"))

            has_summary = plan_id in completed_plan_ids
            if not has_summary:
                incomplete.append(plan_id)

            entry = PlanEntry(
                id=plan_id,
                wave=wave,
                autonomous=autonomous,
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
        phases_dir = _phases_dir(cwd)

        # Read phase directories once
        phase_dir_names: list[str] = []
        if phases_dir.is_dir():
            phase_dir_names = [d.name for d in phases_dir.iterdir() if d.is_dir()]

        # Extract all phase headings
        phase_pattern = re.compile(r"###\s*Phase\s+(\d+(?:\.\d+)*)\s*:\s*([^\n]+)", re.IGNORECASE)
        phases: list[RoadmapPhase] = []

        for match in phase_pattern.finditer(content):
            phase_num = match.group(1)
            phase_name = re.sub(r"\(INSERTED\)", "", match.group(2), flags=re.IGNORECASE).strip()

            # Extract section text
            section_start = match.start()
            rest = content[section_start:]
            next_header = re.search(r"\n###\s+Phase\s+\d", rest, re.IGNORECASE)
            section_end = section_start + next_header.start() if next_header else len(content)
            section = content[section_start:section_end]

            goal_match = re.search(r"\*\*Goal:\*\*\s*([^\n]+)", section, re.IGNORECASE)
            goal = goal_match.group(1).strip() if goal_match else None

            depends_match = re.search(r"\*\*Depends on:\*\*\s*([^\n]+)", section, re.IGNORECASE)
            depends_on = depends_match.group(1).strip() if depends_match else None

            # Check disk status
            normalized = phase_normalize(phase_num)
            disk_status = "no_directory"
            plan_count = 0
            summary_count = 0
            has_context = False
            has_research = False

            dir_match_name = next(
                (d for d in phase_dir_names if d.startswith(normalized + "-") or d == normalized),
                None,
            )

            if dir_match_name:
                phase_files = [f.name for f in (phases_dir / dir_match_name).iterdir() if f.is_file()]
                plan_count = sum(1 for f in phase_files if f.endswith(PLAN_SUFFIX) or f == STANDALONE_PLAN)
                summary_count = sum(1 for f in phase_files if f.endswith(SUMMARY_SUFFIX) or f == STANDALONE_SUMMARY)
                has_context = any(f.endswith("-CONTEXT.md") or f == "CONTEXT.md" for f in phase_files)
                has_research = any(f.endswith("-RESEARCH.md") or f == "RESEARCH.md" for f in phase_files)

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
            escaped_num = re.escape(phase_num)
            checkbox_pattern = re.compile(rf"-\s*\[(x| )\]\s*.*Phase\s+{escaped_num}", re.IGNORECASE)
            checkbox_match = checkbox_pattern.search(content)
            roadmap_complete = checkbox_match is not None and checkbox_match.group(1) == "x"

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
        next_phase = next(
            (p for p in phases if p.disk_status in ("empty", "no_directory", "discussed", "researched")),
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
            progress_percent=round(total_summaries / total_plans * 100) if total_plans > 0 else 0,
            current_phase=current_phase.number if current_phase else None,
            next_phase=next_phase.number if next_phase else None,
        )


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
            for m in re.finditer(r"###\s*Phase\s+(\d+)(?:\.\d+)?:", content, re.IGNORECASE):
                num = int(m.group(1))
                if num > max_phase:
                    max_phase = num

            new_phase_num = max_phase + 1
            padded = str(new_phase_num).zfill(2)
            dir_name = f"{padded}-{slug}"
            dir_path = _phases_dir(cwd) / dir_name

            dir_path.mkdir(parents=True, exist_ok=True)

            phase_entry = (
                f"\n### Phase {new_phase_num}: {description}\n\n"
                f"**Goal:** [To be planned]\n"
                f"**Depends on:** Phase {max_phase}\n"
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

        return PhaseAddResult(
            phase_number=new_phase_num,
            padded=padded,
            name=description,
            slug=slug,
            directory=f".planning/phases/{dir_name}",
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

            escaped = re.escape(after_phase)
            if not re.search(rf"###\s*Phase\s+{escaped}:", content, re.IGNORECASE):
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
            dir_name = f"{decimal_phase}-{slug}"

            phase_entry = (
                f"\n### Phase {decimal_phase}: {description} (INSERTED)\n\n"
                f"**Goal:** [Urgent work - to be planned]\n"
                f"**Depends on:** Phase {after_phase}\n"
                f"**Plans:** 0 plans\n\n"
                f"Plans:\n"
                f"- [ ] TBD (run plan-phase {decimal_phase} to break down)\n"
            )

            header_pattern = re.compile(rf"(###\s*Phase\s+{escaped}:[^\n]*\n)", re.IGNORECASE)
            header_match = header_pattern.search(content)
            if not header_match:
                raise PhaseValidationError(f"Could not find Phase {after_phase} header")

            header_idx = content.index(header_match.group(0))
            after_header = content[header_idx + len(header_match.group(0)) :]
            next_phase_match = re.search(r"\n###\s+Phase\s+\d", after_header, re.IGNORECASE)

            if next_phase_match:
                insert_idx = header_idx + len(header_match.group(0)) + next_phase_match.start()
            else:
                insert_idx = len(content)

            dir_path = phases_dir / dir_name
            dir_path.mkdir(parents=True, exist_ok=True)

            updated = content[:insert_idx] + phase_entry + content[insert_idx:]
            atomic_write(roadmap_path, updated)

        return PhaseInsertResult(
            phase_number=decimal_phase,
            after_phase=after_phase,
            name=description,
            slug=slug,
            directory=f".planning/phases/{dir_name}",
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
    phases_dir = _phases_dir(cwd)

    if not roadmap_path.exists():
        raise RoadmapNotFoundError("ROADMAP.md not found")

    normalized = phase_normalize(target_phase)
    is_decimal = "." in target_phase

    with gpd_span("phases.remove", phase=target_phase, force=force):
        # Find target directory
        target_dir: str | None = None
        if phases_dir.is_dir():
            dirs = _list_phase_dirs(cwd)
            target_dir = next(
                (d for d in dirs if d.startswith(normalized + "-") or d == normalized),
                None,
            )

        # Check for executed work
        if target_dir and not force:
            target_path = phases_dir / target_dir
            summaries = [
                f.name for f in target_path.iterdir() if f.name.endswith(SUMMARY_SUFFIX) or f.name == STANDALONE_SUMMARY
            ]
            if summaries:
                raise PhaseValidationError(
                    f"Phase {target_phase} has {len(summaries)} executed plan(s). Use force=True to remove anyway."
                )

        renamed_dirs: list[RenameEntry] = []
        renamed_files: list[RenameEntry] = []

        with file_lock(roadmap_path):
            # Step 1: Update ROADMAP.md
            roadmap_content = roadmap_path.read_text(encoding="utf-8")
            roadmap_phase_num = phase_unpad(target_phase)
            target_escaped = re.escape(roadmap_phase_num)

            # Remove phase section
            section_pattern = re.compile(
                rf"\n?###\s*Phase\s+{target_escaped}\s*:[\s\S]*?(?=\n###\s+Phase\s+\d|$)",
                re.IGNORECASE,
            )
            roadmap_content = section_pattern.sub("", roadmap_content)

            # Remove checkbox
            checkbox_pattern = re.compile(
                rf"\n?-\s*\[[ x]\]\s*.*Phase\s+{target_escaped}[:\s][^\n]*",
                re.IGNORECASE,
            )
            roadmap_content = checkbox_pattern.sub("", roadmap_content)

            # Remove table row
            table_pattern = re.compile(
                rf"\n?\|\s*{target_escaped}\.?\s[^|]*\|[^\n]*",
                re.IGNORECASE,
            )
            roadmap_content = table_pattern.sub("", roadmap_content)

            # Renumber ROADMAP references for integer removal
            if not is_decimal:
                removed_int = int(normalized)
                max_phase = removed_int
                if phases_dir.is_dir():
                    for entry in phases_dir.iterdir():
                        if entry.is_dir():
                            dm = re.match(r"^(\d+)", entry.name)
                            if dm:
                                max_phase = max(max_phase, int(dm.group(1)))

                for old_num in range(removed_int + 1, max_phase + 1):
                    new_num = old_num - 1
                    old_str = str(old_num)
                    new_str = str(new_num)
                    old_pad = old_str.zfill(2)
                    new_pad = new_str.zfill(2)

                    roadmap_content = re.sub(
                        rf"(###\s*Phase\s+){old_str}(\s*:)",
                        rf"\g<1>{new_str}\2",
                        roadmap_content,
                        flags=re.IGNORECASE,
                    )
                    roadmap_content = re.sub(
                        rf"(^\s*-\s*\[[ x]\]\s*(?:\*\*)?Phase\s+){old_str}([:\s])",
                        rf"\g<1>{new_str}\2",
                        roadmap_content,
                        flags=re.MULTILINE,
                    )
                    roadmap_content = re.sub(
                        rf"(Depends on:\*\*\s*Phase\s+){old_str}\b",
                        rf"\g<1>{new_str}",
                        roadmap_content,
                        flags=re.IGNORECASE,
                    )
                    roadmap_content = re.sub(
                        rf"(?<![\d-]){old_pad}-(\d{{2}})\b",
                        rf"{new_pad}-\1",
                        roadmap_content,
                    )
                    roadmap_content = re.sub(
                        rf"(\|\s*){old_str}\.\s",
                        rf"\g<1>{new_str}. ",
                        roadmap_content,
                    )

            atomic_write(roadmap_path, roadmap_content)

            # Step 2: Filesystem operations
            if target_dir:
                shutil.rmtree(phases_dir / target_dir)

            if is_decimal:
                rd, rf_ = _renumber_decimal_phases(phases_dir, normalized)
            elif phases_dir.is_dir():
                rd, rf_ = _renumber_integer_phases(phases_dir, int(normalized))
            else:
                rd, rf_ = [], []
            renamed_dirs = rd
            renamed_files = rf_

            # Step 3: Update STATE.md
            state_path = _state_path(cwd)
            if state_path.exists():
                with file_lock(state_path):
                    state_content = state_path.read_text(encoding="utf-8")

                    total_match = re.search(r"(\*\*Total Phases:\*\*\s*)(\d+)", state_content)
                    if total_match:
                        old_total = int(total_match.group(2))
                        state_content = re.sub(
                            r"(\*\*Total Phases:\*\*\s*)\d+",
                            rf"\g<1>{old_total - 1}",
                            state_content,
                        )

                    of_match = re.search(r"(\bof\s+)(\d+)(\s*(?:\(|phases?))", state_content, re.IGNORECASE)
                    if of_match:
                        old_total = int(of_match.group(2))
                        state_content = re.sub(
                            r"(\bof\s+)\d+(\s*(?:\(|phases?))",
                            rf"\g<1>{old_total - 1}\2",
                            state_content,
                            flags=re.IGNORECASE,
                        )

                    atomic_write(state_path, state_content)
                    _sync_state_json(cwd, state_content)

        return PhaseRemoveResult(
            removed=target_phase,
            directory_deleted=target_dir,
            renamed_directories=renamed_dirs,
            renamed_files=renamed_files,
            roadmap_updated=True,
            state_updated=state_path.exists(),
        )


def _renumber_decimal_phases(phases_dir: Path, normalized: str) -> tuple[list[RenameEntry], list[RenameEntry]]:
    """Renumber sibling decimal phases after removing one.

    E.g., removing 06.2: 06.3 -> 06.2, 06.4 -> 06.3.
    Sorts descending to avoid conflicts. Validates before executing.
    """
    renamed_dirs: list[RenameEntry] = []
    renamed_files: list[RenameEntry] = []

    if not phases_dir.is_dir():
        return renamed_dirs, renamed_files

    base_parts = normalized.split(".")
    base_int = base_parts[0]
    removed_decimal = int(base_parts[1])

    dirs = _list_phase_dirs_raw(phases_dir)
    dec_pattern = re.compile(rf"^{re.escape(base_int)}\.(\d+)-?(.*)$")

    to_rename = []
    for d in dirs:
        dm = dec_pattern.match(d)
        if dm and int(dm.group(1)) > removed_decimal:
            to_rename.append(
                {
                    "dir": d,
                    "old_decimal": int(dm.group(1)),
                    "slug": dm.group(2) or "",
                }
            )

    to_rename.sort(key=lambda x: x["old_decimal"], reverse=True)

    # Dry-run validation
    planned_ops = []
    for item in to_rename:
        new_decimal = item["old_decimal"] - 1
        new_dir_name = f"{base_int}.{new_decimal}-{item['slug']}" if item["slug"] else f"{base_int}.{new_decimal}"
        src = phases_dir / item["dir"]
        dest = phases_dir / new_dir_name
        if not src.exists():
            raise PhaseError(f'Renumber validation failed: source "{item["dir"]}" does not exist')
        if dest.exists() and not any(t["dir"] == new_dir_name for t in to_rename):
            raise PhaseError(f'Renumber validation failed: destination "{new_dir_name}" already exists')
        planned_ops.append((item, new_decimal, new_dir_name))

    # Execute with rollback tracking
    completed_dir_ops: list[tuple[str, str]] = []
    completed_file_ops: list[tuple[str, str, str]] = []
    try:
        for item, new_decimal, new_dir_name in planned_ops:
            old_phase_id = f"{base_int}.{item['old_decimal']}"
            new_phase_id = f"{base_int}.{new_decimal}"

            (phases_dir / item["dir"]).rename(phases_dir / new_dir_name)
            completed_dir_ops.append((item["dir"], new_dir_name))
            renamed_dirs.append(RenameEntry(**{"from": item["dir"], "to": new_dir_name}))

            for f in sorted((phases_dir / new_dir_name).iterdir()):
                if f.is_file() and f.name.startswith(old_phase_id):
                    new_file_name = new_phase_id + f.name[len(old_phase_id) :]
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
    Sorts descending to avoid naming conflicts. Validates before executing.
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

    to_rename.sort(key=lambda x: x["old_int"], reverse=True)

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
    state_path = _state_path(cwd)
    phases_dir = _phases_dir(cwd)
    unpadded = phase_unpad(phase_num)
    today = date.today().isoformat()

    next_phase_num: str | None = None
    next_phase_name: str | None = None
    is_last_phase = True
    plan_count = 0
    summary_count = 0

    with gpd_span("phases.complete", phase=phase_num):
        with file_lock(roadmap_path) if roadmap_path.exists() else _null_context():
            phase_info = find_phase(cwd, phase_num)
            if not phase_info:
                raise PhaseNotFoundError(phase_num)
            if not phase_info.plans:
                raise PhaseValidationError(f"Phase {phase_num} has no plans. Run plan-phase {phase_num} first.")

            plan_count = len(phase_info.plans)
            summary_count = len(phase_info.summaries)

            if not is_phase_complete(plan_count, summary_count):
                raise PhaseIncompleteError(phase_num, summary_count, plan_count)

            # Update ROADMAP.md
            if roadmap_path.exists():
                roadmap_content = roadmap_path.read_text(encoding="utf-8")
                roadmap_phase = phase_unpad(phase_num)
                roadmap_escaped = re.escape(roadmap_phase)
                unpadded_escaped = re.escape(unpadded)

                roadmap_content = re.sub(
                    rf"(-\s*\[) (\]\s*.*Phase\s+{unpadded_escaped}[:\s][^\n]*)",
                    rf"\g<1>x\2 (completed {today})",
                    roadmap_content,
                    flags=re.IGNORECASE,
                )
                roadmap_content = re.sub(
                    rf"(\|\s*{roadmap_escaped}\.?\s[^|]*\|[^|]*\|)\s*[^|]*(\|)\s*[^|]*(\|)",
                    rf"\1 Complete    \2 {today} \3",
                    roadmap_content,
                    flags=re.IGNORECASE,
                )
                roadmap_content = re.sub(
                    rf"(###\s*Phase\s+{roadmap_escaped}[\s\S]*?\*\*Plans:\*\*\s*)[^\n]+",
                    rf"\g<1>{summary_count}/{plan_count} plans complete",
                    roadmap_content,
                    flags=re.IGNORECASE,
                )
                atomic_write(roadmap_path, roadmap_content)

            # Find next phase
            if phases_dir.is_dir():
                dirs = _list_phase_dirs(cwd)
                for d in dirs:
                    dm = re.match(r"^(\d+(?:\.\d+)*)-?(.*)", d)
                    if dm and compare_phase_numbers(dm.group(1), phase_num) > 0:
                        next_phase_num = dm.group(1)
                        next_phase_name = dm.group(2) or None
                        is_last_phase = False
                        break

            # Update STATE.md
            if state_path.exists():
                with file_lock(state_path):
                    state_content = state_path.read_text(encoding="utf-8")

                    state_content = re.sub(
                        r"(\*\*Current Phase:\*\*\s*).*",
                        rf"\g<1>{next_phase_num or phase_num}",
                        state_content,
                    )

                    if next_phase_name:
                        state_content = re.sub(
                            r"(\*\*Current Phase Name:\*\*\s*).*",
                            rf"\g<1>{next_phase_name.replace('-', ' ')}",
                            state_content,
                        )

                    state_content = re.sub(
                        r"(\*\*Status:\*\*\s*).*",
                        rf"\g<1>{'Milestone complete' if is_last_phase else 'Ready to plan'}",
                        state_content,
                    )

                    state_content = re.sub(
                        r"(\*\*Current Plan:\*\*\s*).*",
                        r"\g<1>Not started",
                        state_content,
                    )

                    em_dash = "\u2014"
                    if next_phase_num:
                        next_info = find_phase(cwd, next_phase_num)
                        next_plan_count = len(next_info.plans) if next_info else 0
                        replacement = str(next_plan_count) if next_plan_count else em_dash
                        state_content = re.sub(
                            r"(\*\*Total Plans in Phase:\*\*\s*).*",
                            rf"\g<1>{replacement}",
                            state_content,
                        )
                    else:
                        state_content = re.sub(
                            r"(\*\*Total Plans in Phase:\*\*\s*).*",
                            rf"\g<1>{em_dash}",
                            state_content,
                        )

                    state_content = re.sub(
                        r"(\*\*Last Activity:\*\*\s*).*",
                        rf"\g<1>{today}",
                        state_content,
                    )

                    transition_msg = f"Phase {phase_num} complete"
                    if next_phase_num:
                        transition_msg += f", transitioned to Phase {next_phase_num}"
                    state_content = re.sub(
                        r"(\*\*Last Activity Description:\*\*\s*).*",
                        rf"\g<1>{transition_msg}",
                        state_content,
                    )

                    atomic_write(state_path, state_content)
                    _sync_state_json(cwd, state_content)

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
            state_updated=state_path.exists(),
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
    req_path = _planning_path(cwd) / "REQUIREMENTS.md"
    state_path = _state_path(cwd)
    milestones_path = _planning_path(cwd) / "MILESTONES.md"
    archive_dir = _planning_path(cwd) / "milestones"
    phases_dir = _phases_dir(cwd)
    today = date.today().isoformat()
    milestone_name = name or version

    archive_dir.mkdir(parents=True, exist_ok=True)

    with gpd_span("milestone.complete", version=version, milestone=milestone_name):
        # Gather stats from phases
        phase_count = 0
        completed_phase_count = 0
        total_plans = 0
        total_tasks = 0
        accomplishments: list[str] = []

        if phases_dir.is_dir():
            dirs = _list_phase_dirs(cwd)
            for d in dirs:
                phase_count += 1
                phase_files = list((phases_dir / d).iterdir())
                file_names = [f.name for f in phase_files if f.is_file()]
                plans = [f for f in file_names if f.endswith(PLAN_SUFFIX) or f == STANDALONE_PLAN]
                summaries_list = [f for f in file_names if f.endswith(SUMMARY_SUFFIX) or f == STANDALONE_SUMMARY]
                total_plans += len(plans)
                if is_phase_complete(len(plans), len(summaries_list)):
                    completed_phase_count += 1

                for s in summaries_list:
                    content = (phases_dir / d / s).read_text(encoding="utf-8")
                    fm = _extract_frontmatter(content)
                    if fm.get("_parse_error"):
                        continue

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
        if phase_count > 0 and completed_phase_count < phase_count:
            raise MilestoneIncompleteError(phase_count - completed_phase_count, phase_count)

        with file_lock(roadmap_path):
            if roadmap_path.exists():
                content = roadmap_path.read_text(encoding="utf-8")
                atomic_write(archive_dir / f"{version}-ROADMAP.md", content)

            if req_path.exists():
                req_content = req_path.read_text(encoding="utf-8")
                archive_header = (
                    f"# Requirements Archive: {version} {milestone_name}\n\n"
                    f"**Archived:** {today}\n"
                    f"**Status:** SHIPPED\n\n"
                    f"For current requirements, see `.planning/REQUIREMENTS.md`.\n\n---\n\n"
                )
                atomic_write(archive_dir / f"{version}-REQUIREMENTS.md", archive_header + req_content)

            audit_file = _planning_path(cwd) / f"{version}-MILESTONE-AUDIT.md"
            if audit_file.exists():
                shutil.move(str(audit_file), str(archive_dir / f"{version}-MILESTONE-AUDIT.md"))

            acc_list = "\n".join(f"- {a}" for a in accomplishments) if accomplishments else "- (none recorded)"
            milestone_entry = (
                f"## {version} {milestone_name} (Shipped: {today})\n\n"
                f"**Phases completed:** {phase_count} phases, {total_plans} plans, {total_tasks} tasks\n\n"
                f"**Key accomplishments:**\n{acc_list}\n\n---\n\n"
            )

            if milestones_path.exists():
                existing = milestones_path.read_text(encoding="utf-8")
                atomic_write(milestones_path, existing + "\n" + milestone_entry)
            else:
                atomic_write(milestones_path, f"# Milestones\n\n{milestone_entry}")

            if state_path.exists():
                with file_lock(state_path):
                    state_content = state_path.read_text(encoding="utf-8")
                    state_content = re.sub(
                        r"(\*\*Status:\*\*\s*).*",
                        rf"\g<1>{version} milestone complete",
                        state_content,
                    )
                    state_content = re.sub(
                        r"(\*\*Last Activity:\*\*\s*).*",
                        rf"\g<1>{today}",
                        state_content,
                    )
                    state_content = re.sub(
                        r"(\*\*Last Activity Description:\*\*\s*).*",
                        rf"\g<1>{version} milestone completed and archived",
                        state_content,
                    )
                    atomic_write(state_path, state_content)
                    _sync_state_json(cwd, state_content)

        return MilestoneCompleteResult(
            version=version,
            name=milestone_name,
            date=today,
            phases=phase_count,
            plans=total_plans,
            tasks=total_tasks,
            accomplishments=accomplishments,
            archived=ArchiveStatus(
                roadmap=(archive_dir / f"{version}-ROADMAP.md").exists(),
                requirements=(archive_dir / f"{version}-REQUIREMENTS.md").exists(),
                audit=(archive_dir / f"{version}-MILESTONE-AUDIT.md").exists(),
            ),
            milestones_updated=True,
            state_updated=state_path.exists(),
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
        phases_dir = _phases_dir(cwd)
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
                plan_count = sum(1 for f in phase_files if f.endswith(PLAN_SUFFIX) or f == STANDALONE_PLAN)
                summary_count = sum(1 for f in phase_files if f.endswith(SUMMARY_SUFFIX) or f == STANDALONE_SUMMARY)

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

        percent = round(total_summaries / total_plans * 100) if total_plans > 0 else 0

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

        return ProgressJsonResult(
            milestone_version=milestone.version,
            milestone_name=milestone.name,
            phases=phases,
            total_plans_in_phase=total_plans,
            total_summaries=total_summaries,
            percent=percent,
        )
