"""PydanticAI paper generator agent + reproducibility appendix.

Uses PydanticAI Agent() for all LLM calls per AGENTS.md mandate.
Generates LaTeX section content from research artifacts, writes figure
captions, creates reproducibility appendix, and orchestrates full
paper generation.
"""

from __future__ import annotations

import logging

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from gpd.core.model_defaults import GPD_DEFAULT_MODEL, resolve_model_and_settings
from gpd.mcp.paper.bibliography import CitationSource, citation_keys_for_sources
from gpd.mcp.paper.models import Author, FigureRef, PaperConfig, Section
from gpd.utils.latex import clean_latex_fences, sanitize_latex

logger = logging.getLogger(__name__)


# ---- Pydantic output models for agents ----


class SectionPlan(BaseModel):
    """Output from section planner: adaptive section structure."""

    sections: list[dict]  # Each dict has "title" and "key_points" fields


class SectionContent(BaseModel):
    """Output from section writer: raw LaTeX content for one section."""

    content: str


class FigureCaption(BaseModel):
    """Output from caption writer: publication-quality figure caption."""

    caption: str


# ---- PydanticAI agents (lazily initialized to avoid requiring API keys at import time) ----

_section_planner: Agent[None, SectionPlan] | None = None
_section_writer: Agent[None, SectionContent] | None = None
_caption_writer: Agent[None, FigureCaption] | None = None


def _get_section_planner() -> Agent[None, SectionPlan]:
    global _section_planner  # noqa: PLW0603
    if _section_planner is None:
        _base_model, _ = resolve_model_and_settings(GPD_DEFAULT_MODEL)
        _section_planner = Agent(
            _base_model,
            output_type=SectionPlan,
            system_prompt=(
                "You are an expert physics paper planner. Given a research summary, "
                "plan an adaptive section structure for a physics paper. Default structure "
                "is PRL-like (Introduction, Methods, Results, Discussion, Conclusion) but "
                "adapt based on the research type. Output section titles and key points for each. "
                "Do NOT include Abstract (handled separately). Include no markdown, only plain text."
            ),
        )
    return _section_planner


def _get_section_writer() -> Agent[None, SectionContent]:
    global _section_writer  # noqa: PLW0603
    if _section_writer is None:
        _base_model, _ = resolve_model_and_settings(GPD_DEFAULT_MODEL)
        _section_writer = Agent(
            _base_model,
            output_type=SectionContent,
            system_prompt=(
                "You are an expert physics paper writer. Write one section of a physics paper "
                "in LaTeX. Use proper LaTeX commands (\\cite{key}, \\ref{fig:label}, \\eqref{eq:label}). "
                "Write publication-quality prose appropriate for the target journal. "
                "Do NOT wrap output in markdown code fences. Do NOT include \\section{} command "
                "(the template handles that). Use inline math $...$ and display math "
                "\\begin{equation}...\\end{equation} as appropriate."
            ),
        )
    return _section_writer


def _get_caption_writer() -> Agent[None, FigureCaption]:
    global _caption_writer  # noqa: PLW0603
    if _caption_writer is None:
        _base_model, _ = resolve_model_and_settings(GPD_DEFAULT_MODEL)
        _caption_writer = Agent(
            _base_model,
            output_type=FigureCaption,
            system_prompt=(
                "You are an expert at writing publication-quality figure captions for physics papers. "
                "Describe what the figure shows, key features, and significance. "
                "Be concise (2-4 sentences). Do NOT include \\caption{} command. "
                "Reference relevant quantities and units."
            ),
        )
    return _caption_writer


# ---- Reproducibility appendix builder (no LLM needed) ----


class ToolUsageRecord(BaseModel):
    """Record of a tool used during research."""

    name: str
    version: str = ""
    description: str = ""
    parameters: dict = Field(default_factory=dict)
    compute_time_s: float | None = None


class ReproducibilityInfo(BaseModel):
    """Information for the reproducibility appendix."""

    tools_used: list[ToolUsageRecord]
    session_id: str = ""
    compute_platform: str = ""
    total_compute_time: str = ""


