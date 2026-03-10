"""Pydantic models for paper configuration, output, and metadata."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from gpd.mcp.paper.bibliography import BibliographyAudit


class Author(BaseModel):
    """Paper author with affiliation."""

    name: str
    email: str = ""
    affiliation: str = ""


class Section(BaseModel):
    """A paper section with title and LaTeX content."""

    title: str
    content: str
    label: str = ""


class FigureRef(BaseModel):
    """Reference to a figure file with metadata."""

    path: Path
    caption: str
    label: str
    width: str = r"\columnwidth"
    double_column: bool = False


class ArtifactSourceRef(BaseModel):
    """A source artifact or upstream input associated with an emitted paper artifact."""

    path: str
    role: str = ""


class ArtifactRecord(BaseModel):
    """Machine-readable record for an emitted paper artifact."""

    artifact_id: str
    category: Literal["tex", "bib", "figure", "pdf", "audit"]
    path: str
    sha256: str
    produced_by: str
    sources: list[ArtifactSourceRef] = Field(default_factory=list)
    metadata: dict[str, str | int | float | bool] = Field(default_factory=dict)


class ArtifactManifest(BaseModel):
    """Manifest describing the concrete paper artifacts emitted by the build."""

    version: int = 1
    paper_title: str
    journal: str
    created_at: str
    artifacts: list[ArtifactRecord] = Field(default_factory=list)


class JournalSpec(BaseModel):
    """Specification for a journal's LaTeX configuration."""

    key: str
    document_class: str
    class_options: list[str]
    bib_style: str
    column_width_cm: float
    double_width_cm: float
    max_height_cm: float
    dpi: int
    preferred_formats: list[str]
    compiler: str = "pdflatex"
    texlive_package: str
    required_tex_files: list[str] = Field(default_factory=list)
    install_hint: str = ""


class PaperConfig(BaseModel):
    """Complete configuration for generating a paper."""

    title: str
    authors: list[Author]
    abstract: str
    sections: list[Section]
    figures: list[FigureRef] = Field(default_factory=list)
    acknowledgments: str = ""
    bib_file: str = "references"
    journal: str = "prl"
    appendix_sections: list[Section] = Field(default_factory=list)
    attribution_footer: str = "Generated with Get Physics Done"


class PaperOutput(BaseModel):
    """Output from the paper build pipeline."""

    tex_content: str
    bib_content: str
    figures_dir: Path | None = None
    pdf_path: Path | None = None
    bibliography_audit_path: Path | None = None
    bibliography_audit: BibliographyAudit | None = None
    manifest_path: Path | None = None
    manifest: ArtifactManifest | None = None
    success: bool
    errors: list[str] = Field(default_factory=list)
