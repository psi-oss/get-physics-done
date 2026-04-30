"""Tests for gpd.mcp.paper.markdown_support + content_format routing.

Covers the heuristic that decides whether a section is markdown or LaTeX,
the graceful/loud error contract of ``maybe_convert_to_latex``, and the
opt-in ``Section.content_format`` path that ``template_registry`` uses
when actually rendering a paper.
"""

from __future__ import annotations

import shutil
from unittest.mock import MagicMock

import pytest

from gpd.mcp.paper import markdown_support
from gpd.mcp.paper import template_registry
from gpd.mcp.paper.markdown_support import looks_like_latex, maybe_convert_to_latex
from gpd.mcp.paper.models import Author, PaperConfig, Section
from gpd.mcp.paper.template_registry import _clean_section, render_paper
from gpd.utils.pandoc import (
    PandocExecutionError,
    PandocNotAvailable,
    PandocStatus,
)

HAS_PANDOC = shutil.which("pandoc") is not None


def _ready_status() -> PandocStatus:
    return PandocStatus(
        available=True,
        binary_path="/usr/bin/pandoc",
        version=(3, 1, 3),
        version_string="pandoc 3.1.3",
        meets_minimum=True,
    )


def _missing_status() -> PandocStatus:
    return PandocStatus(available=False, error="pandoc not found on PATH")


def _too_old_status() -> PandocStatus:
    return PandocStatus(
        available=True,
        binary_path="/usr/bin/pandoc",
        version=(2, 5, 0),
        version_string="pandoc 2.5",
        meets_minimum=False,
    )


# ─── looks_like_latex: positive cases ───────────────────────────────────────


def test_looks_like_latex_documentclass() -> None:
    assert looks_like_latex(r"\documentclass{article}" + "\n\\begin{document}\nhi\n\\end{document}")


def test_looks_like_latex_begin_document() -> None:
    assert looks_like_latex("\\begin{document}\nhi\n\\end{document}")


def test_looks_like_latex_section_command() -> None:
    assert looks_like_latex("\\section{Introduction}\n\nSome prose.")


def test_looks_like_latex_subsection_starred() -> None:
    assert looks_like_latex("\\subsection*{Background}\n\nSome prose.")


def test_looks_like_latex_bibliography_directive() -> None:
    assert looks_like_latex("\\bibliography{refs}")


@pytest.mark.parametrize("env", ["equation", "align", "gather", "multline", "eqnarray"])
def test_looks_like_latex_display_math_environments(env: str) -> None:
    # A section that opens with a display-math environment is LaTeX, not
    # markdown that happens to embed some math.
    body = f"\\begin{{{env}}}\nx = 1\n\\end{{{env}}}"
    assert looks_like_latex(body)


@pytest.mark.parametrize("env", ["equation*", "align*", "gather*", "multline*"])
def test_looks_like_latex_starred_math_environments(env: str) -> None:
    body = f"\\begin{{{env}}}\nx = 1\n\\end{{{env}}}"
    assert looks_like_latex(body)


# ─── looks_like_latex: negative cases ───────────────────────────────────────


def test_looks_like_latex_empty_is_false() -> None:
    assert looks_like_latex("") is False


def test_looks_like_latex_plain_markdown_is_false() -> None:
    assert looks_like_latex("# Heading\n\nSome **bold** text and *emphasis*.\n") is False


def test_looks_like_latex_inline_math_is_not_latex() -> None:
    # Inline ``$...$`` is valid markdown and must not trip the heuristic.
    assert looks_like_latex("Einstein said $E = mc^2$ in 1905.\n") is False


def test_looks_like_latex_display_math_dollars_is_not_latex() -> None:
    # ``$$...$$`` is valid markdown (same as Pandoc display math).
    assert looks_like_latex("Result:\n\n$$\\int_0^1 x\\,dx = \\tfrac{1}{2}$$\n") is False


def test_looks_like_latex_fenced_code_block_with_latex_inside_is_not_latex() -> None:
    # A markdown section showing a LaTeX example inside a fenced code block
    # must still be treated as markdown -- the sigils live inside the fence.
    body = (
        "Here is an example of the section macro:\n\n"
        "```latex\n"
        "\\section{Example}\n"
        "\\begin{equation}\nE = mc^2\n\\end{equation}\n"
        "```\n\n"
        "As shown above, it takes a title argument.\n"
    )
    assert looks_like_latex(body) is False


