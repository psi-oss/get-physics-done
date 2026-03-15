"""Command functions — pure logic with I/O separation.

All functions take state dicts / Path arguments — callers handle persistence.
Layer 1 code: stdlib + pathlib + re + pydantic only.
"""

from __future__ import annotations

import json
import re
import shlex
from datetime import UTC, datetime
from functools import cmp_to_key
from pathlib import Path

from pydantic import BaseModel, Field

from gpd.contracts import ComparisonVerdict, ContractResults
from gpd.core.constants import (
    PHASES_DIR_NAME,
    PLAN_SUFFIX,
    PLANNING_DIR_NAME,
    REQUIRED_RETURN_FIELDS,
    STANDALONE_PLAN,
    STANDALONE_SUMMARY,
    STANDALONE_VERIFICATION,
    SUMMARY_SUFFIX,
    VALID_RETURN_STATUSES,
    VERIFICATION_SUFFIX,
)
from gpd.core.errors import ValidationError
from gpd.core.frontmatter import UNSUPPORTED_FRONTMATTER_FIELDS, FrontmatterParseError, extract_frontmatter
from gpd.core.observability import instrument_gpd_function
from gpd.core.utils import (
    compare_phase_numbers,
    generate_slug,
    is_phase_complete,
    safe_read_file,
)

__all__ = [
    "CurrentTimestampResult",
    "DecisionEntry",
    "GenerateSlugResult",
    "HistoryDigestResult",
    "PhaseDigest",
    "RegressionCheckResult",
    "RegressionIssue",
    "SummaryDecision",
    "SummaryExtractResult",
    "ValidateReturnResult",
    "VerifyPathResult",
    "cmd_current_timestamp",
    "cmd_generate_slug",
    "cmd_history_digest",
    "cmd_regression_check",
    "cmd_summary_extract",
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


class SummaryDecision(BaseModel):
    summary: str
    rationale: str | None = None


class SummaryExtractResult(BaseModel):
    path: str
    one_liner: str | None = None
    key_files: list[str] = Field(default_factory=list)
    key_files_created: list[str] = Field(default_factory=list)
    key_files_modified: list[str] = Field(default_factory=list)
    methods_added: list[str] = Field(default_factory=list)
    patterns: list[str] = Field(default_factory=list)
    decisions: list[SummaryDecision] = Field(default_factory=list)
    affects: list[str] = Field(default_factory=list)
    conventions: dict[str, str] | list[str] | str | None = None
    plan_contract_ref: str | None = None
    contract_results: ContractResults | None = None
    comparison_verdicts: list[ComparisonVerdict] = Field(default_factory=list)
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
    fields: dict[str, object] = Field(default_factory=dict)
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
    fmt = fmt.strip().lower()

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


def _phase_name_from_dir(dir_name: str) -> str:
    """Extract a human-readable name from a phase directory name like '03-core-work'."""
    parts = dir_name.split("-", 1)
    if len(parts) > 1:
        return parts[1].replace("-", " ")
    return "Unknown"


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


def _normalize_string_list(value: object) -> list[str]:
    """Normalize a YAML field into a list of strings."""
    if value is None:
        return []
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped] if stripped else []
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            if isinstance(item, str):
                stripped = item.strip()
                if stripped:
                    result.append(stripped)
            elif item is not None:
                rendered = str(item).strip()
                if rendered:
                    result.append(rendered)
        return result
    return []


def _extract_key_files(value: object) -> tuple[list[str], list[str], list[str]]:
    """Return flattened, created, and modified file lists from summary frontmatter."""
    if isinstance(value, dict):
        created = _normalize_string_list(value.get("created"))
        modified = _normalize_string_list(value.get("modified"))
        flattened = list(dict.fromkeys(created + modified))
        return flattened, created, modified

    flattened = _normalize_string_list(value)
    return flattened, flattened, []


