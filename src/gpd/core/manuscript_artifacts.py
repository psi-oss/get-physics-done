"""Helpers for resolving the active manuscript and its publication artifacts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

__all__ = [
    "ManuscriptArtifacts",
    "locate_publication_artifact",
    "resolve_current_manuscript_artifacts",
    "resolve_current_manuscript_entrypoint",
    "resolve_current_manuscript_root",
]


_MANUSCRIPT_TEXT_ENTRYPOINTS = (
    "paper/main.tex",
    "manuscript/main.tex",
    "draft/main.tex",
)
_MANUSCRIPT_MARKDOWN_ENTRYPOINTS = (
    "paper/main.md",
    "manuscript/main.md",
    "draft/main.md",
)
_REPRODUCIBILITY_MANIFEST_FILENAMES = (
    "reproducibility-manifest.json",
    "REPRODUCIBILITY-MANIFEST.json",
)


@dataclass(frozen=True, slots=True)
class ManuscriptArtifacts:
    """Resolved manuscript root plus the publication artifacts next to it."""

    project_root: Path
    manuscript_root: Path | None
    manuscript_entrypoint: Path | None
    artifact_manifest: Path | None
    bibliography_audit: Path | None
    reproducibility_manifest: Path | None


def _candidate_manuscript_entrypoints(project_root: Path, *, allow_markdown: bool) -> tuple[Path, ...]:
    candidates = [project_root / rel_path for rel_path in _MANUSCRIPT_TEXT_ENTRYPOINTS]
    if allow_markdown:
        candidates.extend(project_root / rel_path for rel_path in _MANUSCRIPT_MARKDOWN_ENTRYPOINTS)
    return tuple(candidates)


def resolve_current_manuscript_entrypoint(project_root: Path, *, allow_markdown: bool = True) -> Path | None:
    """Return the active manuscript entrypoint if one exists."""

    for candidate in _candidate_manuscript_entrypoints(project_root, allow_markdown=allow_markdown):
        if candidate.exists():
            return candidate
    return None


def resolve_current_manuscript_root(project_root: Path, *, allow_markdown: bool = True) -> Path | None:
    """Return the directory containing the active manuscript entrypoint."""

    entrypoint = resolve_current_manuscript_entrypoint(project_root, allow_markdown=allow_markdown)
    if entrypoint is None:
        return None
    return entrypoint.parent


def _normalize_manuscript_base(manuscript_root: Path) -> Path:
    if manuscript_root.exists() and manuscript_root.is_file():
        return manuscript_root.parent
    if manuscript_root.suffix in {".tex", ".md"} and not manuscript_root.is_dir():
        return manuscript_root.parent
    return manuscript_root


def locate_publication_artifact(manuscript_root: Path, *filenames: str) -> Path | None:
    """Return the first publication artifact found beside a manuscript root."""

    base_dir = _normalize_manuscript_base(manuscript_root)
    for filename in filenames:
        candidate = base_dir / filename
        if candidate.exists():
            return candidate
    return None


def resolve_current_manuscript_artifacts(
    project_root: Path,
    *,
    allow_markdown: bool = True,
) -> ManuscriptArtifacts:
    """Resolve the active manuscript and the publication artifacts beside it."""

    entrypoint = resolve_current_manuscript_entrypoint(project_root, allow_markdown=allow_markdown)
    manuscript_root = entrypoint.parent if entrypoint is not None else None
    if manuscript_root is None:
        return ManuscriptArtifacts(
            project_root=project_root,
            manuscript_root=None,
            manuscript_entrypoint=None,
            artifact_manifest=None,
            bibliography_audit=None,
            reproducibility_manifest=None,
        )

    return ManuscriptArtifacts(
        project_root=project_root,
        manuscript_root=manuscript_root,
        manuscript_entrypoint=entrypoint,
        artifact_manifest=locate_publication_artifact(manuscript_root, "ARTIFACT-MANIFEST.json"),
        bibliography_audit=locate_publication_artifact(manuscript_root, "BIBLIOGRAPHY-AUDIT.json"),
        reproducibility_manifest=locate_publication_artifact(manuscript_root, *_REPRODUCIBILITY_MANIFEST_FILENAMES),
    )
