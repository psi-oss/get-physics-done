"""Frontmatter parsing, schema validation, verification suite, and template operations.

Ported from experiments/get-physics-done/get-physics-done/src/frontmatter.js (1142 lines).

Core operations:
  extract_frontmatter / reconstruct_frontmatter / splice_frontmatter — YAML CRUD
  validate_frontmatter — schema enforcement for plan/summary/verification files
  verify_* — verification suite (summary, plan structure, phase, references, commits, artifacts, key links)
  select_template / fill_template — template generation for phase artifacts
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from gpd.core.constants import (
    PLAN_SUFFIX,
    STANDALONE_PLAN,
    STANDALONE_SUMMARY,
    SUMMARY_SUFFIX,
    VERIFICATION_SUFFIX,
)
from gpd.core.errors import GPDError
from gpd.core.observability import instrument_gpd_function
from gpd.core.utils import atomic_write, generate_slug, phase_normalize, safe_read_file

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    # Exceptions
    "FrontmatterParseError",
    "FrontmatterValidationError",
    # Core parsing
    "extract_frontmatter",
    "reconstruct_frontmatter",
    "splice_frontmatter",
    "deep_merge_frontmatter",
    "parse_must_haves_block",
    # Schema validation
    "FRONTMATTER_SCHEMAS",
    "FrontmatterValidation",
    "validate_frontmatter",
    # Verification result types
    "FileCheckResult",
    "SummaryVerification",
    "TaskInfo",
    "PlanValidation",
    "PhaseCompleteness",
    "ReferenceVerification",
    "CommitVerification",
    "ArtifactCheck",
    "ArtifactVerification",
    "KeyLinkCheck",
    "KeyLinkVerification",
    # Verification implementations
    "verify_summary",
    "verify_plan_structure",
    "verify_phase_completeness",
    "verify_references",
    "verify_commits",
    "verify_artifacts",
    "verify_key_links",
    # Template operations
    "TemplateSelection",
    "TemplateResult",
    "TemplateFillOptions",
    "select_template",
    "fill_template",
]

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class FrontmatterParseError(GPDError, ValueError):
    """YAML frontmatter block is syntactically invalid."""


class FrontmatterValidationError(GPDError, ValueError):
    """Frontmatter fails schema validation."""


# ---------------------------------------------------------------------------
# Core parsing
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"^---\r?\n([\s\S]*?)\r?\n---(?:\r?\n|$)")
_EMPTY_FRONTMATTER_RE = re.compile(r"^---\r?\n---(?:\r?\n|$)")

# Matches the full frontmatter block (including empty) for replacement operations.
# Uses a lookahead so the trailing newline is preserved for the caller to reattach.
_FRONTMATTER_BLOCK_RE = re.compile(r"^---\r?\n(?:[\s\S]*?\r?\n)?---(?=\r?\n|$)")


def extract_frontmatter(content: str) -> tuple[dict, str]:
    """Extract YAML frontmatter and body from markdown content.

    Returns ``(meta, body)`` where *meta* is the parsed YAML dict and *body*
    is everything after the closing ``---`` delimiter.

    If no frontmatter block is found, returns ``({}, content)``.

    Raises:
        FrontmatterParseError: If the YAML inside the ``---`` block is malformed.
    """
    clean = content.lstrip("\ufeff")  # strip BOM

    match = _FRONTMATTER_RE.match(clean)
    if match:
        yaml_str = match.group(1)
        body = clean[match.end() :]
        try:
            meta = yaml.safe_load(yaml_str) or {}
        except yaml.YAMLError as exc:
            raise FrontmatterParseError(str(exc)) from exc
        if not isinstance(meta, dict):
            raise FrontmatterParseError(f"Expected mapping, got {type(meta).__name__}")
        return meta, body

    # Empty frontmatter (---\n---)
    match = _EMPTY_FRONTMATTER_RE.match(clean)
    if match:
        return {}, clean[match.end() :]

    # No frontmatter at all
    return {}, clean


def _dump_yaml(meta: dict) -> str:
    """Dump *meta* to a YAML string (without ``---`` delimiters)."""
    return yaml.dump(
        meta,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
        width=999999,
    ).rstrip()


def reconstruct_frontmatter(meta: dict, body: str) -> str:
    """Rebuild full markdown from *meta* dict and *body* text.

    Always uses ``\\n`` line endings regardless of input.
    """
    yaml_str = _dump_yaml(meta)
    return f"---\n{yaml_str}\n---\n\n{body}"


def splice_frontmatter(content: str, updates: dict) -> str:
    """Replace frontmatter fields in *content* with values from *updates*.

    Preserves the body and detects CRLF vs LF line endings from the original
    content.  If *content* has no frontmatter block, one is prepended.
    """
    meta, body = extract_frontmatter(content)
    meta.update(updates)

    eol = "\r\n" if "\r\n" in content else "\n"
    yaml_str = _dump_yaml(meta)

    clean = content.lstrip("\ufeff")
    fm_match = _FRONTMATTER_BLOCK_RE.match(clean)
    if fm_match:
        return f"---{eol}{yaml_str}{eol}---" + clean[fm_match.end() :]
    return f"---{eol}{yaml_str}{eol}---{eol}{eol}" + clean


def deep_merge_frontmatter(content: str, merge_data: dict) -> str:
    """Shallow-merge *merge_data* into existing frontmatter.

    For each key in *merge_data*: if both existing and new values are plain
    dicts (not lists), their top-level entries are merged (one level only).
    Otherwise the new value overwrites.
    """
    meta, _ = extract_frontmatter(content)
    for key, val in merge_data.items():
        existing = meta.get(key)
        if isinstance(val, dict) and isinstance(existing, dict):
            existing.update(val)
        else:
            meta[key] = val

    eol = "\r\n" if "\r\n" in content else "\n"
    yaml_str = _dump_yaml(meta)

    clean = content.lstrip("\ufeff")
    fm_match = _FRONTMATTER_BLOCK_RE.match(clean)
    if fm_match:
        return f"---{eol}{yaml_str}{eol}---" + clean[fm_match.end() :]
    return f"---{eol}{yaml_str}{eol}---{eol}{eol}" + clean


def parse_must_haves_block(content: str, block_name: str) -> list:
    """Extract a list from ``must_haves.<block_name>`` in frontmatter.

    Returns an empty list when the block is absent or not a list.
    """
    meta, _ = extract_frontmatter(content)
    must_haves = meta.get("must_haves") or meta.get("must-haves")
    if not isinstance(must_haves, dict):
        return []
    block = must_haves.get(block_name)
    if not isinstance(block, list):
        return []
    return block


# ---------------------------------------------------------------------------
# Schema definitions and validation
# ---------------------------------------------------------------------------

FRONTMATTER_SCHEMAS: dict[str, dict[str, list[str]]] = {
    "plan": {
        "required": [
            "phase",
            "plan",
            "type",
            "wave",
            "depends_on",
            "files_modified",
            "autonomous",
            "must_haves",
        ],
    },
    "summary": {
        "required": ["phase", "plan", "depth", "provides", "completed"],
    },
    "verification": {
        "required": ["phase", "verified", "status", "score"],
    },
}


class FrontmatterValidation(BaseModel):
    """Result of frontmatter schema validation."""

    valid: bool
    missing: list[str] = Field(default_factory=list)
    present: list[str] = Field(default_factory=list)
    schema_name: str = ""


def _resolve_field(meta: dict, name: str) -> str | None:
    """Check for *name* in both ``under_score`` and ``hyphen-case`` forms."""
    if name in meta:
        return name
    alt = name.replace("_", "-")
    if alt in meta:
        return alt
    return None


@instrument_gpd_function("frontmatter.validate")
def validate_frontmatter(content: str, schema_name: str) -> FrontmatterValidation:
    """Validate frontmatter against a named schema.

    Raises:
        FrontmatterParseError: On malformed YAML.
        FrontmatterValidationError: If *schema_name* is unknown.
    """
    schema = FRONTMATTER_SCHEMAS.get(schema_name)
    if schema is None:
        available = ", ".join(FRONTMATTER_SCHEMAS)
        raise FrontmatterValidationError(f"Unknown schema: {schema_name}. Available: {available}")

    meta, _ = extract_frontmatter(content)  # may raise FrontmatterParseError
    required = schema["required"]

    missing = [f for f in required if _resolve_field(meta, f) is None]
    present = [f for f in required if _resolve_field(meta, f) is not None]

    return FrontmatterValidation(
        valid=len(missing) == 0,
        missing=missing,
        present=present,
        schema_name=schema_name,
    )


# ---------------------------------------------------------------------------
# Verification suite — result types
# ---------------------------------------------------------------------------


class FileCheckResult(BaseModel):
    checked: int = 0
    found: int = 0
    missing: list[str] = Field(default_factory=list)


class SummaryVerification(BaseModel):
    passed: bool
    summary_exists: bool = False
    files_created: FileCheckResult = Field(default_factory=FileCheckResult)
    commits_exist: bool = False
    self_check: str = "not_found"
    errors: list[str] = Field(default_factory=list)


class TaskInfo(BaseModel):
    name: str
    has_files: bool = False
    has_action: bool = False
    has_verify: bool = False
    has_done: bool = False


class PlanValidation(BaseModel):
    valid: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    task_count: int = 0
    tasks: list[TaskInfo] = Field(default_factory=list)
    frontmatter_fields: list[str] = Field(default_factory=list)


class PhaseCompleteness(BaseModel):
    complete: bool
    phase_number: str = ""
    plan_count: int = 0
    summary_count: int = 0
    incomplete_plans: list[str] = Field(default_factory=list)
    orphan_summaries: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ReferenceVerification(BaseModel):
    valid: bool
    found: int = 0
    missing: list[str] = Field(default_factory=list)
    total: int = 0


class CommitVerification(BaseModel):
    all_valid: bool
    valid_hashes: list[str] = Field(default_factory=list)
    invalid_hashes: list[str] = Field(default_factory=list)
    total: int = 0


class ArtifactCheck(BaseModel):
    path: str
    exists: bool = False
    issues: list[str] = Field(default_factory=list)
    passed: bool = False


class ArtifactVerification(BaseModel):
    all_passed: bool
    passed_count: int = 0
    total: int = 0
    artifacts: list[ArtifactCheck] = Field(default_factory=list)


class KeyLinkCheck(BaseModel):
    from_path: str
    to_path: str | None = None
    via: str = ""
    verified: bool = False
    detail: str = ""


class KeyLinkVerification(BaseModel):
    all_verified: bool
    verified_count: int = 0
    total: int = 0
    links: list[KeyLinkCheck] = Field(default_factory=list)


class TemplateSelection(BaseModel):
    template: str
    template_type: str
    task_count: int = 0
    file_count: int = 0
    has_decisions: bool = False


class TemplateResult(BaseModel):
    created: bool
    path: str
    template_type: str


# ---------------------------------------------------------------------------
# Internal helpers (file/git)
# ---------------------------------------------------------------------------


def _exec_git(cwd: Path, args: list[str]) -> tuple[int, str]:
    """Run a git command, return (exit_code, stdout)."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode, result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return 1, ""