def _parse_contract_results(value: object, summary_path: str) -> ContractResults | None:
    """Validate the optional contract-results block in a summary."""
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValidationError(f"Invalid contract_results in {summary_path}: expected an object")
    try:
        return ContractResults.model_validate(value)
    except Exception as exc:  # pragma: no cover - pydantic version specifics
        raise ValidationError(f"Invalid contract_results in {summary_path}: {exc}") from exc


def _parse_comparison_verdicts(value: object, summary_path: str) -> list[ComparisonVerdict]:
    """Validate the optional comparison-verdict ledger in a summary."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError(f"Invalid comparison_verdicts in {summary_path}: expected a list")
    try:
        return [ComparisonVerdict.model_validate(item) for item in value]
    except Exception as exc:  # pragma: no cover - pydantic version specifics
        raise ValidationError(f"Invalid comparison_verdicts in {summary_path}: {exc}") from exc


_BODY_ONE_LINER_RE = re.compile(r"\A---[\s\S]*?---\s*(?:#[^\n]*\n\s*)?\*\*(.+?)\*\*")


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

    unsupported_summary_fields = [
        f"{field}: {message}"
        for field, message in UNSUPPORTED_FRONTMATTER_FIELDS.get("summary", {}).items()
        if field in fm
    ]
    if unsupported_summary_fields:
        raise ValidationError(f"Unsupported summary frontmatter in {summary_path}: {'; '.join(unsupported_summary_fields)}")

    # Extract one-liner: frontmatter first, fall back to body bold text
    one_liner = fm.get("one-liner")
    if not one_liner:
        body_match = _BODY_ONE_LINER_RE.search(content)
        if body_match:
            one_liner = body_match.group(1)

    raw_key_files = fm.get("key-files")
    key_files, key_files_created, key_files_modified = _extract_key_files(raw_key_files)
    contract_results = _parse_contract_results(
        fm.get("contract_results"),
        summary_path,
    )
    comparison_verdicts = _parse_comparison_verdicts(fm.get("comparison_verdicts"), summary_path)

    full_result = SummaryExtractResult(
        path=summary_path,
        one_liner=one_liner,
        key_files=key_files,
        key_files_created=key_files_created,
        key_files_modified=key_files_modified,
        methods_added=((fm.get("methods", {}) or {}).get("added", []) if isinstance(fm.get("methods"), dict) else []),
        patterns=fm.get("patterns-established", []) if isinstance(fm.get("patterns-established"), list) else [],
        decisions=_parse_decisions(fm.get("key-decisions")),
        affects=fm.get("affects", []) if isinstance(fm.get("affects"), list) else [],
        conventions=fm.get("conventions"),
        plan_contract_ref=fm.get("plan_contract_ref") if isinstance(fm.get("plan_contract_ref"), str) else None,
        contract_results=contract_results,
        comparison_verdicts=comparison_verdicts,
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

    Scans .gpd/phases/*/SUMMARY.md for frontmatter fields:
    dependency-graph.provides, dependency-graph.affects, patterns-established,
    key-decisions, and methods.added.
    """
    phases_dir = cwd / PLANNING_DIR_NAME / PHASES_DIR_NAME
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
            f for f in dir_path.iterdir() if f.is_file() and (f.name.endswith(SUMMARY_SUFFIX) or f.name == STANDALONE_SUMMARY)
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
    phases_dir = cwd / PLANNING_DIR_NAME / PHASES_DIR_NAME
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
        plans = [f for f in files if f.endswith(PLAN_SUFFIX) or f == STANDALONE_PLAN]
        summaries = [f for f in files if f.endswith(SUMMARY_SUFFIX) or f == STANDALONE_SUMMARY]
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
            f for f in d.iterdir() if f.is_file() and (f.name.endswith(SUMMARY_SUFFIX) or f.name == STANDALONE_SUMMARY)
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
            if f.is_file() and (f.name.endswith(VERIFICATION_SUFFIX) or f.name == STANDALONE_VERIFICATION)
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
                gap_count = total - verified if total > verified else (1 if not score_match else 0)

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
_GPD_RETURN_FIELD_RE = re.compile(r"^\s{2,4}(\w+):\s*(.+)")
_GPD_RETURN_LIST_START_RE = re.compile(r"^\s{2,4}(\w+):\s*$")
_GPD_RETURN_LIST_ITEM_RE = re.compile(r"^\s{4,}-\s*(.+)")


