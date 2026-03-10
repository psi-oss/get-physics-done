"""LaTeX paper-building utilities for GPD."""

from gpd.mcp.paper.bibliography import CitationSource, build_bibliography
from gpd.mcp.paper.compiler import build_paper, compile_paper
from gpd.mcp.paper.journal_map import get_journal_for_domain, get_journal_spec, list_journals
from gpd.mcp.paper.models import Author, FigureRef, PaperConfig, PaperOutput, Section

__all__ = [
    "Author",
    "CitationSource",
    "FigureRef",
    "PaperConfig",
    "PaperOutput",
    "Section",
    "build_bibliography",
    "build_paper",
    "compile_paper",
    "get_journal_for_domain",
    "get_journal_spec",
    "list_journals",
]