def _write_file_atomic(path: Path, content: str) -> None:
    """Write content to file atomically. Delegates to utils.atomic_write."""
    atomic_write(path, content)


# ---------------------------------------------------------------------------
# Verification suite — implementations
# ---------------------------------------------------------------------------

# Patterns to extract file paths mentioned in markdown
_FILE_MENTION_BACKTICK = re.compile(r"`([^`]+\.[a-zA-Z][a-zA-Z0-9]*)`")
_FILE_MENTION_VERB = re.compile(
    r"(?:Created|Modified|Added|Updated|Edited):\s*`?([^\s`]+\.[a-zA-Z][a-zA-Z0-9]*)`?",
    re.IGNORECASE,
)

# Commit hash patterns: `abc1234` or "commit abc1234"
_COMMIT_HASH_RE = re.compile(
    r"(?:`([0-9a-f]{7,12}|[0-9a-f]{40})`|\bcommit\s+([0-9a-f]{7,40})\b)",
    re.IGNORECASE,
)

# Self-check section heading
_SELF_CHECK_HEADING = re.compile(r"##\s*(?:Self[- ]?Check|Verification|Quality Check)", re.IGNORECASE)
_SELF_CHECK_PASS = re.compile(r"(?:all\s+)?(?:pass|complete|succeeded)", re.IGNORECASE)
_SELF_CHECK_FAIL = re.compile(r"(?:fail|incomplete|blocked)", re.IGNORECASE)