def _strip_wrapping_quotes(value: str) -> str:
    stripped = value.strip()
    if len(stripped) >= 2 and stripped[0] == stripped[-1] and stripped[0] in {'"', "'"}:
        return stripped[1:-1]
    return stripped


def _parse_inline_yaml_list(value: str) -> list[str]:
    stripped = value.strip()
    if not (stripped.startswith("[") and stripped.endswith("]")):
        return []
    inner = stripped[1:-1].strip()
    if not inner:
        return []

    lexer = shlex.shlex(inner, posix=True)
    lexer.whitespace = ","
    lexer.whitespace_split = True
    lexer.commenters = ""
    return [_strip_wrapping_quotes(token) for token in lexer if _strip_wrapping_quotes(token)]


def _parse_gpd_return_fields(yaml_block: str) -> dict[str, object]:
    fields: dict[str, object] = {}
    active_list_key: str | None = None

    for line in yaml_block.split("\n"):
        if not line.strip() or line.strip() == "gpd_return:":
            if not line.strip():
                active_list_key = None
            continue

        list_start = _GPD_RETURN_LIST_START_RE.match(line)
        if list_start:
            active_list_key = list_start.group(1).strip()
            fields[active_list_key] = []
            continue

        kv = _GPD_RETURN_FIELD_RE.match(line)
        if kv:
            active_list_key = None
            key = kv.group(1).strip()
            raw_value = kv.group(2).strip()
            if raw_value.startswith("[") and raw_value.endswith("]"):
                fields[key] = _parse_inline_yaml_list(raw_value)
            else:
                fields[key] = _strip_wrapping_quotes(raw_value)
            continue

        if active_list_key is not None:
            list_item = _GPD_RETURN_LIST_ITEM_RE.match(line)
            if list_item:
                value = _strip_wrapping_quotes(list_item.group(1).strip())
                if value:
                    current = fields.get(active_list_key)
                    if isinstance(current, list):
                        current.append(value)
                continue
            if line.strip():
                active_list_key = None

    return fields


def _field_present(value: object) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    return True


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

    yaml_block = return_match.group(1)
    fields = _parse_gpd_return_fields(yaml_block)

    # Check required fields
    for field in REQUIRED_RETURN_FIELDS:
        if not _field_present(fields.get(field)):
            errors.append(f"Missing required field: {field}")

    # Normalize status for comparison (strip whitespace, lowercase)
    raw_status = fields.get("status", "")
    status_lower = raw_status.strip().lower() if isinstance(raw_status, str) else ""

    # Validate status value
    if raw_status and status_lower not in VALID_RETURN_STATUSES:
        errors.append(
            f"Invalid status '{raw_status}'. Must be one of: {', '.join(sorted(VALID_RETURN_STATUSES))}"
        )

    # Validate task counts are numbers
    for count_field in ("tasks_completed", "tasks_total"):
        val = fields.get(count_field)
        if isinstance(val, str):
            try:
                int(val)
            except ValueError:
                errors.append(f"{count_field} is not a number: '{val}'")

    # Warn if completed but tasks_completed < tasks_total
    if (
        status_lower == "completed"
        and isinstance(fields.get("tasks_completed"), str)
        and isinstance(fields.get("tasks_total"), str)
    ):
        try:
            done = int(str(fields["tasks_completed"]))
            total = int(str(fields["tasks_total"]))
            if done < total:
                warnings.append(f"Status is 'completed' but tasks_completed ({done}) < tasks_total ({total})")
        except ValueError:
            pass

    # Check optional but recommended fields
    for field in ("duration_seconds",):
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
