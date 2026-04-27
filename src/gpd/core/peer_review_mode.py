"""Shared peer-review target and intake-mode resolution helpers."""

from __future__ import annotations

import dataclasses
import os
from collections.abc import Collection
from pathlib import Path

from gpd.core.artifact_text import PEER_REVIEW_ARTIFACT_SUFFIXES
from gpd.core.constants import ProjectLayout
from gpd.core.manuscript_artifacts import (
    _resolve_manuscript_entrypoint_from_root_resolution as resolve_manuscript_entrypoint_from_root_resolution,
)
from gpd.core.manuscript_artifacts import (
    _supported_manuscript_root_for_target as resolve_supported_manuscript_root_for_target,
)
from gpd.core.manuscript_artifacts import resolve_current_manuscript_resolution

PEER_REVIEW_PROJECT_BACKED_MODE = "project-backed manuscript review"
PEER_REVIEW_STANDALONE_MODE = "standalone explicit-artifact review"
PEER_REVIEW_INTERACTIVE_MODE = "interactive intake"
PEER_REVIEW_INVALID_SUBJECT_MODE = "invalid explicit review target"

_SUPPORTED_MANUSCRIPT_ROOTS_DETAIL = (
    "`paper/`, `manuscript/`, `draft/`, or `GPD/publication/<subject_slug>[/manuscript/]`"
)


def _format_display_path_from_cwd(target: str | Path | None, *, cwd: Path) -> str:
    """Format one path relative to *cwd* when possible."""

    if target is None:
        return ""

    raw_target = str(target)
    if not raw_target:
        return ""

    target_path = Path(raw_target).expanduser()
    if not target_path.is_absolute():
        target_path = cwd.expanduser() / target_path

    resolved_target = target_path.resolve(strict=False)
    resolved_cwd = cwd.expanduser().resolve(strict=False)

    try:
        relative = resolved_target.relative_to(resolved_cwd)
    except ValueError:
        if resolved_target.anchor and resolved_target.anchor == resolved_cwd.anchor:
            relative_text = os.path.relpath(resolved_target, resolved_cwd)
            return "." if relative_text in ("", ".") else Path(relative_text).as_posix()
        return resolved_target.as_posix()

    relative_text = relative.as_posix()
    return "." if relative_text in ("", ".") else f"./{relative_text}"


def _supported_manuscript_root_for_target(project_root: Path, target: Path) -> Path | None:
    """Return the project manuscript root that owns *target*, when supported."""

    return resolve_supported_manuscript_root_for_target(project_root, target)


def path_is_within_supported_manuscript_root(project_root: Path, target: Path) -> bool:
    """Return whether *target* lives under a supported project manuscript root."""

    return _supported_manuscript_root_for_target(project_root, target) is not None


