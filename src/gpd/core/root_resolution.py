"""Shared project-root resolution helpers for workspace-aware GPD surfaces.

The resolver keeps two concepts separate:

- the normalized workspace hint supplied by a caller or runtime payload
- the resolved GPD project root used for project-scoped lookups

Resolution prefers an explicit ``project_dir`` only when it can be verified by
walking ancestors for a marker-backed ``GPD/`` directory. If that verification
fails, a verified workspace walk-up still wins over the explicit fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from gpd.core.constants import (
    REQUIRED_PLANNING_DIRS,
    REQUIRED_PLANNING_FILES,
    ProjectLayout,
)

__all__ = [
    "ProjectRootResolution",
    "RootResolutionBasis",
    "RootResolutionConfidence",
    "RootResolutionPolicy",
    "normalize_workspace_hint",
    "resolve_project_root",
    "resolve_project_roots",
]


class RootResolutionBasis(StrEnum):
    """Which caller hint supplied the resolved project root."""

    PROJECT_DIR = "project_dir"
    WORKSPACE = "workspace"


class RootResolutionConfidence(StrEnum):
    """How trustworthy the resolved project root is."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RootResolutionPolicy(StrEnum):
    """How the workspace hint is allowed to resolve a project root."""

    WORKSPACE_LOCKED = "workspace_locked"
    PROJECT_SCOPED = "project_scoped"


@dataclass(frozen=True, slots=True)
class ProjectRootResolution:
    """Typed root-resolution result for workspace-aware callers."""

    workspace_root: Path | None
    project_hint: Path | None
    project_root: Path
    policy: RootResolutionPolicy
    basis: RootResolutionBasis
    confidence: RootResolutionConfidence
    has_project_layout: bool
    walk_up_steps: int

    @property
    def verified(self) -> bool:
        """Return whether the result was verified by locating a marker-backed ``GPD/`` directory."""
        return self.has_project_layout


def normalize_workspace_hint(value: Path | str | None) -> Path | None:
    """Return one normalized absolute path hint or ``None`` when missing."""

    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        raw_path = Path(stripped)
    elif isinstance(value, Path):
        raw_path = value
    else:
        return None

    expanded = raw_path.expanduser()
    try:
        return expanded.resolve(strict=False)
    except OSError:
        return expanded


def _walk_project_root(
    candidate: Path | None,
    *,
    allow_ancestor_walk: bool = True,
) -> tuple[Path | None, int, bool]:
    """Walk *candidate* and its ancestors until the nearest marker-backed ``GPD/`` anchor is found."""

    if candidate is None:
        return None, 0, False

    best_bare: tuple[int, Path] | None = None

    def _has_directory_content(path: Path) -> bool:
        try:
            return path.is_dir() and any(path.iterdir())
        except OSError:
            return False

    def _is_vcs_boundary(path: Path) -> bool:
        """Return whether walking above *path* would cross into a different checkout."""
        return (path / ".git").exists() or (path / ".hg").exists()

    search_roots = (candidate, *candidate.parents) if allow_ancestor_walk else (candidate,)
    for steps, path in enumerate(search_roots):
        layout = ProjectLayout(path)
        if not layout.gpd.is_dir():
            if allow_ancestor_walk and _is_vcs_boundary(path):
                break
            continue

        strong_marker_count = sum(
            1
            for name in REQUIRED_PLANNING_FILES
            if (layout.gpd / name).exists()
        )
        strong_marker_count += 1 if layout.agent_id_file.exists() else 0
        strong_marker_count += sum(1 for name in REQUIRED_PLANNING_DIRS if _has_directory_content(layout.gpd / name))
        strong_marker_count += sum(
            1
            for path in (
                layout.research_map_dir,
                layout.literature_dir,
                layout.knowledge_dir,
                layout.publication_dir,
                layout.review_dir,
                layout.milestones_dir,
                layout.todos_dir,
            )
            if _has_directory_content(path)
        )
        if strong_marker_count > 0:
            return path, steps, True

        if best_bare is None or steps < best_bare[0]:
            best_bare = (steps, path)
        if allow_ancestor_walk and _is_vcs_boundary(path):
            break

    if best_bare is not None:
        return best_bare[1], best_bare[0], False
    return None, 0, False


