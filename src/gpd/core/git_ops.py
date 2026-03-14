"""Git operations for GPD — commit and pre-commit checks.

Provides:
  cmd_pre_commit_check — validate storage paths, frontmatter, and non-finite values
  cmd_commit — stage files, enforce pre-commit checks, and create a git commit

Layer 1 code: stdlib + pathlib + pydantic only (plus yaml for frontmatter).
"""

from __future__ import annotations

import json
import math
import re
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from gpd.core.constants import PLANNING_DIR_NAME
from gpd.core.errors import ConfigError, ValidationError
from gpd.core.observability import instrument_gpd_function
from gpd.core.storage_paths import ProjectStorageLayout, StoragePathError

__all__ = [
    "CommitResult",
    "FileCheckDetail",
    "PreCommitCheckResult",
    "cmd_commit",
    "cmd_pre_commit_check",
]


# ---------------------------------------------------------------------------
# Result models
# ---------------------------------------------------------------------------


class FileCheckDetail(BaseModel):
    """Result of checking a single file during pre-commit."""

    file: str
    exists: bool = True
    regular_file: bool = True
    readable: bool = True
    storage_valid: bool | None = None
    storage_class: str | None = None
    frontmatter_valid: bool | None = None
    has_nan: bool = False
    warnings: list[str] = Field(default_factory=list)


class PreCommitCheckResult(BaseModel):
    """Result of running pre-commit checks on a set of files."""

    passed: bool
    files_checked: int = 0
    warnings: list[str] = Field(default_factory=list)
    details: list[FileCheckDetail] = Field(default_factory=list)


class CommitResult(BaseModel):
    """Result of a git commit operation."""

    committed: bool
    message: str
    files: list[str] = Field(default_factory=list)
    sha: str | None = None
    error: str | None = None
    skipped: bool = False
    reason: str | None = None
    pre_commit: PreCommitCheckResult | None = None


# ---------------------------------------------------------------------------
# Non-finite detection patterns
# ---------------------------------------------------------------------------

