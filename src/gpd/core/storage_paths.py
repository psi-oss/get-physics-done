"""Project-local storage-path policy helpers for GPD.

Stage 1 introduces explicit classification and validation for internal durable
paths, user-visible durable paths, and project-local scratch paths without
rewiring existing callers yet.
"""

from __future__ import annotations

import os
import tempfile
from enum import StrEnum
from pathlib import Path

from gpd.core.constants import PLANNING_DIR_NAME, ProjectLayout
from gpd.core.errors import GPDError

__all__ = [
    "DurableOutputKind",
    "ProjectStorageLayout",
    "StorageClass",
    "StoragePathError",
]


class StorageClass(StrEnum):
    """How a path behaves relative to the current project layout."""

    INTERNAL_DURABLE = "internal_durable"
    USER_DURABLE = "user_durable"
    SCRATCH = "scratch"
    PROJECT_LOCAL_OTHER = "project_local_other"
    TEMP_ROOT = "temp_root"
    EXTERNAL = "external"


class DurableOutputKind(StrEnum):
    """Stable project-local directories for user-facing durable outputs."""

    ARTIFACTS = "artifacts"
    CODE = "code"
    DATA = "data"
    DRAFT = "draft"
    EXPORTS = "exports"
    FIGURES = "figures"
    MANUSCRIPT = "manuscript"
    NOTEBOOKS = "notebooks"
    PAPER = "paper"
    REFERENCES = "references"
    SIMULATIONS = "simulations"
    SLIDES = "slides"


class StoragePathError(GPDError, ValueError):
    """Raised when a final output path violates the storage policy."""


_DURABLE_DIR_NAMES: dict[DurableOutputKind, str] = {
    DurableOutputKind.ARTIFACTS: "artifacts",
    DurableOutputKind.CODE: "code",
    DurableOutputKind.DATA: "data",
    DurableOutputKind.DRAFT: "draft",
    DurableOutputKind.EXPORTS: "exports",
    DurableOutputKind.FIGURES: "figures",
    DurableOutputKind.MANUSCRIPT: "manuscript",
    DurableOutputKind.NOTEBOOKS: "notebooks",
    DurableOutputKind.PAPER: "paper",
    DurableOutputKind.REFERENCES: "references",
    DurableOutputKind.SIMULATIONS: "simulations",
    DurableOutputKind.SLIDES: "slides",
}


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def _safe_component(value: str) -> str:
    cleaned = "".join(
        char
        if (char.isascii() and char.isalnum()) or char in "._-"
        else "-"
        for char in value.strip()
    )
    collapsed = cleaned.strip("-")
    return collapsed or "unnamed"


def _dedupe_paths(paths: list[Path]) -> tuple[Path, ...]:
    unique: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return tuple(unique)


class ProjectStorageLayout:
    """Storage policy view over a single project root."""

    __slots__ = ("root", "gpd")

    def __init__(self, root: Path, gpd_dir: str = PLANNING_DIR_NAME) -> None:
        self.root = root.resolve(strict=False)
        self.gpd = ProjectLayout(self.root, gpd_dir=gpd_dir).gpd.resolve(strict=False)

    @property
    def internal_root(self) -> Path:
        return self.gpd

    @property
    def scratch_dir(self) -> Path:
        # Stage 1 keeps scratch aligned with existing .gpd/tmp workflow examples.
        return self.gpd / "tmp"

    def output_dir(self, kind: DurableOutputKind) -> Path:
        return self.root / _DURABLE_DIR_NAMES[kind]

    def phase_artifacts_dir(self, phase_name: str) -> Path:
        return (
            self.output_dir(DurableOutputKind.ARTIFACTS)
            / "phases"
            / _safe_component(phase_name)
        )

    def resolve(self, path: Path | str) -> Path:
        candidate = Path(path)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        return candidate.resolve(strict=False)

    def temp_roots(self) -> tuple[Path, ...]:
        candidates: list[Path] = []
        values = [tempfile.gettempdir()]
        values.extend(os.environ.get(name, "") for name in ("TMPDIR", "TEMP", "TMP"))
        for value in values:
            if not value:
                continue
            raw = Path(value)
            if not raw.is_absolute():
                continue
            candidates.append(raw.resolve(strict=False))
        return _dedupe_paths(candidates)

    def project_root_is_temporary(self) -> bool:
        return any(_is_relative_to(self.root, temp_root) for temp_root in self.temp_roots())

    def classify(self, path: Path | str) -> StorageClass:
        resolved = self.resolve(path)
        if _is_relative_to(resolved, self.scratch_dir):
            return StorageClass.SCRATCH
        if _is_relative_to(resolved, self.gpd):
            return StorageClass.INTERNAL_DURABLE
        if any(_is_relative_to(resolved, self.output_dir(kind)) for kind in DurableOutputKind):
            return StorageClass.USER_DURABLE
        if _is_relative_to(resolved, self.root):
            return StorageClass.PROJECT_LOCAL_OTHER
        if any(_is_relative_to(resolved, temp_root) for temp_root in self.temp_roots()):
            return StorageClass.TEMP_ROOT
        return StorageClass.EXTERNAL

    def validate_internal_output(self, path: Path | str) -> Path:
        resolved = self.resolve(path)
        classification = self.classify(resolved)
        if classification != StorageClass.INTERNAL_DURABLE:
            raise StoragePathError(
                f"Internal durable outputs must stay under {self.gpd}, got {resolved} ({classification})."
            )
        return resolved

    def validate_user_output(self, path: Path | str, *, kind: DurableOutputKind | None = None) -> Path:
        resolved = self.resolve(path)
        classification = self.classify(resolved)
        if classification != StorageClass.USER_DURABLE:
            raise StoragePathError(
                "User-visible durable outputs must land in a stable project directory, "
                f"got {resolved} ({classification})."
            )
        if kind is not None and not _is_relative_to(resolved, self.output_dir(kind)):
            raise StoragePathError(
                f"Expected a {kind.value} output under {self.output_dir(kind)}, got {resolved}."
            )
        return resolved
