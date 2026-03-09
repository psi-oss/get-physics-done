"""Pydantic models for paper configuration, output, and metadata."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


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


class PaperConfig(BaseModel):
    """Complete configuration for generating a paper."""

    title: str
    authors: list[Author]
    abstract: str
    sections: list[Section]
    figures: list[FigureRef] = []
    acknowledgments: str = ""
    bib_file: str = "references"
    journal: str = "prl"
    appendix_sections: list[Section] = []


class PaperOutput(BaseModel):
    """Output from the paper build pipeline."""

    tex_content: str
    bib_content: str
    figures_dir: Path | None = None
    pdf_path: Path | None = None
    success: bool
    errors: list[str] = []
