"""Filesystem validation for spawned-agent artifact handoffs."""

from __future__ import annotations

import fnmatch
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, Field

from gpd.core.return_contract import validate_gpd_return_markdown


class HandoffArtifactValidationResult(BaseModel):
    """Result for reconciling a child ``gpd_return`` with on-disk artifacts."""

    passed: bool
    errors: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    files_written: list[str] = Field(default_factory=list)
    checked_files: list[str] = Field(default_factory=list)
    expected_artifacts: list[str] = Field(default_factory=list)
    expected_globs: list[str] = Field(default_factory=list)
    allowed_roots: list[str] = Field(default_factory=list)


def parse_fresh_after(value: str | None) -> datetime | None:
    """Parse a CLI freshness timestamp."""
    if value is None or not value.strip():
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise ValueError(f"--fresh-after must be an ISO 8601 timestamp, got {value!r}") from exc


def validate_handoff_artifacts_markdown(
    project_root: Path,
    return_markdown: str,
    *,
    expected_artifacts: list[str] | tuple[str, ...] = (),
    expected_globs: list[str] | tuple[str, ...] = (),
    allowed_roots: list[str] | tuple[str, ...] = (),
    required_suffixes: list[str] | tuple[str, ...] = (),
    require_files_written: bool = False,
    fresh_after: datetime | None = None,
) -> HandoffArtifactValidationResult:
    """Validate that a spawned return names real, in-scope artifacts.

    This deliberately validates filesystem truth separately from the base
    ``gpd_return`` schema so workflow prompts can share one artifact gate.
    """
    root = project_root.expanduser().resolve(strict=False)
    errors: list[str] = []
    warnings: list[str] = []

    return_validation = validate_gpd_return_markdown(return_markdown)
    if not return_validation.passed or return_validation.envelope is None:
        return HandoffArtifactValidationResult(
            passed=False,
            errors=list(return_validation.errors),
            warnings=list(return_validation.warnings),
            expected_artifacts=list(expected_artifacts),
            expected_globs=list(expected_globs),
            allowed_roots=list(allowed_roots),
        )

    envelope = return_validation.envelope
    files_written = [_normalize_project_local_path(path) for path in envelope.files_written]
    expected = [_normalize_project_local_path(path) for path in expected_artifacts]
    globs = [_normalize_project_local_path(pattern) for pattern in expected_globs]
    suffixes = tuple(suffix for suffix in required_suffixes if suffix)

    allowed_resolved, allowed_display, allowed_errors = _normalize_allowed_roots(root, allowed_roots)
    errors.extend(allowed_errors)

    if require_files_written and not files_written:
        errors.append("gpd_return.files_written is empty")

    checked_files: list[str] = []
    seen_files: set[str] = set()
    for relpath in files_written:
        if relpath in seen_files:
            warnings.append(f"duplicate files_written entry: {relpath}")
            continue
        seen_files.add(relpath)
        _validate_one_artifact(
            root,
            relpath,
            errors=errors,
            checked_files=checked_files,
            allowed_roots=allowed_resolved,
            required_suffixes=suffixes,
            fresh_after=fresh_after,
        )

    files_written_set = set(files_written)
    for relpath in expected:
        if relpath not in files_written_set:
            errors.append(f"expected artifact not named in gpd_return.files_written: {relpath}")
        if relpath not in seen_files:
            _validate_one_artifact(
                root,
                relpath,
                errors=errors,
                checked_files=checked_files,
                allowed_roots=allowed_resolved,
                required_suffixes=suffixes,
                fresh_after=fresh_after,
            )

    for pattern in globs:
        if not any(fnmatch.fnmatch(relpath, pattern) for relpath in files_written):
            errors.append(f"no files_written artifact matched expected glob: {pattern}")

    return HandoffArtifactValidationResult(
        passed=not errors,
        errors=errors,
        warnings=warnings + list(return_validation.warnings),
        files_written=files_written,
        checked_files=checked_files,
        expected_artifacts=expected,
        expected_globs=globs,
        allowed_roots=allowed_display,
    )


def _normalize_project_local_path(path_text: str) -> str:
    raw = path_text.strip()
    if not raw:
        return raw
    return Path(raw).as_posix()


def _normalize_allowed_roots(root: Path, allowed_roots: list[str] | tuple[str, ...]) -> tuple[list[Path], list[str], list[str]]:
    if not allowed_roots:
        return [root], ["."], []

    resolved_roots: list[Path] = []
    display_roots: list[str] = []
    errors: list[str] = []
    for raw_root in allowed_roots:
        normalized = _normalize_project_local_path(raw_root)
        candidate = Path(normalized).expanduser()
        resolved = candidate.resolve(strict=False) if candidate.is_absolute() else (root / candidate).resolve(strict=False)
        if not resolved.is_relative_to(root):
            errors.append(f"allowed root is outside project root: {raw_root}")
            continue
        resolved_roots.append(resolved)
        display_roots.append(_display_project_path(root, resolved))
    return resolved_roots, display_roots, errors


def _validate_one_artifact(
    root: Path,
    relpath: str,
    *,
    errors: list[str],
    checked_files: list[str],
    allowed_roots: list[Path],
    required_suffixes: tuple[str, ...],
    fresh_after: datetime | None,
) -> None:
    if not relpath:
        errors.append("artifact path is empty")
        return

    raw_path = Path(relpath)
    if raw_path.is_absolute():
        errors.append(f"artifact path must be project-local, not absolute: {relpath}")
        return
    if any(part == ".." for part in raw_path.parts):
        errors.append(f"artifact path must not traverse outside the project: {relpath}")
        return

    resolved = (root / raw_path).resolve(strict=False)
    if not resolved.is_relative_to(root):
        errors.append(f"artifact path resolves outside project root: {relpath}")
        return

    if not any(resolved.is_relative_to(allowed_root) for allowed_root in allowed_roots):
        errors.append(f"artifact path is outside allowed roots: {relpath}")

    if required_suffixes and not any(relpath.endswith(suffix) for suffix in required_suffixes):
        suffix_text = ", ".join(required_suffixes)
        errors.append(f"artifact path does not end with required suffix ({suffix_text}): {relpath}")

    if not resolved.is_file():
        errors.append(f"artifact is missing or not a file: {relpath}")
        return

    try:
        with resolved.open("rb"):
            pass
    except OSError as exc:
        errors.append(f"artifact is not readable: {relpath}: {exc}")
        return

    if fresh_after is not None:
        file_mtime = datetime.fromtimestamp(resolved.stat().st_mtime, tz=fresh_after.tzinfo)
        if file_mtime < fresh_after:
            errors.append(f"artifact is stale relative to --fresh-after: {relpath}")

    if relpath not in checked_files:
        checked_files.append(relpath)


def _display_project_path(root: Path, path: Path) -> str:
    try:
        return path.relative_to(root).as_posix() or "."
    except ValueError:
        return path.as_posix()
