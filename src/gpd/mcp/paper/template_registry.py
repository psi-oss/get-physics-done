"""Jinja2 template registry for LaTeX journal templates.

Uses custom LaTeX-safe delimiters to avoid conflicts with LaTeX curly braces:
    \\VAR{...}   for variables
    \\BLOCK{...} for control flow
    \\#{...}     for comments
"""

from __future__ import annotations

import logging
from importlib.resources import files

from jinja2 import BaseLoader, Environment, TemplateNotFound

from gpd.mcp.paper.models import Author, FigureRef, PaperConfig, Section
from gpd.utils.latex import clean_latex_fences, sanitize_latex

logger = logging.getLogger(__name__)


class _PackageTemplateLoader(BaseLoader):
    """Jinja2 loader that reads templates from package data via importlib.resources."""

    def get_source(self, environment: Environment, template: str) -> tuple[str, str, None]:
        pkg = files("gpd.mcp.paper.templates")
        # template name is like "prl/prl_template.tex"
        try:
            resource = pkg.joinpath(template)
            source = resource.read_text(encoding="utf-8")
            return source, template, None
        except (FileNotFoundError, TypeError, AttributeError) as exc:
            raise TemplateNotFound(template) from exc


# Jinja2 environment with LaTeX-safe custom delimiters.
_env = Environment(
    loader=_PackageTemplateLoader(),
    block_start_string=r"\BLOCK{",
    block_end_string="}",
    variable_start_string=r"\VAR{",
    variable_end_string="}",
    comment_start_string=r"\#{",
    comment_end_string="}",
    line_statement_prefix="%%",
    line_comment_prefix="%#",
    trim_blocks=True,
    autoescape=False,
)


def load_template(journal: str):
    """Load a Jinja2 template for the given journal.

    Raises:
        FileNotFoundError: If the template file does not exist.
    """
    template_name = f"{journal}/{journal}_template.tex"
    try:
        return _env.get_template(template_name)
    except TemplateNotFound as exc:
        raise FileNotFoundError(f"Template not found for journal '{journal}': {template_name}") from exc


def _clean_author(author: Author) -> Author:
    return author.model_copy(
        update={
            "name": clean_latex_fences(author.name),
            "email": clean_latex_fences(author.email),
            "affiliation": clean_latex_fences(author.affiliation),
        }
    )


def _clean_section(section: Section) -> Section:
    return section.model_copy(
        update={
            "title": clean_latex_fences(section.title),
            "content": clean_latex_fences(section.content),
        }
    )


def _clean_figure(figure: FigureRef) -> FigureRef:
    return figure.model_copy(update={"caption": clean_latex_fences(figure.caption)})


def render_paper(config: PaperConfig) -> str:
    """Render a complete LaTeX document from a PaperConfig.

    Loads the template for config.journal, renders it with all config fields,
    and applies LaTeX sanitization to the output.
    """
    template = load_template(config.journal)
    authors = [_clean_author(author) for author in config.authors]
    sections = [_clean_section(section) for section in config.sections]
    appendix_sections = [_clean_section(section) for section in config.appendix_sections]
    figures = [_clean_figure(figure) for figure in config.figures]
    rendered = template.render(
        title=clean_latex_fences(config.title),
        authors=authors,
        abstract=clean_latex_fences(config.abstract),
        sections=sections,
        figures=figures,
        acknowledgments=clean_latex_fences(config.acknowledgments) if config.acknowledgments else None,
        bib_file=config.bib_file,
        appendix_sections=appendix_sections,
        attribution_footer=clean_latex_fences(config.attribution_footer),
    )

    # Apply LaTeX sanitization as a safety net
    rendered = sanitize_latex(rendered)

    return rendered
