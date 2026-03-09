"""LaTeX paper generation pipeline.

Generates publication-ready LaTeX papers from research artifacts
with domain-appropriate journal templates, auto-generated bibliography,
and Claude-written content.

Public API:
    generate_paper()  - PydanticAI agent generates paper content from research
    build_paper()     - Orchestrates full pipeline (render + bib + figures + compile)
    compile_paper()   - Compiles .tex to PDF via latexmk or manual multi-pass
"""

from gpd.mcp.paper.bibliography import CitationSource, build_bibliography
from gpd.mcp.paper.compiler import build_paper, compile_paper
from gpd.mcp.paper.journal_map import get_journal_for_domain, get_journal_spec, list_journals
from gpd.mcp.paper.models import Author, FigureRef, PaperConfig, PaperOutput, Section


def __getattr__(name: str):
    if name == "generate_paper":
        from gpd.mcp.paper.generator import generate_paper

        return generate_paper
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


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
    "generate_paper",
    "get_journal_for_domain",
    "get_journal_spec",
    "list_journals",
]