@instrument_gpd_function("frontmatter.verify_summary")
def verify_summary(
    cwd: Path,
    summary_path: Path,
    check_file_count: int = 2,
) -> SummaryVerification:
    """Verify a SUMMARY.md file: existence, mentioned files, commit hashes, self-check section."""
    full_path = summary_path if summary_path.is_absolute() else cwd / summary_path

    if not full_path.exists():
        return SummaryVerification(
            passed=False,
            summary_exists=False,
            errors=["SUMMARY.md not found"],
        )

    content = full_path.read_text(encoding="utf-8")
    try:
        extract_frontmatter(content)
    except FrontmatterParseError as exc:
        return SummaryVerification(
            passed=False,
            summary_exists=True,
            errors=[f"Frontmatter YAML parse error: {exc}"],
        )

    errors: list[str] = []

    # --- Spot-check files mentioned in summary ---
    mentioned: set[str] = set()
    for pattern in (_FILE_MENTION_BACKTICK, _FILE_MENTION_VERB):
        for m in pattern.finditer(content):
            fp = m.group(1)
            if fp and not fp.startswith("http") and "/" in fp:
                mentioned.add(fp)

    files_to_check = list(mentioned)[:check_file_count]
    missing_files = [f for f in files_to_check if not (cwd / f).exists()]

    # --- Commit hashes ---
    hashes = [m.group(1) or m.group(2) for m in _COMMIT_HASH_RE.finditer(content)]
    commits_exist = False
    for h in hashes[:3]:
        exit_code, stdout = _exec_git(cwd, ["cat-file", "-t", h])
        if exit_code == 0 and stdout == "commit":
            commits_exist = True
            break

    # --- Self-check section ---
    self_check = "not_found"
    heading_match = _SELF_CHECK_HEADING.search(content)
    if heading_match:
        check_start = heading_match.start()
        next_heading = content.find("\n## ", check_start + 1)
        section = content[check_start:] if next_heading == -1 else content[check_start:next_heading]
        if _SELF_CHECK_FAIL.search(section):
            self_check = "failed"
        elif _SELF_CHECK_PASS.search(section):
            self_check = "passed"

    if missing_files:
        errors.append("Missing files: " + ", ".join(missing_files))
    if not commits_exist and hashes:
        errors.append("Referenced commit hashes not found in git history")
    if self_check == "failed":
        errors.append("Self-check section indicates failure")

    passed = len(missing_files) == 0 and self_check != "failed"
    return SummaryVerification(
        passed=passed,
        summary_exists=True,
        files_created=FileCheckResult(
            checked=len(files_to_check),
            found=len(files_to_check) - len(missing_files),
            missing=missing_files,
        ),
        commits_exist=commits_exist,
        self_check=self_check,
        errors=errors,
    )


