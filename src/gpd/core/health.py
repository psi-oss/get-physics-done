"""Comprehensive GPD system health dashboard.

Aggregates validation and diagnostic checks across project structure, state
consistency, convention completeness, config, roadmap, and more into a single
report with auto-fix capability.
"""

from __future__ import annotations

import dataclasses
import json
import logging
import os
import re
import shlex
import shutil
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
from gpd.core.contract_validation import validate_project_contract
from gpd.core.conventions import KNOWN_CONVENTIONS, is_bogus_value
from gpd.core.errors import GPDError, ValidationError
from gpd.core.frontmatter import FrontmatterParseError, extract_frontmatter, validate_frontmatter
from gpd.core.knowledge_migration import discover_knowledge_migration
from gpd.core.knowledge_runtime import discover_knowledge_docs
from gpd.core.observability import gpd_span
from gpd.core.public_surface_contract import (
    local_cli_doctor_global_command,
    local_cli_doctor_local_command,
    local_cli_permissions_sync_command,
)
from gpd.core.runtime_command_surfaces import format_active_runtime_command
from gpd.core.state import (
    peek_state_json,
    save_state_json,
    state_validate,
)
from gpd.core.storage_paths import ProjectStorageLayout
from gpd.core.utils import (
    atomic_write,
    phase_normalize,
    phase_sort_key,
    safe_read_file,
    strict_parse_int,
)
from gpd.core.workflow_presets import resolve_workflow_preset_readiness
from gpd.hooks.install_metadata import InstallTargetAssessment, assess_install_target

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
    """Check that required GPD/ files and directories exist."""
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


def check_knowledge_inventory(cwd: Path) -> HealthCheck:
    """Summarize knowledge-doc inventory, freshness, and supersession health."""
    from gpd.core.tool_preflight import build_plan_tool_preflight

    layout = ProjectLayout(cwd)
    knowledge_dir = layout.knowledge_dir
    discovery = discover_knowledge_docs(cwd)
    migration_inventory = discover_knowledge_migration(cwd)
    by_id = discovery.by_id()

    stable_records = [record for record in discovery.records if record.status == "stable"]
    active_records = [record for record in discovery.records if record.runtime_active]
    stale_review_records = [
        record
        for record in stable_records
        if record.review_fresh is False or record.runtime_active is False
    ]
    broken_supersession_records = [
        record
        for record in discovery.records
        if record.status == "superseded" and record.superseded_by not in by_id
    ]
    plans_with_knowledge_deps: list[str] = []
    plan_knowledge_issue_files: list[str] = []
    plan_knowledge_dependency_issue_count = 0
    plan_knowledge_blocker_count = 0
    plan_knowledge_warning_count = 0
    plan_dependency_warnings: list[str] = []

    if layout.phases_dir.is_dir():
        phase_dirs = sorted((d for d in layout.phases_dir.iterdir() if d.is_dir()), key=lambda d: phase_sort_key(d.name))
        for phase_dir in phase_dirs:
            plan_files = sorted((f for f in phase_dir.iterdir() if f.is_file() and layout.is_plan_file(f.name)), key=lambda f: f.name)
            for plan_path in plan_files:
                preflight = build_plan_tool_preflight(plan_path)
                if not preflight.knowledge_deps and preflight.knowledge_gate == "off":
                    continue

                rel_plan_path = plan_path.relative_to(cwd.resolve(strict=False)).as_posix()
                plans_with_knowledge_deps.append(rel_plan_path)
                non_ok_checks = [check for check in preflight.knowledge_dependency_checks if check.status != "ok"]
                if not non_ok_checks:
                    continue

                plan_knowledge_issue_files.append(rel_plan_path)
                for check in non_ok_checks:
                    plan_knowledge_dependency_issue_count += 1
                    if check.blocking:
                        plan_knowledge_blocker_count += 1
                    else:
                        plan_knowledge_warning_count += 1
                    plan_dependency_warnings.append(f"{rel_plan_path}: {check.detail}")

    details: dict[str, object] = {
        "knowledge_dir_present": knowledge_dir.is_dir(),
        "knowledge_doc_count": len(discovery.records),
        "stable_knowledge_doc_count": len(stable_records),
        "runtime_active_count": len(active_records),
        "status_counts": discovery.status_counts(),
        "discovery_warning_count": len(discovery.warnings),
        "migration_doc_count": len(migration_inventory.records),
        "migration_classification_counts": migration_inventory.classification_counts(),
        "migration_warning_count": len(migration_inventory.warnings),
        "stale_review_count": len(stale_review_records),
        "stale_review_files": [record.path for record in stale_review_records],
        "missing_supersession_target_count": len(broken_supersession_records),
        "missing_supersession_target_files": [
            f"{record.path} -> {record.superseded_by}" for record in broken_supersession_records
        ],
        "plans_with_knowledge_deps_count": len(plans_with_knowledge_deps),
        "plans_with_knowledge_deps": plans_with_knowledge_deps,
        "plan_knowledge_dependency_issue_count": plan_knowledge_dependency_issue_count,
        "plan_knowledge_warning_count": plan_knowledge_warning_count,
        "plan_knowledge_blocker_count": plan_knowledge_blocker_count,
        "plan_knowledge_issue_files": plan_knowledge_issue_files,
    }
    if not knowledge_dir.is_dir():
        details["reason"] = "no_knowledge_dir"

    warnings: list[str] = list(discovery.warnings)
    warnings.extend(migration_inventory.warnings)
    if stale_review_records:
        stale_paths = ", ".join(record.path for record in stale_review_records)
        warnings.append(f"{len(stale_review_records)} stable knowledge doc(s) have stale reviews: {stale_paths}")
    if broken_supersession_records:
        broken_refs = ", ".join(f"{record.path} -> {record.superseded_by}" for record in broken_supersession_records)
        warnings.append(
            f"{len(broken_supersession_records)} superseded knowledge doc(s) point to missing targets: {broken_refs}"
        )
    warnings.extend(plan_dependency_warnings)

    status = CheckStatus.WARN if warnings else CheckStatus.OK
    return HealthCheck(status=status, label="Knowledge Inventory", details=details, warnings=warnings)


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


