"""Command functions — pure logic with I/O separation.

All functions take state dicts / Path arguments — callers handle persistence.
Layer 1 code: stdlib + pathlib + re + pydantic only.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, date, datetime
from functools import cmp_to_key
from pathlib import Path

from pydantic import BaseModel, Field

from gpd.core.constants import (
    PLAN_SUFFIX,
    PLANNING_DIR_NAME,
    REQUIRED_RETURN_FIELDS,
    SUMMARY_SUFFIX,
    VALID_RETURN_STATUSES,
    VERIFICATION_SUFFIX,
)
from gpd.core.errors import ValidationError
from gpd.core.frontmatter import FrontmatterParseError, extract_frontmatter, splice_frontmatter
from gpd.core.observability import instrument_gpd_function
from gpd.core.utils import (
    atomic_write,
    compare_phase_numbers,
    generate_slug,
    is_phase_complete,
    phase_normalize,
    safe_read_file,
)

__all__ = [
    "REQUIRED_RETURN_FIELDS",
    "VALID_RETURN_STATUSES",
    "CurrentTimestampResult",
    "DecisionEntry",
    "GenerateSlugResult",
    "HistoryDigestResult",
    "PhaseDigest",
    "RegressionCheckResult",
    "RegressionIssue",
    "ScaffoldResult",
    "SummaryDecision",
    "SummaryExtractResult",
    "TodoCompleteResult",
    "ValidateReturnResult",
    "VerifyPathResult",
    "cmd_current_timestamp",
    "cmd_generate_slug",
    "cmd_history_digest",
    "cmd_regression_check",
    "cmd_scaffold",
    "cmd_summary_extract",
    "cmd_todo_complete",
    "cmd_validate_return",
    "cmd_verify_path_exists",
]

# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


class CurrentTimestampResult(BaseModel):
    timestamp: str


class GenerateSlugResult(BaseModel):
    slug: str


class VerifyPathResult(BaseModel):
    exists: bool
    type: str | None = None


class TodoCompleteResult(BaseModel):
    completed: bool
    file: str
    date: str


class ScaffoldResult(BaseModel):
    created: bool
    path: str | None = None
    directory: str | None = None
    reason: str | None = None


class SummaryDecision(BaseModel):
    summary: str
    rationale: str | None = None


class SummaryExtractResult(BaseModel):
    path: str
    one_liner: str | None = None
    key_files: list[str] = Field(default_factory=list)
    methods_added: list[str] = Field(default_factory=list)
    patterns: list[str] = Field(default_factory=list)
    decisions: list[SummaryDecision] = Field(default_factory=list)
    affects: list[str] = Field(default_factory=list)
    conventions: object = None
    key_results: str | None = None
    equations: str | None = None


class DecisionEntry(BaseModel):
    phase: str
    decision: str


class PhaseDigest(BaseModel):
    name: str
    provides: list[str] = Field(default_factory=list)
    affects: list[str] = Field(default_factory=list)
    patterns: list[str] = Field(default_factory=list)


class HistoryDigestResult(BaseModel):
    phases: dict[str, PhaseDigest] = Field(default_factory=dict)
    decisions: list[DecisionEntry] = Field(default_factory=list)
    methods: list[str] = Field(default_factory=list)


class RegressionIssue(BaseModel):
    type: str
    symbol: str | None = None
    definitions: list[dict[str, str]] | None = None
    phase: str | None = None
    file: str | None = None
    status: str | None = None
    score: str | None = None
    gap_count: int | None = None
    error: str | None = None


class RegressionCheckResult(BaseModel):
    passed: bool
    issues: list[RegressionIssue] = Field(default_factory=list)
    phases_checked: int = 0


class ValidateReturnResult(BaseModel):
    passed: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    fields: dict[str, str] = Field(default_factory=dict)
    warning_count: int = 0


# ---------------------------------------------------------------------------
# Implementations
# ---------------------------------------------------------------------------


@instrument_gpd_function("commands.current_timestamp")
def cmd_current_timestamp(fmt: str = "full") -> CurrentTimestampResult:
    """Return current timestamp in the requested format.

    Formats:
        date     — YYYY-MM-DD
        filename — YYYY-MM-DDTHH-MM-SS (colons replaced for filesystem safety)
        full     — ISO 8601 with timezone
    """
    now = datetime.now(UTC)

    if fmt == "date":
        result = now.date().isoformat()
    elif fmt == "filename":
        result = now.isoformat().replace(":", "-").split(".")[0]
    else:
        result = now.isoformat()

    return CurrentTimestampResult(timestamp=result)


@instrument_gpd_function("commands.generate_slug")
def cmd_generate_slug(text: str) -> GenerateSlugResult:
    """Generate a URL-safe slug from *text*.

    Raises:
        ValidationError: If *text* is empty.
    """
    if not text:
        raise ValidationError("text required for slug generation")

    slug = generate_slug(text)
    if slug is None:
        raise ValidationError("text produced empty slug")

    return GenerateSlugResult(slug=slug)


@instrument_gpd_function("commands.verify_path_exists")
def cmd_verify_path_exists(cwd: Path, target_path: str) -> VerifyPathResult:
    """Verify whether *target_path* exists (relative to *cwd* or absolute).

    Raises:
        ValidationError: If *target_path* is empty.
    """
    if not target_path:
        raise ValidationError("path required for verification")

    full = Path(target_path) if Path(target_path).is_absolute() else cwd / target_path

    if not full.exists():
        return VerifyPathResult(exists=False, type=None)

    if full.is_dir():
        path_type = "directory"
    elif full.is_file():
        path_type = "file"
    else:
        path_type = "other"

    return VerifyPathResult(exists=True, type=path_type)


@instrument_gpd_function("commands.todo_complete")
def cmd_todo_complete(cwd: Path, filename: str) -> TodoCompleteResult:
    """Move a todo from pending/ to done/, adding a completion timestamp.

    Uses atomic write + rename to prevent duplication on crash.

    Raises:
        ValidationError: If *filename* is empty or the todo is not found.
        FrontmatterParseError: If the todo has malformed YAML frontmatter.
    """
    if not filename:
        raise ValidationError("filename required for todo complete")

    pending_dir = cwd / PLANNING_DIR_NAME / "todos" / "pending"
    done_dir = cwd / PLANNING_DIR_NAME / "todos" / "done"
    source_path = pending_dir / filename

    if not source_path.exists():
        raise ValidationError(f"Todo not found: {filename}")

    done_dir.mkdir(parents=True, exist_ok=True)

    content = source_path.read_text(encoding="utf-8")
    today = date.today().isoformat()

    meta, _body = extract_frontmatter(content)
    meta["completed"] = today
    content = splice_frontmatter(content, meta)

    dest_path = done_dir / filename
    atomic_write(dest_path, content)

    source_path.unlink(missing_ok=True)

    return TodoCompleteResult(completed=True, file=filename, date=today)


def _find_phase_dir(cwd: Path, phase: str) -> Path | None:
    """Locate a phase directory by number. Returns the absolute path or None."""
    phases_dir = cwd / PLANNING_DIR_NAME / "phases"
    if not phases_dir.is_dir():
        return None

    padded = phase_normalize(phase)

    for entry in sorted(phases_dir.iterdir()):
        if not entry.is_dir():
            continue
        m = re.match(r"^(\d+(?:\.\d+)*)", entry.name)
        if m and phase_normalize(m.group(1)) == padded:
            return entry
    return None


def _phase_name_from_dir(dir_name: str) -> str:
    """Extract a human-readable name from a phase directory name like '03-core-work'."""
    parts = dir_name.split("-", 1)
    if len(parts) > 1:
        return parts[1].replace("-", " ")
    return "Unknown"


@instrument_gpd_function("commands.scaffold")
def cmd_scaffold(
    cwd: Path,
    scaffold_type: str,
    *,
    phase: str | None = None,
    name: str | None = None,
) -> ScaffoldResult:
    """Create a scaffold file (context, validation, verification) or phase directory.

    Scaffold types:
        context      — CONTEXT.md in the phase directory
        validation   — VALIDATION.md in the phase directory
        verification — VERIFICATION.md in the phase directory
        phase-dir    — Create a new phase directory under .planning/phases/

    Raises:
        ValidationError: If required args are missing or type is unknown.
    """
    padded = phase_normalize(phase) if phase else "00"
    today = date.today().isoformat()

    if scaffold_type == "phase-dir":
        if not phase or not name:
            raise ValidationError("phase and name required for phase-dir scaffold")
        slug = generate_slug(name) or name.lower().strip()
        dir_name = f"{padded}-{slug}"
        phases_parent = cwd / PLANNING_DIR_NAME / "phases"
        phases_parent.mkdir(parents=True, exist_ok=True)
        dir_path = phases_parent / dir_name
        dir_path.mkdir(parents=True, exist_ok=True)
        return ScaffoldResult(
            created=True,
            directory=f".planning/phases/{dir_name}",
            path=str(dir_path),
        )

    # For non-phase-dir types, require a phase that exists on disk
    phase_dir = _find_phase_dir(cwd, phase) if phase else None
    if phase_dir is None:
        if phase:
            raise ValidationError(f"Phase {phase} directory not found")
        raise ValidationError(f'--phase is required for scaffold type "{scaffold_type}"')

    phase_name = name or _phase_name_from_dir(phase_dir.name) or "Unnamed"

    if scaffold_type == "context":
        file_path = phase_dir / f"{padded}-CONTEXT.md"
        content = (
            f'---\nphase: "{padded}"\nname: "{phase_name}"\ncreated: {today}\n---\n\n'
            f"# Phase {phase}: {phase_name} \u2014 Context\n\n"
            f"## Decisions\n\n_Decisions will be captured during /gpd:discuss-phase {phase}_\n\n"
            "## Discretion Areas\n\n_Areas where the executor can use judgment_\n\n"
            "## Deferred Ideas\n\n_Ideas to consider later_\n"
        )
    elif scaffold_type == "validation":
        file_path = phase_dir / f"{padded}-VALIDATION.md"
        content = (
            f'---\nphase: "{padded}"\nname: "{phase_name}"\ncreated: {today}\nstatus: pending\n---\n\n'
            f"# Phase {phase}: {phase_name} \u2014 Physics Validation\n\n"
            "## Test Results\n\n| # | Test | Status | Notes |\n|---|------|--------|-------|\n\n"
            "## Summary\n\n_Pending validation_\n"
        )
    elif scaffold_type == "verification":
        file_path = phase_dir / f"{padded}-VERIFICATION.md"
        content = (
            f'---\nphase: "{padded}"\nname: "{phase_name}"\ncreated: {today}\nstatus: pending\n---\n\n'
            f"# Phase {phase}: {phase_name} \u2014 Verification\n\n"
            "## Goal-Backward Verification\n\n**Phase Goal:** [From ROADMAP.md]\n\n"
            "## Checks\n\n| # | Requirement | Status | Evidence |\n|---|------------|--------|----------|\n\n"
            "## Result\n\n_Pending verification_\n"
        )
    else:
        raise ValidationError(
            f"Unknown scaffold type: {scaffold_type}. Available: context, validation, verification, phase-dir"
        )

    if file_path.exists():
        return ScaffoldResult(created=False, path=str(file_path), reason="already_exists")

    atomic_write(file_path, content)
    rel_path = str(file_path.relative_to(cwd))
    return ScaffoldResult(created=True, path=rel_path)


def _parse_decisions(decisions_list: object) -> list[SummaryDecision]:
    """Parse key-decisions from frontmatter into structured format."""
    if not decisions_list or not isinstance(decisions_list, list):
        return []

    results: list[SummaryDecision] = []
    for d in decisions_list:
        if isinstance(d, dict):
            entries = list(d.items())
            if len(entries) == 1:
                results.append(
                    SummaryDecision(
                        summary=str(entries[0][0]).strip(),
                        rationale=str(entries[0][1]).strip(),
                    )
                )
            else:
                results.append(SummaryDecision(summary=json.dumps(d), rationale=None))
        else:
            s = str(d)
            colon_idx = s.find(":")
            if colon_idx > 0:
                results.append(
                    SummaryDecision(
                        summary=s[:colon_idx].strip(),
                        rationale=s[colon_idx + 1 :].strip(),
                    )
                )
            else:
                results.append(SummaryDecision(summary=s, rationale=None))
    return results


def _extract_section(content: str, heading: str) -> str | None:
    """Extract a markdown section by ## heading name."""
    escaped = re.escape(heading)
    header_re = re.compile(rf"^##\s+{escaped}\s*\n", re.MULTILINE)
    hm = header_re.search(content)
    if not hm:
        return None
    rest = content[hm.end() :]
    next_heading = re.search(r"^##\s", rest, re.MULTILINE)
    return rest[: next_heading.start()].strip() if next_heading else rest.strip()