# Task XML patterns
_TASK_ELEMENT_RE = re.compile(r"<task[^>]*>([\s\S]*?)</task>")
_TASK_NAME_RE = re.compile(r"<name>([\s\S]*?)</name>")
_CHECKPOINT_TASK_RE = re.compile(r'<task\s+type=["\']?checkpoint')


@instrument_gpd_function("frontmatter.verify_plan")
def verify_plan_structure(cwd: Path, file_path: Path) -> PlanValidation:
    """Validate plan file structure: required frontmatter, task elements, wave/deps consistency."""
    full_path = file_path if file_path.is_absolute() else cwd / file_path
    content = safe_read_file(full_path)
    if content is None:
        return PlanValidation(valid=False, errors=[f"File not found: {file_path}"])

    try:
        meta, _ = extract_frontmatter(content)
    except FrontmatterParseError as exc:
        return PlanValidation(valid=False, errors=[f"YAML parse error: {exc}"])

    errors: list[str] = []
    warnings: list[str] = []

    # Required frontmatter fields (accept both underscore and hyphen forms)
    for fname in FRONTMATTER_SCHEMAS["plan"]["required"]:
        if _resolve_field(meta, fname) is None:
            errors.append(f"Missing required frontmatter field: {fname}")

    # must_haves validation
    must_haves = meta.get("must_haves") or meta.get("must-haves")
    if must_haves is not None:
        if not isinstance(must_haves, dict):
            if isinstance(must_haves, list):
                if len(must_haves) == 0:
                    errors.append("Invalid must_haves: list must not be empty")
                elif not all(isinstance(v, str) for v in must_haves):
                    errors.append("Invalid must_haves: list items must be strings")
            else:
                errors.append("Invalid must_haves: expected an object or list")

    # Parse task elements
    tasks: list[TaskInfo] = []
    for task_match in _TASK_ELEMENT_RE.finditer(content):
        task_content = task_match.group(1)
        name_match = _TASK_NAME_RE.search(task_content)
        task_name = name_match.group(1).strip() if name_match else "unnamed"

        has_files = "<files>" in task_content
        has_action = "<action>" in task_content
        has_verify = "<verify>" in task_content
        has_done = "<done>" in task_content

        if not name_match:
            errors.append("Task missing <name> element")
        if not has_action:
            errors.append(f"Task '{task_name}' missing <action>")
        if not has_verify:
            warnings.append(f"Task '{task_name}' missing <verify>")
        if not has_done:
            warnings.append(f"Task '{task_name}' missing <done>")
        if not has_files:
            warnings.append(f"Task '{task_name}' missing <files>")

        tasks.append(
            TaskInfo(
                name=task_name,
                has_files=has_files,
                has_action=has_action,
                has_verify=has_verify,
                has_done=has_done,
            )
        )

    if not tasks:
        warnings.append("No <task> elements found")

    # Wave/depends_on consistency
    deps = meta.get("depends_on") or meta.get("depends-on")
    wave = meta.get("wave")
    if wave is not None:
        try:
            wave_int = int(wave)
        except (TypeError, ValueError):
            wave_int = 0
        if wave_int > 1 and (not deps or (isinstance(deps, list) and len(deps) == 0)):
            warnings.append("Wave > 1 but depends_on is empty")

    # Autonomous/checkpoint consistency
    has_checkpoints = bool(_CHECKPOINT_TASK_RE.search(content))
    autonomous = meta.get("autonomous")
    if has_checkpoints and autonomous not in ("false", False):
        errors.append("Has checkpoint tasks but autonomous is not false")

    return PlanValidation(
        valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        task_count=len(tasks),
        tasks=tasks,
        frontmatter_fields=list(meta.keys()),
    )


