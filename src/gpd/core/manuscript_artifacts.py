"""Helpers for resolving the active manuscript and its publication artifacts."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import ValidationError as PydanticValidationError

from gpd.mcp.paper.models import ArtifactManifest, PaperConfig, derive_output_filename

__all__ = [
    "ManuscriptArtifacts",
    "ManuscriptResolution",
    "ManuscriptRootResolution",
    "locate_publication_artifact",
    "resolve_manuscript_entrypoint_from_root",
    "resolve_current_manuscript_artifacts",
    "resolve_current_manuscript_entrypoint",
    "resolve_current_manuscript_resolution",
    "resolve_current_manuscript_root",
]


_MANUSCRIPT_ROOTS = ("paper", "manuscript", "draft")
_REPRODUCIBILITY_MANIFEST_FILENAME = "reproducibility-manifest.json"


@dataclass(frozen=True, slots=True)
class ManuscriptArtifacts:
    """Resolved manuscript root plus the publication artifacts next to it."""

    project_root: Path
    manuscript_root: Path | None
    manuscript_entrypoint: Path | None
    artifact_manifest: Path | None
    bibliography_audit: Path | None
    reproducibility_manifest: Path | None


ManuscriptResolutionStatus = Literal["resolved", "missing", "ambiguous", "invalid"]


@dataclass(frozen=True, slots=True)
class ManuscriptRootResolution:
    """Resolution details for one candidate manuscript root directory."""

    status: Literal["resolved", "missing", "invalid"]
    manuscript_root: Path
    manuscript_entrypoint: Path | None
    detail: str


@dataclass(frozen=True, slots=True)
class ManuscriptResolution:
    """Resolution details for the current project-wide manuscript state."""

    status: ManuscriptResolutionStatus
    manuscript_root: Path | None
    manuscript_entrypoint: Path | None
    detail: str
    root_resolutions: tuple[ManuscriptRootResolution, ...] = ()


def _load_artifact_manifest(manuscript_root: Path) -> ArtifactManifest | None:
    manifest_path = manuscript_root / "ARTIFACT-MANIFEST.json"
    if not manifest_path.exists():
        return None
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        return ArtifactManifest.model_validate(payload)
    except (OSError, json.JSONDecodeError, PydanticValidationError):
        return None


def _manifest_entrypoints(manuscript_root: Path, *, allow_markdown: bool) -> tuple[Path, ...]:
    manifest = _load_artifact_manifest(manuscript_root)
    if manifest is None:
        return ()

    allowed_suffixes = {".tex"}
    if allow_markdown:
        allowed_suffixes.add(".md")
    candidates: list[Path] = []
    for artifact in manifest.artifacts:
        if artifact.category != "tex":
            continue
        candidate = (manuscript_root / artifact.path).resolve(strict=False)
        try:
            candidate.relative_to(manuscript_root.resolve(strict=False))
        except ValueError:
            continue
        if candidate.exists() and candidate.suffix.lower() in allowed_suffixes:
            candidates.append(candidate)
    return tuple(dict.fromkeys(candidates))


def _configured_entrypoints(manuscript_root: Path, *, allow_markdown: bool) -> tuple[Path, ...]:
    config_path = manuscript_root / "PAPER-CONFIG.json"
    if not config_path.exists():
        return ()
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        config = PaperConfig.model_validate(payload)
    except (OSError, json.JSONDecodeError, PydanticValidationError):
        return ()

    stem = derive_output_filename(config)
    candidates = [manuscript_root / f"{stem}.tex"]
    if allow_markdown:
        candidates.append(manuscript_root / f"{stem}.md")
    return tuple(candidate for candidate in candidates if candidate.exists())


def _resolve_manuscript_entrypoint_from_root_resolution(
    manuscript_root: Path,
    *,
    allow_markdown: bool,
) -> ManuscriptRootResolution:
    if not manuscript_root.exists() or not manuscript_root.is_dir():
        return ManuscriptRootResolution(
            status="missing",
            manuscript_root=manuscript_root,
            manuscript_entrypoint=None,
            detail=f"{manuscript_root} does not exist",
        )

    manifest_entrypoints = _manifest_entrypoints(manuscript_root, allow_markdown=allow_markdown)
    configured_entrypoints = _configured_entrypoints(manuscript_root, allow_markdown=allow_markdown)
    manifest_path = manuscript_root / "ARTIFACT-MANIFEST.json"
    config_path = manuscript_root / "PAPER-CONFIG.json"

    manifest_valid = _load_artifact_manifest(manuscript_root) is not None
    manifest_present = manifest_path.exists()
    config_present = config_path.exists()
    manifest_entrypoint = manifest_entrypoints[0] if len(manifest_entrypoints) == 1 else None
    configured_entrypoint = configured_entrypoints[0] if len(configured_entrypoints) == 1 else None

    if len(manifest_entrypoints) > 1:
        return ManuscriptRootResolution(
            status="invalid",
            manuscript_root=manuscript_root,
            manuscript_entrypoint=None,
            detail=f"{manifest_path} declares multiple readable manuscript entrypoints",
        )
    if len(configured_entrypoints) > 1:
        return ManuscriptRootResolution(
            status="invalid",
            manuscript_root=manuscript_root,
            manuscript_entrypoint=None,
            detail=f"{config_path} resolves to multiple readable manuscript entrypoints",
        )
    if manifest_entrypoint is not None and configured_entrypoint is not None:
        if manifest_entrypoint.resolve(strict=False) != configured_entrypoint.resolve(strict=False):
            return ManuscriptRootResolution(
                status="invalid",
                manuscript_root=manuscript_root,
                manuscript_entrypoint=None,
                detail=(
                    f"{manifest_path} resolves to {manifest_entrypoint.name} but "
                    f"{config_path} resolves to {configured_entrypoint.name}"
                ),
            )
        return ManuscriptRootResolution(
            status="resolved",
            manuscript_root=manuscript_root,
            manuscript_entrypoint=manifest_entrypoint,
            detail=f"{manifest_entrypoint} resolved from manifest and config",
        )
    if manifest_entrypoint is not None and config_present and configured_entrypoint is None:
        return ManuscriptRootResolution(
            status="invalid",
            manuscript_root=manuscript_root,
            manuscript_entrypoint=None,
            detail=(
                f"{manifest_path} resolves to {manifest_entrypoint.name} but "
                f"{config_path} does not resolve to a readable manuscript entrypoint"
            ),
        )
    if configured_entrypoint is not None:
        return ManuscriptRootResolution(
            status="resolved",
            manuscript_root=manuscript_root,
            manuscript_entrypoint=configured_entrypoint,
            detail=f"{configured_entrypoint} resolved from paper config",
        )
    if config_present and configured_entrypoint is None:
        return ManuscriptRootResolution(
            status="missing",
            manuscript_root=manuscript_root,
            manuscript_entrypoint=None,
            detail=f"{config_path} exists but no manuscript output has been generated yet",
        )
    if manifest_entrypoint is not None:
        return ManuscriptRootResolution(
            status="resolved",
            manuscript_root=manuscript_root,
            manuscript_entrypoint=manifest_entrypoint,
            detail=f"{manifest_entrypoint} resolved from artifact manifest",
        )
    if manifest_present and manifest_valid and manifest_entrypoint is None:
        return ManuscriptRootResolution(
            status="missing",
            manuscript_root=manuscript_root,
            manuscript_entrypoint=None,
            detail=f"{manifest_path} does not resolve to a readable manuscript entrypoint",
        )
    if manifest_present or config_present:
        return ManuscriptRootResolution(
            status="missing",
            manuscript_root=manuscript_root,
            manuscript_entrypoint=None,
            detail=f"{manuscript_root} contains manuscript metadata but no readable entrypoint",
        )
    return ManuscriptRootResolution(
        status="missing",
        manuscript_root=manuscript_root,
        manuscript_entrypoint=None,
        detail=f"{manuscript_root} does not contain manuscript metadata",
    )


def _manifest_manuscript_entrypoint(manuscript_root: Path, *, allow_markdown: bool) -> Path | None:
    candidates = _manifest_entrypoints(manuscript_root, allow_markdown=allow_markdown)
    return candidates[0] if len(candidates) == 1 else None


def _configured_manuscript_entrypoint(manuscript_root: Path, *, allow_markdown: bool) -> Path | None:
    candidates = _configured_entrypoints(manuscript_root, allow_markdown=allow_markdown)
    return candidates[0] if len(candidates) == 1 else None


def resolve_manuscript_entrypoint_from_root(manuscript_root: Path, *, allow_markdown: bool = True) -> Path | None:
    """Resolve the manuscript entrypoint within one manuscript root directory."""

    resolution = _resolve_manuscript_entrypoint_from_root_resolution(manuscript_root, allow_markdown=allow_markdown)
    return resolution.manuscript_entrypoint if resolution.status == "resolved" else None


def resolve_current_manuscript_resolution(project_root: Path, *, allow_markdown: bool = True) -> ManuscriptResolution:
    """Return the active manuscript resolution status for the project."""

    root_resolutions = tuple(
        _resolve_manuscript_entrypoint_from_root_resolution(project_root / root_name, allow_markdown=allow_markdown)
        for root_name in _MANUSCRIPT_ROOTS
    )
    resolved = [resolution for resolution in root_resolutions if resolution.status == "resolved"]
    invalid = [resolution for resolution in root_resolutions if resolution.status == "invalid"]

    if invalid:
        return ManuscriptResolution(
            status="invalid",
            manuscript_root=None,
            manuscript_entrypoint=None,
            detail="; ".join(resolution.detail for resolution in invalid[:3]),
            root_resolutions=root_resolutions,
        )
    if len(resolved) == 1:
        resolution = resolved[0]
        return ManuscriptResolution(
            status="resolved",
            manuscript_root=resolution.manuscript_root,
            manuscript_entrypoint=resolution.manuscript_entrypoint,
            detail=resolution.detail,
            root_resolutions=root_resolutions,
        )
    if len(resolved) > 1:
        detail = "multiple manuscript roots resolve: " + ", ".join(
            str(resolution.manuscript_entrypoint) for resolution in resolved if resolution.manuscript_entrypoint is not None
        )
        return ManuscriptResolution(
            status="ambiguous",
            manuscript_root=None,
            manuscript_entrypoint=None,
            detail=detail,
            root_resolutions=root_resolutions,
        )
    return ManuscriptResolution(
        status="missing",
        manuscript_root=None,
        manuscript_entrypoint=None,
        detail="no manuscript entrypoint found under paper/, manuscript/, or draft/",
        root_resolutions=root_resolutions,
    )


def resolve_current_manuscript_entrypoint(project_root: Path, *, allow_markdown: bool = True) -> Path | None:
    """Return the active manuscript entrypoint if one exists."""

    resolution = resolve_current_manuscript_resolution(project_root, allow_markdown=allow_markdown)
    return resolution.manuscript_entrypoint if resolution.status == "resolved" else None


def resolve_current_manuscript_root(project_root: Path, *, allow_markdown: bool = True) -> Path | None:
    """Return the directory containing the active manuscript entrypoint."""

    resolution = resolve_current_manuscript_resolution(project_root, allow_markdown=allow_markdown)
    return resolution.manuscript_root


def _normalize_manuscript_base(manuscript_root: Path) -> Path:
    candidate = manuscript_root.resolve(strict=False)
    for ancestor in (candidate, *candidate.parents):
        if ancestor.name in _MANUSCRIPT_ROOTS:
            return ancestor
    if candidate.exists() and candidate.is_file():
        return candidate.parent
    if candidate.suffix in {".tex", ".md"} and not candidate.is_dir():
        return candidate.parent
    return candidate


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

    resolution = resolve_current_manuscript_resolution(project_root, allow_markdown=allow_markdown)
    entrypoint = resolution.manuscript_entrypoint
    manuscript_root = resolution.manuscript_root
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
        reproducibility_manifest=locate_publication_artifact(manuscript_root, _REPRODUCIBILITY_MANIFEST_FILENAME),
    )