def _render_contract_cli_command(
    template: str,
    *,
    runtime_name: str | None = None,
    autonomy: str | None = None,
    target_dir: Path | None = None,
) -> str:
    """Render a contract-owned local CLI template with runtime-specific values."""
    rendered: list[str] = []
    replace_autonomy = False
    for token in shlex.split(template):
        if token == "<runtime>" and runtime_name is not None:
            rendered.append(runtime_name)
            replace_autonomy = False
            continue
        if replace_autonomy and autonomy is not None:
            rendered.append(autonomy)
            replace_autonomy = False
            continue
        rendered.append(token)
        replace_autonomy = token == "--autonomy"
    if target_dir is not None:
        rendered.extend(["--target-dir", str(target_dir)])
    return " ".join(shlex.quote(part) for part in rendered)


def _peek_normalized_state_for_health(cwd: Path) -> tuple[dict[str, object] | None, str | None]:
    """Load normalized state for inspection without mutating on-disk files.

    Health checks need visibility into structurally parseable blocked
    ``project_contract`` payloads so approval blockers are reported as failures
    instead of being hidden by draft-scoping normalization.
    """
    state_obj, _integrity_issues, state_source = peek_state_json(
        cwd,
        recover_intent=False,
        surface_blocked_project_contract=True,
    )
    if not isinstance(state_obj, dict):
        return None, state_source
    return state_obj, state_source


def check_state_validity(cwd: Path) -> HealthCheck:
    """Cross-check state.json and STATE.md consistency.

    Delegates core validation to :func:`state_validate` and wraps the result.
    """
    result = state_validate(cwd, recover_intent=False)
    issues = list(result.issues)
    warnings = list(result.warnings)

    state_obj, state_source = _peek_normalized_state_for_health(cwd)
    if isinstance(state_obj, dict) and state_obj.get("project_contract") is not None:
        approval_validation = validate_project_contract(
            state_obj["project_contract"],
            mode="approved",
            project_root=cwd,
        )
        if not approval_validation.valid:
            for error in approval_validation.errors:
                issue = f"project_contract: {error}"
                if issue not in issues:
                    issues.append(issue)
                if issue in warnings:
                    warnings.remove(issue)

    # Additional: check phase ID format against the effective recovered state.
    if isinstance(state_obj, dict) and isinstance(state_obj.get("position"), dict):
        phase_value = state_obj["position"].get("current_phase")
        if phase_value is not None:
            phase = str(phase_value)
            if not re.match(r"^\d{2,}(\.\d+)*$", phase):
                warnings.append(f'phase ID format: "{phase}" -- expected zero-padded')

    layout = ProjectLayout(cwd)
    details: dict[str, object] = {
        "has_json": layout.state_json.exists(),
        "has_md": layout.state_md.exists(),
    }
    if state_source is not None:
        details["state_source"] = state_source
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
    state_obj, _state_source = _peek_normalized_state_for_health(cwd)

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
    """Check plan file frontmatter for numbering gaps and canonical schema."""
    layout = ProjectLayout(cwd)
    phases_dir = layout.phases_dir
    details: dict[str, object] = {
        "plans_checked": 0,
        "plans_missing_wave": 0,
        "plans_missing_contract": 0,
        "numbering_gaps": 0,
    }
    issues: list[str] = []
    warnings: list[str] = []

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
                validation = validate_frontmatter(content, "plan", source_path=plan_path)
            except FrontmatterParseError:
                issues.append(f"{phase_dir.name}/{plan_name}: YAML parse error")
                continue
            missing = set(validation.missing)
            if "wave" in missing:
                details["plans_missing_wave"] = int(details["plans_missing_wave"]) + 1  # type: ignore[arg-type]
            if "contract" in missing:
                details["plans_missing_contract"] = int(details["plans_missing_contract"]) + 1  # type: ignore[arg-type]
            if missing:
                issues.append(
                    f"{phase_dir.name}/{plan_name}: missing required frontmatter fields: {', '.join(validation.missing)}"
                )
            for error in validation.errors:
                issues.append(f"{phase_dir.name}/{plan_name}: {error}")

    status = CheckStatus.FAIL if issues else (CheckStatus.WARN if warnings else CheckStatus.OK)
    return HealthCheck(status=status, label="Plan Frontmatter", details=details, issues=issues, warnings=warnings)


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
        if val is not None and strict_parse_int(val, None) is None:
            issues.append(f"{summary_name}: {numeric_field} not a number")

    status = CheckStatus.FAIL if issues else (CheckStatus.WARN if warnings else CheckStatus.OK)
    return HealthCheck(status=status, label="Latest Return Envelope", details=details, issues=issues, warnings=warnings)


def check_git_status(cwd: Path) -> HealthCheck:
    """Check for uncommitted files in GPD/."""
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


def _apply_fixes(
    cwd: Path,
    checks: list[HealthCheck],
    *,
    return_refreshed_labels: bool = False,
) -> list[str] | tuple[list[str], set[str]]:
    """Apply automatic fixes for known issues.

    Returns a tuple of the fix descriptions and the labels that should be
    recomputed so the final report reflects the post-fix filesystem state.
    """
    layout = ProjectLayout(cwd)
    fixes: list[str] = []
    refreshed_labels: set[str] = set()

    # Fix 1: Restore state.json through the state loader if missing.
    # The loader prefers a valid state.json.bak before falling back to STATE.md.
    state_check = next((c for c in checks if c.label == "State Validity"), None)
    if state_check and state_check.status != CheckStatus.OK:
        restored_state, _restored_issues, state_source = peek_state_json(cwd)
        if restored_state is not None and state_source in {"state.json.bak", "STATE.md"}:
            try:
                save_state_json(cwd, restored_state)
                if state_source == "state.json.bak":
                    fixes.append("Restored state.json from state.json.bak")
                else:
                    fixes.append("Regenerated state.json from STATE.md")
                state_check.details["state_source"] = state_source
                refreshed_labels.update({"State Validity", "Convention Lock"})
                structure_check = next((c for c in checks if c.label == "Project Structure"), None)
                if structure_check is not None:
                    structure_check.details["state.json"] = "present"
            except OSError as e:
                fixes.append(f"Failed to restore state.json: {e}")

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
            config_check.details = {
                "commit_docs": defaults.commit_docs,
                "model_profile": defaults.model_profile.value,
                "autonomy": defaults.autonomy.value,
                "research_mode": defaults.research_mode.value,
            }
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

    if return_refreshed_labels:
        return fixes, refreshed_labels
    return fixes


# ─── Main Health Command ─────────────────────────────────────────────────────

