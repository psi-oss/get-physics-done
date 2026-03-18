"""Centralized constants for the GPD package.

All filesystem names, file suffixes, environment variable names, and
structural constants live here. Every module that needs the project
metadata directory name, a file suffix, or an env var MUST import from this module
instead of using hardcoded string literals.

Layer 1 code: no external imports beyond stdlib.
"""

from __future__ import annotations

from pathlib import Path

__all__ = [
    "ACTIVE_TRACE_FILENAME",
    "ANALYSIS_DIR_NAME",
    "AGENT_ID_FILENAME",
    "CHECKPOINTS_FILENAME",
    "CONFIG_FILENAME",
    "CONTEXT_SUFFIX",
    "CONVENTIONS_FILENAME",
    "DECISION_THRESHOLD",
    "DEFAULT_MAX_INCLUDE_CHARS",
    "ENV_DATA_DIR",
    "ENV_GPD_ACTIVE_RUNTIME",
    "ENV_GPD_DISABLE_CHECKOUT_REEXEC",
    "ENV_GPD_DEBUG",
    "ENV_MAX_INCLUDE_CHARS",
    "ENV_PATTERNS_ROOT",
    "LITERATURE_DIR_NAME",
    "MILESTONES_DIR_NAME",
    "MILESTONES_FILENAME",
    "MIN_PYTHON_MAJOR",
    "MIN_PYTHON_MINOR",
    "OPTIONAL_PLANNING_FILES",
    "OBSERVABILITY_CURRENT_SESSION_FILENAME",
    "OBSERVABILITY_DIR_NAME",
    "OBSERVABILITY_SESSIONS_DIR_NAME",
    "PATTERNS_BY_DOMAIN_DIR",
    "PATTERNS_DIR_NAME",
    "PATTERNS_INDEX_FILENAME",
    "PHASES_DIR_NAME",
    "PHASE_CHECKPOINTS_DIR_NAME",
    "PLANNING_DIR_NAME",
    "PLAN_SUFFIX",
    "PROJECT_FILENAME",
    "ProjectLayout",
    "RECOMMENDED_PYTHON_VERSION",
    "REQUIRED_PLANNING_DIRS",
    "REQUIRED_PLANNING_FILES",
    "REQUIRED_RETURN_FIELDS",
    "REQUIRED_SPECS_SUBDIRS",
    "REQUIREMENTS_FILENAME",
    "RESEARCH_MAP_DIR_NAME",
    "RESEARCH_SUFFIX",
    "ROADMAP_FILENAME",
    "SCRATCH_DIR_NAME",
    "SEED_PATTERN_INITIAL_OCCURRENCES",
    "SPECS_REFERENCES_DIR",
    "SPECS_TEMPLATES_DIR",
    "SPECS_WORKFLOWS_DIR",
    "STANDALONE_CONTEXT",
    "STANDALONE_PLAN",
    "STANDALONE_RESEARCH",
    "STANDALONE_SUMMARY",
    "STANDALONE_VALIDATION",
    "STANDALONE_VERIFICATION",
    "STATE_ARCHIVE_FILENAME",
    "STATE_JSON_BACKUP_FILENAME",
    "STATE_JSON_FILENAME",
    "STATE_LINES_BUDGET",
    "STATE_LINES_TARGET",
    "STATE_MD_FILENAME",
    "STATE_WRITE_INTENT_FILENAME",
    "SUMMARY_SUFFIX",
    "TODOS_DIR_NAME",
    "TRACES_DIR_NAME",
    "UNCOMMITTED_FILES_THRESHOLD",
    "VALID_RETURN_STATUSES",
    "VALIDATION_SUFFIX",
    "VERIFICATION_SUFFIX",
]

# ─── Planning Directory Layout ────────────────────────────────────────────────
# These define the on-disk layout of a GPD project's .gpd/ directory.

PLANNING_DIR_NAME = ".gpd"
"""Top-level GPD metadata directory inside a project root."""

STATE_JSON_FILENAME = "state.json"
"""Machine-readable authoritative state file."""

STATE_MD_FILENAME = "STATE.md"
"""Human-readable, editable state file kept in sync with state.json."""

