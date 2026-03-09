"""Centralized constants for the GPD package.

All filesystem names, file suffixes, environment variable names, and
structural constants live here. Every module that needs a planning
directory name, a file suffix, or an env var MUST import from this module
instead of using hardcoded string literals.

Layer 1 code: no external imports beyond stdlib.
"""

from __future__ import annotations

from pathlib import Path

__all__ = [
    "ACTIVE_TRACE_FILENAME",
    "AGENT_FILE_PREFIX",
    "AGENT_FILE_SUFFIX",
    "CONFIG_FILENAME",
    "CONVENTIONS_FILENAME",
    "DECISION_THRESHOLD",
    "DEFAULT_LOADER_CACHE_SIZE",
    "DEFAULT_MAX_INCLUDE_CHARS",
    "ENV_DATA_DIR",
    "ENV_MAX_INCLUDE_CHARS",
    "ENV_PATTERNS_ROOT",
    "MIN_PYTHON_MAJOR",
    "MIN_PYTHON_MINOR",
    "NON_BUNDLE_SPECS_DIRS",
    "OPTIONAL_PLANNING_FILES",
    "PATTERNS_BY_DOMAIN_DIR",
    "PATTERNS_DIR_NAME",
    "PATTERNS_INDEX_FILENAME",
    "PHASES_DIR_NAME",
    "PLANNING_DIR_NAME",
    "PLAN_SUFFIX",
    "PROJECT_FILENAME",
    "ProjectLayout",
    "RECOMMENDED_PYTHON_VERSION",
    "REF_DEFAULT_ERROR_CATALOG",
    "REF_ERROR_CATALOG_PREFIX",
    "REF_PROTOCOL_PREFIX",
    "REF_SUBFIELD_GUIDE_FALLBACK",
    "REF_SUBFIELD_PREFIX",
    "REF_VERIFICATION_DOMAIN_PREFIX",
    "REQUIRED_PLANNING_DIRS",
    "REQUIRED_PLANNING_FILES",
    "REQUIRED_RETURN_FIELDS",
    "REQUIRED_SPECS_SUBDIRS",
    "ROADMAP_FILENAME",
    "SEED_PATTERN_INITIAL_OCCURRENCES",
    "SKILL_DIR_PREFIX",
    "SPECS_AGENTS_DIR",
    "SPECS_REFERENCES_DIR",
    "SPECS_SCHEMAS_DIR",
    "SPECS_SKILLS_DIR",
    "SPECS_TEMPLATES_DIR",
    "SPECS_WORKFLOWS_DIR",
    "STANDALONE_PLAN",
    "STANDALONE_SUMMARY",
    "STATE_ARCHIVE_FILENAME",
    "STATE_JSON_BACKUP_FILENAME",
    "STATE_JSON_FILENAME",
    "STATE_JSON_INTENT_SUFFIX",
    "STATE_LINES_BUDGET",
    "STATE_LINES_TARGET",
    "STATE_MD_FILENAME",
    "STATE_WRITE_INTENT_FILENAME",
    "SUMMARY_SUFFIX",
    "TRACES_DIR_NAME",
    "UNCOMMITTED_FILES_THRESHOLD",
    "UNIVERSAL_ERROR_IDS",
    "VALID_RETURN_STATUSES",
    "VERIFICATION_SUFFIX",
]

# ─── Planning Directory Layout ────────────────────────────────────────────────
# These define the on-disk layout of a GPD project's .planning/ directory.

PLANNING_DIR_NAME = ".planning"
"""Top-level planning directory inside a project root."""

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

PHASES_DIR_NAME = "phases"
"""Subdirectory under .planning/ containing per-phase directories."""

TRACES_DIR_NAME = "traces"
"""Subdirectory under .planning/ for execution trace JSONL files."""

ACTIVE_TRACE_FILENAME = ".active-trace"
"""Marker file in traces/ indicating the currently recording trace."""

STATE_ARCHIVE_FILENAME = "STATE-ARCHIVE.md"
"""Archive of compacted historical state entries."""