# Ordered list of checks to run (each is a (name, callable) pair)
_ALL_CHECKS: list[tuple[str, object]] = [
    ("environment", check_environment),
    ("project_structure", check_project_structure),
    ("knowledge_inventory", check_knowledge_inventory),
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
            fixes, refreshed_labels = _apply_fixes(cwd, checks, return_refreshed_labels=True)
            if refreshed_labels:
                refreshed_checks: list[HealthCheck] = []
                check_labels = {
                    "environment": "Environment",
                    "project_structure": "Project Structure",
                    "knowledge_inventory": "Knowledge Inventory",
                    "storage_paths": "Storage-Path Policy",
                    "state_validity": "State Validity",
                    "compaction": "State Compaction",
                    "roadmap": "Roadmap Consistency",
                    "orphans": "Orphan Detection",
                    "convention_lock": "Convention Lock",
                    "plan_frontmatter": "Plan Frontmatter",
                    "latest_return": "Latest Return Envelope",
                    "config": "Config",
                    "checkpoint_tags": "Checkpoint Tags",
                    "git_status": "Git Status",
                }
                for name, check_fn in _ALL_CHECKS:
                    label = check_labels[name]
                    if label not in refreshed_labels:
                        refreshed_checks.append(next(c for c in checks if c.label == label))
                        continue
                    with gpd_span(f"health.check.{name}"):
                        if name == "environment":
                            refreshed_checks.append(check_fn())  # type: ignore[operator]
                        else:
                            refreshed_checks.append(check_fn(cwd))  # type: ignore[operator]
                checks = refreshed_checks

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
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            issues.append(f"{path.name}: unreadable bundle ({exc})")
            continue
        try:
            meta, _body = extract_frontmatter(text)
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
            try:
                asset_exists = asset_path.is_file()
            except OSError as exc:
                message = f"{path.name}: unreadable {role} asset {asset.path} ({exc})"
                if asset.required:
                    issues.append(message)
                else:
                    warnings.append(message)
                continue
            if asset_exists:
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
    mode: str = "installation"
    runtime: str | None = None
    install_scope: str | None = None
    target: str | None = None
    live_executable_probes: bool = False
    summary: HealthSummary
    checks: list[HealthCheck] = Field(default_factory=list)


class DoctorRuntimeReadinessContext(BaseModel):
    """Normalized runtime-scoped readiness inputs used by doctor/install flows."""

    runtime: str
    install_scope: str | None = None
    target: Path
    launch_command: str


@dataclasses.dataclass(frozen=True)
class UnattendedReadinessCheck:
    """One composed check contributing to unattended-readiness."""

    name: str
    passed: bool
    blocking: bool
    detail: str


@dataclasses.dataclass(frozen=True)
class UnattendedReadinessResult:
    """Summary of whether one runtime surface is ready for unattended use."""

    runtime: str
    autonomy: str
    install_scope: str
    target: str | None
    readiness: str
    ready: bool
    passed: bool
    readiness_message: str
    live_executable_probes: bool
    checks: list[UnattendedReadinessCheck]
    blocking_conditions: list[str]
    warnings: list[str]
    next_step: str = ""
    status_scope: str = "unknown"
    current_session_verified: bool = False
    validated_surface: str = "public_runtime_command_surface"


def _permissions_capability_fallback_payload(
    *,
    contract_source: str,
    contract_error: str | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "contract_source": contract_source,
        "permissions_surface": "adapter-defined",
        "permission_surface_kind": "unknown",
        "prompt_free_mode_value": None,
        "supports_runtime_permission_sync": False,
        "supports_prompt_free_mode": False,
        "prompt_free_requires_relaunch": False,
        "statusline_surface": "unknown",
        "statusline_config_surface": "unknown",
        "notify_surface": "unknown",
        "notify_config_surface": "unknown",
        "telemetry_source": "unknown",
        "telemetry_completeness": "unknown",
        "supports_usage_tokens": False,
        "supports_cost_usd": False,
        "supports_context_meter": False,
    }
    if contract_error is not None:
        payload["contract_error"] = contract_error
    return payload


def _permissions_capability_payload(runtime_name: object) -> dict[str, object]:
    """Return the structured runtime capability contract for permissions surfaces."""
    if isinstance(runtime_name, str) and runtime_name:
        try:
            from gpd.adapters.runtime_catalog import get_runtime_capabilities

            capabilities = get_runtime_capabilities(runtime_name)
        except KeyError:
            pass
        except Exception as exc:
            return _permissions_capability_fallback_payload(
                contract_source="runtime-catalog-error",
                contract_error=f"{type(exc).__name__}: {exc}",
            )
        else:
            return {
                "contract_source": "runtime-catalog",
                "permissions_surface": capabilities.permissions_surface,
                "permission_surface_kind": capabilities.permission_surface_kind,
                "prompt_free_mode_value": capabilities.prompt_free_mode_value,
                "supports_runtime_permission_sync": capabilities.supports_runtime_permission_sync,
                "supports_prompt_free_mode": capabilities.supports_prompt_free_mode,
                "prompt_free_requires_relaunch": capabilities.prompt_free_requires_relaunch,
                "statusline_surface": capabilities.statusline_surface,
                "statusline_config_surface": capabilities.statusline_config_surface,
                "notify_surface": capabilities.notify_surface,
                "notify_config_surface": capabilities.notify_config_surface,
                "telemetry_source": capabilities.telemetry_source,
                "telemetry_completeness": capabilities.telemetry_completeness,
                "supports_usage_tokens": capabilities.supports_usage_tokens,
                "supports_cost_usd": capabilities.supports_cost_usd,
                "supports_context_meter": capabilities.supports_context_meter,
            }
    return _permissions_capability_fallback_payload(contract_source="generic-fallback")


def _permissions_requested_surface(payload: dict[str, object]) -> str:
    """Return the requested user-facing permissions surface."""
    desired_mode = payload.get("desired_mode")
    if isinstance(desired_mode, str) and desired_mode == "yolo":
        return "prompt-free"
    return "ordinary-unattended"


def _permissions_status_scope(payload: dict[str, object]) -> str:
    """Return what the local CLI can actually attest to for this payload."""
    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, dict):
        return "adapter-defined"

    permissions_surface = capabilities.get("permissions_surface")
    requested_surface = _permissions_requested_surface(payload)
    if requested_surface == "prompt-free" and permissions_surface == "launch-wrapper":
        return "next-launch"
    if bool(payload.get("requires_relaunch", False)):
        return "next-launch"
    if permissions_surface == "config-file":
        return "config-only"
    if permissions_surface == "launch-wrapper":
        return "launcher-available"
    if permissions_surface == "unsupported":
        return "unsupported"
    return "adapter-defined"