ROADMAP_FILENAME = "ROADMAP.md"
"""Phase-level research roadmap."""

PROJECT_FILENAME = "PROJECT.md"
"""High-level project description and goals."""

CONFIG_FILENAME = "config.json"
"""Project configuration (model profiles, workflow toggles, etc.)."""

CONVENTIONS_FILENAME = "CONVENTIONS.md"
"""Human-readable convention documentation."""

REQUIREMENTS_FILENAME = "REQUIREMENTS.md"
"""Project requirements document."""

MILESTONES_FILENAME = "MILESTONES.md"
"""Milestone tracking document."""

CHECKPOINTS_FILENAME = "CHECKPOINTS.md"
"""Root-level human-facing checkpoint index."""

AGENT_ID_FILENAME = "current-agent-id.txt"
"""File storing the current agent's identifier for resume detection."""

PHASES_DIR_NAME = "phases"
"""Subdirectory under .gpd/ containing per-phase directories."""

PHASE_CHECKPOINTS_DIR_NAME = "phase-checkpoints"
"""Root-level generated checkpoint shelf with one document per phase."""

ANALYSIS_DIR_NAME = "analysis"
"""Subdirectory under .gpd/ for internal analysis/provenance reports."""

TRACES_DIR_NAME = "traces"
"""Subdirectory under .gpd/ for execution trace JSONL files."""

OBSERVABILITY_DIR_NAME = "observability"
"""Subdirectory under .gpd/ for local session/event observability logs."""

OBSERVABILITY_SESSIONS_DIR_NAME = "sessions"
"""Subdirectory under observability/ containing per-session event streams."""

OBSERVABILITY_CURRENT_SESSION_FILENAME = "current-session.json"
"""Pointer to the most recent active local observability session."""

OBSERVABILITY_CURRENT_EXECUTION_FILENAME = "current-execution.json"
"""Pointer to the latest active or resumable execution-state snapshot."""

MILESTONES_DIR_NAME = "milestones"
"""Subdirectory under .gpd/ for archived milestone snapshots."""

TODOS_DIR_NAME = "todos"
"""Subdirectory under .gpd/ for todo items."""

LITERATURE_DIR_NAME = "literature"
"""Subdirectory under .gpd/ for literature review files."""

RESEARCH_MAP_DIR_NAME = "research-map"
"""Subdirectory under .gpd/ for theory/research map files."""

SCRATCH_DIR_NAME = "tmp"
"""Subdirectory under .gpd/ for transient scratch files."""

ACTIVE_TRACE_FILENAME = ".active-trace"
"""Marker file in traces/ indicating the currently recording trace."""

STATE_ARCHIVE_FILENAME = "STATE-ARCHIVE.md"
"""Archive of compacted historical state entries."""

STATE_JSON_BACKUP_FILENAME = "state.json.bak"
"""Backup of state.json for crash recovery."""

STATE_WRITE_INTENT_FILENAME = ".state-write-intent"
"""Intent marker file for atomic dual-write crash recovery."""


# ─── File Suffixes ────────────────────────────────────────────────────────────
# Naming conventions for plan, summary, verification, research, context,
# and validation files within phases.

PLAN_SUFFIX = "-PLAN.md"
"""Suffix for numbered plan files (e.g., '01-PLAN.md')."""

SUMMARY_SUFFIX = "-SUMMARY.md"
"""Suffix for numbered summary files (e.g., '01-SUMMARY.md')."""

VERIFICATION_SUFFIX = "-VERIFICATION.md"
"""Suffix for verification report files."""

RESEARCH_SUFFIX = "-RESEARCH.md"
"""Suffix for numbered research files (e.g., '01-RESEARCH.md')."""

CONTEXT_SUFFIX = "-CONTEXT.md"
"""Suffix for numbered context files (e.g., '01-CONTEXT.md')."""

VALIDATION_SUFFIX = "-VALIDATION.md"
"""Suffix for numbered validation files (e.g., '01-VALIDATION.md')."""

STANDALONE_PLAN = "PLAN.md"
"""Standalone plan filename (no number prefix)."""