def resolve_review_manuscript_target(
    project_root: Path,
    subject: str | None,
    *,
    allow_markdown: bool = True,
    restrict_to_supported_roots: bool = False,
    workspace_cwd: Path | None = None,
    allowed_suffixes: Collection[str] | None = None,
    display_cwd: Path | None = None,
) -> tuple[Path | None, str]:
    """Resolve one explicit or implicit manuscript/artifact target."""

    project_root = project_root.resolve(strict=False)
    subject_base = (workspace_cwd or project_root).resolve(strict=False)
    detail_cwd = (display_cwd or subject_base).resolve(strict=False)
    normalized_allowed_suffixes = {
        suffix.lower()
        for suffix in (
            allowed_suffixes if allowed_suffixes is not None else ({".tex", ".md"} if allow_markdown else {".tex"})
        )
    }
    if not normalized_allowed_suffixes:
        normalized_allowed_suffixes = {".tex"}

    def _allowed_suffix_message() -> str:
        preferred_order = (".tex", ".md", ".txt", ".pdf", ".docx", ".csv", ".tsv", ".xlsx", ".xlsm")
        ordered_suffixes = [suffix for suffix in preferred_order if suffix in normalized_allowed_suffixes]
        extras = sorted(suffix for suffix in normalized_allowed_suffixes if suffix not in set(preferred_order))
        ordered_suffixes.extend(extras)
        if ordered_suffixes == [".tex"]:
            return ".tex file"
        if len(ordered_suffixes) == 2:
            return f"{ordered_suffixes[0]} or {ordered_suffixes[1]} file"
        return ", ".join(ordered_suffixes[:-1]) + f", or {ordered_suffixes[-1]} file"

    def _supported_root_resolution_for_target(target: Path) -> tuple[Path, object] | tuple[None, None]:
        manuscript_root = _supported_manuscript_root_for_target(project_root, target)
        if manuscript_root is None:
            return None, None
        return manuscript_root, resolve_manuscript_entrypoint_from_root_resolution(
            manuscript_root,
            allow_markdown=allow_markdown,
        )

    if isinstance(subject, str) and subject.strip():
        target = Path(subject.strip())
        if not target.is_absolute():
            target = subject_base / target
        target = target.resolve(strict=False)

        target_is_supported_root = path_is_within_supported_manuscript_root(project_root, target)
        if restrict_to_supported_roots and not target_is_supported_root:
            return (
                None,
                (
                    f"explicit manuscript target must stay under {_SUPPORTED_MANUSCRIPT_ROOTS_DETAIL} "
                    "inside the current project"
                ),
            )
        if not target.exists():
            return None, f"missing explicit manuscript target {_format_display_path_from_cwd(target, cwd=detail_cwd)}"

        if target.is_file():
            target_suffix = target.suffix.lower()
            if target_suffix in normalized_allowed_suffixes:
                if target_suffix in {".tex", ".md"}:
                    manuscript_root, root_resolution = _supported_root_resolution_for_target(target)
                    if manuscript_root is not None and root_resolution is not None:
                        if root_resolution.status != "resolved" or root_resolution.manuscript_entrypoint is None:
                            return (
                                None,
                                (
                                    f"{_format_display_path_from_cwd(manuscript_root, cwd=detail_cwd)} is ambiguous "
                                    f"or inconsistent: {root_resolution.detail}"
                                ),
                            )
                        if root_resolution.manuscript_entrypoint.resolve(strict=False) != target.resolve(strict=False):
                            return (
                                None,
                                (
                                    f"{_format_display_path_from_cwd(target, cwd=detail_cwd)} does not match the resolved "
                                    f"manuscript entrypoint "
                                    f"{_format_display_path_from_cwd(root_resolution.manuscript_entrypoint, cwd=detail_cwd)} "
                                    f"under {_format_display_path_from_cwd(manuscript_root, cwd=detail_cwd)}"
                                ),
                            )
                return target, f"{_format_display_path_from_cwd(target, cwd=detail_cwd)} present"
            if target_suffix == ".md" and normalized_allowed_suffixes == {".tex"}:
                return (
                    None,
                    f"explicit manuscript target must be a .tex file: {_format_display_path_from_cwd(target, cwd=detail_cwd)}",
                )
            return (
                None,
                (
                    f"explicit manuscript target must be a {_allowed_suffix_message()}: "
                    f"{_format_display_path_from_cwd(target, cwd=detail_cwd)}"
                ),
            )

        if target.is_dir():
            manuscript_root, root_resolution = _supported_root_resolution_for_target(target)
            resolution = (
                root_resolution
                if manuscript_root is not None and root_resolution is not None
                else resolve_manuscript_entrypoint_from_root_resolution(target, allow_markdown=allow_markdown)
            )
            if resolution.status == "resolved" and resolution.manuscript_entrypoint is not None:
                if manuscript_root is not None and manuscript_root != target:
                    resolved_entrypoint = resolution.manuscript_entrypoint.resolve(strict=False)
                    try:
                        resolved_entrypoint.relative_to(target)
                    except ValueError:
                        return (
                            None,
                            (
                                f"{_format_display_path_from_cwd(target, cwd=detail_cwd)} does not contain the resolved "
                                f"manuscript entrypoint "
                                f"{_format_display_path_from_cwd(resolution.manuscript_entrypoint, cwd=detail_cwd)} "
                                f"under {_format_display_path_from_cwd(manuscript_root, cwd=detail_cwd)}"
                            ),
                        )
                return (
                    resolution.manuscript_entrypoint,
                    (
                        f"{_format_display_path_from_cwd(target, cwd=detail_cwd)} resolved to "
                        f"{_format_display_path_from_cwd(resolution.manuscript_entrypoint, cwd=detail_cwd)}"
                    ),
                )
            if resolution.status == "missing":
                return None, f"no manuscript entry point found under {_format_display_path_from_cwd(target, cwd=detail_cwd)}"
            return (
                None,
                f"{_format_display_path_from_cwd(target, cwd=detail_cwd)} is ambiguous or inconsistent: {resolution.detail}",
            )

    resolution = resolve_current_manuscript_resolution(project_root, allow_markdown=allow_markdown)
    manuscript = resolution.manuscript_entrypoint
    if manuscript is not None and resolution.status == "resolved":
        return manuscript, f"{_format_display_path_from_cwd(manuscript, cwd=detail_cwd)} present"
    if allow_markdown:
        if resolution.status == "missing":
            return (
                None,
                "no manuscript entrypoint found under paper/, manuscript/, or draft/ "
                "(expected ARTIFACT-MANIFEST.json or PAPER-CONFIG.json-derived output)",
            )
        return None, f"ambiguous or inconsistent manuscript roots: {resolution.detail}"
    if resolution.status == "missing":
        return None, "no LaTeX manuscript entrypoint found under paper/, manuscript/, or draft/"
    return None, f"ambiguous or inconsistent manuscript roots: {resolution.detail}"