_BODY_ONE_LINER_RE = re.compile(r"^---[\s\S]*?---\s*(?:#[^\n]*\n\s*)?\*\*(.+?)\*\*", re.MULTILINE)


@instrument_gpd_function("commands.summary_extract")
def cmd_summary_extract(
    cwd: Path,
    summary_path: str,
    fields: list[str] | None = None,
) -> SummaryExtractResult | dict[str, object]:
    """Extract structured data from a SUMMARY.md file.

    Parses frontmatter and body sections (Key Results, Equations Derived).
    If *fields* is provided, returns only those fields.

    Raises:
        ValidationError: If *summary_path* is empty or file not found.
    """
    if not summary_path:
        raise ValidationError("summary-path required for summary-extract")

    full_path = cwd / summary_path
    content = safe_read_file(full_path)
    if content is None:
        raise ValidationError(f"File not found: {summary_path}")

    try:
        fm, _body = extract_frontmatter(content)
    except FrontmatterParseError as exc:
        raise ValidationError(f"YAML parse error in {summary_path}: {exc}") from exc

    # Extract one-liner: frontmatter first, fall back to body bold text
    one_liner = fm.get("one-liner")
    if not one_liner:
        body_match = _BODY_ONE_LINER_RE.search(content)
        if body_match:
            one_liner = body_match.group(1)

    full_result = SummaryExtractResult(
        path=summary_path,
        one_liner=one_liner,
        key_files=fm.get("key-files", []) if isinstance(fm.get("key-files"), list) else [],
        methods_added=((fm.get("methods", {}) or {}).get("added", []) if isinstance(fm.get("methods"), dict) else []),
        patterns=fm.get("patterns-established", []) if isinstance(fm.get("patterns-established"), list) else [],
        decisions=_parse_decisions(fm.get("key-decisions")),
        affects=fm.get("affects", []) if isinstance(fm.get("affects"), list) else [],
        conventions=fm.get("conventions"),
        key_results=_extract_section(content, "Key Results"),
        equations=_extract_section(content, "Equations Derived"),
    )

    if fields:
        result_dict = full_result.model_dump()
        filtered: dict[str, object] = {"path": summary_path}
        for f in fields:
            if f in result_dict:
                filtered[f] = result_dict[f]
        return filtered

    return full_result