STANDALONE_SUMMARY = "SUMMARY.md"
"""Standalone summary filename (no number prefix)."""

STANDALONE_VERIFICATION = "VERIFICATION.md"
"""Standalone verification filename (no number prefix)."""

STANDALONE_RESEARCH = "RESEARCH.md"
"""Standalone research filename (no number prefix)."""

STANDALONE_CONTEXT = "CONTEXT.md"
"""Standalone context filename (no number prefix)."""

STANDALONE_VALIDATION = "VALIDATION.md"
"""Standalone validation filename (no number prefix)."""


# ─── Specs Directory Structure ────────────────────────────────────────────────
# Subdirectory names within the specs/ bundle directory.

SPECS_REFERENCES_DIR = "references"
"""Reference markdown files (protocols, errors, verification checklists)."""

SPECS_WORKFLOWS_DIR = "workflows"
"""Workflow definition files."""

SPECS_TEMPLATES_DIR = "templates"
"""Project and phase template files."""

# ─── Pattern Library Layout ───────────────────────────────────────────────────
# On-disk layout for the cross-project pattern library.

PATTERNS_DIR_NAME = "learned-patterns"
"""Root directory name for the pattern library."""

PATTERNS_INDEX_FILENAME = "index.json"
"""Pattern library index file."""

PATTERNS_BY_DOMAIN_DIR = "patterns-by-domain"
"""Subdirectory containing domain-organized pattern files."""


# ─── Environment Variable Names ──────────────────────────────────────────────
# All env vars that GPD reads.

ENV_PATTERNS_ROOT = "GPD_PATTERNS_ROOT"
"""Override for pattern library root directory."""

ENV_DATA_DIR = "GPD_DATA_DIR"
"""Override for GPD data directory (patterns default to {data_dir}/learned-patterns)."""

ENV_MAX_INCLUDE_CHARS = "GPD_MAX_INCLUDE_CHARS"
"""Override for maximum characters when reading files for context."""

ENV_GPD_ACTIVE_RUNTIME = "GPD_ACTIVE_RUNTIME"
"""Explicit runtime override for GPD-owned shell invocations."""

ENV_GPD_DISABLE_CHECKOUT_REEXEC = "GPD_DISABLE_CHECKOUT_REEXEC"
"""Disable CLI checkout re-exec when a managed runtime bridge already pinned execution."""

ENV_GPD_DEBUG = "GPD_DEBUG"
"""Enable verbose debug output (stderr diagnostics, extra logging)."""


# ─── Required / Optional Planning Files ───────────────────────────────────────
# Used by health checks to validate project structure.

REQUIRED_PLANNING_FILES: tuple[str, ...] = (
    ROADMAP_FILENAME,
    STATE_MD_FILENAME,
    STATE_JSON_FILENAME,
    PROJECT_FILENAME,
)
"""Files that must exist in .gpd/ for a valid project."""

REQUIRED_PLANNING_DIRS: tuple[str, ...] = (PHASES_DIR_NAME,)
"""Directories that must exist in .gpd/ for a valid project."""

OPTIONAL_PLANNING_FILES: tuple[str, ...] = (CONFIG_FILENAME, CONVENTIONS_FILENAME)
"""Files that are checked but not required in .gpd/."""


# ─── Specs Doctor Required Subdirs ────────────────────────────────────────────

REQUIRED_SPECS_SUBDIRS: tuple[str, ...] = (
    SPECS_REFERENCES_DIR,
    SPECS_TEMPLATES_DIR,
    SPECS_WORKFLOWS_DIR,
)
"""Subdirectories expected in the specs/ bundle root."""

# ─── Default Max Include Chars ──────────────────────────────────────────────

DEFAULT_MAX_INCLUDE_CHARS = 20000
"""Default character limit for file includes (overridable via GPD_MAX_INCLUDE_CHARS)."""


# ─── Health Check Thresholds ────────────────────────────────────────────────

STATE_LINES_TARGET = 150
"""Maximum lines for STATE.md before suggesting compaction."""

STATE_LINES_BUDGET = 1500
"""Hard line budget for STATE.md; above this, compaction runs in aggressive mode."""

