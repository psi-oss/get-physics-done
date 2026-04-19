"""Shared path normalization helpers for publication review artifacts."""

from __future__ import annotations

import posixpath
import re
from pathlib import Path

from gpd.core.manuscript_artifacts import (
    PublicationSubjectResolution,
)
from gpd.core.manuscript_artifacts import (
    publication_root_for_subject as _publication_root_for_subject,
)
from gpd.core.manuscript_artifacts import (
    review_dir_for_subject as _review_dir_for_subject,
)

__all__ = [
    "manuscript_matches_review_artifact_path",
    "normalize_review_path_label",
    "publication_root_for_subject",
    "resolve_review_manuscript_path",
    "review_dir_for_subject",
    "review_artifact_round",
    "review_round_suffix",
]


def publication_root_for_subject(publication_subject: PublicationSubjectResolution) -> Path | None:
    """Return the canonical publication root for one publication subject."""

    return _publication_root_for_subject(publication_subject)


def review_dir_for_subject(publication_subject: PublicationSubjectResolution) -> Path | None:
    """Return the canonical review directory for one publication subject."""

    return _review_dir_for_subject(publication_subject)


def review_artifact_round(path: Path, *, pattern: re.Pattern[str]) -> tuple[int, str] | None:
    """Return the round number and suffix encoded in a review artifact filename."""
    match = pattern.fullmatch(path.name)
    if match is None:
        return None
    round_text = match.group("round")
    if round_text is None:
        return 1, ""
    if round_text.startswith("0"):
        return None
    round_number = int(round_text)
    if round_number <= 1:
        return None
    return round_number, match.group("round_suffix") or ""


def review_round_suffix(round_number: int) -> str:
    """Return the canonical publication round suffix for one round number."""

    return "" if round_number <= 1 else f"-R{round_number}"


def normalize_review_path_label(value: str) -> str:
    """Normalize artifact manuscript path labels across OS-specific separators."""
    normalized = value.strip().replace("\\", "/")
    if not normalized:
        return ""
    return posixpath.normpath(normalized)


def resolve_review_manuscript_path(project_root: Path, manuscript_path: str) -> Path:
    """Resolve one stored manuscript path against the active project root."""

    artifact_path = Path(manuscript_path).expanduser()
    if not artifact_path.is_absolute():
        artifact_path = project_root / artifact_path
    return artifact_path.resolve(strict=False)


def manuscript_matches_review_artifact_path(artifact_path: str, manuscript: Path, *, cwd: Path) -> bool:
    """Return whether a stored manuscript path points at the active manuscript."""
    normalized_artifact_path = normalize_review_path_label(artifact_path)
    if not normalized_artifact_path:
        return False

    resolved_manuscript = resolve_review_manuscript_path(cwd, manuscript.as_posix())
    resolved_cwd = cwd.expanduser().resolve(strict=False)
    candidates = {
        normalize_review_path_label(resolved_manuscript.as_posix()),
        normalize_review_path_label(manuscript.as_posix()),
    }
    try:
        candidates.add(normalize_review_path_label(resolved_manuscript.relative_to(resolved_cwd).as_posix()))
    except ValueError:
        pass
    return normalized_artifact_path in candidates