def _merge_list_or_string(target_set: set[str], value: object) -> None:
    """Merge a value that may be a list of strings or a single string into a set."""
    if isinstance(value, list):
        for item in value:
            target_set.add(str(item))
    elif isinstance(value, str):
        target_set.add(value)


@instrument_gpd_function("commands.history_digest")
def cmd_history_digest(cwd: Path) -> HistoryDigestResult:
    """Build a digest of project history from phase SUMMARY files.

    Scans .planning/phases/*/SUMMARY.md for frontmatter fields:
    dependency-graph.provides, dependency-graph.affects, patterns-established,
    key-decisions, and methods.added.
    """
    phases_dir = cwd / PLANNING_DIR_NAME / "phases"
    methods_set: set[str] = set()
    phase_sets: dict[str, dict[str, set[str]]] = {}
    digest = HistoryDigestResult()

    if not phases_dir.is_dir():
        return digest

    phase_dirs = sorted(
        [d for d in phases_dir.iterdir() if d.is_dir()],
        key=cmp_to_key(lambda a, b: compare_phase_numbers(a.name, b.name)),
    )

    for dir_path in phase_dirs:
        dir_name = dir_path.name
        summaries = [
            f for f in dir_path.iterdir() if f.is_file() and (f.name.endswith("-SUMMARY.md") or f.name == "SUMMARY.md")
        ]

        for summary_file in summaries:
            content = safe_read_file(summary_file)
            if content is None:
                continue
            try:
                fm, _body = extract_frontmatter(content)
            except FrontmatterParseError:
                continue

            raw_phase = fm.get("phase", dir_name.split("-")[0])
            phase_match = re.match(r"^(\d+(?:\.\d+)*)", str(raw_phase))
            phase_num = phase_match.group(1) if phase_match else str(raw_phase)

            if phase_num not in phase_sets:
                phase_sets[phase_num] = {
                    "provides": set(),
                    "affects": set(),
                    "patterns": set(),
                }
                phase_display = fm.get("name") or _phase_name_from_dir(dir_name) or "Unknown"
                digest.phases[phase_num] = PhaseDigest(name=phase_display)

            # Merge provides
            dep_graph = fm.get("dependency-graph")
            provides = (dep_graph.get("provides") if isinstance(dep_graph, dict) else None) or fm.get("provides")
            _merge_list_or_string(phase_sets[phase_num]["provides"], provides)

            # Merge affects
            affects = (dep_graph.get("affects") if isinstance(dep_graph, dict) else None) or fm.get("affects")
            _merge_list_or_string(phase_sets[phase_num]["affects"], affects)

            # Merge patterns
            _merge_list_or_string(phase_sets[phase_num]["patterns"], fm.get("patterns-established"))

            # Merge decisions
            key_decisions = fm.get("key-decisions")
            if isinstance(key_decisions, list):
                for d in key_decisions:
                    digest.decisions.append(DecisionEntry(phase=phase_num, decision=str(d)))
            elif isinstance(key_decisions, str):
                digest.decisions.append(DecisionEntry(phase=phase_num, decision=key_decisions))

            # Merge methods
            methods = fm.get("methods")
            methods_added = methods.get("added") if isinstance(methods, dict) else None
            if isinstance(methods_added, list):
                for t in methods_added:
                    methods_set.add(str(t) if not isinstance(t, str) else t)
            elif isinstance(methods_added, str):
                methods_set.add(methods_added)

    # Convert sets to lists
    for p, sets in phase_sets.items():
        digest.phases[p].provides = sorted(sets["provides"])
        digest.phases[p].affects = sorted(sets["affects"])
        digest.phases[p].patterns = sorted(sets["patterns"])

    digest.methods = sorted(methods_set)
    return digest