DECISION_THRESHOLD = 20
"""Number of decisions before suggesting compaction."""

UNCOMMITTED_FILES_THRESHOLD = 20
"""Number of uncommitted files before raising a warning."""

MIN_PYTHON_MAJOR = 3
"""Minimum required Python major version."""

MIN_PYTHON_MINOR = 11
"""Minimum required Python minor version."""

RECOMMENDED_PYTHON_VERSION: tuple[int, int] = (3, 12)
"""Recommended Python version for best compatibility."""

SEED_PATTERN_INITIAL_OCCURRENCES: int = 5
"""Initial occurrence count for seed patterns in pattern_seed()."""

VALID_RETURN_STATUSES: frozenset[str] = frozenset({"completed", "checkpoint", "blocked", "failed"})
"""Allowed values for gpd_return.status in summary files."""

REQUIRED_RETURN_FIELDS: tuple[str, ...] = ("status", "files_written", "issues", "next_actions")
"""Fields that must be present in a gpd_return YAML block."""


# ─── Project Layout ─────────────────────────────────────────────────────────


class ProjectLayout:
    """Configurable project directory structure.

    Centralizes ALL path construction for a GPD project so that no module
    needs to hardcode ``".gpd"`` or filename strings.  Every path-
    producing helper in state.py, phases.py, health.py, trace.py, config.py,
    and query.py should delegate to an instance of this class.

    Example::

        layout = ProjectLayout(project_root)
        state_json = layout.state_json        # project_root / ".gpd" / "state.json"
        traces      = layout.traces_dir              # project_root / ".gpd" / "traces"
        sessions    = layout.observability_sessions_dir  # project_root / ".gpd" / "observability" / "sessions"
        current_obs = layout.current_observability_session
        phase_dir   = layout.phase_dir("01-setup")
    """

    __slots__ = ("root", "gpd")

    def __init__(self, root: Path, gpd_dir: str = PLANNING_DIR_NAME) -> None:
        self.root = root
        self.gpd = root / gpd_dir

    # ── Top-level GPD files ───────────────────────────────────────────────

    @property
    def state_json(self) -> Path:
        return self.gpd / STATE_JSON_FILENAME

    @property
    def state_md(self) -> Path:
        return self.gpd / STATE_MD_FILENAME

    @property
    def roadmap(self) -> Path:
        return self.gpd / ROADMAP_FILENAME

    @property
    def project_md(self) -> Path:
        return self.gpd / PROJECT_FILENAME

    @property
    def config_json(self) -> Path:
        return self.gpd / CONFIG_FILENAME

    @property
    def conventions_md(self) -> Path:
        return self.gpd / CONVENTIONS_FILENAME

    @property
    def state_archive(self) -> Path:
        return self.gpd / STATE_ARCHIVE_FILENAME

    @property
    def state_json_backup(self) -> Path:
        return self.gpd / STATE_JSON_BACKUP_FILENAME

    @property
    def state_intent(self) -> Path:
        return self.gpd / STATE_WRITE_INTENT_FILENAME

    @property
    def requirements_md(self) -> Path:
        return self.gpd / REQUIREMENTS_FILENAME

    @property
    def milestones_md(self) -> Path:
        return self.gpd / MILESTONES_FILENAME

    @property
    def checkpoints_md(self) -> Path:
        return self.root / CHECKPOINTS_FILENAME

    @property
    def agent_id_file(self) -> Path:
        return self.gpd / AGENT_ID_FILENAME

    # ── Directories ───────────────────────────────────────────────────────

    @property
    def phases_dir(self) -> Path:
        return self.gpd / PHASES_DIR_NAME

    @property
    def phase_checkpoints_dir(self) -> Path:
        return self.root / PHASE_CHECKPOINTS_DIR_NAME

    @property
    def analysis_dir(self) -> Path:
        return self.gpd / ANALYSIS_DIR_NAME

    @property
    def traces_dir(self) -> Path:
        return self.gpd / TRACES_DIR_NAME

    @property
    def observability_dir(self) -> Path:
        return self.gpd / OBSERVABILITY_DIR_NAME

    @property
    def observability_sessions_dir(self) -> Path:
        return self.observability_dir / OBSERVABILITY_SESSIONS_DIR_NAME

    @property
    def current_observability_session(self) -> Path:
        return self.observability_dir / OBSERVABILITY_CURRENT_SESSION_FILENAME

    @property
    def current_observability_execution(self) -> Path:
        return self.observability_dir / OBSERVABILITY_CURRENT_EXECUTION_FILENAME

    @property
    def milestones_dir(self) -> Path:
        return self.gpd / MILESTONES_DIR_NAME

    @property
    def todos_dir(self) -> Path:
        return self.gpd / TODOS_DIR_NAME

    @property
    def literature_dir(self) -> Path:
        return self.gpd / LITERATURE_DIR_NAME

    @property
    def research_map_dir(self) -> Path:
        return self.gpd / RESEARCH_MAP_DIR_NAME

    @property
    def scratch_dir(self) -> Path:
        return self.gpd / SCRATCH_DIR_NAME

    # ── Derived paths ─────────────────────────────────────────────────────

    @property
    def active_trace(self) -> Path:
        return self.traces_dir / ACTIVE_TRACE_FILENAME

    def observability_session_events(self, session_id: str) -> Path:
        """Return the per-session observability JSONL path."""
        safe_session = "".join(c if c.isalnum() or c in "._-" else "-" for c in session_id)
        return self.observability_sessions_dir / f"{safe_session}.jsonl"

    def phase_dir(self, phase_name: str) -> Path:
        """Return path to a specific phase directory."""
        return self.phases_dir / phase_name

    def phase_checkpoint_file(self, phase_name: str) -> Path:
        """Return the generated checkpoint note path for a phase directory."""
        return self.phase_checkpoints_dir / f"{phase_name}.md"

    def trace_file(self, phase: str, plan: str) -> Path:
        """Return path to a trace JSONL file for a given phase+plan."""
        safe_phase = "".join(c if c.isalnum() or c in "._-" else "-" for c in phase)
        safe_plan = "".join(c if c.isalnum() or c in "._-" else "-" for c in plan)
        return self.traces_dir / f"{safe_phase}-{safe_plan}.jsonl"

    def plan_file(self, phase_name: str, plan_id: str) -> Path:
        """Return path to a numbered plan file within a phase."""
        return self.phase_dir(phase_name) / f"{plan_id}{PLAN_SUFFIX}"

    def summary_file(self, phase_name: str, plan_id: str) -> Path:
        """Return path to a numbered summary file within a phase."""
        return self.phase_dir(phase_name) / f"{plan_id}{SUMMARY_SUFFIX}"

    def verification_file(self, phase_name: str, plan_id: str) -> Path:
        """Return path to a verification file within a phase."""
        return self.phase_dir(phase_name) / f"{plan_id}{VERIFICATION_SUFFIX}"

    # ── Predicates ────────────────────────────────────────────────────────

    def is_plan_file(self, filename: str) -> bool:
        """Check if a filename matches the plan naming convention."""
        return filename.endswith(PLAN_SUFFIX) or filename == STANDALONE_PLAN

    def is_summary_file(self, filename: str) -> bool:
        """Check if a filename matches the summary naming convention."""
        return filename.endswith(SUMMARY_SUFFIX) or filename == STANDALONE_SUMMARY

    def is_verification_file(self, filename: str) -> bool:
        """Check if a filename matches the verification naming convention."""
        return filename.endswith(VERIFICATION_SUFFIX) or filename == STANDALONE_VERIFICATION

    def strip_plan_suffix(self, filename: str) -> str:
        """Remove plan suffix from filename to get the plan ID."""
        if filename.endswith(PLAN_SUFFIX):
            return filename[: -len(PLAN_SUFFIX)]
        if filename == STANDALONE_PLAN:
            return ""
        return filename

    def strip_summary_suffix(self, filename: str) -> str:
        """Remove summary suffix from filename to get the plan ID."""
        if filename.endswith(SUMMARY_SUFFIX):
            return filename[: -len(SUMMARY_SUFFIX)]
        if filename == STANDALONE_SUMMARY:
            return ""
        return filename
