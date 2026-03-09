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

from gpd.mcp.paper.models import PaperConfig

logger = logging.getLogger(__name__)

# Lazy-import pipeline.latex_utils to avoid hard dependency at import time.
# These functions are optional safety nets; if unavailable, skip them.
_sanitize_latex = None
_clean_latex_fences = None


def _local_clean_latex_fences(raw: str) -> str:
    """Strip markdown code fences from LLM output (local fallback)."""
    latex = raw.strip()
    if "```latex" in latex:
        latex = latex.split("```latex", 1)[1].split("```", 1)[0].strip()
    elif "```" in latex:
        parts = latex.split("```")
        if len(parts) >= 3:
            latex = parts[1].strip()
    return latex


def _load_latex_utils() -> None:
    """Load latex_utils functions on first use."""
    global _sanitize_latex, _clean_latex_fences  # noqa: PLW0603
    if _sanitize_latex is not None:
        return
    try:
        from pipeline.latex_utils import clean_latex_fences, sanitize_latex

        _sanitize_latex = sanitize_latex
        _clean_latex_fences = clean_latex_fences
    except ImportError:
        logger.debug("pipeline.latex_utils not available; using local fallbacks")
        _sanitize_latex = lambda x: x  # noqa: E731
        _clean_latex_fences = _local_clean_latex_fences


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


def render_paper(config: PaperConfig) -> str:
    """Render a complete LaTeX document from a PaperConfig.

    Loads the template for config.journal, renders it with all config fields,
    and applies LaTeX sanitization to the output.
    """
    template = load_template(config.journal)
    rendered = template.render(
        title=config.title,
        authors=config.authors,
        abstract=config.abstract,
        sections=config.sections,
        figures=config.figures,
        acknowledgments=config.acknowledgments,
        bib_file=config.bib_file,
        appendix_sections=config.appendix_sections,
    )

    # Apply LaTeX sanitization as a safety net
    _load_latex_utils()
    rendered = _clean_latex_fences(rendered)
    rendered = _sanitize_latex(rendered)

    return rendered