_CONVENTION_KV_RE = re.compile(r"^([^=:]+?)\s*[=:]\s*(.+)$")


@instrument_gpd_function("commands.regression_check")
def cmd_regression_check(cwd: Path, *, quick: bool = False) -> RegressionCheckResult:
    """Check for regressions across completed phases.

    Scans completed phase directories for:
    1. Convention redefinitions — same symbol defined with different values across SUMMARYs.
    2. Unresolved verification issues — VERIFICATION.md files with non-passing status.

    In quick mode, only checks the most recent 2 completed phases.

    Returns a result indicating pass/fail with detailed issue list.
    """
    phases_dir = cwd / PLANNING_DIR_NAME / "phases"
    issues: list[RegressionIssue] = []

    # Collect completed phase directories
    try:
        all_dirs = sorted(
            [d for d in phases_dir.iterdir() if d.is_dir()],
            key=cmp_to_key(lambda a, b: compare_phase_numbers(a.name, b.name)),
        )
    except FileNotFoundError:
        return RegressionCheckResult(passed=True, issues=[], phases_checked=0)

    completed_dirs: list[Path] = []
    for d in all_dirs:
        files = [f.name for f in d.iterdir() if f.is_file()]
        plans = [f for f in files if f.endswith(PLAN_SUFFIX) or f == "PLAN.md"]
        summaries = [f for f in files if f.endswith(SUMMARY_SUFFIX) or f == "SUMMARY.md"]
        if is_phase_complete(len(plans), len(summaries)):
            completed_dirs.append(d)

    if not completed_dirs:
        return RegressionCheckResult(passed=True, issues=[], phases_checked=0)

    if quick and len(completed_dirs) > 2:
        completed_dirs = completed_dirs[-2:]

    # 1. Convention redefinitions across SUMMARYs
    conventions_by_symbol: dict[str, list[dict[str, str]]] = {}
    for d in completed_dirs:
        summaries = [
            f for f in d.iterdir() if f.is_file() and (f.name.endswith("-SUMMARY.md") or f.name == "SUMMARY.md")
        ]
        for summary_file in summaries:
            content = safe_read_file(summary_file)
            if content is None:
                continue
            try:
                fm, _body = extract_frontmatter(content)
            except FrontmatterParseError:
                continue

            conventions = fm.get("conventions", [])
            if isinstance(conventions, list):
                for conv in conventions:
                    match = _CONVENTION_KV_RE.match(str(conv))
                    if match:
                        symbol = match.group(1).strip()
                        value = match.group(2).strip()
                        conventions_by_symbol.setdefault(symbol, []).append(
                            {"phase": d.name, "file": summary_file.name, "value": value}
                        )
            elif isinstance(conventions, dict):
                for symbol, value in conventions.items():
                    conventions_by_symbol.setdefault(symbol, []).append(
                        {"phase": d.name, "file": summary_file.name, "value": str(value)}
                    )

    # Find symbols with conflicting values
    for symbol, entries in conventions_by_symbol.items():
        unique_values = {e["value"] for e in entries}
        if len(unique_values) > 1:
            issues.append(
                RegressionIssue(
                    type="convention_conflict",
                    symbol=symbol,
                    definitions=entries,
                )
            )

    # 2. Unresolved VERIFICATION.md issues
    for d in completed_dirs:
        verifications = [
            f
            for f in d.iterdir()
            if f.is_file() and (f.name.endswith(VERIFICATION_SUFFIX) or f.name == "VERIFICATION.md")
        ]
        for v_file in verifications:
            content = safe_read_file(v_file)
            if content is None:
                continue
            try:
                fm, _body = extract_frontmatter(content)
            except FrontmatterParseError as exc:
                issues.append(
                    RegressionIssue(
                        type="unparseable_verification",
                        phase=d.name,
                        file=v_file.name,
                        error=str(exc),
                    )
                )
                continue

            status = fm.get("status")
            if status in ("gaps_found", "expert_needed", "human_needed"):
                score_str = str(fm.get("score", ""))
                score_match = re.match(r"(\d+)/(\d+)", score_str)
                verified = int(score_match.group(1)) if score_match else 0
                total = int(score_match.group(2)) if score_match else 0
                gap_count = total - verified if total > verified else 1

                issues.append(
                    RegressionIssue(
                        type="unresolved_verification_issues",
                        phase=d.name,
                        file=v_file.name,
                        status=status,
                        score=score_str,
                        gap_count=gap_count,
                    )
                )

    passed = len(issues) == 0
    return RegressionCheckResult(passed=passed, issues=issues, phases_checked=len(completed_dirs))


