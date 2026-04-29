"""Helpers for resolving the active manuscript and its publication artifacts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import ValidationError as PydanticValidationError

from gpd.core.constants import PUBLICATION_MANUSCRIPT_DIR_NAME, ProjectLayout
from gpd.core.utils import normalize_ascii_slug
from gpd.mcp.paper.artifact_manifest import validate_artifact_manifest_freshness
from gpd.mcp.paper.models import ArtifactManifest, PaperConfig, PublicationPathSemantics, derive_output_filename

__all__ = [
    "PublicationBootstrapResolution",
    "ManuscriptArtifacts",
    "ManuscriptResolution",
    "ManuscriptRootResolution",
    "PublicationSubjectResolution",
    "infer_publication_artifact_base",
    "locate_publication_artifact",
    "publication_root_for_subject",
    "review_dir_for_subject",
    "resolve_current_publication_subject",
    "resolve_manuscript_entrypoint_from_root",
    "resolve_explicit_publication_subject",
    "resolve_current_manuscript_artifacts",
    "resolve_current_manuscript_entrypoint",
    "resolve_current_manuscript_resolution",
    "resolve_current_manuscript_root",
    "resolve_publication_bootstrap_resolution",
    "resolve_publication_subject",
    "resolve_publication_subject_artifact",
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
PublicationSubjectStatus = Literal["resolved", "missing", "ambiguous", "invalid"]
PublicationSubjectSource = Literal["current_project", "explicit_target"]
PublicationLaneKind = Literal["canonical_project_manuscript", "managed_publication_manuscript", "external_artifact"]
PublicationLaneOwner = Literal["project_managed", "external_artifact"]
PublicationBootstrapMode = Literal["resume_existing_manuscript", "fresh_project_bootstrap", "blocked"]


@dataclass(frozen=True, slots=True)
class ManuscriptRootResolution:
    """Resolution details for one candidate manuscript root directory."""

    status: Literal["resolved", "missing", "invalid"]
    manuscript_root: Path
    manuscript_entrypoint: Path | None
    detail: str


@dataclass(frozen=True, slots=True)
class _ManifestEntrypointResolution:
    """Resolved fresh manifest entrypoints plus stale snapshot diagnostics."""

    manifest: ArtifactManifest | None
    entrypoints: tuple[Path, ...]
    manifest_path: Path | None = None
    stale_details: tuple[str, ...] = ()
    invalid_detail: str | None = None


@dataclass(frozen=True, slots=True)
class _ArtifactManifestLoadResult:
    """Loaded artifact manifest, or the reason a present manifest cannot be trusted."""

    manifest: ArtifactManifest | None
    manifest_path: Path | None = None
    invalid_detail: str | None = None


@dataclass(frozen=True, slots=True)
class ManuscriptResolution:
    """Resolution details for the current project-wide manuscript state."""

    status: ManuscriptResolutionStatus
    manuscript_root: Path | None
    manuscript_entrypoint: Path | None
    detail: str
    root_resolutions: tuple[ManuscriptRootResolution, ...] = ()


@dataclass(frozen=True, slots=True)
class PublicationSubjectResolution:
    """Resolved publication subject plus the artifact base and sidecars it owns."""

    project_root: Path
    status: PublicationSubjectStatus
    source: PublicationSubjectSource
    detail: str
    target_path: Path | None = None
    manuscript_root: Path | None = None
    manuscript_entrypoint: Path | None = None
    artifact_base: Path | None = None
    artifact_manifest: Path | None = None
    bibliography_audit: Path | None = None
    reproducibility_manifest: Path | None = None
    path_semantics: PublicationPathSemantics | None = None
    publication_subject_slug: str | None = None
    publication_lane_kind: PublicationLaneKind | None = None
    publication_lane_owner: PublicationLaneOwner | None = None
    managed_publication_root: Path | None = None
    managed_intake_root: Path | None = None
    managed_manuscript_root: Path | None = None
    root_resolutions: tuple[ManuscriptRootResolution, ...] = ()

    @property
    def resolved(self) -> bool:
        return self.status == "resolved" and self.manuscript_entrypoint is not None

    @property
    def publication_root(self) -> Path | None:
        return publication_root_for_subject(self)

    @property
    def review_dir(self) -> Path | None:
        return review_dir_for_subject(self)

    def as_manuscript_resolution(self) -> ManuscriptResolution:
        """Project this subject onto the narrower manuscript-resolution view."""

        return ManuscriptResolution(
            status=self.status,
            manuscript_root=self.manuscript_root,
            manuscript_entrypoint=self.manuscript_entrypoint,
            detail=self.detail,
            root_resolutions=self.root_resolutions,
        )

    def as_manuscript_artifacts(self) -> ManuscriptArtifacts:
        """Project this subject onto the narrower manuscript-artifacts view."""

        return ManuscriptArtifacts(
            project_root=self.project_root,
            manuscript_root=self.manuscript_root,
            manuscript_entrypoint=self.manuscript_entrypoint,
            artifact_manifest=self.artifact_manifest,
            bibliography_audit=self.bibliography_audit,
            reproducibility_manifest=self.reproducibility_manifest,
        )

    def to_context_dict(self) -> dict[str, object]:
        """Return a machine-readable summary of the resolved publication subject."""

        return {
            "status": self.status,
            "source": self.source,
            "detail": self.detail,
            "target_path": _relative_path(self.project_root, self.target_path),
            "artifact_base": _relative_path(self.project_root, self.artifact_base),
            "publication_root": _relative_path(self.project_root, self.publication_root),
            "review_dir": _relative_path(self.project_root, self.review_dir),
            "manuscript_root": _relative_path(self.project_root, self.manuscript_root),
            "manuscript_entrypoint": _relative_path(self.project_root, self.manuscript_entrypoint),
            "artifact_manifest": _relative_path(self.project_root, self.artifact_manifest),
            "bibliography_audit": _relative_path(self.project_root, self.bibliography_audit),
            "reproducibility_manifest": _relative_path(self.project_root, self.reproducibility_manifest),
            "publication_subject_slug": self.publication_subject_slug,
            "publication_lane_kind": self.publication_lane_kind,
            "publication_lane_owner": self.publication_lane_owner,
            "managed_publication_root": _relative_path(self.project_root, self.managed_publication_root),
            "managed_intake_root": _relative_path(self.project_root, self.managed_intake_root),
            "managed_manuscript_root": _relative_path(self.project_root, self.managed_manuscript_root),
            "path_semantics": None if self.path_semantics is None else self.path_semantics.model_dump(mode="python"),
        }

    def to_bootstrap_context_dict(self) -> dict[str, object]:
        """Return the compact publication-subject payload used during bootstrap."""

        manuscript_resolution = self.as_manuscript_resolution()
        return {
            "publication_subject": self.to_context_dict(),
            "publication_subject_status": self.status,
            "publication_subject_source": self.source,
            "publication_subject_detail": self.detail,
            "publication_subject_slug": self.publication_subject_slug,
            "publication_lane_kind": self.publication_lane_kind,
            "publication_lane_owner": self.publication_lane_owner,
            "publication_artifact_base": _relative_path(self.project_root, self.artifact_base),
            "publication_root": _relative_path(self.project_root, self.publication_root),
            "review_dir": _relative_path(self.project_root, self.review_dir),
            "manuscript_resolution_status": manuscript_resolution.status,
            "manuscript_resolution_detail": manuscript_resolution.detail,
            "manuscript_root": _relative_path(self.project_root, self.manuscript_root),
            "manuscript_entrypoint": _relative_path(self.project_root, self.manuscript_entrypoint),
            "artifact_manifest_path": _relative_path(self.project_root, self.artifact_manifest),
            "bibliography_audit_path": _relative_path(self.project_root, self.bibliography_audit),
            "reproducibility_manifest_path": _relative_path(self.project_root, self.reproducibility_manifest),
            "managed_publication_root": _relative_path(self.project_root, self.managed_publication_root),
            "managed_intake_root": _relative_path(self.project_root, self.managed_intake_root),
            "managed_manuscript_root": _relative_path(self.project_root, self.managed_manuscript_root),
        }


@dataclass(frozen=True, slots=True)
class PublicationBootstrapResolution:
    """Resolved bootstrap intent for publication-aware authoring commands."""

    project_root: Path
    publication_subject: PublicationSubjectResolution
    mode: PublicationBootstrapMode
    detail: str
    bootstrap_root: Path | None = None

    def to_context_dict(self) -> dict[str, object]:
        """Return a machine-readable summary of the bootstrap plan."""

        return {
            "mode": self.mode,
            "detail": self.detail,
            "bootstrap_root": _relative_path(self.project_root, self.bootstrap_root),
        }


def _publication_artifact_candidate_paths(manuscript_root: Path, filename: str) -> tuple[Path, ...]:
    """Return root-level then nested sidecar candidates under one manuscript base."""

    base_dir = _normalize_manuscript_base(manuscript_root)
    candidates: list[Path] = []
    direct_candidate = base_dir / filename
    direct_resolved = direct_candidate.resolve(strict=False)
    if direct_candidate.exists() and direct_candidate.is_file():
        candidates.append(direct_candidate)

    if not base_dir.exists() or not base_dir.is_dir():
        return tuple(candidates)

    try:
        nested_candidates = sorted(
            (
                path
                for path in base_dir.rglob(filename)
                if path.is_file()
                and path.resolve(strict=False) != direct_resolved
                and path.relative_to(base_dir).parts[0].startswith(".")
            ),
            key=lambda path: path.relative_to(base_dir).as_posix(),
        )
    except OSError:
        nested_candidates = []
    candidates.extend(nested_candidates)
    return tuple(dict.fromkeys(candidates))


def _resolve_single_publication_artifact_path(
    manuscript_root: Path,
    filename: str,
) -> tuple[Path | None, str | None]:
    """Resolve one sidecar path, failing closed on ambiguous nested copies."""

    candidates = _publication_artifact_candidate_paths(manuscript_root, filename)
    if not candidates:
        return None, None

    base_dir = _normalize_manuscript_base(manuscript_root)
    if len(candidates) == 1:
        return candidates[0], None

    preview_paths = []
    for path in candidates[:3]:
        try:
            preview_paths.append(path.relative_to(base_dir).as_posix())
        except ValueError:
            preview_paths.append(path.as_posix())
    suffix = f" (+{len(candidates) - 3} more)" if len(candidates) > 3 else ""
    return None, f"{filename} is ambiguous under {base_dir}: {', '.join(preview_paths)}{suffix}"


def _load_artifact_manifest(manuscript_root: Path) -> _ArtifactManifestLoadResult:
    manifest_path, ambiguous_detail = _resolve_single_publication_artifact_path(
        manuscript_root,
        "ARTIFACT-MANIFEST.json",
    )
    if ambiguous_detail is not None:
        return _ArtifactManifestLoadResult(manifest=None, invalid_detail=ambiguous_detail)
    if manifest_path is None:
        return _ArtifactManifestLoadResult(manifest=None)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        if payload == {}:
            # Legacy bootstrap placeholders wrote `{}` before a real build manifest existed.
            # Keep only that empty-object placeholder recoverable; all other invalid manifests fail closed.
            return _ArtifactManifestLoadResult(manifest=None, manifest_path=manifest_path)
        return _ArtifactManifestLoadResult(
            manifest=ArtifactManifest.model_validate(payload),
            manifest_path=manifest_path,
        )
    except (OSError, json.JSONDecodeError, PydanticValidationError) as exc:
        return _ArtifactManifestLoadResult(
            manifest=None,
            manifest_path=manifest_path,
            invalid_detail=f"{manifest_path} is invalid: {exc}",
        )


def _manifest_entrypoint_resolution(
    manuscript_root: Path,
    *,
    allow_markdown: bool,
) -> _ManifestEntrypointResolution:
    load_result = _load_artifact_manifest(manuscript_root)
    manifest = load_result.manifest
    if manifest is None:
        return _ManifestEntrypointResolution(
            manifest=None,
            entrypoints=(),
            manifest_path=load_result.manifest_path,
            invalid_detail=load_result.invalid_detail,
        )

    allowed_suffixes = {".tex"}
    if allow_markdown:
        allowed_suffixes.add(".md")
    candidates: list[Path] = []
    stale_details: list[str] = []
    for artifact in manifest.artifacts:
        if artifact.category != "tex":
            continue
        candidate = (manuscript_root / artifact.path).resolve(strict=False)
        try:
            candidate.relative_to(manuscript_root.resolve(strict=False))
        except ValueError:
            continue
        if candidate.exists() and candidate.suffix.lower() in allowed_suffixes:
            freshness = validate_artifact_manifest_freshness(manifest, candidate)
            if freshness.fresh:
                candidates.append(candidate)
            else:
                stale_details.append(f"{candidate}: {freshness.detail}")
    return _ManifestEntrypointResolution(
        manifest=manifest,
        entrypoints=tuple(dict.fromkeys(candidates)),
        manifest_path=load_result.manifest_path,
        stale_details=tuple(dict.fromkeys(stale_details)),
    )


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


def _relative_path(project_root: Path, path: Path | None) -> str | None:
    if path is None:
        return None
    resolved_root = project_root.resolve(strict=False)
    resolved_path = path.resolve(strict=False)
    try:
        return resolved_path.relative_to(resolved_root).as_posix()
    except ValueError:
        return resolved_path.as_posix()


def _canonical_manuscript_root_for_target(project_root: Path, target: Path) -> Path | None:
    try:
        relative = target.resolve(strict=False).relative_to(project_root.resolve(strict=False))
    except ValueError:
        return None
    if not relative.parts or relative.parts[0] not in _MANUSCRIPT_ROOTS:
        return None
    return project_root / relative.parts[0]


def _managed_publication_manuscript_root_for_target(project_root: Path, target: Path) -> Path | None:
    layout = ProjectLayout(project_root)
    publication_dir = layout.publication_dir.resolve(strict=False)
    resolved_target = target.resolve(strict=False)
    try:
        relative = resolved_target.relative_to(publication_dir)
    except ValueError:
        return None
    if not relative.parts:
        return None

    subject_root = publication_dir / relative.parts[0]
    manuscript_root = subject_root / PUBLICATION_MANUSCRIPT_DIR_NAME
    if len(relative.parts) == 1:
        return manuscript_root if manuscript_root.exists() and manuscript_root.is_dir() else None
    if relative.parts[1] != PUBLICATION_MANUSCRIPT_DIR_NAME:
        return None
    return manuscript_root


def _managed_publication_subject_slug_for_root(project_root: Path, manuscript_root: Path) -> str | None:
    layout = ProjectLayout(project_root)
    publication_dir = layout.publication_dir.resolve(strict=False)
    resolved_root = manuscript_root.resolve(strict=False)
    try:
        relative = resolved_root.relative_to(publication_dir)
    except ValueError:
        return None
    if len(relative.parts) != 2 or relative.parts[1] != PUBLICATION_MANUSCRIPT_DIR_NAME:
        return None
    return relative.parts[0]


def _iter_managed_publication_manuscript_roots(project_root: Path) -> tuple[Path, ...]:
    publication_dir = ProjectLayout(project_root).publication_dir
    if not publication_dir.exists() or not publication_dir.is_dir():
        return ()
    try:
        subject_dirs = sorted((path for path in publication_dir.iterdir() if path.is_dir()), key=lambda path: path.name)
    except OSError:
        return ()
    return tuple(
        candidate
        for subject_dir in subject_dirs
        if (candidate := subject_dir / PUBLICATION_MANUSCRIPT_DIR_NAME).is_dir()
    )


def _publication_slug_label(project_root: Path, anchor_path: Path) -> str:
    resolved_project_root = project_root.resolve(strict=False)
    resolved_anchor = anchor_path.resolve(strict=False)
    try:
        return resolved_anchor.relative_to(resolved_project_root).as_posix()
    except ValueError:
        return resolved_anchor.as_posix()


def _derive_hashed_publication_subject_slug(project_root: Path, anchor_path: Path) -> str:
    label = _publication_slug_label(project_root, anchor_path)
    slug_source = label[: -len(anchor_path.suffix)] if anchor_path.suffix else label
    slug = normalize_ascii_slug(slug_source.replace("/", "-")) or "manuscript"
    slug = slug[:48].rstrip("-") or "manuscript"
    digest = hashlib.sha256(label.encode("utf-8")).hexdigest()[:12]
    return f"{slug}-{digest}"


def _unique_managed_publication_manuscript_root(
    project_root: Path,
    root_resolutions: tuple[ManuscriptRootResolution, ...],
) -> Path | None:
    managed_roots = tuple(
        dict.fromkeys(
            resolution.manuscript_root
            for resolution in root_resolutions
            if _managed_publication_subject_slug_for_root(project_root, resolution.manuscript_root) is not None
        )
    )
    return managed_roots[0] if len(managed_roots) == 1 else None


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

    manifest_resolution = _manifest_entrypoint_resolution(manuscript_root, allow_markdown=allow_markdown)
    manifest_entrypoints = manifest_resolution.entrypoints
    configured_entrypoints = _configured_entrypoints(manuscript_root, allow_markdown=allow_markdown)
    manifest_path = manifest_resolution.manifest_path or manuscript_root / "ARTIFACT-MANIFEST.json"
    config_path = manuscript_root / "PAPER-CONFIG.json"

    manifest_valid = manifest_resolution.manifest is not None
    manifest_present = manifest_resolution.manifest_path is not None and manifest_path.exists()
    config_present = config_path.exists()
    manifest_entrypoint = manifest_entrypoints[0] if len(manifest_entrypoints) == 1 else None
    configured_entrypoint = configured_entrypoints[0] if len(configured_entrypoints) == 1 else None

    if manifest_resolution.invalid_detail is not None:
        return ManuscriptRootResolution(
            status="invalid",
            manuscript_root=manuscript_root,
            manuscript_entrypoint=None,
            detail=manifest_resolution.invalid_detail,
        )
    if manifest_resolution.stale_details:
        return ManuscriptRootResolution(
            status="invalid",
            manuscript_root=manuscript_root,
            manuscript_entrypoint=None,
            detail=f"{manifest_path} is stale: " + "; ".join(manifest_resolution.stale_details),
        )
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


def resolve_manuscript_entrypoint_from_root(manuscript_root: Path, *, allow_markdown: bool = True) -> Path | None:
    """Resolve the manuscript entrypoint within one manuscript root directory."""

    resolution = _resolve_manuscript_entrypoint_from_root_resolution(manuscript_root, allow_markdown=allow_markdown)
    return resolution.manuscript_entrypoint if resolution.status == "resolved" else None


def resolve_current_manuscript_resolution(project_root: Path, *, allow_markdown: bool = True) -> ManuscriptResolution:
    """Return the active manuscript resolution status for the project."""

    canonical_root_resolutions = tuple(
        _resolve_manuscript_entrypoint_from_root_resolution(project_root / root_name, allow_markdown=allow_markdown)
        for root_name in _MANUSCRIPT_ROOTS
    )
    managed_root_resolutions = tuple(
        _resolve_manuscript_entrypoint_from_root_resolution(manuscript_root, allow_markdown=allow_markdown)
        for manuscript_root in _iter_managed_publication_manuscript_roots(project_root)
    )
    root_resolutions = canonical_root_resolutions + managed_root_resolutions
    resolved = [resolution for resolution in root_resolutions if resolution.status == "resolved"]
    invalid = [resolution for resolution in root_resolutions if resolution.status == "invalid"]

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
            str(resolution.manuscript_entrypoint)
            for resolution in resolved
            if resolution.manuscript_entrypoint is not None
        )
        return ManuscriptResolution(
            status="ambiguous",
            manuscript_root=None,
            manuscript_entrypoint=None,
            detail=detail,
            root_resolutions=root_resolutions,
        )
    if invalid:
        return ManuscriptResolution(
            status="invalid",
            manuscript_root=None,
            manuscript_entrypoint=None,
            detail="; ".join(resolution.detail for resolution in invalid[:3]),
            root_resolutions=root_resolutions,
        )
    return ManuscriptResolution(
        status="missing",
        manuscript_root=None,
        manuscript_entrypoint=None,
        detail="no manuscript entrypoint found under paper/, manuscript/, draft/, or GPD/publication/*/manuscript",
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


def _supported_manuscript_root_for_target(project_root: Path, target: Path) -> Path | None:
    canonical_root = _canonical_manuscript_root_for_target(project_root, target)
    if canonical_root is not None:
        return canonical_root
    return _managed_publication_manuscript_root_for_target(project_root, target)


def _resolve_publication_sidecars(
    artifact_base: Path | None,
) -> tuple[Path | None, Path | None, Path | None]:
    if artifact_base is None:
        return None, None, None
    return (
        locate_publication_artifact(artifact_base, "ARTIFACT-MANIFEST.json"),
        locate_publication_artifact(artifact_base, "BIBLIOGRAPHY-AUDIT.json"),
        locate_publication_artifact(artifact_base, _REPRODUCIBILITY_MANIFEST_FILENAME),
    )


def _publication_lane_anchor(
    *,
    artifact_base: Path | None,
    manuscript_root: Path | None,
    manuscript_entrypoint: Path | None,
    target_path: Path | None,
    root_resolutions: tuple[ManuscriptRootResolution, ...],
    project_root: Path,
) -> Path | None:
    for candidate in (
        manuscript_root,
        artifact_base,
        manuscript_entrypoint,
        target_path,
        _unique_managed_publication_manuscript_root(project_root, root_resolutions),
    ):
        if candidate is not None:
            return candidate
    return None


def _publication_lane_kind(
    project_root: Path,
    *,
    artifact_base: Path | None,
    manuscript_root: Path | None,
    manuscript_entrypoint: Path | None,
    target_path: Path | None,
    root_resolutions: tuple[ManuscriptRootResolution, ...],
) -> PublicationLaneKind | None:
    anchor = _publication_lane_anchor(
        artifact_base=artifact_base,
        manuscript_root=manuscript_root,
        manuscript_entrypoint=manuscript_entrypoint,
        target_path=target_path,
        root_resolutions=root_resolutions,
        project_root=project_root,
    )
    if anchor is None:
        return None
    if _managed_publication_manuscript_root_for_target(project_root, anchor) is not None:
        return "managed_publication_manuscript"
    if _canonical_manuscript_root_for_target(project_root, anchor) is not None:
        return "canonical_project_manuscript"
    return "external_artifact"


def _publication_subject_slug(
    project_root: Path,
    *,
    artifact_base: Path | None,
    manuscript_root: Path | None,
    manuscript_entrypoint: Path | None,
    target_path: Path | None,
    root_resolutions: tuple[ManuscriptRootResolution, ...],
) -> str | None:
    for candidate in (manuscript_root, artifact_base, manuscript_entrypoint, target_path):
        if candidate is None:
            continue
        managed_root = _managed_publication_manuscript_root_for_target(project_root, candidate)
        if managed_root is not None:
            return _managed_publication_subject_slug_for_root(project_root, managed_root)
    unique_managed_root = _unique_managed_publication_manuscript_root(project_root, root_resolutions)
    if unique_managed_root is not None:
        return _managed_publication_subject_slug_for_root(project_root, unique_managed_root)
    for candidate in (manuscript_entrypoint, target_path):
        if candidate is not None:
            return _derive_hashed_publication_subject_slug(project_root, candidate)
    return None


def _managed_publication_paths(
    project_root: Path,
    *,
    publication_subject_slug: str | None,
    publication_lane_kind: PublicationLaneKind | None,
) -> tuple[Path | None, Path | None, Path | None]:
    if publication_subject_slug is None:
        return None, None, None
    layout = ProjectLayout(project_root)
    publication_root = layout.publication_subject_dir(publication_subject_slug)
    intake_root = layout.publication_intake_dir(publication_subject_slug)
    if publication_lane_kind == "external_artifact":
        return publication_root, intake_root, None
    if publication_lane_kind in {
        "canonical_project_manuscript",
        "managed_publication_manuscript",
    }:
        return publication_root, intake_root, layout.publication_manuscript_dir(publication_subject_slug)
    return None, None, None


def _publication_output_paths(
    project_root: Path,
    *,
    source: PublicationSubjectSource,
    publication_subject_slug: str | None,
    publication_lane_kind: PublicationLaneKind | None,
    publication_lane_owner: PublicationLaneOwner | None,
) -> tuple[Path | None, Path | None]:
    layout = ProjectLayout(project_root)
    if publication_lane_kind == "managed_publication_manuscript" and publication_subject_slug is not None:
        return (
            layout.publication_subject_dir(publication_subject_slug),
            layout.publication_review_dir(publication_subject_slug),
        )
    if source == "current_project" or publication_lane_kind == "canonical_project_manuscript":
        return layout.gpd, layout.review_dir
    if publication_lane_owner == "external_artifact" and publication_subject_slug is not None:
        return (
            layout.publication_subject_dir(publication_subject_slug),
            layout.publication_review_dir(publication_subject_slug),
        )
    return None, None


def publication_root_for_subject(publication_subject: PublicationSubjectResolution) -> Path | None:
    """Return the canonical GPD publication root for one scoped publication subject."""

    publication_root, _review_dir = _publication_output_paths(
        publication_subject.project_root,
        source=publication_subject.source,
        publication_subject_slug=publication_subject.publication_subject_slug,
        publication_lane_kind=publication_subject.publication_lane_kind,
        publication_lane_owner=publication_subject.publication_lane_owner,
    )
    return publication_root


def review_dir_for_subject(publication_subject: PublicationSubjectResolution) -> Path | None:
    """Return the canonical review directory for one scoped publication subject."""

    _publication_root, review_dir = _publication_output_paths(
        publication_subject.project_root,
        source=publication_subject.source,
        publication_subject_slug=publication_subject.publication_subject_slug,
        publication_lane_kind=publication_subject.publication_lane_kind,
        publication_lane_owner=publication_subject.publication_lane_owner,
    )
    return review_dir


def _bootstrap_candidate_root(project_root: Path, manuscript_root: Path) -> bool:
    if not manuscript_root.exists() or not manuscript_root.is_dir():
        return False
    if _managed_publication_subject_slug_for_root(project_root, manuscript_root) is not None:
        return True
    marker_files = (
        "PAPER-CONFIG.json",
        "ARTIFACT-MANIFEST.json",
        "BIBLIOGRAPHY-AUDIT.json",
        _REPRODUCIBILITY_MANIFEST_FILENAME,
    )
    return any((manuscript_root / filename).exists() for filename in marker_files)


def _bootstrap_candidate_roots(
    project_root: Path,
    root_resolutions: tuple[ManuscriptRootResolution, ...],
) -> tuple[Path, ...]:
    return tuple(
        dict.fromkeys(
            resolution.manuscript_root
            for resolution in root_resolutions
            if _bootstrap_candidate_root(project_root, resolution.manuscript_root)
        )
    )


def infer_publication_artifact_base(
    project_root: Path,
    *,
    allow_markdown: bool = True,
) -> Path | None:
    """Infer a unique publication artifact base without defaulting to ``paper/``."""

    resolved_project_root = Path(project_root).resolve(strict=False)
    subject = resolve_current_publication_subject(
        resolved_project_root,
        allow_markdown=allow_markdown,
    )
    if subject.resolved and subject.artifact_base is not None:
        return subject.artifact_base
    if subject.status in {"ambiguous", "invalid"}:
        return None

    candidates: list[Path] = []
    content_suffixes = {".tex"}
    if allow_markdown:
        content_suffixes.add(".md")
    for root_name in _MANUSCRIPT_ROOTS:
        candidate = resolved_project_root / root_name
        if not candidate.exists() or not candidate.is_dir():
            continue
        has_publication_artifacts = any(
            (candidate / artifact_name).exists()
            for artifact_name in (
                "PAPER-CONFIG.json",
                "ARTIFACT-MANIFEST.json",
                "BIBLIOGRAPHY-AUDIT.json",
                "FIGURE_TRACKER.md",
                _REPRODUCIBILITY_MANIFEST_FILENAME,
            )
        )
        has_manuscript_content = any(
            path.is_file() and path.suffix.lower() in content_suffixes for path in candidate.rglob("*")
        )
        if has_publication_artifacts or has_manuscript_content:
            candidates.append(candidate)
    return candidates[0] if len(candidates) == 1 else None


def _publication_subject_from_resolution(
    project_root: Path,
    resolution: ManuscriptResolution,
    *,
    source: PublicationSubjectSource,
    target_path: Path | None = None,
) -> PublicationSubjectResolution:
    publication_subject_slug = _publication_subject_slug(
        project_root,
        artifact_base=resolution.manuscript_root,
        manuscript_root=resolution.manuscript_root,
        manuscript_entrypoint=resolution.manuscript_entrypoint,
        target_path=target_path,
        root_resolutions=resolution.root_resolutions,
    )
    publication_lane_kind = _publication_lane_kind(
        project_root,
        artifact_base=resolution.manuscript_root,
        manuscript_root=resolution.manuscript_root,
        manuscript_entrypoint=resolution.manuscript_entrypoint,
        target_path=target_path,
        root_resolutions=resolution.root_resolutions,
    )
    publication_lane_owner: PublicationLaneOwner | None = None
    if publication_lane_kind is not None:
        publication_lane_owner = (
            "project_managed" if publication_lane_kind != "external_artifact" else "external_artifact"
        )
    managed_publication_root, managed_intake_root, managed_manuscript_root = _managed_publication_paths(
        project_root,
        publication_subject_slug=publication_subject_slug,
        publication_lane_kind=publication_lane_kind,
    )

    if resolution.status != "resolved" or resolution.manuscript_entrypoint is None:
        return PublicationSubjectResolution(
            project_root=project_root,
            status=resolution.status,
            source=source,
            detail=resolution.detail,
            target_path=target_path,
            manuscript_root=resolution.manuscript_root,
            manuscript_entrypoint=resolution.manuscript_entrypoint,
            publication_subject_slug=publication_subject_slug,
            publication_lane_kind=publication_lane_kind,
            publication_lane_owner=publication_lane_owner,
            managed_publication_root=managed_publication_root,
            managed_intake_root=managed_intake_root,
            managed_manuscript_root=managed_manuscript_root,
            root_resolutions=resolution.root_resolutions,
        )

    artifact_base = _normalize_manuscript_base(
        target_path or resolution.manuscript_root or resolution.manuscript_entrypoint
    )
    artifact_manifest, bibliography_audit, reproducibility_manifest = _resolve_publication_sidecars(artifact_base)
    publication_subject_slug = _publication_subject_slug(
        project_root,
        artifact_base=artifact_base,
        manuscript_root=resolution.manuscript_root,
        manuscript_entrypoint=resolution.manuscript_entrypoint,
        target_path=target_path,
        root_resolutions=resolution.root_resolutions,
    )
    publication_lane_kind = _publication_lane_kind(
        project_root,
        artifact_base=artifact_base,
        manuscript_root=resolution.manuscript_root,
        manuscript_entrypoint=resolution.manuscript_entrypoint,
        target_path=target_path,
        root_resolutions=resolution.root_resolutions,
    )
    publication_lane_owner = "project_managed" if publication_lane_kind != "external_artifact" else "external_artifact"
    managed_publication_root, managed_intake_root, managed_manuscript_root = _managed_publication_paths(
        project_root,
        publication_subject_slug=publication_subject_slug,
        publication_lane_kind=publication_lane_kind,
    )
    return PublicationSubjectResolution(
        project_root=project_root,
        status="resolved",
        source=source,
        detail=resolution.detail,
        target_path=target_path or resolution.manuscript_root or resolution.manuscript_entrypoint,
        manuscript_root=resolution.manuscript_root,
        manuscript_entrypoint=resolution.manuscript_entrypoint,
        artifact_base=artifact_base,
        artifact_manifest=artifact_manifest,
        bibliography_audit=bibliography_audit,
        reproducibility_manifest=reproducibility_manifest,
        path_semantics=PublicationPathSemantics.from_paths(
            project_root,
            subject_path=target_path or resolution.manuscript_root or resolution.manuscript_entrypoint,
            artifact_base_path=artifact_base,
            manuscript_root_path=resolution.manuscript_root,
            manuscript_entrypoint_path=resolution.manuscript_entrypoint,
        ),
        publication_subject_slug=publication_subject_slug,
        publication_lane_kind=publication_lane_kind,
        publication_lane_owner=publication_lane_owner,
        managed_publication_root=managed_publication_root,
        managed_intake_root=managed_intake_root,
        managed_manuscript_root=managed_manuscript_root,
        root_resolutions=resolution.root_resolutions,
    )


def resolve_current_publication_subject(
    project_root: Path,
    *,
    allow_markdown: bool = True,
) -> PublicationSubjectResolution:
    """Resolve the current project-wide publication subject without guessing a root."""

    resolved_root = Path(project_root).resolve(strict=False)
    resolution = resolve_current_manuscript_resolution(resolved_root, allow_markdown=allow_markdown)
    return _publication_subject_from_resolution(
        resolved_root,
        resolution,
        source="current_project",
    )


def resolve_explicit_publication_subject(
    project_root: Path,
    target: str | Path,
    *,
    allow_markdown: bool = True,
    subject_base: Path | None = None,
) -> PublicationSubjectResolution:
    """Resolve one explicit publication subject path into a typed subject envelope."""

    resolved_project_root = Path(project_root).resolve(strict=False)
    resolved_subject_base = (subject_base or resolved_project_root).resolve(strict=False)
    explicit_target = Path(target)
    if not explicit_target.is_absolute():
        explicit_target = resolved_subject_base / explicit_target
    explicit_target = explicit_target.resolve(strict=False)

    if not explicit_target.exists():
        return PublicationSubjectResolution(
            project_root=resolved_project_root,
            status="missing",
            source="explicit_target",
            detail=f"{explicit_target} does not exist",
            target_path=explicit_target,
        )

    allowed_suffixes = {".tex"}
    if allow_markdown:
        allowed_suffixes.add(".md")

    if explicit_target.is_file():
        if explicit_target.suffix.lower() not in allowed_suffixes:
            return PublicationSubjectResolution(
                project_root=resolved_project_root,
                status="invalid",
                source="explicit_target",
                detail=f"{explicit_target} is not a supported publication manuscript entrypoint",
                target_path=explicit_target,
            )

        supported_root = _supported_manuscript_root_for_target(resolved_project_root, explicit_target)
        if supported_root is not None:
            root_resolution = _resolve_manuscript_entrypoint_from_root_resolution(
                supported_root,
                allow_markdown=allow_markdown,
            )
            if root_resolution.status != "resolved" or root_resolution.manuscript_entrypoint is None:
                return PublicationSubjectResolution(
                    project_root=resolved_project_root,
                    status="invalid",
                    source="explicit_target",
                    detail=f"{supported_root} is ambiguous or inconsistent: {root_resolution.detail}",
                    target_path=explicit_target,
                )
            if root_resolution.manuscript_entrypoint.resolve(strict=False) != explicit_target:
                return PublicationSubjectResolution(
                    project_root=resolved_project_root,
                    status="invalid",
                    source="explicit_target",
                    detail=(
                        f"{explicit_target} does not match the resolved manuscript entrypoint "
                        f"{root_resolution.manuscript_entrypoint} under {supported_root}"
                    ),
                    target_path=explicit_target,
                )
            return _publication_subject_from_resolution(
                resolved_project_root,
                ManuscriptResolution(
                    status="resolved",
                    manuscript_root=supported_root,
                    manuscript_entrypoint=explicit_target,
                    detail=f"{explicit_target} present",
                ),
                source="explicit_target",
                target_path=explicit_target,
            )

        return _publication_subject_from_resolution(
            resolved_project_root,
            ManuscriptResolution(
                status="resolved",
                manuscript_root=explicit_target.parent,
                manuscript_entrypoint=explicit_target,
                detail=f"{explicit_target} present",
            ),
            source="explicit_target",
            target_path=explicit_target,
        )

    supported_root = _supported_manuscript_root_for_target(resolved_project_root, explicit_target)
    manuscript_root = supported_root or explicit_target
    root_resolution = _resolve_manuscript_entrypoint_from_root_resolution(
        manuscript_root,
        allow_markdown=allow_markdown,
    )
    if root_resolution.status != "resolved" or root_resolution.manuscript_entrypoint is None:
        return PublicationSubjectResolution(
            project_root=resolved_project_root,
            status="missing" if root_resolution.status == "missing" else "invalid",
            source="explicit_target",
            detail=(
                f"no publication manuscript entrypoint found under {explicit_target}"
                if root_resolution.status == "missing"
                else f"{explicit_target} is ambiguous or inconsistent: {root_resolution.detail}"
            ),
            target_path=explicit_target,
        )

    if supported_root is not None and supported_root != explicit_target:
        try:
            root_resolution.manuscript_entrypoint.resolve(strict=False).relative_to(
                explicit_target.resolve(strict=False)
            )
        except ValueError:
            return PublicationSubjectResolution(
                project_root=resolved_project_root,
                status="invalid",
                source="explicit_target",
                detail=(
                    f"{explicit_target} does not contain the resolved manuscript entrypoint "
                    f"{root_resolution.manuscript_entrypoint} under {supported_root}"
                ),
                target_path=explicit_target,
            )

    return _publication_subject_from_resolution(
        resolved_project_root,
        ManuscriptResolution(
            status="resolved",
            manuscript_root=manuscript_root,
            manuscript_entrypoint=root_resolution.manuscript_entrypoint,
            detail=f"{explicit_target} resolved to {root_resolution.manuscript_entrypoint}",
        ),
        source="explicit_target",
        target_path=explicit_target,
    )


def resolve_publication_subject(
    project_root: Path,
    target: str | Path | None = None,
    *,
    allow_markdown: bool = True,
    subject_base: Path | None = None,
) -> PublicationSubjectResolution:
    """Resolve the current or explicit publication subject into a public typed surface."""

    if target is None:
        return resolve_current_publication_subject(project_root, allow_markdown=allow_markdown)
    return resolve_explicit_publication_subject(
        project_root,
        target,
        allow_markdown=allow_markdown,
        subject_base=subject_base,
    )


def resolve_publication_bootstrap_resolution(
    project_root: Path,
    *,
    allow_markdown: bool = True,
    default_bootstrap_root: str | Path = "paper",
) -> PublicationBootstrapResolution:
    """Return the current bootstrap plan for publication-aware authoring."""

    resolved_project_root = Path(project_root).resolve(strict=False)
    subject = resolve_current_publication_subject(
        resolved_project_root,
        allow_markdown=allow_markdown,
    )
    bootstrap_candidate = Path(default_bootstrap_root)
    if not bootstrap_candidate.is_absolute():
        bootstrap_candidate = resolved_project_root / bootstrap_candidate
    bootstrap_candidate = bootstrap_candidate.resolve(strict=False)

    if subject.resolved:
        bootstrap_root = (
            subject.artifact_base
            or subject.manuscript_root
            or (subject.manuscript_entrypoint.parent if subject.manuscript_entrypoint is not None else None)
        )
        return PublicationBootstrapResolution(
            project_root=resolved_project_root,
            publication_subject=subject,
            mode="resume_existing_manuscript",
            detail=(
                f"resume the resolved manuscript root at {bootstrap_root}"
                if bootstrap_root is not None
                else "resume the resolved manuscript subject"
            ),
            bootstrap_root=bootstrap_root,
        )

    if subject.status == "missing":
        bootstrap_roots = _bootstrap_candidate_roots(resolved_project_root, subject.root_resolutions)
        if len(bootstrap_roots) > 1:
            return PublicationBootstrapResolution(
                project_root=resolved_project_root,
                publication_subject=subject,
                mode="blocked",
                detail=(
                    "publication bootstrap is blocked: multiple manuscript bootstrap roots are present: "
                    + ", ".join(str(root) for root in bootstrap_roots)
                ),
                bootstrap_root=None,
            )
        if len(bootstrap_roots) == 1:
            bootstrap_root = bootstrap_roots[0]
            bootstrap_detail = (
                f"no publication subject is resolved; bootstrap the managed manuscript lane at {bootstrap_root}"
                if _managed_publication_subject_slug_for_root(resolved_project_root, bootstrap_root) is not None
                else f"no publication subject is resolved; bootstrap a fresh manuscript scaffold at {bootstrap_root}"
            )
            return PublicationBootstrapResolution(
                project_root=resolved_project_root,
                publication_subject=subject,
                mode="fresh_project_bootstrap",
                detail=bootstrap_detail,
                bootstrap_root=bootstrap_root,
            )
        return PublicationBootstrapResolution(
            project_root=resolved_project_root,
            publication_subject=subject,
            mode="fresh_project_bootstrap",
            detail=(
                f"no publication subject is resolved; current write-paper bootstrap remains at {bootstrap_candidate}"
            ),
            bootstrap_root=bootstrap_candidate,
        )

    return PublicationBootstrapResolution(
        project_root=resolved_project_root,
        publication_subject=subject,
        mode="blocked",
        detail=f"publication bootstrap is blocked: {subject.detail}",
        bootstrap_root=None,
    )


def locate_publication_artifact(manuscript_root: Path, *filenames: str) -> Path | None:
    """Return the first publication artifact found beside a manuscript root."""

    for filename in filenames:
        candidate, ambiguous_detail = _resolve_single_publication_artifact_path(manuscript_root, filename)
        if ambiguous_detail is not None:
            return None
        if candidate is not None:
            return candidate
    return None


def resolve_publication_subject_artifact(
    publication_subject: PublicationSubjectResolution,
    *filenames: str,
) -> Path | None:
    """Resolve one sidecar artifact from a typed publication subject."""

    if not publication_subject.resolved or publication_subject.artifact_base is None:
        return None
    return locate_publication_artifact(publication_subject.artifact_base, *filenames)


def resolve_current_manuscript_artifacts(
    project_root: Path,
    *,
    allow_markdown: bool = True,
) -> ManuscriptArtifacts:
    """Resolve the active manuscript and the publication artifacts beside it."""

    return resolve_current_publication_subject(
        project_root,
        allow_markdown=allow_markdown,
    ).as_manuscript_artifacts()