def test_looks_like_latex_unfenced_section_outside_code_block_is_detected() -> None:
    # Mixing: if there IS a real \section outside the fence, we still catch it.
    body = (
        "```latex\n"
        "some example\n"
        "```\n\n"
        "\\section{Real Section}\n\nProse.\n"
    )
    assert looks_like_latex(body) is True


def test_looks_like_latex_at_sigil_alone_is_markdown() -> None:
    # ``@citekey`` alone is pandoc-flavored markdown cite syntax, not LaTeX.
    assert looks_like_latex("Pioneered by @einstein1905 and later @michelson1887.\n") is False


# ─── maybe_convert_to_latex: routing + soft/hard failure modes ──────────────


def test_maybe_convert_to_latex_empty_passthrough() -> None:
    assert maybe_convert_to_latex("") == ""
    assert maybe_convert_to_latex("   \n\n  ") == "   \n\n  "


def test_maybe_convert_to_latex_passes_through_latex_without_calling_pandoc(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Tripwire: if the content already looks like LaTeX, pandoc must not be
    # invoked -- otherwise legacy raw-LaTeX callers pay the subprocess cost
    # and risk double-escaping.
    called: dict[str, bool] = {"ran": False}

    def boom(*_a, **_kw):
        called["ran"] = True
        raise AssertionError("markdown_to_latex_fragment should not be called")

    monkeypatch.setattr(markdown_support, "markdown_to_latex_fragment", boom)
    out = maybe_convert_to_latex("\\section{Hi}\n\nProse.", pandoc_status=_ready_status())
    assert "\\section{Hi}" in out
    assert called["ran"] is False


def test_maybe_convert_to_latex_pandoc_unavailable_is_soft_failure() -> None:
    # Soft fallback: return input unchanged, debug-log, do not raise. Legacy
    # payloads keep compiling on hosts without pandoc.
    body = "# Hello\n\nProse with **bold**.\n"
    assert maybe_convert_to_latex(body, pandoc_status=_missing_status()) == body


def test_maybe_convert_to_latex_pandoc_too_old_is_soft_failure() -> None:
    body = "# Hello\n\nProse with **bold**.\n"
    assert maybe_convert_to_latex(body, pandoc_status=_too_old_status()) == body


def test_maybe_convert_to_latex_reraises_pandoc_execution_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Hard failure: if pandoc runs but blows up, surface the error. Silently
    # shoving raw markdown into a ``.tex`` file would compile to garbage.
    def explode(*_a, **_kw):
        raise PandocExecutionError("pandoc exited 1", stderr="bad input")

    monkeypatch.setattr(markdown_support, "markdown_to_latex_fragment", explode)
    with pytest.raises(PandocExecutionError):
        maybe_convert_to_latex("# Hi\n\nProse.\n", pandoc_status=_ready_status())


def test_maybe_convert_to_latex_invokes_fragment_converter_with_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: dict[str, object] = {}

    def fake_fragment(content: str, **kwargs: object) -> str:
        recorded["content"] = content
        recorded["kwargs"] = kwargs
        return "LATEX"

    monkeypatch.setattr(markdown_support, "markdown_to_latex_fragment", fake_fragment)
    out = maybe_convert_to_latex(
        "# Hi\n\nProse.\n",
        natbib=False,
        citeproc=True,
        external_filters=["pandoc-crossref"],
        pandoc_status=_ready_status(),
    )
    assert out == "LATEX"
    assert recorded["content"] == "# Hi\n\nProse.\n"
    kwargs = recorded["kwargs"]
    assert kwargs["natbib"] is False
    assert kwargs["citeproc"] is True
    assert kwargs["external_filters"] == ["pandoc-crossref"]


# ─── Section.content_format routing through _clean_section ──────────────────


def test_clean_section_latex_content_passes_through_without_pandoc() -> None:
    section = Section(
        title="Intro",
        content="Raw \\emph{LaTeX} prose with $x = 1$.",
        content_format="latex",
    )
    # No pandoc_status passed, and content_format="latex" -- must not probe.
    out = _clean_section(section)
    assert out.content == "Raw \\emph{LaTeX} prose with $x = 1$."


def test_clean_section_markdown_raises_when_pandoc_missing() -> None:
    section = Section(
        title="Intro",
        content="# Hi\n\nProse.\n",
        content_format="markdown",
    )
    with pytest.raises(PandocNotAvailable) as exc:
        _clean_section(section, pandoc_status=_missing_status())
    message = str(exc.value)
    assert "'Intro'" in message
    assert "markdown" in message
    # Error message tells the user how to recover.
    assert "latex" in message.lower() or "install pandoc" in message.lower()


def test_clean_section_markdown_raises_when_pandoc_too_old() -> None:
    section = Section(
        title="Intro",
        content="# Hi\n\nProse.\n",
        content_format="markdown",
    )
    with pytest.raises(PandocNotAvailable):
        _clean_section(section, pandoc_status=_too_old_status())


def test_clean_section_markdown_invokes_fragment_converter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: dict[str, object] = {}

    def fake_fragment(content: str, *, status: PandocStatus, **_kw) -> str:
        recorded["content"] = content
        recorded["status"] = status
        return "\\emph{converted}"

    monkeypatch.setattr(template_registry, "markdown_to_latex_fragment", fake_fragment)
    section = Section(
        title="Intro",
        content="# Hi\n\nProse.\n",
        content_format="markdown",
    )
    out = _clean_section(section, pandoc_status=_ready_status())
    assert out.content == "\\emph{converted}"
    # Section.content validator strips surrounding whitespace before storage.
    assert recorded["content"] == "# Hi\n\nProse."
    assert recorded["status"].meets_minimum is True


# ─── render_paper end-to-end opt-in routing ─────────────────────────────────


def _minimal_config(**overrides: object) -> PaperConfig:
    defaults: dict[str, object] = dict(
        title="A Title",
        authors=[Author(name="A. N. Author")],
        abstract="An abstract that is long enough.",
        sections=[Section(title="Intro", content="Raw LaTeX prose.")],
    )
    defaults.update(overrides)
    return PaperConfig(**defaults)


def test_render_paper_skips_pandoc_probe_when_all_sections_are_latex(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: dict[str, int] = {"n": 0}

    def counting_detect() -> PandocStatus:
        called["n"] += 1
        return _ready_status()

    monkeypatch.setattr(template_registry, "detect_pandoc", counting_detect)
    config = _minimal_config()
    rendered = render_paper(config)
    assert "Raw LaTeX prose." in rendered
    # Pure-LaTeX payload: pandoc must NOT be probed. Opt-in is strict.
    assert called["n"] == 0


def test_render_paper_probes_pandoc_once_even_with_many_markdown_sections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    called: dict[str, int] = {"n": 0}

    def counting_detect() -> PandocStatus:
        called["n"] += 1
        return _ready_status()

    monkeypatch.setattr(template_registry, "detect_pandoc", counting_detect)
    monkeypatch.setattr(
        template_registry,
        "markdown_to_latex_fragment",
        lambda content, **_kw: f"CONVERTED({content!r})",
    )
    config = _minimal_config(
        sections=[
            Section(title="Intro", content="# Hi\n\nA.\n", content_format="markdown"),
            Section(title="Methods", content="# Hey\n\nB.\n", content_format="markdown"),
        ],
        appendix_sections=[
            Section(title="App", content="# Appendix\n\nC.\n", content_format="markdown"),
        ],
    )
    rendered = render_paper(config)
    # Single probe shared across all three sections.
    assert called["n"] == 1
    assert "CONVERTED" in rendered


def test_render_paper_markdown_without_pandoc_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(template_registry, "detect_pandoc", _missing_status)
    config = _minimal_config(
        sections=[Section(title="Intro", content="# Hi\n\nProse.\n", content_format="markdown")],
    )
    with pytest.raises(PandocNotAvailable):
        render_paper(config)


@pytest.mark.skipif(not HAS_PANDOC, reason="pandoc not installed")
def test_render_paper_markdown_roundtrip_with_real_pandoc() -> None:
    # Integration: a markdown section actually becomes a LaTeX fragment in
    # the rendered template, with pandoc-generated natbib cite commands.
    config = _minimal_config(
        sections=[
            Section(
                title="Intro",
                content=(
                    "Einstein's paper [@einstein1905] started it all. "
                    "Michelson and Morley @michelson1887 came first though.\n\n"
                    "A list:\n\n- item one\n- item two\n"
                ),
                content_format="markdown",
            )
        ],
    )
    rendered = render_paper(config)
    # Pandoc emitted natbib cite commands, not raw ``@`` sigils.
    assert "@einstein1905" not in rendered
    assert "\\citet{michelson1887}" in rendered or "\\citep{einstein1905}" in rendered
    # Bullet lists came through.
    assert "\\begin{itemize}" in rendered
    # Full document wrapper comes from the journal template, not from pandoc.
    assert "\\documentclass" in rendered
    assert rendered.count("\\begin{document}") == 1