def _permissions_more_permissive_than_requested(payload: dict[str, object]) -> bool:
    """Return whether local config is clearly more permissive than the requested autonomy."""
    if _permissions_requested_surface(payload) != "ordinary-unattended":
        return False

    capabilities = payload.get("capabilities")
    if not isinstance(capabilities, dict) or capabilities.get("permissions_surface") != "config-file":
        return False

    if not bool(capabilities.get("supports_prompt_free_mode", False)):
        return False

    prompt_free_mode_value = capabilities.get("prompt_free_mode_value")
    if not isinstance(prompt_free_mode_value, str) or not prompt_free_mode_value.strip():
        return False

    configured_mode = payload.get("configured_mode")
    if not isinstance(configured_mode, str):
        return False

    return configured_mode.strip() == prompt_free_mode_value.strip()


def annotate_permissions_payload(
    payload: dict[str, object],
    *,
    requested_runtime: str | None = None,
) -> dict[str, object]:
    """Attach structured capability and evidence metadata to a permissions payload."""

    annotated = dict(payload)
    runtime_name = annotated.get("runtime")
    if not isinstance(annotated.get("capabilities"), dict):
        annotated["capabilities"] = _permissions_capability_payload(
            runtime_name if isinstance(runtime_name, str) and runtime_name else requested_runtime
        )
    annotated["requested_surface"] = _permissions_requested_surface(annotated)
    if not isinstance(annotated.get("status_scope"), str) or not str(annotated.get("status_scope")).strip():
        annotated["status_scope"] = _permissions_status_scope(annotated)
    if "current_session_verified" not in annotated:
        annotated["current_session_verified"] = False
    if "more_permissive_than_requested" not in annotated:
        annotated["more_permissive_than_requested"] = _permissions_more_permissive_than_requested(annotated)
    return annotated


def normalize_permissions_readiness_payload(
    payload: dict[str, object],
    *,
    requested_runtime: str | None,
) -> dict[str, object]:
    """Normalize runtime-permissions status into unattended-readiness verdict fields.

    The returned payload preserves the public field names currently consumed by the
    CLI and unattended-readiness surfaces: ``readiness``, ``ready``,
    ``readiness_message``, ``next_step``, ``status_scope``,
    ``current_session_verified``, and ``more_permissive_than_requested``.
    """

    normalized = annotate_permissions_payload(payload, requested_runtime=requested_runtime)
    runtime_name = normalized.get("runtime")

    explicit_readiness = (
        isinstance(normalized.get("readiness"), str)
        and str(normalized.get("readiness")).strip()
        and isinstance(normalized.get("ready"), bool)
        and isinstance(normalized.get("readiness_message"), str)
        and str(normalized.get("readiness_message")).strip()
    )

    more_permissive_than_requested = bool(normalized.get("more_permissive_than_requested", False))
    if not explicit_readiness:
        ready = (
            bool(normalized.get("runtime"))
            and bool(normalized.get("target"))
            and bool(normalized.get("config_aligned", False))
            and not bool(normalized.get("requires_relaunch", False))
            and not more_permissive_than_requested
        )

        if ready:
            readiness = "ready"
            readiness_message = "Runtime permissions are ready for unattended use."
        elif bool(normalized.get("requires_relaunch", False)):
            readiness = "relaunch-required"
            readiness_message = "Runtime permissions are aligned, but the runtime must be relaunched before unattended use."
        elif more_permissive_than_requested:
            readiness = "not-ready"
            readiness_message = (
                "Runtime permissions are more permissive than the requested autonomy, so unattended readiness is not confirmed."
            )
        elif "config_aligned" in normalized:
            readiness = "not-ready"
            readiness_message = "Runtime permissions are not ready for unattended use under the requested autonomy."
        else:
            readiness = "unresolved"
            readiness_message = str(normalized.get("message") or "Runtime permissions are not ready for unattended use.")

        next_step = normalized.get("next_step")
        if not isinstance(next_step, str) or not next_step.strip():
            next_step = None
        capability_payload = normalized.get("capabilities")
        permissions_surface = (
            capability_payload.get("permissions_surface")
            if isinstance(capability_payload, dict) and isinstance(capability_payload.get("permissions_surface"), str)
            else None
        )

        if next_step is None:
            autonomy_value = normalized.get("autonomy")
            if readiness == "relaunch-required" and isinstance(runtime_name, str) and runtime_name:
                if permissions_surface == "launch-wrapper":
                    next_step = f"Exit and relaunch {runtime_name} through the GPD-managed launcher before treating unattended use as ready."
                else:
                    next_step = f"Exit and relaunch {runtime_name} before treating unattended use as ready."
            elif (
                readiness == "not-ready"
                and isinstance(runtime_name, str)
                and runtime_name
                and isinstance(autonomy_value, str)
                and autonomy_value
            ):
                permissions_sync_command = _render_contract_cli_command(
                    local_cli_permissions_sync_command(),
                    runtime_name=runtime_name,
                    autonomy=autonomy_value,
                )
                if permissions_surface == "launch-wrapper":
                    next_step = (
                        f"Use `{_doctor_active_runtime_settings_command()}` inside the runtime for guided changes, or run "
                        f"`{permissions_sync_command}` "
                        "from your normal system terminal to generate the launcher needed for the next session."
                    )
                else:
                    next_step = (
                        f"Use `{_doctor_active_runtime_settings_command()}` inside the runtime for guided changes, or run "
                        f"`{permissions_sync_command}` "
                        "from your normal system terminal."
                    )
            elif readiness == "unresolved" and requested_runtime is None:
                next_step = "Pass `--runtime <runtime>` to inspect a specific installed runtime."

        normalized["readiness"] = readiness
        normalized["ready"] = ready
        normalized["readiness_message"] = readiness_message
        normalized["next_step"] = next_step
    return normalized


def _doctor_active_virtualenv() -> bool:
    """Return whether the active interpreter is running inside a virtualenv."""
    return bool(
        getattr(sys, "real_prefix", None) is not None
        or getattr(sys, "base_prefix", sys.prefix) != sys.prefix
        or os.environ.get("VIRTUAL_ENV")
    )


