"""Markdown-aware section handling for the paper pipeline.

Paper-writer agents authored in raw LaTeX historically. This module lets
them author in markdown instead and converts the content to a LaTeX
fragment before the template registry substitutes it. Content that still
looks like raw LaTeX is passed through unchanged, so existing
``PaperConfig`` payloads keep working.

The module is intentionally thin: pandoc does the real work (via
``gpd.utils.pandoc``), this module just decides *when* to invoke it and
falls back gracefully when pandoc is missing.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from gpd.utils.pandoc import (
    PandocExecutionError,
    PandocNotAvailable,
    PandocStatus,
    detect_pandoc,
    markdown_to_latex_fragment,
)

logger = logging.getLogger(__name__)

# Fenced markdown code blocks (``` ... ```). Stripped before the
# LaTeX-sigil scan so that prose showing a LaTeX example in a code block
# does not get misread as an instruction to skip pandoc.
_FENCED_CODE_BLOCK_PATTERN = re.compile(r"(?ms)^\s*```.*?^\s*```\s*$")

# Markers that say "this is already LaTeX, don't feed it to pandoc".
# Order matters: the first match wins. We look for structural LaTeX
# commands that would be out of place in a markdown body. Math-mode
# environments (equation / align / gather / multline / eqnarray and
# their starred variants) are included -- a section that opens with a
# display-math environment is LaTeX, not markdown that happens to embed
# some math. Inline ``$...$`` and ``$$...$$`` stay in markdown territory.
_LATEX_SIGIL_PATTERN = re.compile(
    r"(?m)"
    r"^\s*\\documentclass\b"       # full document
    r"|^\s*\\begin\{(?:document|thebibliography|figure|table|abstract|itemize|enumerate|description|tabular|center|quote|quotation|verbatim|lstlisting|equation|align|gather|multline|eqnarray)\*?\}"
    r"|^\s*\\(?:section|subsection|subsubsection|paragraph|subparagraph|chapter)\*?\s*\{"
    r"|^\s*\\(?:title|author|date|maketitle|tableofcontents|bibliography|bibliographystyle|addbibresource|printbibliography)\b"
)


def looks_like_latex(content: str) -> bool:
    """Return True if *content* appears to already be raw LaTeX.

    The check is conservative -- we only treat content as LaTeX when it
    contains structural commands (``\\section{``, ``\\begin{document}``,
    display-math environments, ``\\documentclass``, etc.) that would not
    appear inside a markdown body. Fenced code blocks are stripped before
    the scan so a markdown section containing a LaTeX example in a
    ``` ``` ``` block is still treated as markdown. Inline math
    (``$x$``, ``$$...$$``) is valid in markdown and does not trigger the
    heuristic.
    """
    if not content:
        return False
    stripped = _FENCED_CODE_BLOCK_PATTERN.sub("", content)
    return _LATEX_SIGIL_PATTERN.search(stripped) is not None


def maybe_convert_to_latex(
    content: str,
    *,
    lua_filters: list[Path] | None = None,
    bibliography: Path | None = None,
    citeproc: bool = False,
    natbib: bool = True,
    external_filters: list[str] | None = None,
    pandoc_status: PandocStatus | None = None,
) -> str:
    """Convert *content* to a LaTeX fragment if it looks like markdown.

    Intended for callers that do NOT know in advance whether ``content``
    is markdown or LaTeX (e.g. legacy payloads, user-supplied text).
    Callers with explicit intent should use ``markdown_to_latex_fragment``
    directly and check pandoc availability up front -- that path fails
    loudly when pandoc is missing, which is usually what you want when
    the author explicitly asked for markdown.

    Behaviour matrix:

    ================================  ==================================
    content is empty                  returned unchanged
    content looks like LaTeX          returned unchanged
    pandoc unavailable / old          returned unchanged (debug-logged)
    pandoc conversion raises          *re-raised* (PandocExecutionError)
    otherwise                         pandoc output
    ================================  ==================================

    The "unavailable -> pass through" path is the only soft-fail. A
    pandoc execution failure against markdown content is *not* soft --
    returning the raw markdown would inject it into a ``.tex`` file and
    compile to garbage. The caller sees the error and can decide how to
    recover.

    ``natbib`` defaults to True: the paper pipeline emits natbib
    commands (``\\citet{key}`` for textual ``@key`` and ``\\citep{k1, k2}``
    for ``[@k1; @k2]`` groups) so the template's ``\\bibliography{...}``
    can resolve them via bibtex. Literal ``@token`` in prose will be
    misread as a cite key in this mode -- pass ``natbib=False`` or
    escape as ``\\@`` if the content has email addresses or social
    handles. ``citeproc=True`` takes precedence and disables natbib.

    External filters (currently only ``pandoc-crossref``) are
    auto-detected via ``status.installed_filters`` and prepended to the
    filter chain. Pass ``external_filters=[]`` to opt out. Legacy
    ``pandoc-citeproc`` is deliberately excluded from auto-detection to
    prevent double-processing alongside ``--natbib``; callers that
    genuinely need it must request it explicitly.
    """
    if not content or not content.strip():
        return content
    if looks_like_latex(content):
        return content

    status = pandoc_status if pandoc_status is not None else detect_pandoc()
    if not status.available or not status.meets_minimum:
        logger.debug(
            "pandoc unavailable (%s); leaving section content as-is",
            status.error or ("version below minimum" if status.available else "not found"),
        )
        return content

    return markdown_to_latex_fragment(
        content,
        lua_filters=lua_filters,
        bibliography=bibliography,
        citeproc=citeproc,
        natbib=natbib,
        external_filters=external_filters,
        status=status,
    )


__all__ = ["looks_like_latex", "maybe_convert_to_latex"]
