"""Artifact manifest generation for emitted paper build outputs."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from gpd.mcp.paper.bibliography import BibliographyAudit
from gpd.mcp.paper.models import (
    ArtifactManifest,
    ArtifactRecord,
    ArtifactSourceRef,
    FigureRef,
    PaperConfig,
    normalize_manifest_artifact_path,
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class ArtifactManifestFreshness:
    """Freshness check result for one manifest/manuscript snapshot pair."""

    fresh: bool
    detail: str
    actual_sha256: str | None = None
    actual_mtime_ns: int | None = None


@dataclass(frozen=True, slots=True)
class ArtifactManifestIntegrity:
    """Integrity check result for manifest-contained artifact records."""

    passed: bool
    detail: str


def validate_artifact_manifest_freshness(
    manifest: ArtifactManifest,
    manuscript_path: Path,
) -> ArtifactManifestFreshness:
    """Validate that a manifest still describes the active manuscript file.

    ``manuscript_sha256`` is the authoritative freshness field. The mtime is
    recorded for diagnostics, but a matching digest remains fresh even if file
    metadata changed without a content edit. Manifests without a top-level
    manuscript digest are stale because freshness cannot be verified.
    """

    try:
        stat = manuscript_path.stat()
    except OSError as exc:
        return ArtifactManifestFreshness(
            fresh=False,
            detail=f"could not read active manuscript snapshot: {exc}",
        )

    actual_mtime_ns = stat.st_mtime_ns
    try:
        actual_sha256 = _sha256(manuscript_path)
    except OSError as exc:
        return ArtifactManifestFreshness(
            fresh=False,
            detail=f"could not hash active manuscript snapshot: {exc}",
            actual_mtime_ns=actual_mtime_ns,
        )
    expected_sha256 = manifest.manuscript_sha256
    if expected_sha256 is None:
        return ArtifactManifestFreshness(
            fresh=False,
            detail="manifest is missing manuscript_sha256; freshness cannot be verified",
            actual_sha256=actual_sha256,
            actual_mtime_ns=actual_mtime_ns,
        )
    if expected_sha256 != actual_sha256:
        return ArtifactManifestFreshness(
            fresh=False,
            detail="manuscript_sha256 does not match the active manuscript snapshot",
            actual_sha256=actual_sha256,
            actual_mtime_ns=actual_mtime_ns,
        )
    if manifest.manuscript_mtime_ns is not None and manifest.manuscript_mtime_ns != actual_mtime_ns:
        return ArtifactManifestFreshness(
            fresh=True,
            detail="manuscript_sha256 matches; manuscript_mtime_ns differs",
            actual_sha256=actual_sha256,
            actual_mtime_ns=actual_mtime_ns,
        )
    return ArtifactManifestFreshness(
        fresh=True,
        detail="manuscript snapshot matches artifact manifest",
        actual_sha256=actual_sha256,
        actual_mtime_ns=actual_mtime_ns,
    )


def _manifest_artifact_roots(
    artifact_root: Path,
    selected_manuscript_path: Path | None,
) -> tuple[Path, ...]:
    roots = [Path(artifact_root)]
    if selected_manuscript_path is None:
        return tuple(roots)

    selected_resolved = Path(selected_manuscript_path).resolve(strict=False)
    selected_parent = selected_resolved.parent
    resolved_root = Path(artifact_root).resolve(strict=False)
    for sidecar_root in (resolved_root, *resolved_root.parents):
        if not sidecar_root.name.startswith("."):
            continue
        sidecar_parent = sidecar_root.parent
        if selected_resolved == sidecar_parent or selected_resolved.is_relative_to(sidecar_parent):
            roots.insert(0, sidecar_parent)
            break
    if resolved_root != selected_parent and resolved_root.is_relative_to(selected_parent):
        roots.insert(0, selected_parent)
    return tuple(dict.fromkeys(roots))


def _resolve_contained_manifest_artifact_path(path: str, artifact_roots: tuple[Path, ...]) -> Path | None:
    try:
        portable_path = normalize_manifest_artifact_path(path)
    except ValueError:
        return None
    candidate = Path(portable_path)
    for artifact_root in artifact_roots:
        root_candidate = artifact_root / candidate
        resolved_candidate = root_candidate.resolve(strict=False)
        resolved_root = artifact_root.resolve(strict=False)
        if resolved_candidate == resolved_root or resolved_candidate.is_relative_to(resolved_root):
            return root_candidate
    return None


def validate_artifact_manifest_integrity(
    manifest: ArtifactManifest,
    artifact_root: Path,
    *,
    selected_manuscript_path: Path | None = None,
    hash_categories: frozenset[str] = frozenset({"tex", "bib", "audit", "figure", "pdf"}),
) -> ArtifactManifestIntegrity:
    """Validate manifest artifact paths and recorded artifact digests.

    Manifest artifact paths are portable paths relative to the paper artifact
    root. Review preflight relies on the TeX/BibTeX/audit/PDF records, so those
    records must remain contained in the paper package and their sha256 values
    must match the current file bytes.
    """

    root = Path(artifact_root)
    artifact_roots = _manifest_artifact_roots(root, selected_manuscript_path)
    selected_resolved = (
        Path(selected_manuscript_path).resolve(strict=False) if selected_manuscript_path is not None else None
    )

    if selected_resolved is not None:
        tex_artifacts = [artifact for artifact in manifest.artifacts if artifact.category == "tex"]
        if not tex_artifacts:
            return ArtifactManifestIntegrity(
                passed=False,
                detail="artifact manifest has no tex artifact for the selected manuscript",
            )
        if len(tex_artifacts) != 1:
            return ArtifactManifestIntegrity(
                passed=False,
                detail=f"artifact manifest must contain exactly one tex artifact; found {len(tex_artifacts)}",
            )
        mismatched_tex_paths: list[str] = []
        matching_tex_paths = 0
        for artifact in tex_artifacts:
            candidate = _resolve_contained_manifest_artifact_path(artifact.path, artifact_roots)
            if candidate is None or candidate.resolve(strict=False) != selected_resolved:
                mismatched_tex_paths.append(artifact.path)
            else:
                matching_tex_paths += 1
        if mismatched_tex_paths or matching_tex_paths == 0:
            preview = ", ".join(mismatched_tex_paths[:3])
            suffix = f" (+{len(mismatched_tex_paths) - 3} more)" if len(mismatched_tex_paths) > 3 else ""
            return ArtifactManifestIntegrity(
                passed=False,
                detail=(
                    "artifact manifest tex artifact path does not resolve to the selected manuscript"
                    + (f": {preview}{suffix}" if preview else "")
                ),
            )

    for artifact in manifest.artifacts:
        if artifact.category not in hash_categories:
            continue
        candidate = _resolve_contained_manifest_artifact_path(artifact.path, artifact_roots)
        if candidate is None:
            return ArtifactManifestIntegrity(
                passed=False,
                detail=f"artifact manifest {artifact.category} artifact {artifact.artifact_id} path escapes artifact root: {artifact.path}",
            )
        if not candidate.exists():
            return ArtifactManifestIntegrity(
                passed=False,
                detail=f"artifact manifest {artifact.category} artifact {artifact.artifact_id} path does not exist: {artifact.path}",
            )
        try:
            actual_sha256 = _sha256(candidate)
        except OSError as exc:
            return ArtifactManifestIntegrity(
                passed=False,
                detail=f"could not hash artifact manifest {artifact.category} artifact {artifact.artifact_id}: {exc}",
            )
        if actual_sha256 != artifact.sha256:
            return ArtifactManifestIntegrity(
                passed=False,
                detail=(
                    f"artifact manifest sha256 mismatch for {artifact.category} artifact "
                    f"{artifact.artifact_id}: {artifact.path}"
                ),
            )

    return ArtifactManifestIntegrity(passed=True, detail="artifact manifest artifact paths and sha256 values match")


def _display_path(path: Path, output_dir: Path) -> str:
    try:
        relative_path = path.resolve(strict=False).relative_to(output_dir.resolve(strict=False))
    except ValueError:
        raise ValueError(f"artifact path must stay inside output_dir: {path}") from None
    return normalize_manifest_artifact_path(relative_path.as_posix())


def _portable_source_ref(path: Path, output_dir: Path, *, role: str) -> ArtifactSourceRef:
    """Return a portable source reference without leaking local absolute paths."""

    if not path.is_absolute():
        return ArtifactSourceRef(path=path.as_posix(), role=role)

    resolved_path = path.resolve(strict=False)
    resolved_output_dir = output_dir.resolve(strict=False)
    if resolved_path == resolved_output_dir or resolved_path.is_relative_to(resolved_output_dir):
        return ArtifactSourceRef(path=resolved_path.relative_to(resolved_output_dir).as_posix(), role=role)

    cwd = Path.cwd().resolve(strict=False)
    if resolved_path == cwd or resolved_path.is_relative_to(cwd):
        return ArtifactSourceRef(path=resolved_path.relative_to(cwd).as_posix(), role=role)

    return ArtifactSourceRef(path=f"external:{path.name}", role=f"external-{role}")


def _resolve_output_path(path: Path, output_dir: Path) -> Path:
    return path if path.is_absolute() else output_dir / path


def _resolve_contained_output_path(path: Path, output_dir: Path) -> Path | None:
    candidate = _resolve_output_path(path, output_dir)
    resolved_candidate = candidate.resolve(strict=False)
    resolved_output_dir = output_dir.resolve(strict=False)
    if resolved_candidate == resolved_output_dir or resolved_candidate.is_relative_to(resolved_output_dir):
        return candidate
    return None


def build_artifact_manifest(
    config: PaperConfig,
    output_dir: Path,
    *,
    tex_path: Path,
    bib_path: Path | None = None,
    bib_entry_source: str | None = None,
    bibliography_audit_path: Path | None = None,
    bibliography_audit: BibliographyAudit | None = None,
    original_figures: list[FigureRef] | None = None,
    prepared_figures: list[FigureRef] | None = None,
    figure_source_pairs: list[tuple[FigureRef, FigureRef]] | None = None,
    pdf_path: Path | None = None,
) -> ArtifactManifest:
    """Build a machine-readable manifest for emitted paper artifacts."""

    artifacts: list[ArtifactRecord] = [
        ArtifactRecord(
            artifact_id="tex-paper",
            category="tex",
            path=_display_path(tex_path, output_dir),
            sha256=_sha256(tex_path),
            produced_by="build_paper:render_tex",
            metadata={
                "journal": config.journal,
                "section_count": len(config.sections),
                "appendix_count": len(config.appendix_sections),
                "figure_count": len(config.figures),
            },
        )
    ]

    if bib_path is not None and bib_path.exists():
        metadata: dict[str, str] = {}
        if bib_entry_source:
            metadata["entry_source"] = bib_entry_source
        artifacts.append(
            ArtifactRecord(
                artifact_id=f"bib-{bib_path.stem}",
                category="bib",
                path=_display_path(bib_path, output_dir),
                sha256=_sha256(bib_path),
                produced_by="build_paper:write_bibliography",
                metadata=metadata,
            )
        )

    if bibliography_audit_path is not None and bibliography_audit_path.exists():
        metadata: dict[str, str | int | float | bool] = {}
        if bibliography_audit is not None:
            metadata = {
                "total_sources": bibliography_audit.total_sources,
                "resolved_sources": bibliography_audit.resolved_sources,
                "partial_sources": bibliography_audit.partial_sources,
                "unverified_sources": bibliography_audit.unverified_sources,
                "failed_sources": bibliography_audit.failed_sources,
            }
        artifacts.append(
            ArtifactRecord(
                artifact_id="audit-bibliography",
                category="audit",
                path=_display_path(bibliography_audit_path, output_dir),
                sha256=_sha256(bibliography_audit_path),
                produced_by="build_paper:write_bibliography_audit",
                metadata=metadata,
            )
        )

    source_pairs = figure_source_pairs or list(zip(original_figures or [], prepared_figures or [], strict=False))
    for original, prepared in source_pairs:
        prepared_path = _resolve_contained_output_path(prepared.path, output_dir)
        if prepared_path is None:
            continue
        if not prepared_path.exists():
            continue
        artifacts.append(
            ArtifactRecord(
                artifact_id=f"figure-{prepared.label or prepared_path.stem}",
                category="figure",
                path=_display_path(prepared_path, output_dir),
                sha256=_sha256(prepared_path),
                produced_by="build_paper:prepare_figures",
                sources=[_portable_source_ref(original.path, output_dir, role="source-figure")],
                metadata={
                    "label": prepared.label,
                    "caption_length": len(prepared.caption),
                    "double_column": prepared.double_column,
                },
            )
        )

    if pdf_path is not None and pdf_path.exists():
        pdf_sources = [ArtifactSourceRef(path=_display_path(tex_path, output_dir), role="compiled-from")]
        if bib_path is not None and bib_path.exists():
            pdf_sources.append(ArtifactSourceRef(path=_display_path(bib_path, output_dir), role="bibliography"))
        artifacts.append(
            ArtifactRecord(
                artifact_id=f"pdf-{pdf_path.stem}",
                category="pdf",
                path=_display_path(pdf_path, output_dir),
                sha256=_sha256(pdf_path),
                produced_by="build_paper:compile",
                sources=pdf_sources,
            )
        )

    manuscript_sha256: str | None = None
    manuscript_mtime_ns: int | None = None
    if tex_path.exists():
        manuscript_sha256 = _sha256(tex_path)
        try:
            manuscript_mtime_ns = tex_path.stat().st_mtime_ns
        except OSError:
            manuscript_mtime_ns = None

    return ArtifactManifest(
        paper_title=config.title,
        journal=config.journal,
        created_at=datetime.now(UTC).isoformat(),
        artifacts=artifacts,
        manuscript_sha256=manuscript_sha256,
        manuscript_mtime_ns=manuscript_mtime_ns,
    )


def write_artifact_manifest(manifest: ArtifactManifest, output_path: Path) -> None:
    """Persist the artifact manifest as JSON."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest.model_dump(mode="json"), indent=2), encoding="utf-8")