def _doctor_check_python_runtime() -> HealthCheck:
    """Check the active Python interpreter and stdlib venv availability."""
    issues: list[str] = []
    warnings: list[str] = []
    active_virtualenv = _doctor_active_virtualenv()
    details = {
        "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "venv_available": True,
        "active_virtualenv": active_virtualenv,
        "python_executable": sys.executable,
    }

    if sys.version_info < (MIN_PYTHON_MAJOR, MIN_PYTHON_MINOR):
        issues.append(f"Python {sys.version_info.major}.{sys.version_info.minor} < {MIN_PYTHON_MAJOR}.{MIN_PYTHON_MINOR}")
    elif sys.version_info < RECOMMENDED_PYTHON_VERSION:
        warnings.append(f"Python >= {RECOMMENDED_PYTHON_VERSION[0]}.{RECOMMENDED_PYTHON_VERSION[1]} recommended")

    try:
        import venv as _venv  # noqa: F401
    except Exception as exc:  # pragma: no cover - stdlib import failure is rare
        details["venv_available"] = False
        issues.append(f"Standard library venv module unavailable: {exc}")

    return HealthCheck(
        status=CheckStatus.FAIL if issues else CheckStatus.WARN if warnings else CheckStatus.OK,
        label="Python Runtime",
        details=details,
        issues=issues,
        warnings=warnings,
    )


def _doctor_check_package_imports() -> HealthCheck:
    """Verify core package modules import correctly."""
    import_issues: list[str] = []
    for module in ("gpd.core.utils", "gpd.core.config", "gpd.core.state", "gpd.core.conventions"):
        try:
            __import__(module)
        except ImportError as exc:
            import_issues.append(f"Cannot import {module}: {exc}")
    return HealthCheck(
        status=CheckStatus.FAIL if import_issues else CheckStatus.OK,
        label="Package Imports",
        details={"modules_checked": 4},
        issues=import_issues,
    )


_DOCTOR_LIVE_EXECUTABLE_PROBE_TIMEOUT_SECONDS = 5
_DOCTOR_LIVE_EXECUTABLE_OPTIONAL_COMMANDS = ("pdflatex", "bibtex", "latexmk", "kpsewhich", "wolframscript")


def _doctor_run_executable_probe(argv: list[str], *, timeout_seconds: int) -> dict[str, object]:
    """Run one short-lived executable probe and capture its output."""
    started_at = time.perf_counter()
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError as exc:
        elapsed_seconds = round(time.perf_counter() - started_at, 3)
        return {
            "command": argv,
            "status": "missing",
            "elapsed_seconds": elapsed_seconds,
            "error": str(exc),
        }
    except subprocess.TimeoutExpired:
        elapsed_seconds = round(time.perf_counter() - started_at, 3)
        return {
            "command": argv,
            "status": "timeout",
            "elapsed_seconds": elapsed_seconds,
            "error": f"timed out after {timeout_seconds}s",
        }

    elapsed_seconds = round(time.perf_counter() - started_at, 3)
    stdout = (completed.stdout or "").strip()
    stderr = (completed.stderr or "").strip()
    output = stdout or stderr
    return {
        "command": argv,
        "status": "ok" if completed.returncode == 0 else "failed",
        "elapsed_seconds": elapsed_seconds,
        "returncode": completed.returncode,
        "stdout": stdout,
        "stderr": stderr,
        "output": output,
    }


def _doctor_gpd_cli_probe_command() -> list[str]:
    """Return the local command used to prove the GPD CLI can execute."""
    return [sys.executable, "-m", "gpd.cli", "--help"]


def _doctor_which(executable: str) -> str | None:
    """Resolve *executable* using PATH lookup.

    Tests patch this helper instead of ``shutil.which`` so concurrent suites do
    not share mutable stdlib state.
    """
    return shutil.which(executable)


def _doctor_check_live_executable_probes() -> HealthCheck:
    """Optionally run harmless local executable probes for live doctor feedback."""
    probe_results: list[dict[str, object]] = []
    issues: list[str] = []
    warnings: list[str] = []
    skipped: list[str] = []

    gpd_probe = _doctor_run_executable_probe(
        _doctor_gpd_cli_probe_command(),
        timeout_seconds=_DOCTOR_LIVE_EXECUTABLE_PROBE_TIMEOUT_SECONDS,
    )
    gpd_probe["label"] = "gpd-cli"
    probe_results.append(gpd_probe)
    if gpd_probe["status"] != "ok":
        issues.append(
            f"gpd-cli probe failed: {gpd_probe.get('error') or gpd_probe.get('output') or 'no output captured'}"
        )

    for executable in _DOCTOR_LIVE_EXECUTABLE_OPTIONAL_COMMANDS:
        resolved = _doctor_which(executable)
        if resolved is None:
            skipped.append(executable)
            probe_results.append(
                {
                    "label": executable,
                    "command": [executable, "--version"],
                    "status": "skipped",
                    "reason": "not found on PATH",
                }
            )
            warnings.append(f"{executable} not found on PATH")
            continue

        probe = _doctor_run_executable_probe([resolved, "--version"], timeout_seconds=_DOCTOR_LIVE_EXECUTABLE_PROBE_TIMEOUT_SECONDS)
        probe["label"] = executable
        probe["resolved_path"] = resolved
        probe_results.append(probe)
        if probe["status"] != "ok":
            warnings.append(
                f"{executable} probe failed: {probe.get('error') or probe.get('output') or 'no output captured'}"
            )

    details: dict[str, object] = {
        "enabled": True,
        "timeout_seconds": _DOCTOR_LIVE_EXECUTABLE_PROBE_TIMEOUT_SECONDS,
        "mandatory_probe": "python -m gpd.cli --help",
        "optional_commands": list(_DOCTOR_LIVE_EXECUTABLE_OPTIONAL_COMMANDS),
        "probe_count": len(probe_results),
        "probed": probe_results,
        "skipped": skipped,
    }
    return HealthCheck(
        status=CheckStatus.FAIL if issues else CheckStatus.WARN if warnings else CheckStatus.OK,
        label="Live Executable Probes",
        details=details,
        issues=issues,
        warnings=warnings,
    )


def _nearest_existing_ancestor(path: Path) -> Path:
    """Return the nearest existing ancestor for *path* or the filesystem root."""
    candidate = path.expanduser().resolve(strict=False)
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def _doctor_normalize_runtime(runtime: str) -> str:
    """Resolve a runtime alias to its canonical runtime id."""
    from gpd.adapters.runtime_catalog import normalize_runtime_name

    normalized = normalize_runtime_name(runtime)
    if normalized is None:
        raise ValidationError(f"Unknown runtime {runtime!r}")
    return normalized


