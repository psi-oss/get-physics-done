"""Project-local storage-path policy helpers for GPD.

These helpers classify and validate internal durable paths, user-visible
durable paths, and project-local scratch paths so callers can route outputs
consistently.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from gpd.core.constants import PLANNING_DIR_NAME, ProjectLayout
from gpd.core.errors import GPDError

__all__ = [
    "DurableOutputKind",
    "ProjectStorageLayout",
    "StorageClass",
    "StoragePathCheck",
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


@dataclass(frozen=True, slots=True)
class StoragePathCheck:
    """Warning-mode inspection result for a candidate storage path."""

    path: Path
    classification: StorageClass
    kind: DurableOutputKind | None = None
    warnings: tuple[str, ...] = ()

    @property
    def ok(self) -> bool:
        return not self.warnings


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

_SUSPICIOUS_INTERNAL_SEGMENTS: frozenset[str] = frozenset(
    {"results", "figures", "plots", "data", "exports", "simulations", "artifacts"}
)
_SUSPICIOUS_DURABLE_SUFFIXES: frozenset[str] = frozenset(
    {
        ".pdf",
        ".png",
        ".jpg",
        ".jpeg",
        ".svg",
        ".eps",
        ".tiff",
        ".csv",
        ".tsv",
        ".dat",
        ".h5",
        ".hdf5",
        ".npy",
        ".npz",
        ".parquet",
        ".tex",
    }
)
_SCRATCH_TEMP_SUFFIXES: frozenset[str] = frozenset({".tmp", ".lock", ".bak"})


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

    def phase_operation_dir(self, phase_name: str, operation: str, *, slug: str | None = None) -> Path:
        path = self.phase_artifacts_dir(phase_name) / _safe_component(operation)
        if slug is not None:
            path /= _safe_component(slug)
        return path

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

    def check_user_output(self, path: Path | str, *, kind: DurableOutputKind | None = None) -> StoragePathCheck:
        resolved = self.resolve(path)
        classification = self.classify(resolved)
        warnings: list[str] = []

        if self.project_root_is_temporary():
            warnings.append(f"Project root is under a temporary directory: {self.root}")

        if classification != StorageClass.USER_DURABLE:
            warnings.append(
                "User-visible durable outputs should land in a stable project directory, "
                f"got {resolved} ({classification})."
            )
        elif kind is not None and not _is_relative_to(resolved, self.output_dir(kind)):
            warnings.append(f"Expected a {kind.value} output under {self.output_dir(kind)}, got {resolved}.")

        return StoragePathCheck(
            path=resolved,
            classification=classification,
            kind=kind,
            warnings=tuple(warnings),
        )

    def audit_storage_warnings(self) -> tuple[str, ...]:
        warnings: list[str] = []
        if self.project_root_is_temporary():
            warnings.append(f"Project root is under a temporary directory: {self.root}")

        if self.gpd.exists():
            for path in self.gpd.rglob("*"):
                if not path.is_file():
                    continue
                rel = path.relative_to(self.root)
                suffix = path.suffix.lower()

                if _is_relative_to(path, self.scratch_dir) and suffix not in _SCRATCH_TEMP_SUFFIXES:
                    warnings.append(f"Scratch file should not be treated as durable output: {rel}")
                    continue

                if any(segment in _SUSPICIOUS_INTERNAL_SEGMENTS for segment in rel.parts):
                    warnings.append(f"Suspicious durable-artifact path under internal storage: {rel}")
                    continue

                if (
                    (_is_relative_to(path, self.gpd / "phases") or _is_relative_to(path, self.gpd / "paper"))
                    and suffix in _SUSPICIOUS_DURABLE_SUFFIXES
                ):
                    warnings.append(f"Artifact-like file stored under internal metadata directories: {rel}")

        return tuple(dict.fromkeys(warnings))