@instrument_gpd_function("frontmatter.verify_phase")
def verify_phase_completeness(cwd: Path, phase: str) -> PhaseCompleteness:
    """Verify that every plan in a phase has a matching summary.

    Uses lazy import of ``find_phase`` from ``gpd.core.phases``
    to break circular dependency.
    """
    from gpd.core.phases import find_phase

    phase_info = find_phase(cwd, phase)
    if phase_info is None:
        return PhaseCompleteness(
            complete=False,
            errors=[f"Phase not found: {phase}"],
        )

    phase_dir = cwd / phase_info.directory
    if not phase_dir.is_dir():
        return PhaseCompleteness(
            complete=False,
            errors=["Cannot read phase directory"],
        )

    files = [f.name for f in phase_dir.iterdir() if f.is_file()]
    plans = [f for f in files if f.endswith(PLAN_SUFFIX) or f == STANDALONE_PLAN]
    summaries = [f for f in files if f.endswith(SUMMARY_SUFFIX) or f == STANDALONE_SUMMARY]

    # Extract plan IDs
    def plan_id(p: str) -> str:
        if p == STANDALONE_PLAN:
            return "_standalone"
        return p.removesuffix(PLAN_SUFFIX) if p.endswith(PLAN_SUFFIX) else p

    def summary_id(s: str) -> str:
        if s == STANDALONE_SUMMARY:
            return "_standalone"
        return s.removesuffix(SUMMARY_SUFFIX) if s.endswith(SUMMARY_SUFFIX) else s

    plan_ids = {plan_id(p) for p in plans}
    summary_ids = {summary_id(s) for s in summaries}

    incomplete = sorted(plan_ids - summary_ids)
    orphans = sorted(summary_ids - plan_ids)

    errors: list[str] = []
    warnings: list[str] = []
    if incomplete:
        errors.append(f"Plans without summaries: {', '.join(incomplete)}")
    if orphans:
        warnings.append(f"Summaries without plans: {', '.join(orphans)}")

    return PhaseCompleteness(
        complete=len(errors) == 0,
        phase_number=phase_info.phase_number,
        plan_count=len(plans),
        summary_count=len(summaries),
        incomplete_plans=incomplete,
        orphan_summaries=orphans,
        errors=errors,
        warnings=warnings,
    )


# Patterns for file references
_AT_REF_RE = re.compile(r"@([^\s\n,)]+/[^\s\n,)]+)")
_BACKTICK_FILE_RE = re.compile(r"`([^`]+/[^`]+\.[a-zA-Z][a-zA-Z0-9]{0,9})`")


@instrument_gpd_function("frontmatter.verify_references")
def verify_references(cwd: Path, file_path: Path) -> ReferenceVerification:
    """Check that ``@path`` and backtick-quoted file paths actually exist on disk."""
    full_path = file_path if file_path.is_absolute() else cwd / file_path
    content = safe_read_file(full_path)
    if content is None:
        return ReferenceVerification(valid=False, missing=[str(file_path)])

    found: list[str] = []
    missing: list[str] = []
    seen: set[str] = set()

    # @-references
    for m in _AT_REF_RE.finditer(content):
        ref = m.group(1)
        if ref in seen:
            continue
        seen.add(ref)
        resolved = Path.home() / ref[2:] if ref.startswith("~/") else cwd / ref
        (found if resolved.exists() else missing).append(ref)

    # Backtick file paths
    for m in _BACKTICK_FILE_RE.finditer(content):
        ref = m.group(1)
        if ref in seen or ref.startswith("http") or "${" in ref or "{{" in ref:
            continue
        seen.add(ref)
        resolved = cwd / ref
        (found if resolved.exists() else missing).append(ref)

    return ReferenceVerification(
        valid=len(missing) == 0,
        found=len(found),
        missing=missing,
        total=len(found) + len(missing),
    )