def _doctor_check_runtime_launcher(runtime: str) -> HealthCheck:
    """Verify the selected runtime launcher is available on PATH."""
    from gpd.adapters.runtime_catalog import get_runtime_descriptor

    descriptor = get_runtime_descriptor(runtime)
    try:
        launch_argv = shlex.split(descriptor.launch_command)
    except ValueError:
        launch_argv = []
    launch_executable = launch_argv[0] if launch_argv else descriptor.launch_command.strip()
    launch_path = _doctor_which(launch_executable) if launch_executable else None
    issues = [] if launch_path else [f"{launch_executable or descriptor.launch_command} not found on PATH"]
    return HealthCheck(
        status=CheckStatus.OK if launch_path else CheckStatus.FAIL,
        label="Runtime Launcher",
        details={
            "runtime": descriptor.runtime_name,
            "display_name": descriptor.display_name,
            "launch_command": descriptor.launch_command,
            "launch_executable": launch_executable or None,
            "launcher_path": launch_path,
        },
        issues=issues,
        warnings=[] if launch_path else [f"Install or expose {descriptor.display_name} before running GPD there."],
    )


def _doctor_active_runtime_settings_command(*, cwd: Path | None = None) -> str:
    """Return the active runtime settings command, or a runtime-surface-neutral fallback."""
    return format_active_runtime_command(
        "settings",
        cwd=cwd,
        fallback="the active runtime's `settings` command",
    )


def _doctor_runtime_install_issue(assessment: InstallTargetAssessment, runtime: str | None) -> str | None:
    """Return a user-facing issue for a non-ready install assessment."""
    if assessment.state == "owned_incomplete":
        missing = ", ".join(f"`{item}`" for item in assessment.missing_install_artifacts) or "required install artifacts"
        return f"{assessment.config_dir} has an incomplete GPD install; missing artifacts: {missing}."
    if assessment.state == "foreign_runtime":
        owner = f"`{assessment.manifest_runtime}`" if assessment.manifest_runtime else "another runtime"
        runtime_label = f"`{runtime}`" if runtime else "the selected runtime"
        return f"{assessment.config_dir} belongs to {owner}, not {runtime_label}."
    if assessment.state == "untrusted_manifest":
        return f"{assessment.config_dir} has an untrusted GPD manifest and cannot be treated as a ready install target."
    return None


def _doctor_check_runtime_target(target_dir: Path, *, runtime: str | None = None) -> HealthCheck:
    """Verify the selected install target can be created or written."""
    resolved = target_dir.expanduser().resolve(strict=False)
    details: dict[str, object] = {
        "target": str(resolved),
        "exists": resolved.exists(),
    }
    issues: list[str] = []
    warnings: list[str] = []

    if resolved.exists() and not resolved.is_dir():
        issues.append(f"{resolved} exists but is not a directory")
        details["probe_dir"] = str(resolved)
        return HealthCheck(status=CheckStatus.FAIL, label="Runtime Config Target", details=details, issues=issues)

    probe_dir = resolved if resolved.exists() else _nearest_existing_ancestor(resolved.parent)
    details["probe_dir"] = str(probe_dir)
    if not probe_dir.exists():
        issues.append(f"No existing parent directory found for {resolved}")
    elif not probe_dir.is_dir():
        issues.append(f"{probe_dir} is not a directory")
    elif not os.access(probe_dir, os.W_OK | os.X_OK):
        issues.append(f"{probe_dir} is not writable")
    elif not resolved.exists():
        warnings.append(f"{resolved} does not exist yet; GPD will create it during install.")

    assessment = assess_install_target(resolved, expected_runtime=runtime)
    details.update(
        {
            "install_state": assessment.state,
            "manifest_state": assessment.manifest_state,
            "manifest_runtime": assessment.manifest_runtime,
            "has_managed_markers": assessment.has_managed_markers,
            "missing_install_artifacts": list(assessment.missing_install_artifacts),
        }
    )

    install_issue = _doctor_runtime_install_issue(assessment, runtime)
    if install_issue is not None:
        issues.append(install_issue)

    return HealthCheck(
        status=CheckStatus.FAIL if issues else CheckStatus.OK,
        label="Runtime Config Target",
        details=details,
        issues=issues,
        warnings=warnings,
    )


def _doctor_check_bootstrap_network_access() -> HealthCheck:
    """Provide manual guidance for bootstrap/update network readiness."""
    return HealthCheck(
        status=CheckStatus.OK,
        label="Bootstrap Network Access",
        details={
            "verification": "manual",
            "note": "doctor does not perform live outbound network probes",
        },
        warnings=[
            "Bootstrap/update network reachability is not verified automatically; confirm outbound access if installs or updates fail."
        ],
    )


def _doctor_check_provider_auth(runtime: str, launch_command: str, target_dir: Path) -> HealthCheck:
    """Provide non-blocking guidance for provider authentication readiness."""
    return HealthCheck(
        status=CheckStatus.OK,
        label="Provider/Auth Guidance",
        details={
            "runtime": runtime,
            "launch_command": launch_command,
            "target": str(target_dir.expanduser().resolve(strict=False)),
            "verification": "manual",
        },
        warnings=[
            (
                f"GPD does not verify provider credentials automatically for {runtime}. "
                f"Launch `{launch_command}` once and confirm your account or API provider is configured."
            )
        ],
    )


