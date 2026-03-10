"""LaTeX paper-building utilities for GPD."""

from gpd.mcp.paper.bibliography import (
    BibliographyAudit,
    CitationAuditRecord,
    CitationSource,
    build_bibliography,
    build_bibliography_with_audit,
    write_bibliography_audit,
)
from gpd.mcp.paper.compiler import build_paper, compile_paper
from gpd.mcp.paper.journal_map import get_journal_for_domain, get_journal_spec, list_journals
from gpd.mcp.paper.models import ArtifactManifest, ArtifactRecord, ArtifactSourceRef, Author, FigureRef, PaperConfig, PaperOutput, Section

__all__ = [
    "Author",
    "ArtifactManifest",
    "ArtifactRecord",
    "ArtifactSourceRef",
    "BibliographyAudit",
    "CitationAuditRecord",
    "CitationSource",
    "FigureRef",
    "PaperConfig",
    "PaperOutput",
    "Section",
    "build_bibliography",
    "build_bibliography_with_audit",
    "build_paper",
    "compile_paper",
    "get_journal_for_domain",
    "get_journal_spec",
    "list_journals",
    "write_bibliography_audit",
]
