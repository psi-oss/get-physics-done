"""Comprehensive GPD system health dashboard.

Aggregates validation and diagnostic checks across project structure, state
consistency, convention completeness, config, roadmap, and more into a single
report with auto-fix capability.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
import sys
import time
from enum import StrEnum
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field
from pydantic import ValidationError as PydanticValidationError

from gpd.core.config import GPDProjectConfig, load_config
from gpd.core.constants import (
    DECISION_THRESHOLD,
    MIN_PYTHON_MAJOR,
    MIN_PYTHON_MINOR,
    OPTIONAL_PLANNING_FILES,
    PLANNING_DIR_NAME,
    RECOMMENDED_PYTHON_VERSION,
    REQUIRED_PLANNING_DIRS,
    REQUIRED_PLANNING_FILES,
    REQUIRED_RETURN_FIELDS,
    REQUIRED_SPECS_SUBDIRS,
    STATE_LINES_TARGET,
    UNCOMMITTED_FILES_THRESHOLD,
    VALID_RETURN_STATUSES,
    ProjectLayout,
)
from gpd.core.conventions import KNOWN_CONVENTIONS, is_bogus_value
from gpd.core.errors import GPDError, ValidationError
from gpd.core.frontmatter import FrontmatterParseError, extract_frontmatter
from gpd.core.observability import gpd_span
from gpd.core.state import (
    load_state_json,
    state_validate,
    sync_state_json,
)
from gpd.core.storage_paths import ProjectStorageLayout
from gpd.core.utils import (
    atomic_write,
    phase_normalize,
    phase_sort_key,
    safe_parse_int,
    safe_read_file,
)

logger = logging.getLogger(__name__)

SECONDS_PER_DAY = 24 * 60 * 60
STALE_CHECKPOINT_TAG_MAX_AGE_DAYS = 7
STALE_CHECKPOINT_TAG_MAX_AGE_SECONDS = STALE_CHECKPOINT_TAG_MAX_AGE_DAYS * SECONDS_PER_DAY

# ─── Check Status ────────────────────────────────────────────────────────────


class CheckStatus(StrEnum):
    """Outcome of a single health check."""

    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


# ─── Pydantic Models ─────────────────────────────────────────────────────────


class HealthCheck(BaseModel):
    """Result of a single health check."""

    model_config = ConfigDict(validate_assignment=True)

    status: CheckStatus
    label: str
    details: dict[str, object] = Field(default_factory=dict)
    issues: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class HealthSummary(BaseModel):
    """Aggregated counts from all health checks."""

    ok: int = 0
    warn: int = 0
    fail: int = 0
    total: int = 0


class HealthReport(BaseModel):
    """Full health report across all checks."""

    overall: CheckStatus
    summary: HealthSummary
    checks: list[HealthCheck] = Field(default_factory=list)
    fixes_applied: list[str] = Field(default_factory=list)


# All thresholds, file lists, and return validation constants imported from constants.py


# ─── Individual Health Checks ────────────────────────────────────────────────


def check_environment() -> HealthCheck:
    """Check Python version and git availability."""
    details: dict[str, object] = {}
    issues: list[str] = []

    # Python version
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    details["python_version"] = py_version
    if sys.version_info < (MIN_PYTHON_MAJOR, MIN_PYTHON_MINOR):
        issues.append(f"Python {py_version} < {MIN_PYTHON_MAJOR}.{MIN_PYTHON_MINOR} required")

    # Git available
    try:
        result = subprocess.run(
            ["git", "--version"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        details["git_version"] = result.stdout.strip()
        if result.returncode != 0:
            issues.append("git not functioning correctly")
    except FileNotFoundError:
        issues.append("git not found in PATH")
        details["git_version"] = None
    except subprocess.TimeoutExpired:
        issues.append("git --version timed out")
        details["git_version"] = None

    status = CheckStatus.FAIL if issues else CheckStatus.OK
    return HealthCheck(status=status, label="Environment", details=details, issues=issues)


def check_project_structure(cwd: Path) -> HealthCheck:
    """Check that required .gpd/ files and directories exist."""
    layout = ProjectLayout(cwd)
    issues: list[str] = []
    details: dict[str, object] = {}

    for name in REQUIRED_PLANNING_FILES:
        full = layout.gpd / name
        if full.exists():
            details[name] = "present"
        else:
            details[name] = "missing"
            issues.append(f"Required file missing: {PLANNING_DIR_NAME}/{name}")

    for name in REQUIRED_PLANNING_DIRS:
        full = layout.gpd / name
        if full.is_dir():
            details[name] = "present"
        else:
            details[name] = "missing"
            issues.append(f"Required directory missing: {PLANNING_DIR_NAME}/{name}/")

    for name in OPTIONAL_PLANNING_FILES:
        full = layout.gpd / name
        details[name] = "present" if full.exists() else "absent"

    status = CheckStatus.FAIL if issues else CheckStatus.OK
    return HealthCheck(status=status, label="Project Structure", details=details, issues=issues)


def check_storage_paths(cwd: Path) -> HealthCheck:
    """Warn on suspicious storage-policy violations without blocking the project."""
    layout = ProjectStorageLayout(cwd)
    warnings = list(layout.audit_storage_warnings())
    details: dict[str, object] = {
        "project_root": str(layout.root),
        "internal_root": str(layout.internal_root),
        "temporary_project_root": layout.project_root_is_temporary(),
        "warning_count": len(warnings),
    }
    status = CheckStatus.WARN if warnings else CheckStatus.OK
    return HealthCheck(status=status, label="Storage-Path Policy", details=details, warnings=warnings)


def check_state_validity(cwd: Path) -> HealthCheck:
    """Cross-check state.json and STATE.md consistency.

    Delegates core validation to :func:`state_validate` and wraps the result.
    """
    result = state_validate(cwd)
    issues = list(result.issues)
    warnings = list(result.warnings)

    # Additional: check phase ID format
    layout = ProjectLayout(cwd)
    try:
        state_obj = json.loads(layout.state_json.read_text(encoding="utf-8"))
        if isinstance(state_obj, dict) and state_obj.get("position", {}).get("current_phase") is not None:
            phase = str(state_obj["position"]["current_phase"])
            if not re.match(r"^\d{2,}(\.\d+)*$", phase):
                warnings.append(f'phase ID format: "{phase}" -- expected zero-padded')
    except (FileNotFoundError, json.JSONDecodeError, OSError, AttributeError, KeyError, TypeError):
        pass

    details: dict[str, object] = {"has_json": layout.state_json.exists(), "has_md": layout.state_md.exists()}
    status = CheckStatus.FAIL if issues else (CheckStatus.WARN if warnings else CheckStatus.OK)
    return HealthCheck(status=status, label="State Validity", details=details, issues=issues, warnings=warnings)


def check_compaction_needed(cwd: Path) -> HealthCheck:
    """Check if STATE.md needs compaction based on line/decision counts."""
    md_path = ProjectLayout(cwd).state_md
    content = safe_read_file(md_path)
    if content is None:
        return HealthCheck(
            status=CheckStatus.OK,
            label="State Compaction",
            details={"reason": "no_state_file"},
        )

    line_count = len(content.split("\n"))

    # Count decisions
    dec_match = re.search(
        r"###?\s*Decisions\s*\n([\s\S]*?)(?=\n###?|\n##[^#]|$)",
        content,
        re.IGNORECASE,
    )
    decision_count = (
        len(re.findall(r"^\s*-\s+\[?Phase", dec_match.group(1), re.MULTILINE | re.IGNORECASE)) if dec_match else 0
    )

    triggers: list[str] = []
    if line_count > STATE_LINES_TARGET:
        triggers.append(f"lines: {line_count}/{STATE_LINES_TARGET}")
    if decision_count > DECISION_THRESHOLD:
        triggers.append(f"decisions: {decision_count}/{DECISION_THRESHOLD}")

    warnings = [f"Compaction recommended: {', '.join(triggers)}"] if triggers else []
    status = CheckStatus.WARN if triggers else CheckStatus.OK
    return HealthCheck(
        status=status,
        label="State Compaction",
        details={"lines": line_count, "decisions": decision_count, "target_lines": STATE_LINES_TARGET},
        warnings=warnings,
    )


def check_roadmap_consistency(cwd: Path) -> HealthCheck:
    """Check that ROADMAP.md phases match directories on disk."""
    layout = ProjectLayout(cwd)
    roadmap_path = layout.roadmap
    phases_dir = layout.phases_dir
    issues: list[str] = []
    warnings: list[str] = []

    content = safe_read_file(roadmap_path)
    if content is None:
        return HealthCheck(status=CheckStatus.FAIL, label="Roadmap Consistency", issues=["ROADMAP.md not found"])

    # Extract phase numbers from ROADMAP
    roadmap_phases: set[str] = set()
    for m in re.finditer(r"(?<!#)#{2,4}(?!#)\s*Phase\s+(\d+(?:\.\d+)*)\s*:", content):
        roadmap_phases.add(m.group(1))

    # Phases on disk
    disk_phases: set[str] = set()
    if phases_dir.is_dir():
        for entry in phases_dir.iterdir():
            if entry.is_dir():
                dm = re.match(r"^(\d+(?:\.\d+)*)", entry.name)
                if dm:
                    disk_phases.add(dm.group(1))

    # Cross-check
    for p in roadmap_phases:
        if p not in disk_phases and phase_normalize(p) not in disk_phases:
            warnings.append(f"Phase {p} in ROADMAP but no directory on disk")

    for p in disk_phases:
        unpadded = ".".join(str(int(seg)) for seg in p.split("."))
        if p not in roadmap_phases and unpadded not in roadmap_phases:
            warnings.append(f"Phase {p} on disk but not in ROADMAP")

    # Sequential check
    integer_phases = sorted(int(p) for p in disk_phases if "." not in p)
    for i in range(1, len(integer_phases)):
        if integer_phases[i] != integer_phases[i - 1] + 1:
            warnings.append(f"Gap in phase numbering: {integer_phases[i - 1]} -> {integer_phases[i]}")

    status = CheckStatus.FAIL if issues else (CheckStatus.WARN if warnings else CheckStatus.OK)
    return HealthCheck(
        status=status,
        label="Roadmap Consistency",
        details={"roadmap_phases": len(roadmap_phases), "disk_phases": len(disk_phases)},
        issues=issues,
        warnings=warnings,
    )


def check_orphans(cwd: Path) -> HealthCheck:
    """Detect orphan plans/summaries and empty phase directories."""
    layout = ProjectLayout(cwd)
    phases_dir = layout.phases_dir
    warnings: list[str] = []

    if not phases_dir.is_dir():
        return HealthCheck(status=CheckStatus.OK, label="Orphan Detection")

    dirs = sorted(
        (d for d in phases_dir.iterdir() if d.is_dir()),
        key=lambda d: phase_sort_key(d.name),
    )

    for phase_dir in dirs:
        files = [f.name for f in phase_dir.iterdir() if f.is_file()]
        plans = [f for f in files if layout.is_plan_file(f)]
        summaries = [f for f in files if layout.is_summary_file(f)]

        # Summaries without matching plans
        for summary in summaries:
            if layout.strip_summary_suffix(summary) not in {layout.strip_plan_suffix(plan) for plan in plans}:
                warnings.append(f"Orphan summary: {phase_dir.name}/{summary} (no matching plan)")

        # Empty phase directories
        if not plans and not summaries and not files:
            warnings.append(f"Empty phase directory: {phase_dir.name}/")

    status = CheckStatus.WARN if warnings else CheckStatus.OK
    return HealthCheck(status=status, label="Orphan Detection", warnings=warnings)


def check_convention_lock(cwd: Path) -> HealthCheck:
    """Check convention lock completeness."""
    warnings: list[str] = []
    state_obj = load_state_json(cwd)

    if state_obj is None:
        return HealthCheck(status=CheckStatus.WARN, label="Convention Lock", warnings=["state.json not found"])

    cl = state_obj.get("convention_lock")
    if cl is None:
        return HealthCheck(
            status=CheckStatus.WARN, label="Convention Lock", warnings=["No convention_lock in state.json"]
        )

    if not isinstance(cl, dict):
        return HealthCheck(
            status=CheckStatus.WARN,
            label="Convention Lock",
            warnings=["convention_lock is not a dict"],
            details={},
        )

    set_count = 0
    total_count = 0
    for key in KNOWN_CONVENTIONS:
        total_count += 1
        val = cl.get(key)
        if not is_bogus_value(val):
            set_count += 1

    unset = total_count - set_count
    if unset > 0:
        warnings.append(f"{unset}/{total_count} core conventions unset")

    status = CheckStatus.WARN if unset > 0 else CheckStatus.OK
    return HealthCheck(
        status=status,
        label="Convention Lock",
        details={"set": set_count, "total": total_count},
        warnings=warnings,
    )


def check_config(cwd: Path) -> HealthCheck:
    """Validate project config.json."""
    config_path = ProjectLayout(cwd).config_json

    if not config_path.exists():
        return HealthCheck(
            status=CheckStatus.WARN,
            label="Config",
            warnings=["config.json not found (using defaults)"],
        )

    try:
        config = load_config(cwd)
        details: dict[str, object] = {
            "commit_docs": config.commit_docs,
            "model_profile": config.model_profile.value,
            "autonomy": config.autonomy.value,
            "research_mode": config.research_mode.value,
        }
        return HealthCheck(status=CheckStatus.OK, label="Config", details=details)
    except (ValueError, OSError, GPDError) as e:
        return HealthCheck(
            status=CheckStatus.FAIL,
            label="Config",
            issues=[f"config.json parse error: {e}"],
        )


def check_plan_frontmatter(cwd: Path) -> HealthCheck:
    """Check plan file frontmatter for 'wave' field and numbering gaps."""
    layout = ProjectLayout(cwd)
    phases_dir = layout.phases_dir
    warnings: list[str] = []
    details: dict[str, object] = {"plans_checked": 0, "plans_missing_wave": 0, "numbering_gaps": 0}

    if not phases_dir.is_dir():
        return HealthCheck(status=CheckStatus.OK, label="Plan Frontmatter", details=details)

    dirs = sorted(
        (d for d in phases_dir.iterdir() if d.is_dir()),
        key=lambda d: phase_sort_key(d.name),
    )

    for phase_dir in dirs:
        plans = sorted(f.name for f in phase_dir.iterdir() if f.is_file() and layout.is_plan_file(f.name))

        # Plan numbering gaps
        plan_nums: list[int] = []
        for p in plans:
            if p == "PLAN.md":
                continue
            pm = re.search(r"(\d{2,})-PLAN\.md$", p)
            if pm:
                plan_nums.append(int(pm.group(1)))

        for i in range(1, len(plan_nums)):
            if plan_nums[i] != plan_nums[i - 1] + 1:
                warnings.append(f"Plan numbering gap in {phase_dir.name}: plan {plan_nums[i - 1]} -> {plan_nums[i]}")
                details["numbering_gaps"] = int(details["numbering_gaps"]) + 1  # type: ignore[arg-type]

        # Frontmatter field check
        for plan_name in plans:
            details["plans_checked"] = int(details["plans_checked"]) + 1  # type: ignore[arg-type]
            plan_path = phase_dir / plan_name
            content = safe_read_file(plan_path)
            if content is None:
                continue
            try:
                meta, _ = extract_frontmatter(content)
            except FrontmatterParseError:
                warnings.append(f"{phase_dir.name}/{plan_name}: YAML parse error")
                continue
            if meta.get("wave") is None:
                warnings.append(f"{phase_dir.name}/{plan_name}: missing 'wave' in frontmatter")
                details["plans_missing_wave"] = int(details["plans_missing_wave"]) + 1  # type: ignore[arg-type]

    status = CheckStatus.WARN if warnings else CheckStatus.OK
    return HealthCheck(status=status, label="Plan Frontmatter", details=details, warnings=warnings)


def check_latest_return(cwd: Path) -> HealthCheck:
    """Validate the gpd_return YAML block in the most recent SUMMARY file."""
    layout = ProjectLayout(cwd)
    phases_dir = layout.phases_dir
    warnings: list[str] = []
    issues: list[str] = []
    details: dict[str, object] = {}

    # Find most recent SUMMARY file
    latest: tuple[float, Path, str] | None = None
    if phases_dir.is_dir():
        for phase_dir in phases_dir.iterdir():
            if not phase_dir.is_dir():
                continue
            for f in phase_dir.iterdir():
                if f.is_file() and layout.is_summary_file(f.name):
                    mtime = f.stat().st_mtime
                    if latest is None or mtime > latest[0]:
                        latest = (mtime, f, f"{phase_dir.name}/{f.name}")

    if latest is None:
        return HealthCheck(
            status=CheckStatus.OK,
            label="Latest Return Envelope",
            details={"reason": "no_summaries"},
        )

    _, summary_path, summary_name = latest
    details["file"] = summary_name

    content = safe_read_file(summary_path)
    if content is None:
        issues.append(f"{summary_name}: cannot read file")
        return HealthCheck(status=CheckStatus.FAIL, label="Latest Return Envelope", details=details, issues=issues)

    return_match = re.search(r"```ya?ml\s*\n(\s*gpd_return:\s*\n[\s\S]*?)```", content)
    if not return_match:
        warnings.append(f"{summary_name}: no gpd_return YAML block")
        return HealthCheck(
            status=CheckStatus.WARN,
            label="Latest Return Envelope",
            details=details,
            warnings=warnings,
        )

    try:
        parsed = yaml.safe_load(return_match.group(1))
    except yaml.YAMLError as e:
        issues.append(f"{summary_name}: gpd_return YAML parse error: {e}")
        return HealthCheck(status=CheckStatus.FAIL, label="Latest Return Envelope", details=details, issues=issues)

    raw = parsed.get("gpd_return") if isinstance(parsed, dict) else None
    fields = raw if isinstance(raw, dict) else {}
    details["fields_found"] = list(fields.keys())

    for field_name in REQUIRED_RETURN_FIELDS:
        if field_name not in fields or fields[field_name] is None:
            issues.append(f"{summary_name}: missing required field '{field_name}' in gpd_return")

    if fields.get("status") and str(fields["status"]).lower() not in VALID_RETURN_STATUSES:
        issues.append(f"{summary_name}: invalid status '{fields['status']}'")

    for numeric_field in ("tasks_completed", "tasks_total"):
        val = fields.get(numeric_field)
        if val is not None and safe_parse_int(val, None) is None:
            issues.append(f"{summary_name}: {numeric_field} not a number")

    status = CheckStatus.FAIL if issues else (CheckStatus.WARN if warnings else CheckStatus.OK)
    return HealthCheck(status=status, label="Latest Return Envelope", details=details, issues=issues, warnings=warnings)


def check_git_status(cwd: Path) -> HealthCheck:
    """Check for uncommitted files in .gpd/."""
    warnings: list[str] = []
    details: dict[str, object] = {}

    try:
        result = subprocess.run(
            ["git", "status", "--porcelain", f"{PLANNING_DIR_NAME}/"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            details["repo_detected"] = False
            message = result.stderr.strip() or "git status check failed"
            warnings.append(message)
            status = CheckStatus.WARN
            return HealthCheck(status=status, label="Git Status", details=details, warnings=warnings)

        lines = [ln for ln in result.stdout.strip().split("\n") if ln.strip()] if result.stdout.strip() else []
        uncommitted = len(lines)
        details["repo_detected"] = True
        details["uncommitted_files"] = uncommitted

        if uncommitted > UNCOMMITTED_FILES_THRESHOLD:
            warnings.append(f"{uncommitted} uncommitted files in {PLANNING_DIR_NAME}/")
    except (FileNotFoundError, subprocess.TimeoutExpired):
        details["repo_detected"] = False
        warnings.append("git status check failed")

    status = CheckStatus.WARN if warnings else CheckStatus.OK
    return HealthCheck(status=status, label="Git Status", details=details, warnings=warnings)


def check_checkpoint_tags(cwd: Path) -> HealthCheck:
    """Warn about stale GPD checkpoint tags left behind in git."""
    warnings: list[str] = []
    details: dict[str, object] = {"repo_detected": True, "tag_count": 0, "stale_tags": []}

    try:
        result = subprocess.run(
            ["git", "tag", "-l", "gpd-checkpoint/*"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode != 0:
            details["repo_detected"] = False
            message = result.stderr.strip() or "git tag check failed"
            warnings.append(message)
            return HealthCheck(status=CheckStatus.WARN, label="Checkpoint Tags", details=details, warnings=warnings)

        tags = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        details["tag_count"] = len(tags)

        now = int(time.time())
        stale_tags: list[str] = []
        for tag in tags:
            tag_result = subprocess.run(
                ["git", "log", "-1", "--format=%ct", tag],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if tag_result.returncode != 0:
                warnings.append(f"Unable to inspect checkpoint tag {tag}")
                continue
            try:
                created_at = int(tag_result.stdout.strip())
            except ValueError:
                warnings.append(f"Invalid timestamp for checkpoint tag {tag}")
                continue
            if now - created_at >= STALE_CHECKPOINT_TAG_MAX_AGE_SECONDS:
                stale_tags.append(tag)

        details["stale_tags"] = stale_tags
        if stale_tags:
            warnings.append(
                f"{len(stale_tags)} checkpoint tag(s) older than {STALE_CHECKPOINT_TAG_MAX_AGE_DAYS} days"
            )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        details["repo_detected"] = False
        warnings.append("git tag check failed")

    status = CheckStatus.WARN if warnings else CheckStatus.OK
    return HealthCheck(status=status, label="Checkpoint Tags", details=details, warnings=warnings)


# ─── Auto-Fix ────────────────────────────────────────────────────────────────


def _apply_fixes(cwd: Path, checks: list[HealthCheck]) -> list[str]:
    """Apply automatic fixes for known issues. Returns list of fix descriptions."""
    layout = ProjectLayout(cwd)
    fixes: list[str] = []

    # Fix 1: Regenerate state.json from STATE.md if missing
    state_check = next((c for c in checks if c.label == "State Validity"), None)
    if state_check and state_check.details.get("has_md") and not state_check.details.get("has_json"):
        md_path = layout.state_md
        content = safe_read_file(md_path)
        if content is not None:
            try:
                sync_state_json(cwd, content)
                fixes.append("Regenerated state.json from STATE.md")
                state_check.issues = [i for i in state_check.issues if "state.json not found" not in i]
                state_check.status = CheckStatus.WARN if state_check.warnings else CheckStatus.OK
            except Exception as e:
                fixes.append(f"Failed to regenerate state.json: {e}")

    # Fix 2: Create config.json if missing or malformed
    config_check = next((c for c in checks if c.label == "Config"), None)
    if config_check and (
        any("not found" in w for w in config_check.warnings)
        or any("parse error" in i for i in config_check.issues)
    ):
        config_path = layout.config_json
        try:
            defaults = GPDProjectConfig()
            config_dict = {
                "model_profile": defaults.model_profile.value,
                "autonomy": defaults.autonomy.value,
                "research_mode": defaults.research_mode.value,
                "commit_docs": defaults.commit_docs,
                "branching_strategy": defaults.branching_strategy.value,
                "phase_branch_template": defaults.phase_branch_template,
                "milestone_branch_template": defaults.milestone_branch_template,
                "workflow": {
                    "research": defaults.research,
                    "plan_checker": defaults.plan_checker,
                    "verifier": defaults.verifier,
                },
                "parallelization": defaults.parallelization,
            }
            config_path.parent.mkdir(parents=True, exist_ok=True)
            if config_path.exists():
                import shutil
                shutil.copy2(config_path, config_path.with_suffix(".json.bak"))
            atomic_write(config_path, json.dumps(config_dict, indent=2) + "\n")
            fixes.append("Created default config.json")
            config_check.warnings = []
            config_check.issues = []
            config_check.status = CheckStatus.OK
        except OSError as e:
            fixes.append(f"Failed to create config.json: {e}")

    # Fix 3: Remove stale checkpoint tags.
    checkpoint_check = next((c for c in checks if c.label == "Checkpoint Tags"), None)
    stale_tags = checkpoint_check.details.get("stale_tags") if checkpoint_check else []
    if checkpoint_check and isinstance(stale_tags, list) and stale_tags:
        try:
            result = subprocess.run(
                ["git", "tag", "-d", *[str(tag) for tag in stale_tags]],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                fixes.append(f"Removed {len(stale_tags)} stale checkpoint tag(s)")
                checkpoint_check.details["tag_count"] = max(
                    0,
                    int(checkpoint_check.details.get("tag_count", len(stale_tags))) - len(stale_tags),
                )
                checkpoint_check.details["stale_tags"] = []
                checkpoint_check.warnings = []
                checkpoint_check.status = CheckStatus.OK
            else:
                fixes.append(result.stderr.strip() or "Failed to delete stale checkpoint tags")
        except (FileNotFoundError, subprocess.TimeoutExpired) as e:
            fixes.append(f"Failed to delete stale checkpoint tags: {e}")

    return fixes


# ─── Main Health Command ─────────────────────────────────────────────────────

# Ordered list of checks to run (each is a (name, callable) pair)
_ALL_CHECKS: list[tuple[str, object]] = [
    ("environment", check_environment),
    ("project_structure", check_project_structure),
    ("storage_paths", check_storage_paths),
    ("state_validity", check_state_validity),
    ("compaction", check_compaction_needed),
    ("roadmap", check_roadmap_consistency),
    ("orphans", check_orphans),
    ("convention_lock", check_convention_lock),
    ("plan_frontmatter", check_plan_frontmatter),
    ("latest_return", check_latest_return),
    ("config", check_config),
    ("checkpoint_tags", check_checkpoint_tags),
    ("git_status", check_git_status),
]


def run_health(cwd: Path, *, fix: bool = False) -> HealthReport:
    """Run all health checks and return a full report.

    Args:
        cwd: Project root directory.
        fix: If True, attempt auto-fixes for common issues.
    """
    with gpd_span("health.run", **{"gpd.health.fix": fix}):
        checks: list[HealthCheck] = []

        for name, check_fn in _ALL_CHECKS:
            with gpd_span(f"health.check.{name}"):
                if name == "environment":
                    checks.append(check_fn())  # type: ignore[operator]
                else:
                    checks.append(check_fn(cwd))  # type: ignore[operator]

        fixes: list[str] = []
        if fix:
            fixes = _apply_fixes(cwd, checks)

        ok_count = sum(1 for c in checks if c.status == CheckStatus.OK)
        warn_count = sum(1 for c in checks if c.status == CheckStatus.WARN)
        fail_count = sum(1 for c in checks if c.status == CheckStatus.FAIL)

        overall = CheckStatus.FAIL if fail_count > 0 else (CheckStatus.WARN if warn_count > 0 else CheckStatus.OK)

        report = HealthReport(
            overall=overall,
            summary=HealthSummary(ok=ok_count, warn=warn_count, fail=fail_count, total=len(checks)),
            checks=checks,
            fixes_applied=fixes,
        )

        logger.info(
            "health_report",
            extra={"overall": overall, "ok": ok_count, "warn": warn_count, "fail": fail_count},
        )
        return report


def _doctor_check_protocol_bundles(specs_dir: Path) -> HealthCheck:
    """Validate bundle frontmatter and referenced asset paths when bundles exist."""
    from gpd.core.protocol_bundles import ProtocolBundle
    from gpd.core.verification_checks import get_verification_check

    bundles_dir = specs_dir / "bundles"
    details: dict[str, object] = {
        "bundles_dir": str(bundles_dir),
        "document_count": 0,
        "bundle_count": 0,
        "bundle_ids": [],
        "reason": None,
    }
    if not bundles_dir.is_dir():
        details["reason"] = "no_bundles_dir"
        return HealthCheck(status=CheckStatus.OK, label="Protocol Bundles", details=details)

    issues: list[str] = []
    warnings: list[str] = []
    bundle_ids: dict[str, Path] = {}
    validated_bundles: list[tuple[Path, ProtocolBundle]] = []
    document_count = 0
    bundle_count = 0

    for path in sorted(bundles_dir.glob("*.md")):
        document_count += 1
        try:
            meta, _body = extract_frontmatter(path.read_text(encoding="utf-8"))
        except FrontmatterParseError as exc:
            issues.append(f"{path.name}: invalid frontmatter ({exc})")
            continue

        if "bundle_id" not in meta:
            continue

        try:
            bundle = ProtocolBundle.model_validate(meta)
        except PydanticValidationError as exc:
            issues.append(f"{path.name}: invalid bundle schema ({exc})")
            continue

        bundle_count += 1
        previous = bundle_ids.get(bundle.bundle_id)
        if previous is not None:
            issues.append(f"Duplicate bundle_id {bundle.bundle_id}: {previous.name} and {path.name}")
            continue
        bundle_ids[bundle.bundle_id] = path
        validated_bundles.append((path, bundle))

        for role, asset in bundle.assets.iter_assets():
            asset_path = specs_dir / asset.path
            if asset_path.exists():
                continue
            message = f"{path.name}: missing {role} asset {asset.path}"
            if asset.required:
                issues.append(message)
            else:
                warnings.append(message)

    for path, bundle in validated_bundles:
        for exclusive_bundle_id in bundle.trigger.exclusive_with:
            if exclusive_bundle_id == bundle.bundle_id:
                issues.append(f"{path.name}: bundle cannot be exclusive_with itself ({exclusive_bundle_id})")
                continue
            if exclusive_bundle_id not in bundle_ids:
                issues.append(f"{path.name}: unknown exclusive_with bundle {exclusive_bundle_id}")

        for extension_index, extension in enumerate(bundle.verifier_extensions):
            for check_id in extension.check_ids:
                if get_verification_check(check_id) is not None:
                    continue
                issues.append(
                    f"{path.name}: verifier_extensions[{extension_index}] "
                    f"{extension.name!r} uses unknown check_id {check_id!r}"
                )

    details.update(
        {
            "document_count": document_count,
            "bundle_count": bundle_count,
            "bundle_ids": sorted(bundle_ids),
        }
    )
    status = CheckStatus.FAIL if issues else CheckStatus.WARN if warnings else CheckStatus.OK
    return HealthCheck(status=status, label="Protocol Bundles", details=details, issues=issues, warnings=warnings)


# ─── Doctor Command ─────────────────────────────────────────────────────────


class DoctorReport(BaseModel):
    """Cross-runtime installation verification report."""

    overall: CheckStatus
    version: str | None = None
    summary: HealthSummary
    checks: list[HealthCheck] = Field(default_factory=list)


def run_doctor(specs_dir: Path | None = None, version: str | None = None) -> DoctorReport:
    """Cross-runtime installation verification.

    Checks that the bundled specs content is correctly installed: references,
    workflows, templates, learned-pattern assets, Python version, and package
    importability.

    Args:
        specs_dir: Path to the specs directory. Required (no automatic discovery).
        version: Version string to include in the report.
    """
    if specs_dir is None:
        raise ValidationError(
            "specs_dir is required. Pass the specs directory explicitly "
            "(e.g., from SPECS_DIR in gpd or via CLI argument)."
        )
    if version is None:
        import importlib.metadata

        try:
            version = importlib.metadata.version("get-physics-done")
        except importlib.metadata.PackageNotFoundError:
            version = None
    sd = specs_dir

    with gpd_span("doctor.run"):
        checks: list[HealthCheck] = []

        # 1. Specs directory structure
        missing = [d for d in REQUIRED_SPECS_SUBDIRS if not (sd / d).is_dir()]
        checks.append(
            HealthCheck(
                status=CheckStatus.FAIL if missing else CheckStatus.OK,
                label="Specs Structure",
                details={"specs_dir": str(sd), "missing": missing},
                issues=[f"Missing directory: {d}/" for d in missing],
            )
        )

        # 2. Key reference files
        key_refs = [
            "references/shared/shared-protocols.md",
            "references/verification/core/verification-core.md",
            "references/verification/errors/llm-physics-errors.md",
        ]
        missing_refs = [r for r in key_refs if not (sd / r).exists()]
        checks.append(
            HealthCheck(
                status=CheckStatus.OK if not missing_refs else CheckStatus.WARN,
                label="Key References",
                details={"checked": len(key_refs), "missing": len(missing_refs)},
                warnings=[f"Missing reference: {r}" for r in missing_refs],
            )
        )

        # 3. Workflow files
        workflows_dir = sd / "workflows"
        workflow_count = len([f for f in workflows_dir.iterdir() if f.suffix == ".md"]) if workflows_dir.is_dir() else 0
        checks.append(
            HealthCheck(
                status=CheckStatus.OK if workflow_count > 0 else CheckStatus.WARN,
                label="Workflow Files",
                details={"workflow_count": workflow_count},
                warnings=[] if workflow_count > 0 else ["No workflow files found"],
            )
        )

        # 4. Template files
        templates_dir = sd / "templates"
        template_count = sum(1 for _ in templates_dir.rglob("*.md")) if templates_dir.is_dir() else 0
        checks.append(
            HealthCheck(
                status=CheckStatus.OK if template_count > 0 else CheckStatus.WARN,
                label="Template Files",
                details={"template_count": template_count},
                warnings=[] if template_count > 0 else ["No template files found"],
            )
        )

        # 5. Bundle registry and asset paths
        checks.append(_doctor_check_protocol_bundles(sd))

        # 6. Python version
        py_issues: list[str] = []
        py_warnings: list[str] = []
        if sys.version_info < (MIN_PYTHON_MAJOR, MIN_PYTHON_MINOR):
            py_issues.append(
                f"Python {sys.version_info.major}.{sys.version_info.minor} < {MIN_PYTHON_MAJOR}.{MIN_PYTHON_MINOR}"
            )
        elif sys.version_info < RECOMMENDED_PYTHON_VERSION:
            py_warnings.append(f"Python >= {RECOMMENDED_PYTHON_VERSION[0]}.{RECOMMENDED_PYTHON_VERSION[1]} recommended")
        checks.append(
            HealthCheck(
                status=CheckStatus.FAIL if py_issues else CheckStatus.WARN if py_warnings else CheckStatus.OK,
                label="Python Version",
                details={"version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"},
                issues=py_issues,
                warnings=py_warnings,
            )
        )

        # 7. Package importability
        import_issues: list[str] = []
        for module in ("gpd.core.utils", "gpd.core.config", "gpd.core.state", "gpd.core.conventions"):
            try:
                __import__(module)
            except ImportError as e:
                import_issues.append(f"Cannot import {module}: {e}")
        checks.append(
            HealthCheck(
                status=CheckStatus.FAIL if import_issues else CheckStatus.OK,
                label="Package Imports",
                details={"modules_checked": 4},
                issues=import_issues,
            )
        )

        # Version (passed as parameter, no gpd import needed)

        ok_count = sum(1 for c in checks if c.status == CheckStatus.OK)
        warn_count = sum(1 for c in checks if c.status == CheckStatus.WARN)
        fail_count = sum(1 for c in checks if c.status == CheckStatus.FAIL)
        overall = CheckStatus.FAIL if fail_count > 0 else CheckStatus.WARN if warn_count > 0 else CheckStatus.OK

        logger.info("doctor_complete", extra={"overall": overall, "version": version})

        return DoctorReport(
            overall=overall,
            version=version,
            summary=HealthSummary(ok=ok_count, warn=warn_count, fail=fail_count, total=len(checks)),
            checks=checks,
        )


__all__ = [
    "CheckStatus",
    "DoctorReport",
    "HealthCheck",
    "HealthReport",
    "HealthSummary",
    "check_compaction_needed",
    "check_config",
    "check_convention_lock",
    "check_environment",
    "check_git_status",
    "check_checkpoint_tags",
    "check_latest_return",
    "check_orphans",
    "check_plan_frontmatter",
    "check_project_structure",
    "check_roadmap_consistency",
    "check_state_validity",
    "check_storage_paths",
    "run_doctor",
    "run_health",
]
