"""Shared project-root resolution helpers for workspace-aware GPD surfaces.

The resolver keeps two concepts separate:

- the normalized workspace hint supplied by a caller or runtime payload
- the resolved GPD project root used for project-scoped lookups

Resolution prefers an explicit ``project_dir`` only when it can be verified by
walking ancestors for a ``GPD/`` directory. If that verification fails, a
verified workspace walk-up still wins over the explicit fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from gpd.core.constants import ProjectLayout

__all__ = [
    "ProjectRootResolution",
    "RootResolutionBasis",
    "RootResolutionConfidence",
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


@dataclass(frozen=True, slots=True)
class ProjectRootResolution:
    """Typed root-resolution result for workspace-aware callers."""

    workspace_root: Path | None
    project_hint: Path | None
    project_root: Path
    basis: RootResolutionBasis
    confidence: RootResolutionConfidence
    has_project_layout: bool
    walk_up_steps: int

    @property
    def verified(self) -> bool:
        """Return whether the result was verified by locating a ``GPD/`` directory."""
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


def _walk_project_root(candidate: Path | None) -> tuple[Path | None, int]:
    """Walk *candidate* and its ancestors until a ``GPD/`` layout is found."""

    if candidate is None:
        return None, 0

    for steps, path in enumerate((candidate, *candidate.parents)):
        if ProjectLayout(path).gpd.exists():
            return path, steps
    return None, 0


def resolve_project_roots(
    workspace: Path | str | None = None,
    *,
    project_dir: Path | str | None = None,
) -> ProjectRootResolution | None:
    """Resolve the normalized workspace hint and best project root.

    Precedence is intentionally verification-aware:

    1. verified explicit ``project_dir``
    2. verified workspace walk-up
    3. explicit ``project_dir`` fallback
    4. workspace fallback
    """

    workspace_root = normalize_workspace_hint(workspace)
    project_hint = normalize_workspace_hint(project_dir)

    explicit_root, explicit_steps = _walk_project_root(project_hint)
    if explicit_root is not None:
        return ProjectRootResolution(
            workspace_root=workspace_root,
            project_hint=project_hint,
            project_root=explicit_root,
            basis=RootResolutionBasis.PROJECT_DIR,
            confidence=RootResolutionConfidence.HIGH,
            has_project_layout=True,
            walk_up_steps=explicit_steps,
        )

    workspace_project_root, workspace_steps = _walk_project_root(workspace_root)
    if workspace_project_root is not None:
        return ProjectRootResolution(
            workspace_root=workspace_root,
            project_hint=project_hint,
            project_root=workspace_project_root,
            basis=RootResolutionBasis.WORKSPACE,
            confidence=RootResolutionConfidence.HIGH,
            has_project_layout=True,
            walk_up_steps=workspace_steps,
        )

    if project_hint is not None:
        return ProjectRootResolution(
            workspace_root=workspace_root,
            project_hint=project_hint,
            project_root=project_hint,
            basis=RootResolutionBasis.PROJECT_DIR,
            confidence=RootResolutionConfidence.MEDIUM,
            has_project_layout=False,
            walk_up_steps=0,
        )

    if workspace_root is not None:
        return ProjectRootResolution(
            workspace_root=workspace_root,
            project_hint=project_hint,
            project_root=workspace_root,
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
) -> Path | None:
    """Return the resolved project root path for compatibility callers."""

    resolution = resolve_project_roots(workspace, project_dir=project_dir)
    if resolution is None:
        return None
    if require_layout and not resolution.has_project_layout:
        return None
    return resolution.project_root
