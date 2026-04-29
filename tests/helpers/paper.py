"""Paper-specific test builders."""

from __future__ import annotations

from gpd.mcp.paper.models import Author, FigureRef, PaperConfig, Section


def minimal_paper_config(
    title: str,
    *,
    section_content: str = "No citations here.",
    journal: str = "prl",
    output_filename: str | None = None,
    figures: list[FigureRef] | None = None,
) -> PaperConfig:
    kwargs: dict[str, object] = {
        "title": title,
        "authors": [Author(name="A. Researcher")],
        "abstract": "Abstract.",
        "sections": [Section(title="Intro", content=section_content)],
        "journal": journal,
    }
    if output_filename is not None:
        kwargs["output_filename"] = output_filename
    if figures is not None:
        kwargs["figures"] = figures
    return PaperConfig(**kwargs)