@instrument_gpd_function("frontmatter.verify_commits")
def verify_commits(cwd: Path, hashes: list[str]) -> CommitVerification:
    """Verify that git commit hashes exist in the repository."""
    if not hashes:
        raise FrontmatterValidationError("At least one commit hash required")

    valid: list[str] = []
    invalid: list[str] = []
    for h in hashes:
        exit_code, stdout = _exec_git(cwd, ["cat-file", "-t", h])
        if exit_code == 0 and stdout.strip() == "commit":
            valid.append(h)
        else:
            invalid.append(h)

    return CommitVerification(
        all_valid=len(invalid) == 0,
        valid_hashes=valid,
        invalid_hashes=invalid,
        total=len(hashes),
    )


@instrument_gpd_function("frontmatter.verify_artifacts")
def verify_artifacts(cwd: Path, plan_file_path: Path) -> ArtifactVerification:
    """Verify artifacts declared in ``must_haves.artifacts`` of a plan file."""
    full_path = plan_file_path if plan_file_path.is_absolute() else cwd / plan_file_path
    content = safe_read_file(full_path)
    if content is None:
        return ArtifactVerification(
            all_passed=False,
            artifacts=[ArtifactCheck(path=str(plan_file_path), issues=["Plan file not found"])],
            total=1,
        )

    artifacts_list = parse_must_haves_block(content, "artifacts")
    if not artifacts_list:
        return ArtifactVerification(
            all_passed=False,
            artifacts=[],
            total=0,
        )

    results: list[ArtifactCheck] = []
    for artifact in artifacts_list:
        if isinstance(artifact, str):
            exists = (cwd / artifact).exists()
            results.append(
                ArtifactCheck(
                    path=artifact,
                    exists=exists,
                    issues=[] if exists else ["File not found"],
                    passed=exists,
                )
            )
            continue

        if not isinstance(artifact, dict):
            continue
        art_path = artifact.get("path")
        if not art_path:
            continue

        art_full = cwd / art_path
        exists = art_full.exists()
        check = ArtifactCheck(path=art_path, exists=exists)

        if exists:
            file_content = safe_read_file(art_full) or ""
            line_count = file_content.count("\n") + 1

            min_lines = artifact.get("min_lines")
            if min_lines and line_count < min_lines:
                check.issues.append(f"Only {line_count} lines, need {min_lines}")

            contains = artifact.get("contains")
            if contains and contains not in file_content:
                check.issues.append(f"Missing pattern: {contains}")

            expected_results = artifact.get("results")
            if expected_results:
                if not isinstance(expected_results, list):
                    expected_results = [expected_results]
                for res in expected_results:
                    if res not in file_content:
                        check.issues.append(f"Missing result: {res}")

            check.passed = len(check.issues) == 0
        else:
            check.issues.append("File not found")

        results.append(check)

    passed_count = sum(1 for r in results if r.passed)
    return ArtifactVerification(
        all_passed=passed_count == len(results) and len(results) > 0,
        passed_count=passed_count,
        total=len(results),
        artifacts=results,
    )


# Regex safety: reject patterns with nested quantifiers
_UNSAFE_REGEX_RE = re.compile(r"([+*?}])\s*[+*?{]")
_MAX_PATTERN_LEN = 200