STATE_JSON_BACKUP_FILENAME = "state.json.bak"
"""Backup of state.json for crash recovery."""

STATE_JSON_INTENT_SUFFIX = ".intent"
"""Suffix for intent-marker files used in crash recovery."""

STATE_WRITE_INTENT_FILENAME = ".state-write-intent"
"""Intent marker file for atomic dual-write crash recovery."""


# ─── File Suffixes ────────────────────────────────────────────────────────────
# Naming conventions for plan, summary, and verification files within phases.

PLAN_SUFFIX = "-PLAN.md"
"""Suffix for numbered plan files (e.g., '01-PLAN.md')."""

SUMMARY_SUFFIX = "-SUMMARY.md"
"""Suffix for numbered summary files (e.g., '01-SUMMARY.md')."""

VERIFICATION_SUFFIX = "-VERIFICATION.md"
"""Suffix for verification report files."""

STANDALONE_PLAN = "PLAN.md"
"""Standalone plan filename (no number prefix)."""

STANDALONE_SUMMARY = "SUMMARY.md"
"""Standalone summary filename (no number prefix)."""


# ─── Specs Directory Structure ────────────────────────────────────────────────
# Subdirectory names within the specs/ bundle directory.

SPECS_REFERENCES_DIR = "references"
"""Reference markdown files (protocols, errors, verification checklists)."""

SPECS_AGENTS_DIR = "agents"
"""Agent prompt files (gpd-executor.md, etc.)."""

SPECS_WORKFLOWS_DIR = "workflows"
"""Workflow definition files."""

SPECS_TEMPLATES_DIR = "templates"
"""Project and phase template files."""

SPECS_SKILLS_DIR = "skills"
"""Skill definition directories (gpd-execute-phase/, etc.)."""

AGENT_FILE_PREFIX = "gpd-"
"""Filename prefix for GPD agent files."""

AGENT_FILE_SUFFIX = ".md"
"""File extension for agent prompt files."""

SKILL_DIR_PREFIX = "gpd-"
"""Directory name prefix for GPD skill directories."""

SPECS_SCHEMAS_DIR = "schemas"
"""Schema definition files for bundle validation."""


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


# ─── Required / Optional Planning Files ───────────────────────────────────────
# Used by health checks to validate project structure.

REQUIRED_PLANNING_FILES: tuple[str, ...] = (
    ROADMAP_FILENAME,
    STATE_MD_FILENAME,
    STATE_JSON_FILENAME,
    PROJECT_FILENAME,
)
"""Files that must exist in .planning/ for a valid project."""

REQUIRED_PLANNING_DIRS: tuple[str, ...] = (PHASES_DIR_NAME,)
"""Directories that must exist in .planning/ for a valid project."""

OPTIONAL_PLANNING_FILES: tuple[str, ...] = (CONFIG_FILENAME, CONVENTIONS_FILENAME)
"""Files that are checked but not required in .planning/."""


# ─── Specs Doctor Required Subdirs ────────────────────────────────────────────

REQUIRED_SPECS_SUBDIRS: tuple[str, ...] = (
    SPECS_REFERENCES_DIR,
    SPECS_TEMPLATES_DIR,
    SPECS_WORKFLOWS_DIR,
    SPECS_AGENTS_DIR,
    SPECS_SKILLS_DIR,
)
"""Subdirectories expected in the specs/ bundle root."""

NON_BUNDLE_SPECS_DIRS: frozenset[str] = frozenset(REQUIRED_SPECS_SUBDIRS) | {SPECS_SCHEMAS_DIR}
"""Specs subdirectories that are NOT loadable bundles (used by bundle_loader to skip)."""


# ─── Reference File Prefixes ─────────────────────────────────────────────────
# Used by loader.py to classify references into sub-indexes.

REF_PROTOCOL_PREFIX = "protocols/"
"""Prefix for protocol reference files."""

REF_VERIFICATION_DOMAIN_PREFIX = "verification-domain-"
"""Prefix for verification domain checklist files."""