def _doctor_check_latex_toolchain() -> HealthCheck:
    """Report LaTeX toolchain availability as an advisory capability check."""
    try:
        from gpd.mcp.paper.compiler import detect_latex_toolchain
    except Exception as exc:  # pragma: no cover - import failure is environment specific
        return HealthCheck(
            status=CheckStatus.WARN,
            label="LaTeX Toolchain",
            details={
                "compiler": "pdflatex",
                "available": False,
                "compiler_available": False,
                "full_toolchain_available": False,
                "compiler_path": None,
                "distribution": None,
                "latexmk_available": None,
                "bibtex_available": None,
                "bibliography_support_available": False,
                "kpsewhich_available": None,
                "readiness_state": "blocked",
                "message": "Could not load LaTeX detection helpers.",
                "warnings": [f"Could not load LaTeX detection helpers: {exc}"],
                "paper_build_ready": False,
                "arxiv_submission_ready": False,
                "missing_components": [],
            },
            warnings=[f"Could not load LaTeX detection helpers: {exc}"],
        )

    latex_status = detect_latex_toolchain()
    capability_details = latex_status.model_dump(mode="python")
    compiler_available = bool(capability_details["compiler_available"])
    latexmk_available = bool(capability_details["latexmk_available"])
    bibtex_available = bool(capability_details["bibtex_available"])
    kpsewhich_available = bool(capability_details["kpsewhich_available"])
    full_toolchain_available = bool(capability_details["full_toolchain_available"])
    missing_components: list[str] = []
    if not compiler_available:
        missing_components.append(str(capability_details.get("compiler") or "pdflatex"))
    if compiler_available and not latexmk_available:
        missing_components.append("latexmk")
    if compiler_available and not bibtex_available:
        missing_components.append("bibtex")
    if compiler_available and not kpsewhich_available:
        missing_components.append("kpsewhich")

    warnings = list(capability_details.get("warnings", [])) if isinstance(capability_details.get("warnings"), list) else []
    if compiler_available and missing_components:
        missing_text = ", ".join(f"`{component}`" for component in missing_components)
        warnings.append(
            "LaTeX compiler found, but the toolchain is partial: "
            f"missing {missing_text}. Generic doctor only reports `OK` when the full toolchain is present."
        )

    return HealthCheck(
        status=CheckStatus.OK if full_toolchain_available else CheckStatus.WARN,
        label="LaTeX Toolchain",
        details={
            **capability_details,
            "missing_components": missing_components,
        },
        warnings=warnings,
    )


def _doctor_check_workflow_presets(*, latex_check: HealthCheck, base_ready: bool) -> HealthCheck:
    """Report readiness for workflow presets backed by known checks."""
    latex_capability = dict(latex_check.details)
    if "warnings" not in latex_capability:
        latex_capability["warnings"] = list(latex_check.warnings)

    details = resolve_workflow_preset_readiness(base_ready=base_ready, latex_capability=latex_capability)
    capability_details = details.get("latex_capability")
    compiler_ready = (
        bool(capability_details.get("compiler_available", capability_details.get("available", False)))
        if isinstance(capability_details, dict)
        else False
    )
    bibliography_support_ready = (
        bool(capability_details.get("bibliography_support_available", False))
        if isinstance(capability_details, dict)
        else False
    )
    arxiv_submission_ready = (
        bool(capability_details.get("arxiv_submission_ready", False)) if isinstance(capability_details, dict) else False
    )
    warnings: list[str] = []
    if not base_ready:
        warnings.append("Workflow preset readiness is blocked until the base runtime-readiness failures are fixed.")
    elif not compiler_ready:
        warnings.append(
            "Publication / manuscript and full research presets are degraded without a LaTeX compiler: "
            "`write-paper` and `peer-review` remain usable, but `paper-build` and `arxiv-submission` stay blocked."
        )
    elif not bibliography_support_ready:
        warnings.append(
            "Publication / manuscript and full research presets are degraded without bibliography tooling: "
            "`write-paper` and `peer-review` remain usable, while `paper-build` and `arxiv-submission` may fail for manuscripts that require bibliography processing."
        )
    elif not arxiv_submission_ready:
        warnings.append(
            "Publication / manuscript and full research presets are degraded without arxiv-submission support: "
            "`paper-build` remains usable, but `arxiv-submission` stays blocked until TeX resource checks pass."
        )

    status = CheckStatus.OK if details["degraded"] == 0 and details["blocked"] == 0 else CheckStatus.WARN
    return HealthCheck(
        status=status,
        label="Workflow Presets",
        details=details,
        warnings=warnings,
    )


def resolve_doctor_runtime_readiness(
    runtime: str,
    *,
    install_scope: str | None = None,
    target_dir: str | Path | None = None,
    cwd: Path | None = None,
) -> DoctorRuntimeReadinessContext:
    """Normalize runtime readiness inputs to one canonical runtime/scope/target tuple."""
    from gpd.adapters import get_adapter

    normalized_runtime = _doctor_normalize_runtime(runtime)
    normalized_scope_input = install_scope.lower() if isinstance(install_scope, str) else None
    if normalized_scope_input not in {None, "local", "global"}:
        raise ValidationError(
            f"Unsupported install_scope {install_scope!r}; expected 'local' or 'global'."
        )

    adapter = get_adapter(normalized_runtime)
    workspace_root = cwd or Path.cwd()
    normalized_scope = normalized_scope_input
    if target_dir is not None:
        explicit_target = Path(target_dir).expanduser()
        if explicit_target.is_absolute():
            resolved_target = explicit_target.resolve(strict=False)
        else:
            resolved_target = (workspace_root / explicit_target).resolve(strict=False)
    else:
        resolved_target = adapter.resolve_target_dir(normalized_scope == "global", workspace_root)
    if normalized_scope is None and target_dir is None:
        normalized_scope = "local"

    return DoctorRuntimeReadinessContext(
        runtime=normalized_runtime,
        install_scope=normalized_scope,
        target=resolved_target,
        launch_command=adapter.launch_command,
    )


def extract_doctor_blockers(report: DoctorReport) -> list[HealthCheck]:
    """Return the blocking doctor checks for install-gating decisions."""
    return [check for check in report.checks if check.status == CheckStatus.FAIL]


def extract_doctor_advisories(report: DoctorReport) -> list[str]:
    """Return unique warning/issue messages from non-blocking doctor checks."""
    advisories: list[str] = []
    seen: set[str] = set()
    for check in report.checks:
        if check.status == CheckStatus.FAIL:
            continue
        for message in [*check.issues, *check.warnings]:
            if message not in seen:
                seen.add(message)
                advisories.append(message)
    return advisories


def runtime_doctor_hint(runtime_name: str, *, install_scope: str, target_dir: Path | None) -> str:
    """Build the exact doctor command that inspects one install target."""
    template = local_cli_doctor_global_command() if install_scope == "global" else local_cli_doctor_local_command()
    return _render_contract_cli_command(template, runtime_name=runtime_name, target_dir=target_dir)