@instrument_gpd_function("frontmatter.verify_links")
def verify_key_links(cwd: Path, plan_file_path: Path) -> KeyLinkVerification:
    """Verify key links declared in ``must_haves.key_links`` of a plan file."""
    full_path = plan_file_path if plan_file_path.is_absolute() else cwd / plan_file_path
    content = safe_read_file(full_path)
    if content is None:
        return KeyLinkVerification(
            all_verified=False,
            links=[KeyLinkCheck(from_path=str(plan_file_path), detail="Plan file not found")],
            total=1,
        )

    key_links = parse_must_haves_block(content, "key_links")
    if not key_links:
        return KeyLinkVerification(all_verified=False, total=0)

    results: list[KeyLinkCheck] = []
    for link in key_links:
        if isinstance(link, str):
            exists = (cwd / link).exists()
            results.append(
                KeyLinkCheck(
                    from_path=link,
                    verified=exists,
                    detail="File exists" if exists else "File not found",
                )
            )
            continue

        if not isinstance(link, dict):
            continue

        check = KeyLinkCheck(
            from_path=link.get("from", ""),
            to_path=link.get("to"),
            via=link.get("via", ""),
        )

        if not check.from_path or not check.to_path:
            check.detail = "Malformed key_link: missing from or to field"
            results.append(check)
            continue

        source_content = safe_read_file(cwd / check.from_path)
        if source_content is None:
            check.detail = "Source file not found"
        elif "pattern" in link:
            pattern = link["pattern"]
            # Reject unsafe regex
            if _UNSAFE_REGEX_RE.search(pattern) or len(pattern) > _MAX_PATTERN_LEN:
                check.detail = f"Unsafe regex pattern rejected: {pattern[:50]}"
                results.append(check)
                continue
            try:
                regex = re.compile(pattern)
            except re.error:
                check.detail = f"Invalid regex pattern: {pattern}"
                results.append(check)
                continue

            if regex.search(source_content):
                check.verified = True
                check.detail = "Pattern found in source"
            else:
                target_content = safe_read_file(cwd / check.to_path)
                if target_content and regex.search(target_content):
                    check.verified = True
                    check.detail = "Pattern found in target"
                else:
                    check.detail = f'Pattern "{pattern}" not found in source or target'
        else:
            # No pattern — check source references target
            if check.to_path in source_content:
                check.verified = True
                check.detail = "Target referenced in source"
            else:
                check.detail = "Target not referenced in source"

        results.append(check)

    verified_count = sum(1 for r in results if r.verified)
    return KeyLinkVerification(
        all_verified=verified_count == len(results) and len(results) > 0,
        verified_count=verified_count,
        total=len(results),
        links=results,
    )


# ---------------------------------------------------------------------------
# Template operations
# ---------------------------------------------------------------------------

_FILE_MENTION_RE = re.compile(r"`([^`]+\.[a-zA-Z][a-zA-Z0-9]*)`")
_TASK_HEADING_RE = re.compile(r"###\s*Task\s*\d+")
_DECISION_RE = re.compile(r"decision", re.IGNORECASE)


@instrument_gpd_function("frontmatter.select_template")
def select_template(cwd: Path, plan_path: Path) -> TemplateSelection:
    """Analyse a plan file and recommend a template type: minimal, standard, or complex."""
    full_path = plan_path if plan_path.is_absolute() else cwd / plan_path
    content = safe_read_file(full_path)
    if content is None:
        raise FrontmatterValidationError(f"Plan file not found: {plan_path}")

    task_count = len(_TASK_HEADING_RE.findall(content))
    has_decisions = bool(_DECISION_RE.search(content))

    file_mentions: set[str] = set()
    for m in _FILE_MENTION_RE.finditer(content):
        fp = m.group(1)
        if "/" in fp and not fp.startswith("http"):
            file_mentions.add(fp)
    file_count = len(file_mentions)

    if task_count <= 2 and file_count <= 3 and not has_decisions:
        ttype = "minimal"
    elif has_decisions or file_count > 6 or task_count > 5:
        ttype = "complex"
    else:
        ttype = "standard"

    return TemplateSelection(
        template="templates/summary.md",
        template_type=ttype,
        task_count=task_count,
        file_count=file_count,
        has_decisions=has_decisions,
    )


class TemplateFillOptions(BaseModel):
    """Options for ``fill_template``."""

    phase: str
    name: str | None = None
    plan: str | None = None
    plan_type: str = "execute"
    wave: int | None = None
    fields: dict | None = None


def _normalize_phase_name(phase: str) -> str:
    """Pad a phase number to 2 digits using canonical phase_normalize.

    '3' -> '03', '72.1' -> '72.1', '003' -> '03'.
    """
    return phase_normalize(phase)


def _generate_slug(name: str) -> str:
    """Generate a URL-safe slug from a name.

    Delegates to utils.generate_slug with a non-None fallback.
    """
    return generate_slug(name) or name.lower().strip()