REF_ERROR_CATALOG_PREFIX = "llm-errors-"
"""Prefix for error catalog files."""

REF_SUBFIELD_PREFIX = "subfields/"
"""Prefix for subfield guide files."""

REF_SUBFIELD_GUIDE_FALLBACK = "executor-subfield-guide"
"""Fallback reference name when no subfield guide matches."""

REF_DEFAULT_ERROR_CATALOG = "llm-errors-core"
"""Default error catalog used when no keyword matches."""

# ─── Universal Error Class IDs ──────────────────────────────────────────────
# Error classes that are always relevant regardless of physics domain.

UNIVERSAL_ERROR_IDS: frozenset[int] = frozenset({11, 15, 33, 37})
"""Error class IDs always included when no specific keyword matches.

11: Hallucinated mathematical identities
15: Dimensional analysis errors
33: Natural unit restoration errors
37: Metric signature mismatch
"""


# ─── Default Max Cache Size ──────────────────────────────────────────────────

DEFAULT_LOADER_CACHE_SIZE = 64
"""Default maximum number of reference files cached by ReferenceLoader."""

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

REQUIRED_RETURN_FIELDS: tuple[str, ...] = ("status", "phase", "plan", "tasks_completed", "tasks_total")
"""Fields that must be present in a gpd_return YAML block."""


# ─── Project Layout ─────────────────────────────────────────────────────────


class ProjectLayout:
    """Configurable project directory structure.

    Centralizes ALL path construction for a GPD project so that no module
    needs to hardcode ``".planning"`` or filename strings.  Every path-
    producing helper in state.py, phases.py, health.py, trace.py, config.py,
    and query.py should delegate to an instance of this class.

    Example::

        layout = ProjectLayout(project_root)
        state_json = layout.state_json        # project_root / ".planning" / "state.json"
        traces     = layout.traces_dir        # project_root / ".planning" / "traces"
        phase_dir  = layout.phase_dir("01-setup")
    """

    __slots__ = ("root", "planning")

    def __init__(self, root: Path, planning_dir: str = PLANNING_DIR_NAME) -> None:
        self.root = root
        self.planning = root / planning_dir

    # ── Top-level planning files ──────────────────────────────────────────

    @property
    def state_json(self) -> Path:
        return self.planning / STATE_JSON_FILENAME

    @property
    def state_md(self) -> Path:
        return self.planning / STATE_MD_FILENAME

    @property
    def roadmap(self) -> Path:
        return self.planning / ROADMAP_FILENAME

    @property
    def project_md(self) -> Path:
        return self.planning / PROJECT_FILENAME

    @property
    def config_json(self) -> Path:
        return self.planning / CONFIG_FILENAME

    @property
    def conventions_md(self) -> Path:
        return self.planning / CONVENTIONS_FILENAME

    @property
    def state_archive(self) -> Path:
        return self.planning / STATE_ARCHIVE_FILENAME

    @property
    def state_json_backup(self) -> Path:
        return self.planning / STATE_JSON_BACKUP_FILENAME

    @property
    def state_intent(self) -> Path:
        return self.planning / STATE_WRITE_INTENT_FILENAME

    # ── Directories ───────────────────────────────────────────────────────

    @property
    def phases_dir(self) -> Path:
        return self.planning / PHASES_DIR_NAME

    @property
    def traces_dir(self) -> Path:
        return self.planning / TRACES_DIR_NAME

    # ── Derived paths ─────────────────────────────────────────────────────

    @property
    def active_trace(self) -> Path:
        return self.traces_dir / ACTIVE_TRACE_FILENAME

    def phase_dir(self, phase_name: str) -> Path:
        """Return path to a specific phase directory."""
        return self.phases_dir / phase_name

    def trace_file(self, phase: str, plan: str) -> Path:
        """Return path to a trace JSONL file for a given phase+plan."""
        safe_plan = "".join(c if c.isalnum() or c in "._-" else "-" for c in plan)
        return self.traces_dir / f"{phase}-{safe_plan}.jsonl"

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
        return filename.endswith(VERIFICATION_SUFFIX)

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
