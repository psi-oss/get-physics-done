"""Helpers for resolving the active manuscript and its publication artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError as PydanticValidationError

from gpd.mcp.paper.models import ArtifactManifest, PaperConfig, derive_output_filename

__all__ = [
    "ManuscriptArtifacts",
    "locate_publication_artifact",
    "resolve_manuscript_entrypoint_from_root",
    "resolve_current_manuscript_artifacts",
    "resolve_current_manuscript_entrypoint",
    "resolve_current_manuscript_root",
]


_MANUSCRIPT_ROOTS = ("paper", "manuscript", "draft")
_LEGACY_MANUSCRIPT_TEXT_BASENAMES = ("main.tex",)
_LEGACY_MANUSCRIPT_MARKDOWN_BASENAMES = ("main.md",)
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


def _load_artifact_manifest(manuscript_root: Path) -> ArtifactManifest | None:
    manifest_path = manuscript_root / "ARTIFACT-MANIFEST.json"
    if not manifest_path.exists():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        return ArtifactManifest.model_validate(payload)
    except (OSError, json.JSONDecodeError, PydanticValidationError):
        return None


def _manifest_manuscript_entrypoint(manuscript_root: Path, *, allow_markdown: bool) -> Path | None:
    manifest = _load_artifact_manifest(manuscript_root)
    if manifest is None:
        return None
    allowed_suffixes = {".tex"}
    if allow_markdown:
        allowed_suffixes.add(".md")
    for artifact in manifest.artifacts:
        if artifact.category != "tex":
            continue
        candidate = manuscript_root / artifact.path
        if candidate.exists() and candidate.suffix.lower() in allowed_suffixes:
            return candidate
    return None


def _configured_manuscript_entrypoint(manuscript_root: Path, *, allow_markdown: bool) -> Path | None:
    config_path = manuscript_root / "PAPER-CONFIG.json"
    if not config_path.exists():
        return None
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        config = PaperConfig.model_validate(payload)
    except (OSError, json.JSONDecodeError, PydanticValidationError):
        return None

    stem = derive_output_filename(config)
    candidates = [manuscript_root / f"{stem}.tex"]
    if allow_markdown:
        candidates.append(manuscript_root / f"{stem}.md")
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def _legacy_manuscript_entrypoint(manuscript_root: Path, *, allow_markdown: bool) -> Path | None:
    candidates = [manuscript_root / basename for basename in _LEGACY_MANUSCRIPT_TEXT_BASENAMES]
    if allow_markdown:
        candidates.extend(manuscript_root / basename for basename in _LEGACY_MANUSCRIPT_MARKDOWN_BASENAMES)
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def resolve_manuscript_entrypoint_from_root(manuscript_root: Path, *, allow_markdown: bool = True) -> Path | None:
    """Resolve the manuscript entrypoint within one manuscript root directory."""

    if not manuscript_root.exists() or not manuscript_root.is_dir():
        return None
    return (
        _manifest_manuscript_entrypoint(manuscript_root, allow_markdown=allow_markdown)
        or _configured_manuscript_entrypoint(manuscript_root, allow_markdown=allow_markdown)
        or _legacy_manuscript_entrypoint(manuscript_root, allow_markdown=allow_markdown)
    )


def resolve_current_manuscript_entrypoint(project_root: Path, *, allow_markdown: bool = True) -> Path | None:
    """Return the active manuscript entrypoint if one exists."""

    for root_name in _MANUSCRIPT_ROOTS:
        candidate = resolve_manuscript_entrypoint_from_root(
            project_root / root_name,
            allow_markdown=allow_markdown,
        )
        if candidate is not None:
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