@instrument_gpd_function("frontmatter.fill_template")
def fill_template(
    cwd: Path,
    template_type: str,
    options: TemplateFillOptions,
) -> TemplateResult:
    """Generate a pre-filled template file (summary, plan, or verification) in the phase directory.

    Uses lazy import of ``find_phase`` from ``gpd.core.phases``.
    """
    from gpd.core.phases import find_phase

    phase_info = find_phase(cwd, options.phase)
    if phase_info is None:
        raise FrontmatterValidationError(f"Phase not found: {options.phase}")

    padded = _normalize_phase_name(options.phase)

    from datetime import date

    today = date.today().isoformat()
    phase_name = options.name or phase_info.phase_name or "Unnamed"
    phase_slug = phase_info.phase_slug or _generate_slug(phase_name)
    phase_id = f"{padded}-{phase_slug}"
    plan_num = (options.plan or "01").zfill(2)
    fields = options.fields or {}

    if template_type == "summary":
        frontmatter = {
            "phase": phase_id,
            "plan": plan_num,
            "depth": "standard",
            "one-liner": "[Substantive one-liner describing outcome]",
            "subsystem": "[primary category]",
            "tags": [],
            "requires": [],
            "provides": [],
            "affects": [],
            "methods": {"added": [], "patterns": []},
            "key-files": {"created": [], "modified": []},
            "key-decisions": [],
            "patterns-established": [],
            "duration": "[X]min",
            "completed": today,
            **fields,
        }
        body = "\n".join(
            [
                f"# Phase {options.phase}: {phase_name} Summary",
                "",
                "**[Substantive one-liner describing outcome]**",
                "",
                "## Performance",
                "- **Duration:** [time]",
                "- **Tasks:** [count completed]",
                "- **Files modified:** [count]",
                "",
                "## Accomplishments",
                "- [Key outcome 1]",
                "- [Key outcome 2]",
                "",
                "## Task Commits",
                "1. **Task 1: [task name]** - `hash`",
                "",
                "## Files Created/Modified",
                "- `path/to/calculation.py` - What it does",
                "",
                "## Decisions & Deviations",
                '[Key decisions or "None - followed plan as specified"]',
                "",
                "## Next Phase Readiness",
                "[What's ready for next phase]",
            ]
        )
        file_name = f"{padded}-{plan_num}{SUMMARY_SUFFIX}"

    elif template_type == "plan":
        wave_val = options.wave if options.wave is not None else 1
        frontmatter = {
            "phase": phase_id,
            "plan": plan_num,
            "type": options.plan_type,
            "wave": wave_val,
            "depends_on": [],
            "files_modified": [],
            "autonomous": True,
            "user_setup": [],
            "must_haves": {
                "truths": [],
                "artifacts": [],
                "key_links": [],
                "uncertainties": [],
            },
            **fields,
        }
        body = "\n".join(
            [
                f"# Phase {options.phase} Plan {plan_num}: [Title]",
                "",
                "## Objective",
                "- **What:** [What this plan builds]",
                "- **Why:** [Why it matters for the phase goal]",
                "- **Output:** [Concrete deliverable]",
                "",
                "## Context",
                "@.planning/PROJECT.md",
                "@.planning/ROADMAP.md",
                "@.planning/STATE.md",
                "",
                "## Tasks",
                "",
                '<task type="code">',
                "  <name>[Task name]</name>",
                "  <files>[file paths]</files>",
                "  <action>[What to do]</action>",
                "  <verify>[How to verify]</verify>",
                "  <done>[Definition of done]</done>",
                "</task>",
                "",
                "## Verification",
                "[How to verify this plan achieved its objective]",
                "",
                "## Success Criteria",
                "- [ ] [Criterion 1]",
                "- [ ] [Criterion 2]",
            ]
        )
        file_name = f"{padded}-{plan_num}{PLAN_SUFFIX}"

    elif template_type == "verification":
        frontmatter = {
            "phase": phase_id,
            "verified": today,
            "status": "pending",
            "score": "0/0 must-haves verified",
            **fields,
        }
        body = "\n".join(
            [
                f"# Phase {options.phase}: {phase_name} — Verification",
                "",
                "## Observable Truths",
                "| # | Truth | Status | Evidence |",
                "|---|-------|--------|----------|",
                "| 1 | [Truth] | pending | |",
                "",
                "## Required Artifacts",
                "| Artifact | Expected | Status | Details |",
                "|----------|----------|--------|---------|",
                "| [path] | [what] | pending | |",
                "",
                "## Key Link Verification",
                "| From | To | Via | Status | Details |",
                "|------|----|----|--------|---------|",
                "| [source] | [target] | [connection] | pending | |",
                "",
                "## Requirements Coverage",
                "| Requirement | Status | Blocking Issue |",
                "|-------------|--------|----------------|",
                "| [req] | pending | |",
                "",
                "## Result",
                "[Pending verification]",
            ]
        )
        file_name = f"{padded}{VERIFICATION_SUFFIX}"

    else:
        raise FrontmatterValidationError(
            f"Unknown template type: {template_type}. Available: summary, plan, verification"
        )

    full_content = reconstruct_frontmatter(frontmatter, body) + "\n"
    phase_dir = cwd / phase_info.directory
    out_path = phase_dir / file_name

    if out_path.exists():
        raise FrontmatterValidationError(f"File already exists: {out_path.relative_to(cwd)}")

    _write_file_atomic(out_path, full_content)
    rel_path = str(out_path.relative_to(cwd))
    return TemplateResult(created=True, path=rel_path, template_type=template_type)