_GPD_RETURN_BLOCK_RE = re.compile(r"```ya?ml\s*\n(gpd_return:\s*\n[\s\S]*?)```")
_GPD_RETURN_FIELD_RE = re.compile(r"^\s{2}(\w+):\s*(.+)")


@instrument_gpd_function("commands.validate_return")
def cmd_validate_return(file_path: Path) -> ValidateReturnResult:
    """Validate a gpd_return YAML block in a file.

    Checks for required fields, valid status values, and numeric task counts.

    Raises:
        ValidationError: If the file does not exist.
    """
    content = safe_read_file(file_path)
    if content is None:
        raise ValidationError(f"File not found: {file_path}")

    errors: list[str] = []
    warnings: list[str] = []

    return_match = _GPD_RETURN_BLOCK_RE.search(content)
    if not return_match:
        return ValidateReturnResult(
            passed=False,
            errors=["No gpd_return YAML block found"],
            warnings=warnings,
        )

    # Parse the YAML-like block (simple key: value parsing)
    yaml_block = return_match.group(1)
    fields: dict[str, str] = {}
    for line in yaml_block.split("\n"):
        kv = _GPD_RETURN_FIELD_RE.match(line)
        if kv:
            key = kv.group(1).strip()
            val = kv.group(2).strip()
            # Strip quotes
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            fields[key] = val

    # Check required fields
    for field in REQUIRED_RETURN_FIELDS:
        if not fields.get(field):
            errors.append(f"Missing required field: {field}")

    # Validate status value
    if fields.get("status") and fields["status"] not in VALID_RETURN_STATUSES:
        errors.append(
            f"Invalid status '{fields['status']}'. Must be one of: {', '.join(sorted(VALID_RETURN_STATUSES))}"
        )

    # Validate task counts are numbers
    for count_field in ("tasks_completed", "tasks_total"):
        val = fields.get(count_field)
        if val is not None:
            try:
                int(val)
            except ValueError:
                errors.append(f"{count_field} is not a number: '{val}'")

    # Warn if completed but tasks_completed < tasks_total
    if fields.get("status") == "completed" and fields.get("tasks_completed") and fields.get("tasks_total"):
        try:
            done = int(fields["tasks_completed"])
            total = int(fields["tasks_total"])
            if done < total:
                warnings.append(f"Status is 'completed' but tasks_completed ({done}) < tasks_total ({total})")
        except ValueError:
            pass

    # Check optional but recommended fields
    for field in ("files_written", "duration_seconds"):
        if not fields.get(field):
            warnings.append(f"Recommended field missing: {field}")

    passed = len(errors) == 0
    return ValidateReturnResult(
        passed=passed,
        errors=errors,
        warnings=warnings,
        fields=fields,
        warning_count=len(warnings),
    )