def resolve_project_roots(
    workspace: Path | str | None = None,
    *,
    project_dir: Path | str | None = None,
    policy: RootResolutionPolicy = RootResolutionPolicy.PROJECT_SCOPED,
) -> ProjectRootResolution | None:
    """Resolve the normalized workspace hint and best project root.

    Precedence is intentionally verification-aware:

    1. verified explicit ``project_dir``
    2. verified workspace walk-up
    3. explicit ``project_dir`` fallback
    4. workspace fallback

    ``policy`` controls only how the workspace hint participates:

    - ``project_scoped`` allows ancestor walk-up from the workspace
    - ``workspace_locked`` keeps the workspace bound to the exact requested path

    Explicit ``project_dir`` hints still verify by ancestor walk-up so callers
    can pass nested project hints without losing the authoritative root.
    """

    workspace_root = normalize_workspace_hint(workspace)
    project_hint = normalize_workspace_hint(project_dir)

    explicit_root, explicit_steps, explicit_verified = _walk_project_root(project_hint)
    if explicit_root is not None and explicit_verified:
        return ProjectRootResolution(
            workspace_root=workspace_root,
            project_hint=project_hint,
            project_root=explicit_root,
            policy=policy,
            basis=RootResolutionBasis.PROJECT_DIR,
            confidence=RootResolutionConfidence.HIGH,
            has_project_layout=True,
            walk_up_steps=explicit_steps,
        )

    workspace_project_root, workspace_steps, workspace_verified = _walk_project_root(
        workspace_root,
        allow_ancestor_walk=policy != RootResolutionPolicy.WORKSPACE_LOCKED,
    )
    if workspace_project_root is not None and workspace_verified:
        return ProjectRootResolution(
            workspace_root=workspace_root,
            project_hint=project_hint,
            project_root=workspace_project_root,
            policy=policy,
            basis=RootResolutionBasis.WORKSPACE,
            confidence=RootResolutionConfidence.HIGH if workspace_verified else RootResolutionConfidence.LOW,
            has_project_layout=workspace_verified,
            walk_up_steps=workspace_steps,
        )

    if explicit_root is not None:
        return ProjectRootResolution(
            workspace_root=workspace_root,
            project_hint=project_hint,
            project_root=explicit_root,
            policy=policy,
            basis=RootResolutionBasis.PROJECT_DIR,
            confidence=RootResolutionConfidence.MEDIUM,
            has_project_layout=False,
            walk_up_steps=explicit_steps,
        )

    if project_hint is not None:
        return ProjectRootResolution(
            workspace_root=workspace_root,
            project_hint=project_hint,
            project_root=project_hint,
            policy=policy,
            basis=RootResolutionBasis.PROJECT_DIR,
            confidence=RootResolutionConfidence.MEDIUM,
            has_project_layout=False,
            walk_up_steps=0,
        )

    if workspace_project_root is not None:
        return ProjectRootResolution(
            workspace_root=workspace_root,
            project_hint=project_hint,
            project_root=workspace_project_root,
            policy=policy,
            basis=RootResolutionBasis.WORKSPACE,
            confidence=RootResolutionConfidence.LOW,
            has_project_layout=False,
            walk_up_steps=workspace_steps,
        )

    if workspace_root is not None:
        return ProjectRootResolution(
            workspace_root=workspace_root,
            project_hint=project_hint,
            project_root=workspace_root,
            policy=policy,
            basis=RootResolutionBasis.WORKSPACE,
            confidence=RootResolutionConfidence.LOW,
            has_project_layout=False,
            walk_up_steps=0,
        )

    return None


def resolve_project_root(
    workspace: Path | str | None = None,
    *,
    project_dir: Path | str | None = None,
    require_layout: bool = False,
    policy: RootResolutionPolicy = RootResolutionPolicy.PROJECT_SCOPED,
) -> Path | None:
    """Return the resolved project root path for single-root callers."""

    resolution = resolve_project_roots(workspace, project_dir=project_dir, policy=policy)
    if resolution is None:
        return None
    if require_layout and not resolution.has_project_layout:
        return None
    return resolution.project_root
