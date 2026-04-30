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

from gpd.mcp.paper.models import Author, FigureRef, PaperConfig, Section, normalize_acknowledgments
from gpd.utils.latex import clean_latex_fences, escape_user_text_for_latex, fix_bibliography_conflict, sanitize_latex
from gpd.utils.pandoc import PandocNotAvailable, PandocStatus, detect_pandoc, markdown_to_latex_fragment

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
            "name": _clean_user_text(author.name),
            "email": _clean_user_text(author.email),
            "affiliation": _clean_user_text(author.affiliation),
        }
    )


def _clean_section(section: Section, pandoc_status: PandocStatus | None = None) -> Section:
    content = section.content
    if section.content_format == "markdown":
        if pandoc_status is None:
            pandoc_status = detect_pandoc()
        if not pandoc_status.available or not pandoc_status.meets_minimum:
            reason = pandoc_status.error or (
                "pandoc version below minimum" if pandoc_status.available else "pandoc not found on PATH"
            )
            raise PandocNotAvailable(
                f"Section {section.title!r} has content_format='markdown' which requires pandoc, "
                f"but {reason}. Install pandoc or switch the section to content_format='latex'."
            )
        content = markdown_to_latex_fragment(content, status=pandoc_status)
    return section.model_copy(
        update={
            "title": clean_latex_fences(section.title),
            "content": clean_latex_fences(content),
            "label": clean_latex_fences(section.label),
        }
    )


def _clean_figure(figure: FigureRef) -> dict:
    """Return a template-ready dict with LaTeX-safe fields and POSIX path."""
    return {
        "path": figure.path.as_posix(),
        "caption": clean_latex_fences(figure.caption),
        "label": clean_latex_fences(figure.label),
        "width": figure.width,
        "double_column": figure.double_column,
    }


def _clean_user_text(raw: str) -> str:
    """Clean and escape a user-provided metadata string for LaTeX."""
    return escape_user_text_for_latex(clean_latex_fences(raw))


def render_paper(config: PaperConfig) -> str:
    """Render a complete LaTeX document from a PaperConfig.

    Loads the template for config.journal, renders it with all config fields,
    and applies LaTeX sanitization to the output.

    Sections with ``content_format="markdown"`` are converted to LaTeX
    fragments via pandoc before template substitution. Pandoc is probed
    once per render call and the status is shared across sections.
    """
    template = load_template(config.journal)
    authors = [_clean_author(author) for author in config.authors]
    all_sections = list(config.sections) + list(config.appendix_sections)
    pandoc_status: PandocStatus | None = None
    if any(section.content_format == "markdown" for section in all_sections):
        pandoc_status = detect_pandoc()
    sections = [_clean_section(section, pandoc_status) for section in config.sections]
    appendix_sections = [_clean_section(section, pandoc_status) for section in config.appendix_sections]
    figures = [_clean_figure(figure) for figure in config.figures]
    rendered = template.render(
        title=_clean_user_text(config.title),
        authors=authors,
        abstract=_clean_user_text(config.abstract),
        sections=sections,
        figures=figures,
        acknowledgments=_clean_user_text(normalize_acknowledgments(config.acknowledgments)),
        bib_file=config.bib_file,
        appendix_sections=appendix_sections,
        attribution_footer=clean_latex_fences(config.attribution_footer),
    )

    # Apply LaTeX sanitization as a safety net
    rendered = sanitize_latex(rendered)

    # Fix conflicting bibliography styles: if the paper-writer agent injected
    # inline \begin{thebibliography} entries, strip the template's
    # \bibliographystyle and \bibliography commands which are incompatible.
    rendered = fix_bibliography_conflict(rendered)

    return rendered
