"""Command functions — pure logic with I/O separation.

All functions take state dicts / Path arguments — callers handle persistence.
Layer 1 code: stdlib + pathlib + re + pydantic only.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from functools import cmp_to_key
from pathlib import Path

from pydantic import BaseModel, Field

from gpd.contracts import (
    ComparisonVerdict,
    ContractResults,
    parse_comparison_verdicts_data_strict,
    parse_contract_results_data_artifact,
)
from gpd.core.child_return_application import ApplyChildReturnResult, apply_child_return_updates
from gpd.core.constants import (
    PHASES_DIR_NAME,
    PLAN_SUFFIX,
    PLANNING_DIR_NAME,
    STANDALONE_PLAN,
    VERIFICATION_SUFFIX,
    ProjectLayout,
)
from gpd.core.errors import ValidationError
from gpd.core.frontmatter import (
    VERIFICATION_REPORT_STATUSES,
    FrontmatterParseError,
    extract_frontmatter,
    validate_frontmatter,
)
from gpd.core.observability import instrument_gpd_function
from gpd.core.return_contract import validate_gpd_return_markdown
from gpd.core.utils import (
    compare_phase_numbers,
    generate_slug,
    is_phase_complete,
    matching_phase_artifact_count,
    safe_read_file,
)

__all__ = [
    "ApplyChildReturnResult",
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
    "cmd_apply_return_updates",
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
    warning: str | None = None


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


def _parse_decisions(decisions_list: object, *, summary_path: str) -> list[SummaryDecision]:
    """Parse key-decisions from frontmatter into structured format."""
    if decisions_list is None:
        return []
    if not isinstance(decisions_list, list):
        raise ValidationError(f"Invalid key-decisions in {summary_path}: expected a list")

    results: list[SummaryDecision] = []
    for index, d in enumerate(decisions_list):
        if isinstance(d, dict):
            entries = list(d.items())
            if len(entries) != 1:
                raise ValidationError(
                    f"Invalid key-decisions in {summary_path}: entry {index} must be a single-entry mapping"
                )
            summary, rationale = entries[0]
            if not isinstance(summary, str) or not summary.strip():
                raise ValidationError(
                    f"Invalid key-decisions in {summary_path}: entry {index} summary must be a non-empty string"
                )
            if not isinstance(rationale, str) or not rationale.strip():
                raise ValidationError(
                    f"Invalid key-decisions in {summary_path}: entry {index} rationale must be a non-empty string"
                )
            results.append(
                SummaryDecision(
                    summary=summary.strip(),
                    rationale=rationale.strip(),
                )
            )
            continue

        if not isinstance(d, str) or not d.strip():
            raise ValidationError(
                f"Invalid key-decisions in {summary_path}: entry {index} must be a non-empty string or mapping"
            )
        s = d.strip()
        colon_idx = s.find(":")
        if colon_idx > 0:
            summary = s[:colon_idx].strip()
            rationale = s[colon_idx + 1 :].strip()
            if not summary or not rationale:
                raise ValidationError(
                    f"Invalid key-decisions in {summary_path}: entry {index} must include non-empty summary and rationale"
                )
            results.append(
                SummaryDecision(
                    summary=summary,
                    rationale=rationale,
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
    """Best-effort string-list normalization for derived, non-authoritative readers."""
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


def _require_non_empty_string_list(
    value: object,
    *,
    field_name: str,
    summary_path: str,
) -> list[str]:
    """Return a validated list of non-empty strings or raise."""
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValidationError(f"Invalid {field_name} in {summary_path}: expected a list of non-empty strings")

    normalized: list[str] = []
    for index, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise ValidationError(
                f"Invalid {field_name} in {summary_path}: entry {index} must be a non-empty string"
            )
        normalized.append(item.strip())
    return normalized


def _extract_key_files(value: object, *, summary_path: str) -> tuple[list[str], list[str], list[str]]:
    """Return flattened, created, and modified file lists from summary frontmatter."""
    if isinstance(value, dict):
        extra_keys = sorted(str(key) for key in value if key not in {"created", "modified"})
        if extra_keys:
            raise ValidationError(
                f"Invalid key-files in {summary_path}: unexpected key(s) {', '.join(extra_keys)}"
            )
        created = _require_non_empty_string_list(
            value.get("created"),
            field_name="key-files.created",
            summary_path=summary_path,
        )
        modified = _require_non_empty_string_list(
            value.get("modified"),
            field_name="key-files.modified",
            summary_path=summary_path,
        )
        flattened = list(dict.fromkeys(created + modified))
        return flattened, created, modified
    if value is not None and not isinstance(value, list):
        raise ValidationError(
            f"Invalid key-files in {summary_path}: expected a list of non-empty strings or an object with created/modified lists"
        )

    flattened = _require_non_empty_string_list(value, field_name="key-files", summary_path=summary_path)
    return flattened, flattened, []


def _extract_methods_added(frontmatter: dict[str, object], *, summary_path: str) -> list[str]:
    """Return validated ``methods.added`` entries from summary frontmatter."""
    methods = frontmatter.get("methods")
    if methods is None:
        return []
    if not isinstance(methods, dict):
        raise ValidationError(f"Invalid methods in {summary_path}: expected an object")
    return _require_non_empty_string_list(
        methods.get("added"),
        field_name="methods.added",
        summary_path=summary_path,
    )


def _parse_contract_results(value: object, summary_path: str) -> ContractResults | None:
    """Validate the optional contract-results block in a summary."""
    if value is _MISSING:
        return None
    try:
        return parse_contract_results_data_artifact(value)
    except Exception as exc:  # pragma: no cover - pydantic version specifics
        raise ValidationError(f"Invalid contract_results in {summary_path}: {exc}") from exc


def _parse_comparison_verdicts(value: object, summary_path: str) -> list[ComparisonVerdict]:
    """Validate the optional comparison-verdict ledger in a summary."""
    try:
        return parse_comparison_verdicts_data_strict(value)
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

    validation = validate_frontmatter(content, "summary", source_path=full_path)
    if not validation.valid:
        problems = [*validation.missing, *validation.errors]
        raise ValidationError(
            f"Invalid summary frontmatter in {summary_path}: {'; '.join(problems)}"
        )

    # Extract one-liner: frontmatter first, fall back to body bold text
    one_liner = fm.get("one-liner")
    if not one_liner:
        body_match = _BODY_ONE_LINER_RE.search(content)
        if body_match:
            one_liner = body_match.group(1)

    raw_key_files = fm.get("key-files")
    key_files, key_files_created, key_files_modified = _extract_key_files(raw_key_files, summary_path=summary_path)
    methods_added = _extract_methods_added(fm, summary_path=summary_path)
    patterns = _require_non_empty_string_list(
        fm.get("patterns-established"),
        field_name="patterns-established",
        summary_path=summary_path,
    )
    affects = _require_non_empty_string_list(
        fm.get("affects"),
        field_name="affects",
        summary_path=summary_path,
    )
    contract_results = _parse_contract_results(
        fm["contract_results"] if "contract_results" in fm else _MISSING,
        summary_path,
    )
    comparison_verdicts = _parse_comparison_verdicts(fm.get("comparison_verdicts"), summary_path)

    full_result = SummaryExtractResult(
        path=summary_path,
        one_liner=one_liner,
        key_files=key_files,
        key_files_created=key_files_created,
        key_files_modified=key_files_modified,
        methods_added=methods_added,
        patterns=patterns,
        decisions=_parse_decisions(fm.get("key-decisions"), summary_path=summary_path),
        affects=affects,
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


def _merge_list_or_string(target_set: set[str], value: object, *, field_name: str, summary_path: str) -> None:
    """Merge a value that may be a list of strings or a single string into a set."""
    if isinstance(value, list):
        for index, item in enumerate(value):
            if not isinstance(item, str) or not item.strip():
                raise ValidationError(
                    f"Invalid {field_name} in {summary_path}: entry {index} must be a non-empty string"
                )
            target_set.add(item.strip())
        return
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ValidationError(f"Invalid {field_name} in {summary_path}: expected a non-empty string")
        target_set.add(stripped)
        return
    if value is not None:
        raise ValidationError(f"Invalid {field_name} in {summary_path}: expected a string or list of non-empty strings")


@instrument_gpd_function("commands.history_digest")
def cmd_history_digest(cwd: Path) -> HistoryDigestResult:
    """Build a digest of project history from phase SUMMARY files.

    Scans GPD/phases/*/*SUMMARY.md for frontmatter fields:
    dependency-graph.provides, dependency-graph.affects, patterns-established,
    key-decisions, and methods.added.
    """
    phases_dir = cwd / PLANNING_DIR_NAME / PHASES_DIR_NAME
    methods_set: set[str] = set()
    phase_sets: dict[str, dict[str, set[str]]] = {}
    digest = HistoryDigestResult()

    if not phases_dir.is_dir():
        return digest
    layout = ProjectLayout(cwd)

    phase_dirs = sorted(
        [d for d in phases_dir.iterdir() if d.is_dir()],
        key=cmp_to_key(lambda a, b: compare_phase_numbers(a.name, b.name)),
    )

    for dir_path in phase_dirs:
        dir_name = dir_path.name
        summaries = [f for f in dir_path.iterdir() if f.is_file() and layout.is_summary_file(f.name)]

        for summary_file in summaries:
            content = safe_read_file(summary_file)
            if content is None:
                continue
            summary_relpath = summary_file.relative_to(cwd).as_posix()
            try:
                fm, _body = extract_frontmatter(content)
            except FrontmatterParseError as exc:
                raise ValidationError(f"Malformed frontmatter in {summary_relpath}: {exc}") from exc

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
            _merge_list_or_string(
                phase_sets[phase_num]["provides"],
                provides,
                field_name="provides",
                summary_path=summary_relpath,
            )

            # Merge affects
            affects = (dep_graph.get("affects") if isinstance(dep_graph, dict) else None) or fm.get("affects")
            _merge_list_or_string(
                phase_sets[phase_num]["affects"],
                affects,
                field_name="affects",
                summary_path=summary_relpath,
            )

            # Merge patterns
            _merge_list_or_string(
                phase_sets[phase_num]["patterns"],
                fm.get("patterns-established"),
                field_name="patterns-established",
                summary_path=summary_relpath,
            )

            # Merge decisions
            key_decisions = fm.get("key-decisions")
            for decision in _parse_decisions(key_decisions, summary_path=summary_relpath):
                text = decision.summary if decision.rationale is None else f"{decision.summary}: {decision.rationale}"
                digest.decisions.append(DecisionEntry(phase=phase_num, decision=text))

            # Merge methods
            methods = fm.get("methods")
            if methods is not None and not isinstance(methods, dict):
                raise ValidationError(f"Invalid methods in {summary_relpath}: expected an object")
            methods_added = _require_non_empty_string_list(
                methods.get("added") if isinstance(methods, dict) else None,
                field_name="methods.added",
                summary_path=summary_relpath,
            )
            methods_set.update(methods_added)

    # Convert sets to lists
    for p, sets in phase_sets.items():
        digest.phases[p].provides = sorted(sets["provides"])
        digest.phases[p].affects = sorted(sets["affects"])
        digest.phases[p].patterns = sorted(sets["patterns"])

    digest.methods = sorted(methods_set)
    return digest


_CONVENTION_KV_RE = re.compile(r"^([^=:]+?)\s*[=:]\s*(.+)$")


def _matches_phase_scope(dir_name: str, phase: str | None) -> bool:
    """Return whether a completed phase directory matches an optional phase scope."""

    if phase is None:
        return True

    requested = phase.strip()
    if not requested:
        return True

    dir_phase = dir_name.split("-", 1)[0]
    return compare_phase_numbers(dir_phase, requested) == 0


@instrument_gpd_function("commands.regression_check")
def cmd_regression_check(cwd: Path, *, phase: str | None = None, quick: bool = False) -> RegressionCheckResult:
    """Check for regressions across completed phases.

    Scans completed phase directories for:
    1. Convention redefinitions — same symbol defined with different values across SUMMARYs.
    2. Unresolved verification issues — *-VERIFICATION.md files with non-passing status.

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
        return RegressionCheckResult(passed=True, issues=[], phases_checked=0, warning="No completed phases found to check")

    layout = ProjectLayout(cwd)
    completed_dirs: list[Path] = []
    for d in all_dirs:
        files = [f.name for f in d.iterdir() if f.is_file()]
        plans = [f for f in files if f.endswith(PLAN_SUFFIX) or f == STANDALONE_PLAN]
        summaries = [f for f in files if layout.is_summary_file(f)]
        if is_phase_complete(len(plans), matching_phase_artifact_count(plans, summaries)):
            completed_dirs.append(d)

    if not completed_dirs:
        return RegressionCheckResult(passed=True, issues=[], phases_checked=0, warning="No completed phases found to check")
    completed_dirs = [d for d in completed_dirs if _matches_phase_scope(d.name, phase)]
    if not completed_dirs:
        return RegressionCheckResult(passed=True, issues=[], phases_checked=0, warning="No completed phases found to check")

    if quick and len(completed_dirs) > 2:
        completed_dirs = completed_dirs[-2:]

    # 1. Convention redefinitions across SUMMARYs
    conventions_by_symbol: dict[str, list[dict[str, str]]] = {}
    for d in completed_dirs:
        summaries = [f for f in d.iterdir() if f.is_file() and layout.is_summary_file(f.name)]
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

    # 2. Unresolved *-VERIFICATION.md issues
    for d in completed_dirs:
        verifications = [f for f in d.iterdir() if f.is_file() and f.name.endswith(VERIFICATION_SUFFIX)]
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
            status_text = str(status).strip() if status is not None else ""
            if not status_text:
                issues.append(
                    RegressionIssue(
                        type="invalid_verification_status",
                        phase=d.name,
                        file=v_file.name,
                        status=status_text or None,
                        error="verification status must be one of passed, gaps_found, expert_needed, human_needed",
                    )
                )
                continue

            if status_text not in VERIFICATION_REPORT_STATUSES:
                issues.append(
                    RegressionIssue(
                        type="invalid_verification_status",
                        phase=d.name,
                        file=v_file.name,
                        status=status_text,
                        error="verification status must be one of passed, gaps_found, expert_needed, human_needed",
                    )
                )
                continue

            if status_text in ("gaps_found", "expert_needed", "human_needed"):
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

    validation = validate_gpd_return_markdown(content)
    return ValidateReturnResult(
        passed=validation.passed,
        errors=validation.errors,
        warnings=validation.warnings,
        fields=validation.fields,
        warning_count=validation.warning_count,
    )


@instrument_gpd_function("commands.apply_return_updates")
def cmd_apply_return_updates(cwd: Path, file_path: Path) -> ApplyChildReturnResult:
    """Validate and apply the durable subset of one ``gpd_return`` envelope."""
    content = safe_read_file(file_path)
    if content is None:
        raise ValidationError(f"File not found: {file_path}")

    validation = validate_gpd_return_markdown(content)
    if not validation.passed or validation.envelope is None:
        return ApplyChildReturnResult(
            passed=False,
            status="failed",
            errors=list(validation.errors),
            warnings=list(validation.warnings),
        )

    result = apply_child_return_updates(cwd, validation.envelope)
    if validation.warnings:
        result.warnings.extend(warning for warning in validation.warnings if warning not in result.warnings)
    return result
_MISSING = object()