def build_unattended_readiness_result(
    *,
    runtime: str,
    autonomy: str | None,
    install_scope: str,
    target_dir: Path | None,
    doctor_report: DoctorReport,
    permissions_payload: dict[str, object],
    live_executable_probes: bool,
    validated_surface: str = "public_runtime_command_surface",
) -> UnattendedReadinessResult:
    """Compose doctor and permissions status into one unattended-readiness verdict."""
    normalized_permissions = normalize_permissions_readiness_payload(
        permissions_payload,
        requested_runtime=runtime,
    )
    blocker_messages: list[str] = []
    seen_blockers: set[str] = set()
    for check in extract_doctor_blockers(doctor_report):
        messages = [*check.issues, *check.warnings]
        if not messages:
            messages = [f"{check.label}: readiness check failed."]
        for message in messages:
            if message not in seen_blockers:
                seen_blockers.add(message)
                blocker_messages.append(message)

    advisory_messages = extract_doctor_advisories(doctor_report)
    readiness = str(normalized_permissions.get("readiness") or "unresolved")
    permissions_ready = bool(normalized_permissions.get("ready", False))
    readiness_message = str(
        normalized_permissions.get("readiness_message") or "Runtime permissions are not ready for unattended use."
    )

    doctor_detail = "Runtime readiness checks passed."
    if blocker_messages:
        doctor_detail = "; ".join(blocker_messages[:3])
    elif advisory_messages:
        doctor_detail = f"Runtime readiness checks passed with {len(advisory_messages)} advisory(s)."

    checks = [
        UnattendedReadinessCheck(
            name="permissions",
            passed=permissions_ready,
            blocking=not permissions_ready,
            detail=readiness_message,
        ),
        UnattendedReadinessCheck(
            name="doctor",
            passed=not blocker_messages,
            blocking=bool(blocker_messages),
            detail=doctor_detail,
        ),
    ]

    blocking_conditions: list[str] = []
    if not permissions_ready and readiness_message not in blocking_conditions:
        blocking_conditions.append(readiness_message)
    for message in blocker_messages:
        if message not in blocking_conditions:
            blocking_conditions.append(message)

    warnings: list[str] = []
    for message in advisory_messages:
        if message not in warnings:
            warnings.append(message)

    next_step = str(normalized_permissions.get("next_step") or "").strip()
    if not next_step and blocker_messages:
        next_step = (
            f"Run `{runtime_doctor_hint(runtime, install_scope=install_scope, target_dir=target_dir)}` "
            "to inspect and clear the blocking runtime-readiness issues."
        )

    target = normalized_permissions.get("target")
    if not isinstance(target, str) or not target.strip():
        target = str(target_dir) if target_dir is not None else getattr(doctor_report, "target", None)

    resolved_autonomy = normalized_permissions.get("autonomy")
    autonomy_value = str(resolved_autonomy) if isinstance(resolved_autonomy, str) and resolved_autonomy else (autonomy or "")
    passed = permissions_ready and not blocker_messages
    return UnattendedReadinessResult(
        runtime=runtime,
        autonomy=autonomy_value,
        install_scope=install_scope,
        target=target,
        readiness=readiness,
        ready=permissions_ready,
        passed=passed,
        readiness_message=readiness_message,
        live_executable_probes=live_executable_probes,
        checks=checks,
        blocking_conditions=blocking_conditions,
        warnings=warnings,
        next_step=next_step,
        status_scope=str(normalized_permissions.get("status_scope") or "unknown"),
        current_session_verified=bool(normalized_permissions.get("current_session_verified", False)),
        validated_surface=validated_surface,
    )


def run_doctor(
    specs_dir: Path | None = None,
    version: str | None = None,
    *,
    runtime: str | None = None,
    install_scope: str | None = None,
    target_dir: str | Path | None = None,
    cwd: Path | None = None,
    live_executable_probes: bool = False,
) -> DoctorReport:
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
    if runtime is None and (install_scope is not None or target_dir is not None):
        raise ValidationError("install_scope and target_dir require runtime to be set.")
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

        # 6. Python runtime + venv
        checks.append(_doctor_check_python_runtime())

        # 7. Package importability
        checks.append(_doctor_check_package_imports())

        if live_executable_probes:
            checks.append(_doctor_check_live_executable_probes())

        resolved_target_str: str | None = None
        normalized_scope: str | None = None
        normalized_runtime: str | None = None
        if runtime is not None:
            runtime_context = resolve_doctor_runtime_readiness(
                runtime,
                install_scope=install_scope,
                target_dir=target_dir,
                cwd=cwd,
            )
            normalized_runtime = runtime_context.runtime
            normalized_scope = runtime_context.install_scope
            resolved_target = runtime_context.target
            resolved_target_str = str(resolved_target)
            checks.append(_doctor_check_runtime_launcher(normalized_runtime))
            checks.append(_doctor_check_runtime_target(resolved_target, runtime=normalized_runtime))
            checks.append(_doctor_check_bootstrap_network_access())
            checks.append(
                _doctor_check_provider_auth(
                    normalized_runtime,
                    runtime_context.launch_command,
                    resolved_target,
                )
            )
            latex_check = _doctor_check_latex_toolchain()
            checks.append(latex_check)
            base_ready = not any(check.status == CheckStatus.FAIL for check in checks)
            checks.append(_doctor_check_workflow_presets(latex_check=latex_check, base_ready=base_ready))

        # Version (passed as parameter, no gpd import needed)

        ok_count = sum(1 for c in checks if c.status == CheckStatus.OK)
        warn_count = sum(1 for c in checks if c.status == CheckStatus.WARN)
        fail_count = sum(1 for c in checks if c.status == CheckStatus.FAIL)
        overall = CheckStatus.FAIL if fail_count > 0 else CheckStatus.WARN if warn_count > 0 else CheckStatus.OK

        logger.info("doctor_complete", extra={"overall": overall, "version": version})

        return DoctorReport(
            overall=overall,
            version=version,
            mode="runtime-readiness" if runtime is not None else "installation",
            runtime=normalized_runtime,
            install_scope=normalized_scope,
            target=resolved_target_str,
            live_executable_probes=live_executable_probes,
            summary=HealthSummary(ok=ok_count, warn=warn_count, fail=fail_count, total=len(checks)),
            checks=checks,
        )


__all__ = [
    "CheckStatus",
    "DoctorReport",
    "DoctorRuntimeReadinessContext",
    "HealthCheck",
    "HealthReport",
    "HealthSummary",
    "annotate_permissions_payload",
    "normalize_permissions_readiness_payload",
    "UnattendedReadinessCheck",
    "UnattendedReadinessResult",
    "build_unattended_readiness_result",
    "extract_doctor_advisories",
    "extract_doctor_blockers",
    "resolve_doctor_runtime_readiness",
    "runtime_doctor_hint",
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