def build_reproducibility_appendix(info: ReproducibilityInfo) -> Section:
    """Generate a reproducibility appendix Section from tool usage records."""
    lines: list[str] = []

    # Computational Environment
    lines.append(r"\subsection{Computational Environment}")
    if info.tools_used:
        lines.append(r"\begin{itemize}")
        for tool in info.tools_used:
            version_str = f" (v{tool.version})" if tool.version else ""
            desc_str = f": {tool.description}" if tool.description else ""
            lines.append(f"\\item \\textbf{{{tool.name}}}{version_str}{desc_str}")
        lines.append(r"\end{itemize}")
    else:
        lines.append("No tools recorded.")

    # Simulation Parameters (from first tool if available)
    lines.append(r"\subsection{Simulation Parameters}")
    if info.tools_used and info.tools_used[0].parameters:
        params = info.tools_used[0].parameters
        lines.append(r"\begin{tabular}{ll}")
        lines.append(r"\hline")
        lines.append(r"Parameter & Value \\")
        lines.append(r"\hline")
        for key, value in params.items():
            lines.append(f"{key} & {value} \\\\")
        lines.append(r"\hline")
        lines.append(r"\end{tabular}")
    else:
        lines.append("No simulation parameters recorded.")

    # Compute Resources
    lines.append(r"\subsection{Compute Resources}")
    if info.total_compute_time:
        lines.append(f"Total compute time: {info.total_compute_time} \\\\")
    if info.compute_platform:
        lines.append(f"Platform: {info.compute_platform} \\\\")
    if info.session_id:
        lines.append(f"Session ID: \\texttt{{{info.session_id}}}")

    return Section(
        title="Reproducibility",
        content="\n".join(lines),
        label="reproducibility",
    )


# ---- Orchestrator ----


async def generate_paper(
    research_summary: str,
    title: str,
    authors: list[Author],
    abstract: str,
    figures: list[FigureRef],
    citations: list[CitationSource],
    journal: str = "prl",
    reproducibility: ReproducibilityInfo | None = None,
    model: str = GPD_DEFAULT_MODEL,
) -> PaperConfig:
    """Generate a complete paper from research artifacts via PydanticAI agents.

    1. Plan sections from research summary
    2. Write each section with the AI agent
    3. Generate figure captions
    4. Build reproducibility appendix
    5. Assemble PaperConfig
    """
    # Resolve effort suffix → (base model ID, provider-specific settings)
    base_model, model_settings = resolve_model_and_settings(model)

    # Build citation key list for context
    cite_keys = citation_keys_for_sources(citations)
    fig_labels = [f.label for f in figures]

    # 1. Plan sections
    logger.info("Planning paper sections...")
    plan_result = await _get_section_planner().run(
        f"Research summary:\n{research_summary}\n\nJournal: {journal}",
        model=base_model,
        model_settings=model_settings,
    )
    section_plan = plan_result.output

    # 2. Write each section
    sections: list[Section] = []
    for sec_info in section_plan.sections:
        sec_title = sec_info.get("title", "Untitled")
        key_points = sec_info.get("key_points", [])
        logger.info("Writing section: %s", sec_title)

        prompt = (
            f"Section: {sec_title}\n"
            f"Key points: {key_points}\n"
            f"Research summary: {research_summary}\n"
            f"Available citation keys: {cite_keys}\n"
            f"Available figure labels: {fig_labels}\n"
            f"Journal: {journal}"
        )
        sec_result = await _get_section_writer().run(prompt, model=base_model, model_settings=model_settings)
        content = sec_result.output.content
        content = clean_latex_fences(content)
        content = sanitize_latex(content)
        sections.append(Section(title=sec_title, content=content))

    # 3. Generate figure captions
    updated_figures: list[FigureRef] = []
    for fig in figures:
        logger.info("Generating caption for figure: %s", fig.label)
        caption_prompt = (
            f"Figure label: {fig.label}\n"
            f"Current caption hint: {fig.caption}\n"
            f"Research context: {research_summary[:500]}"
        )
        cap_result = await _get_caption_writer().run(caption_prompt, model=base_model, model_settings=model_settings)
        caption = clean_latex_fences(cap_result.output.caption)
        caption = sanitize_latex(caption)
        updated_figures.append(fig.model_copy(update={"caption": caption}))

    # 4. Build reproducibility appendix
    appendix_sections: list[Section] = []
    if reproducibility:
        appendix_sections.append(build_reproducibility_appendix(reproducibility))

    # 5. Assemble PaperConfig
    return PaperConfig(
        title=title,
        authors=authors,
        abstract=abstract,
        sections=sections,
        figures=updated_figures,
        acknowledgments="",
        journal=journal,
        appendix_sections=appendix_sections,
    )
