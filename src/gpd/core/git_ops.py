"""Git operations for GPD — commit and pre-commit checks.

Provides:
  cmd_pre_commit_check — validate frontmatter and detect NaN in planning files
  cmd_commit — stage files and create a git commit

Layer 1 code: stdlib + pathlib + pydantic only (plus yaml for frontmatter).
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from pydantic import BaseModel, Field

from gpd.core.constants import PLANNING_DIR_NAME
from gpd.core.errors import ValidationError
from gpd.core.observability import instrument_gpd_function

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


# ---------------------------------------------------------------------------
# NaN detection pattern
# ---------------------------------------------------------------------------

# Matches common NaN representations in markdown/YAML content.
# Avoids false positives like "NaN" inside words (e.g., "Nantes").
_NAN_PATTERN = re.compile(
    r"""
    (?:^|[\s:=,\[\(])   # preceded by start, whitespace, or delimiter
    (?:
        [Nn][Aa][Nn]     # NaN, nan, NAN etc.
        | -?inf          # inf / -inf
        | -?Inf
        | -?INF
        | -?[Ii]nfinity   # Infinity / -Infinity / -infinity
        | \.[Nn][Aa][Nn]  # YAML .nan / .NaN / .NAN
        | -?\.[Ii][Nn][Ff]  # YAML .inf / -.inf / .Inf / .INF
    )
    (?:$|[\s,.\]\);:!?])  # followed by end, whitespace, or delimiter/punctuation
    """,
    re.VERBOSE | re.MULTILINE,
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


def _check_single_file(cwd: Path, file_path: str) -> FileCheckDetail:
    """Run pre-commit checks on a single file."""
    detail = FileCheckDetail(file=file_path)
    full_path = Path(file_path) if Path(file_path).is_absolute() else cwd / file_path

    if not full_path.exists():
        detail.exists = False
        detail.warnings.append(f"File not found: {file_path}")
        return detail

    if not full_path.is_file():
        detail.warnings.append(f"Not a regular file: {file_path}")
        return detail

    try:
        content = full_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        detail.warnings.append(f"Cannot read file: {exc}")
        return detail

    # Only check markdown files for frontmatter
    if full_path.suffix.lower() in (".md", ".markdown"):
        _check_frontmatter(content, detail)

    # NaN detection in all text files
    _check_nan(content, detail)

    return detail


def _check_frontmatter(content: str, detail: FileCheckDetail) -> None:
    """Validate YAML frontmatter in a markdown file."""
    from gpd.core.frontmatter import FrontmatterParseError, extract_frontmatter

    try:
        meta, _ = extract_frontmatter(content)
        detail.frontmatter_valid = True
    except FrontmatterParseError as exc:
        detail.frontmatter_valid = False
        detail.warnings.append(f"Frontmatter YAML parse error: {exc}")


def _check_nan(content: str, detail: FileCheckDetail) -> None:
    """Detect NaN/Inf values in file content."""
    if _NAN_PATTERN.search(content):
        detail.has_nan = True
        detail.warnings.append("File contains NaN or Inf values")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@instrument_gpd_function("git_ops.pre_commit_check")
def cmd_pre_commit_check(cwd: Path, files: list[str]) -> PreCommitCheckResult:
    """Run pre-commit validation checks on planning files.

    Checks:
    1. Frontmatter YAML validity (for .md files)
    2. NaN/Inf detection in file content

    Returns a result with per-file details and overall pass/fail.
    """
    if not files:
        return PreCommitCheckResult(passed=True, files_checked=0)

    details: list[FileCheckDetail] = []
    all_warnings: list[str] = []

    for file_path in files:
        detail = _check_single_file(cwd, file_path)
        details.append(detail)
        all_warnings.extend(detail.warnings)

    # Determine overall pass/fail
    # Fail on: invalid frontmatter, NaN detected, missing files
    passed = all(
        detail.exists
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
        CommitResult with committed status, SHA, and any error.

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

    # Stage files
    rc, stdout, stderr = _exec_git(cwd, ["add", "--", *files_to_stage])
    if rc != 0:
        return CommitResult(
            committed=False,
            message=message,
            files=files_to_stage,
            error=f"git add failed: {stderr or stdout}",
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
        )

    # Commit
    rc, stdout, stderr = _exec_git(cwd, ["commit", "-m", message])
    if rc != 0:
        return CommitResult(
            committed=False,
            message=message,
            files=files_to_stage,
            error=f"git commit failed: {stderr or stdout}",
        )

    # Get the resulting commit SHA
    rc_sha, sha, _ = _exec_git(cwd, ["rev-parse", "--short", "HEAD"])
    commit_sha = sha if rc_sha == 0 else None

    return CommitResult(
        committed=True,
        message=message,
        files=files_to_stage,
        sha=commit_sha,
    )