# Keep text scanning focused on serialized non-finite values rather than
# natural-language mentions or physics limit notation like `T -> inf`.
_NONFINITE_TOKEN_RE = re.compile(
    r"(?i)^(?:nan|[+-]?inf|\.nan|[+-]?\.inf)$",
)
_NUMERICISH_TOKEN_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
_KEY_VALUE_NONFINITE_RE = re.compile(
    r"""
    ^\s*
    (?:[-*]\s+)?        # optional markdown bullet
    [^:=\n][^:=\n]*?    # key / label
    \s*:\s*
    (?P<value>.+?)
    \s*$
    """,
    re.VERBOSE,
)
_ASSIGNMENT_NONFINITE_RE = re.compile(
    r"""
    ^\s*
    (?:[-*]\s+)?        # optional markdown bullet
    [^=\n][^=\n]*?      # lhs
    \s*=\s*
    (?P<value>.+?)
    \s*$
    """,
    re.VERBOSE,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _exec_git(cwd: Path, args: list[str], *, timeout: int = 30) -> tuple[int, str, str]:
    """Run a git command, return (exit_code, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout.strip(), result.stderr.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError) as exc:
        return 1, "", str(exc)


def _staged_files(cwd: Path) -> list[str]:
    """Return staged file paths relative to *cwd* when available."""
    rc, stdout, _ = _exec_git(cwd, ["diff", "--cached", "--name-only", "--diff-filter=ACMR"])
    if rc != 0 or not stdout:
        return []
    return [line.strip() for line in stdout.splitlines() if line.strip()]


def _expand_check_inputs(cwd: Path, files: list[str]) -> list[str]:
    """Resolve staged-file defaults and expand directory inputs recursively."""
    inputs = files or _staged_files(cwd)
    expanded: list[str] = []
    seen: set[str] = set()

    for file_path in inputs:
        input_path = Path(file_path)
        full_path = input_path if input_path.is_absolute() else cwd / input_path

        if full_path.is_dir():
            for child in sorted(path for path in full_path.rglob("*") if path.is_file()):
                resolved = str(child if input_path.is_absolute() else child.relative_to(cwd))
                if resolved not in seen:
                    seen.add(resolved)
                    expanded.append(resolved)
            continue

        normalized = str(input_path if input_path.is_absolute() else file_path)
        if normalized not in seen:
            seen.add(normalized)
            expanded.append(normalized)

    return expanded


def _token_is_nonfinite(token: str) -> bool:
    """Return True when *token* is a serialized non-finite value token."""
    return bool(_NONFINITE_TOKEN_RE.fullmatch(token.strip()))


def _value_is_nonfinite(value: object) -> bool:
    """Recursively detect non-finite numeric values in parsed content."""
    if isinstance(value, float):
        return math.isnan(value) or math.isinf(value)
    if isinstance(value, dict):
        return any(_value_is_nonfinite(item) for item in value.values())
    if isinstance(value, (list, tuple, set)):
        return any(_value_is_nonfinite(item) for item in value)
    return False


def _line_is_key_value_nonfinite(line: str) -> bool:
    """Match `key: NaN` and similar structured key-value lines."""
    match = _KEY_VALUE_NONFINITE_RE.match(line)
    if match:
        return _token_is_nonfinite(match.group("value"))
    match = _ASSIGNMENT_NONFINITE_RE.match(line)
    if match:
        return _token_is_nonfinite(match.group("value"))
    return False


def _line_has_nonfinite_table_cell(line: str) -> bool:
    """Detect exact non-finite tokens in markdown table cells."""
    if "|" not in line:
        return False
    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
    return any(_token_is_nonfinite(cell) for cell in cells if cell)


def _is_numericish_token(token: str) -> bool:
    """Return True for finite numeric tokens used in delimited data files."""
    return bool(_NUMERICISH_TOKEN_RE.fullmatch(token))


def _line_has_nonfinite_data_cell(line: str) -> bool:
    """Detect non-finite values in delimited numeric data rows."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return False

    if "," in stripped:
        cells = [cell.strip() for cell in stripped.split(",")]
    elif "\t" in stripped:
        cells = [cell.strip() for cell in stripped.split("\t")]
    else:
        cells = stripped.split()
        if len(cells) < 2:
            return False

    nonempty = [cell for cell in cells if cell]
    if not nonempty or not any(_token_is_nonfinite(cell) for cell in nonempty):
        return False

    numericish_count = sum(
        1 for cell in nonempty if _token_is_nonfinite(cell) or _is_numericish_token(cell)
    )
    return numericish_count >= max(2, len(nonempty) - 1)


def _text_contains_nonfinite_value(content: str) -> bool:
    """Detect serialized non-finite values while avoiding prose false positives."""
    for line in content.splitlines():
        stripped = line.strip()
        if not stripped:
            continue

        bare = stripped.lstrip("-* ").strip()
        if _token_is_nonfinite(bare):
            return True
        if _line_is_key_value_nonfinite(stripped):
            return True
        if _line_has_nonfinite_table_cell(stripped):
            return True
        if _line_has_nonfinite_data_cell(stripped):
            return True

    return False


def _mark_nonfinite(detail: FileCheckDetail) -> None:
    """Mark a file as containing serialized non-finite values."""
    if detail.has_nan:
        return
    detail.has_nan = True
    detail.warnings.append("File contains NaN or Inf values")


def _check_markdown(content: str, detail: FileCheckDetail) -> None:
    """Validate markdown frontmatter and detect non-finite serialized values."""
    from gpd.core.frontmatter import FrontmatterParseError, extract_frontmatter

    body = content
    meta: dict[str, object] | None = None
    try:
        meta, body = extract_frontmatter(content)
        detail.frontmatter_valid = True
    except FrontmatterParseError as exc:
        detail.frontmatter_valid = False
        detail.warnings.append(f"Frontmatter YAML parse error: {exc}")

    if meta is not None and _value_is_nonfinite(meta):
        _mark_nonfinite(detail)
    if _text_contains_nonfinite_value(body):
        _mark_nonfinite(detail)


def _check_json(content: str, detail: FileCheckDetail) -> None:
    """Detect non-finite values in JSON and JSON-like text files."""
    try:
        parsed = json.loads(content)
    except json.JSONDecodeError:
        if _text_contains_nonfinite_value(content):
            _mark_nonfinite(detail)
        return

    if _value_is_nonfinite(parsed):
        _mark_nonfinite(detail)


def _check_storage_path(layout: ProjectStorageLayout, full_path: Path, detail: FileCheckDetail) -> None:
    """Validate that the file path itself is safe to commit."""
    detail.storage_class = layout.classify(full_path).value
    try:
        layout.validate_commit_target(full_path)
        detail.storage_valid = True
    except StoragePathError as exc:
        detail.storage_valid = False
        detail.warnings.append(str(exc))


def _check_single_file(cwd: Path, file_path: str, *, layout: ProjectStorageLayout) -> FileCheckDetail:
    """Run pre-commit checks on a single file."""
    detail = FileCheckDetail(file=file_path)
    full_path = Path(file_path) if Path(file_path).is_absolute() else cwd / file_path

    if not full_path.exists():
        detail.exists = False
        detail.warnings.append(f"File not found: {file_path}")
        return detail

    if not full_path.is_file():
        detail.regular_file = False
        detail.warnings.append(f"Not a regular file: {file_path}")
        return detail

    _check_storage_path(layout, full_path.resolve(strict=False), detail)

    try:
        content = full_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        detail.readable = False
        detail.warnings.append(f"Cannot read file: {exc}")
        return detail

    suffix = full_path.suffix.lower()
    if suffix in (".md", ".markdown"):
        _check_markdown(content, detail)
    elif suffix == ".json":
        _check_json(content, detail)
    elif _text_contains_nonfinite_value(content):
        _mark_nonfinite(detail)

    return detail


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@instrument_gpd_function("git_ops.pre_commit_check")
def cmd_pre_commit_check(cwd: Path, files: list[str]) -> PreCommitCheckResult:
    """Run pre-commit validation checks on planning files.

    Checks:
    1. Storage-path policy for commit targets
    2. Frontmatter YAML validity (for .md files)
    3. NaN/Inf detection in serialized file content

    Behavior:
    - If *files* is empty, validates the currently staged files.
    - Directory inputs are expanded recursively to regular files.
    - Blocks scratch/internal artifact paths while allowing normal `.gpd` docs.
    """
    resolved_files = _expand_check_inputs(cwd, files)
    if not resolved_files:
        return PreCommitCheckResult(passed=True, files_checked=0)

    layout = ProjectStorageLayout(cwd)
    details: list[FileCheckDetail] = []
    all_warnings: list[str] = []

    for file_path in resolved_files:
        detail = _check_single_file(cwd, file_path, layout=layout)
        details.append(detail)
        all_warnings.extend(detail.warnings)

    # Determine overall pass/fail
    # Fail on: storage violations, invalid frontmatter, NaN detected, missing files
    passed = all(
        detail.exists
        and detail.regular_file
        and detail.readable
        and detail.storage_valid is not False
        and detail.frontmatter_valid is not False
        and not detail.has_nan
        for detail in details
    )

    return PreCommitCheckResult(
        passed=passed,
        files_checked=len(details),
        warnings=all_warnings,
        details=details,
    )


@instrument_gpd_function("git_ops.commit")
def cmd_commit(
    cwd: Path,
    message: str,
    files: list[str] | None = None,
) -> CommitResult:
    """Stage specified files (or all .gpd/ changes) and create a git commit.

    Args:
        cwd: Project root directory.
        message: Commit message.
        files: Specific files to stage. If empty/None, stages all .gpd/ changes.

    Returns:
        CommitResult with commit status, any skip reason, and pre-commit details.

    Raises:
        ValidationError: If message is empty.
    """
    if not message or not message.strip():
        raise ValidationError("Commit message is required")

    # Determine files to stage
    files_to_stage: list[str]
    if files:
        files_to_stage = list(files)
    else:
        files_to_stage = [f"{PLANNING_DIR_NAME}/"]

    try:
        from gpd.core.config import load_config

        config = load_config(cwd)
    except ConfigError as exc:
        return CommitResult(
            committed=False,
            message=message,
            files=files_to_stage,
            error=f"config load failed: {exc}",
            reason="config_error",
        )

    if not config.commit_docs:
        return CommitResult(
            committed=False,
            message=message,
            files=files_to_stage,
            skipped=True,
            reason="commit_docs_disabled",
        )

    pre_commit = cmd_pre_commit_check(cwd, files_to_stage)
    if not pre_commit.passed:
        warning_summary = "; ".join(dict.fromkeys(pre_commit.warnings)) or "validation failed"
        return CommitResult(
            committed=False,
            message=message,
            files=files_to_stage,
            error=f"pre-commit check failed: {warning_summary}",
            reason="pre_commit_check_failed",
            pre_commit=pre_commit,
        )

    # Stage files
    rc, stdout, stderr = _exec_git(cwd, ["add", "--", *files_to_stage])
    if rc != 0:
        return CommitResult(
            committed=False,
            message=message,
            files=files_to_stage,
            error=f"git add failed: {stderr or stdout}",
            reason="git_add_failed",
        )

    # Check if there's anything to commit
    rc, stdout, stderr = _exec_git(cwd, ["diff", "--cached", "--quiet"])
    if rc == 0:
        # Nothing staged — no changes to commit
        return CommitResult(
            committed=False,
            message=message,
            files=files_to_stage,
            error="nothing to commit (no staged changes)",
            reason="nothing_to_commit",
        )

    # Commit
    rc, stdout, stderr = _exec_git(cwd, ["commit", "-m", message])
    if rc != 0:
        return CommitResult(
            committed=False,
            message=message,
            files=files_to_stage,
            error=f"git commit failed: {stderr or stdout}",
            reason="git_commit_failed",
        )

    # Get the resulting commit SHA
    rc_sha, sha, _ = _exec_git(cwd, ["rev-parse", "--short", "HEAD"])
    commit_sha = sha if rc_sha == 0 else None

    return CommitResult(
        committed=True,
        message=message,
        files=files_to_stage,
        sha=commit_sha,
        reason="committed",
    )