@dataclasses.dataclass(frozen=True)
class PeerReviewModeResolution:
    """Resolved peer-review intake mode and supporting target details."""

    resolved_mode: str
    mode_reason: str
    project_exists: bool
    subject: str | None = None
    subject_path: Path | None = None
    resolved_target: Path | None = None
    resolution_detail: str = ""
    standalone_artifact_mode: bool = False


def resolve_peer_review_mode_details(
    project_root: Path,
    subject: str | None,
    *,
    workspace_cwd: Path | None = None,
    display_cwd: Path | None = None,
) -> PeerReviewModeResolution:
    """Resolve peer-review mode from project context and the requested subject."""

    project_root = project_root.resolve(strict=False)
    workspace_cwd = (workspace_cwd or project_root).resolve(strict=False)
    detail_cwd = (display_cwd or workspace_cwd).resolve(strict=False)
    project_exists = ProjectLayout(project_root).project_md.exists()
    normalized_subject = subject.strip() if isinstance(subject, str) and subject.strip() else None

    if normalized_subject is None:
        if project_exists:
            return PeerReviewModeResolution(
                resolved_mode=PEER_REVIEW_PROJECT_BACKED_MODE,
                mode_reason=(
                    "no explicit review target was supplied, so peer review will use the active project manuscript "
                    "when available"
                ),
                project_exists=True,
            )
        return PeerReviewModeResolution(
            resolved_mode=PEER_REVIEW_INTERACTIVE_MODE,
            mode_reason=(
                "no initialized GPD project was detected and no explicit review target was supplied, "
                "so peer review can prompt for one standalone artifact path at runtime"
            ),
            project_exists=False,
        )

    subject_path = Path(normalized_subject)
    if not subject_path.is_absolute():
        subject_path = workspace_cwd / subject_path
    subject_path = subject_path.resolve(strict=False)

    resolved_target, resolution_detail = resolve_review_manuscript_target(
        project_root,
        normalized_subject,
        allow_markdown=True,
        restrict_to_supported_roots=False,
        workspace_cwd=workspace_cwd,
        allowed_suffixes=PEER_REVIEW_ARTIFACT_SUFFIXES,
        display_cwd=detail_cwd,
    )
    if resolved_target is None:
        return PeerReviewModeResolution(
            resolved_mode=PEER_REVIEW_INVALID_SUBJECT_MODE,
            mode_reason=resolution_detail,
            project_exists=project_exists,
            subject=normalized_subject,
            subject_path=subject_path,
            resolution_detail=resolution_detail,
        )

    display_subject = _format_display_path_from_cwd(subject_path, cwd=detail_cwd)
    if project_exists and path_is_within_supported_manuscript_root(project_root, subject_path):
        return PeerReviewModeResolution(
            resolved_mode=PEER_REVIEW_PROJECT_BACKED_MODE,
            mode_reason=(
                f"explicit review target {display_subject} stays under "
                f"{_SUPPORTED_MANUSCRIPT_ROOTS_DETAIL} in the active project"
            ),
            project_exists=True,
            subject=normalized_subject,
            subject_path=subject_path,
            resolved_target=resolved_target,
            resolution_detail=resolution_detail,
        )

    if project_exists:
        mode_reason = (
            f"explicit review target {display_subject} resolves outside `paper/`, `manuscript/`, and `draft/`, "
            "so standalone explicit-artifact intake applies"
        )
    else:
        mode_reason = f"explicit review target {display_subject} is a supported standalone peer-review artifact"
    return PeerReviewModeResolution(
        resolved_mode=PEER_REVIEW_STANDALONE_MODE,
        mode_reason=mode_reason,
        project_exists=project_exists,
        subject=normalized_subject,
        subject_path=subject_path,
        resolved_target=resolved_target,
        resolution_detail=resolution_detail,
        standalone_artifact_mode=True,
    )


def resolve_peer_review_mode(
    project_root: Path,
    subject: str | None,
    *,
    workspace_cwd: Path | None = None,
) -> tuple[str, str]:
    """Return the resolved peer-review intake mode and the reason it was selected."""

    resolution = resolve_peer_review_mode_details(project_root, subject, workspace_cwd=workspace_cwd)
    return resolution.resolved_mode, resolution.mode_reason
