"""LaTeX utilities -- auto-fix, fence stripping, Unicode sanitization.

Provides rule-based auto-fix for common LaTeX compilation errors,
Unicode-to-LaTeX command conversion, and markdown fence stripping.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# =============================================================================
# Auto-fix rules
# =============================================================================


@dataclass(frozen=True)
class AutoFixResult:
    """Result of attempting to auto-fix LaTeX content."""

    fixed_content: str | None = None
    fixes_applied: tuple[str, ...] = field(default_factory=tuple)
    was_modified: bool = False


def _split_by_math_mode(tex: str) -> list[tuple[str, bool]]:
    r"""Split LaTeX content into segments, marking which are in math mode.

    Handles: $...$, $$...$$, \[...\], \(...\), and \begin/\end math environments.
    """
    math_pattern = re.compile(
        r"(\$\$.*?\$\$|\$[^$]+?\$|\\\[.*?\\\]|\\\(.*?\\\)"
        r"|\\begin\{(?:equation|align|alignat|gather|multline|flalign|eqnarray|math|displaymath)\*?\}.*?"
        r"\\end\{(?:equation|align|alignat|gather|multline|flalign|eqnarray|math|displaymath)\*?\})",
        re.DOTALL,
    )
    parts: list[tuple[str, bool]] = []
    last_end = 0
    for match in math_pattern.finditer(tex):
        if match.start() > last_end:
            parts.append((tex[last_end : match.start()], False))
        parts.append((match.group(0), True))
        last_end = match.end()
    if last_end < len(tex):
        parts.append((tex[last_end:], False))
    return parts if parts else [(tex, False)]


def _fix_unescaped_underscores(tex: str) -> str:
    parts = _split_by_math_mode(tex)
    result: list[str] = []
    for content, is_math in parts:
        if is_math:
            result.append(content)
        else:
            fixed = re.sub(r"(?<!\\)_", r"\\_", content)
            result.append(fixed)
    return "".join(result)


def _fix_unescaped_carets(tex: str) -> str:
    parts = _split_by_math_mode(tex)
    result: list[str] = []
    for content, is_math in parts:
        if is_math:
            result.append(content)
        else:
            fixed = re.sub(r"(?<!\\)\^", r"\\^{}", content)
            result.append(fixed)
    return "".join(result)


def _fix_missing_document_begin(tex: str) -> str:
    has_documentclass = re.search(r"\\documentclass", tex)
    has_begin_doc = re.search(r"\\begin\s*\{document\}", tex)
    if has_documentclass and not has_begin_doc:
        preamble_patterns = [
            r"\\usepackage(?:\[[^\]]*\])?\s*\{[^}]*\}",
            r"\\newcommand\s*\{[^}]*\}(?:\[[^\]]*\])?\{(?:[^{}]|\{[^{}]*\})*\}",
            r"\\renewcommand\s*\{[^}]*\}(?:\[[^\]]*\])?\{(?:[^{}]|\{[^{}]*\})*\}",
            r"\\author\s*\{[^}]*\}",
            r"\\title\s*\{[^}]*\}",
            r"\\date\s*\{[^}]*\}",
        ]
        last_preamble_end = 0
        for pattern in preamble_patterns:
            for match in re.finditer(pattern, tex):
                if match.end() > last_preamble_end:
                    last_preamble_end = match.end()
        if last_preamble_end == 0:
            dc_match = re.search(r"\\documentclass[^\n]*\n", tex)
            if dc_match:
                last_preamble_end = dc_match.end()
        if last_preamble_end > 0:
            return tex[:last_preamble_end] + "\n\\begin{document}\n" + tex[last_preamble_end:]
    return tex


def _fix_missing_document_end(tex: str) -> str:
    has_begin_doc = re.search(r"\\begin\s*\{document\}", tex)
    has_end_doc = re.search(r"\\end\s*\{document\}", tex)
    if has_begin_doc and not has_end_doc:
        tex = tex.rstrip() + "\n\\end{document}\n"
    return tex


def _fix_unbalanced_braces(tex: str) -> str:
    open_count = tex.count("{") - tex.count("\\{")
    close_count = tex.count("}") - tex.count("\\}")
    if open_count > close_count:
        missing = open_count - close_count
        tex = tex.rstrip() + ("}" * missing)
    elif close_count > open_count:
        missing = close_count - open_count
        tex = ("{" * missing) + tex.lstrip()
    return tex


def _fix_unescaped_underscores_and_carets(tex: str) -> str:
    """Apply both underscore and caret fixes for 'Missing $ inserted' errors."""
    return _fix_unescaped_carets(_fix_unescaped_underscores(tex))


_AUTO_FIX_RULES: list[tuple[str, Callable[[str], str], str]] = [
    (r"Missing \$ inserted", _fix_unescaped_underscores_and_carets, "Escaped underscores and carets outside math mode"),
    (r"Missing \\begin\{document\}", _fix_missing_document_begin, "Added missing \\begin{document}"),
    (r"LaTeX Error: \\begin\{document\} ended", _fix_missing_document_end, "Added missing \\end{document}"),
    (r"Runaway argument", _fix_unbalanced_braces, "Balanced unmatched braces"),
    (r"Too many \}'s", _fix_unbalanced_braces, "Attempted to balance braces"),
]


def try_autofix(tex_content: str, log: str) -> AutoFixResult:
    """Attempt to auto-fix common LaTeX errors based on compilation log.

    Parses the compilation log for known error patterns and applies
    appropriate fixes.
    """
    if not log:
        return AutoFixResult()

    fixes_applied: list[str] = []
    current_content = tex_content

    for pattern, fixer, description in _AUTO_FIX_RULES:
        if re.search(pattern, log, re.IGNORECASE):
            try:
                fixed = fixer(current_content)
                if fixed != current_content:
                    current_content = fixed
                    if description not in fixes_applied:
                        fixes_applied.append(description)
            except Exception as e:
                logger.warning("autofix rule failed: pattern=%s error=%s", pattern, e)
                continue

    if fixes_applied:
        return AutoFixResult(
            fixed_content=current_content,
            fixes_applied=tuple(fixes_applied),
            was_modified=True,
        )
    return AutoFixResult()


# =============================================================================
# Unicode sanitization
# =============================================================================

_UNICODE_TO_LATEX: dict[str, str] = {
    # Greek lowercase
    "\u03b1": r"$\alpha$",
    "\u03b2": r"$\beta$",
    "\u03b3": r"$\gamma$",
    "\u03b4": r"$\delta$",
    "\u03b5": r"$\epsilon$",
    "\u03b6": r"$\zeta$",
    "\u03b7": r"$\eta$",
    "\u03b8": r"$\theta$",
    "\u03b9": r"$\iota$",
    "\u03ba": r"$\kappa$",
    "\u03bb": r"$\lambda$",
    "\u03bc": r"$\mu$",
    "\u03bd": r"$\nu$",
    "\u03be": r"$\xi$",
    "\u03c0": r"$\pi$",
    "\u03c1": r"$\rho$",
    "\u03c3": r"$\sigma$",
    "\u03c4": r"$\tau$",
    "\u03c5": r"$\upsilon$",
    "\u03c6": r"$\phi$",
    "\u03c7": r"$\chi$",
    "\u03c8": r"$\psi$",
    "\u03c9": r"$\omega$",
    "\u03f5": r"$\varepsilon$",
    "\u03d1": r"$\vartheta$",
    "\u03d5": r"$\varphi$",
    # Greek uppercase
    "\u0393": r"$\Gamma$",
    "\u0394": r"$\Delta$",
    "\u0398": r"$\Theta$",
    "\u039b": r"$\Lambda$",
    "\u039e": r"$\Xi$",
    "\u03a0": r"$\Pi$",
    "\u03a3": r"$\Sigma$",
    "\u03a5": r"$\Upsilon$",
    "\u03a6": r"$\Phi$",
    "\u03a8": r"$\Psi$",
    "\u03a9": r"$\Omega$",
    # Math symbols
    "\u221e": r"$\infty$",
    "\u2202": r"$\partial$",
    "\u2207": r"$\nabla$",
    "\u222b": r"$\int$",
    "\u2211": r"$\sum$",
    "\u220f": r"$\prod$",
    "\u221a": r"$\sqrt{}$",
    "\u00b1": r"$\pm$",
    "\u00d7": r"$\times$",
    "\u00f7": r"$\div$",
    "\u2264": r"$\leq$",
    "\u2265": r"$\geq$",
    "\u2260": r"$\neq$",
    "\u2248": r"$\approx$",
    "\u2261": r"$\equiv$",
    "\u221d": r"$\propto$",
    "\u2192": r"$\rightarrow$",
    "\u2190": r"$\leftarrow$",
    "\u21d2": r"$\Rightarrow$",
    "\u2208": r"$\in$",
    "\u2209": r"$\notin$",
    "\u2282": r"$\subset$",
    "\u222a": r"$\cup$",
    "\u2229": r"$\cap$",
    "\u2205": r"$\emptyset$",
    "\u2200": r"$\forall$",
    "\u2203": r"$\exists$",
    "\u210f": r"$\hbar$",
    "\u2113": r"$\ell$",
    "\u00b0": r"$^{\circ}$",
    "\u00b7": r"$\cdot$",
    "\u22c5": r"$\cdot$",
    "\u27e8": r"$\langle$",
    "\u27e9": r"$\rangle$",
    "\u222e": r"$\oint$",
    "\u2223": r"$\mid$",
    # Superscripts / subscripts
    "\u00b2": r"$^{2}$",
    "\u00b3": r"$^{3}$",
    "\u00b9": r"$^{1}$",
    "\u2080": r"$_{0}$",
    "\u2081": r"$_{1}$",
    "\u2082": r"$_{2}$",
    "\u2083": r"$_{3}$",
    # Fractions
    "\u00bd": r"$\frac{1}{2}$",
    "\u00bc": r"$\frac{1}{4}$",
    "\u00be": r"$\frac{3}{4}$",
    # Typography
    "\u2013": "--",
    "\u2014": "---",
    "\u2026": r"\ldots",
    "\u00a9": r"\copyright",
    "\u00c5": r"\AA",
}

_EMOJI_RE = re.compile(
    "["
    "\U0001f600-\U0001f64f\U0001f300-\U0001f5ff\U0001f680-\U0001f6ff"
    "\U0001f1e0-\U0001f1ff\U00002702-\U000027b0\U0001f900-\U0001f9ff"
    "\U0001fa00-\U0001fa6f\U0001fa70-\U0001faff\U00002600-\U000026ff"
    "]+",
    flags=re.UNICODE,
)

# Build a math-mode variant of the mapping that strips $...$ wrappers.
# Inside math regions we need the bare command (e.g. \alpha), not $\alpha$.
_DOLLAR_WRAP_RE = re.compile(r"^\$(.+)\$$")
_UNICODE_TO_LATEX_MATH: dict[str, str] = {}
for _char, _cmd in _UNICODE_TO_LATEX.items():
    _m = _DOLLAR_WRAP_RE.match(_cmd)
    _UNICODE_TO_LATEX_MATH[_char] = _m.group(1) if _m else _cmd


def _apply_unicode_replacements(text: str, mapping: dict[str, str]) -> str:
    """Replace Unicode characters in *text* using *mapping*."""
    for char, cmd in mapping.items():
        text = text.replace(char, cmd)
    return text


def sanitize_latex(latex: str) -> str:
    """Convert Unicode chars to LaTeX commands and strip emojis.

    Math-mode-aware: inside existing ``$...$``, ``$$...$$``, ``\\[...\\]``,
    ``\\(...\\)``, and ``\\begin{equation}``-style environments, Unicode
    characters are replaced with bare LaTeX commands (no extra ``$``
    delimiters).  Outside math mode the ``$...$``-wrapped forms are used so
    the commands render correctly.
    """
    parts = _split_by_math_mode(latex)
    result: list[str] = []
    for segment, is_math in parts:
        if is_math:
            result.append(_apply_unicode_replacements(segment, _UNICODE_TO_LATEX_MATH))
        else:
            result.append(_apply_unicode_replacements(segment, _UNICODE_TO_LATEX))
    return _EMOJI_RE.sub("", "".join(result))


def clean_latex_fences(raw: str) -> str:
    """Strip markdown code fences from LLM output."""
    latex = raw.strip()
    if "```latex" in latex:
        latex = latex.split("```latex", 1)[1].split("```", 1)[0].strip()
    elif "```" in latex:
        parts = latex.split("```")
        if len(parts) >= 3:
            latex = parts[1].strip()
    return latex
