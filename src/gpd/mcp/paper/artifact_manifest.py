"""Artifact manifest generation for emitted paper build outputs."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from gpd.mcp.paper.bibliography import BibliographyAudit
from gpd.mcp.paper.models import ArtifactManifest, ArtifactRecord, ArtifactSourceRef, FigureRef, PaperConfig


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(8192), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path, output_dir: Path) -> str:
    try:
        return str(path.relative_to(output_dir))
    except ValueError:
        return str(path)


def _resolve_output_path(path: Path, output_dir: Path) -> Path:
    return path if path.is_absolute() else output_dir / path


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
        prepared_path = _resolve_output_path(prepared.path, output_dir)
        if not prepared_path.exists():
            continue
        artifacts.append(
            ArtifactRecord(
                artifact_id=f"figure-{prepared.label or prepared_path.stem}",
                category="figure",
                path=_display_path(prepared_path, output_dir),
                sha256=_sha256(prepared_path),
                produced_by="build_paper:prepare_figures",
                sources=[ArtifactSourceRef(path=str(original.path), role="source-figure")],
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

    return ArtifactManifest(
        paper_title=config.title,
        journal=config.journal,
        created_at=datetime.now(UTC).isoformat(),
        artifacts=artifacts,
    )


def write_artifact_manifest(manifest: ArtifactManifest, output_path: Path) -> None:
    """Persist the artifact manifest as JSON."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest.model_dump(mode="json"), indent=2), encoding="utf-8")
