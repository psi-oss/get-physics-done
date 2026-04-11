from __future__ import annotations

import pytest

from gpd.mcp.paper.models import PaperConfig, Section
from gpd.mcp.paper.template_registry import render_paper
from gpd.utils.latex import clean_latex_fences


def test_clean_latex_fences_preserves_prose_around_fenced_blocks() -> None:
    content = "Intro paragraph.\n```latex\n\\section{Results}\n```\nClosing note."

    assert clean_latex_fences(content) == "Intro paragraph.\n\n\\section{Results}\n\nClosing note."


def test_clean_latex_fences_preserves_plain_text_between_multiple_blocks() -> None:
    content = "Lead.\n```tex\nx^2\n```\nBridge.\n```latex\n\\alpha + \\beta\n```\nTail."

    assert clean_latex_fences(content) == "Lead.\n\nx^2\n\nBridge.\n\n\\alpha + \\beta\n\nTail."


def test_render_paper_apj_includes_packages_for_unicode_sanitization_macros() -> None:
    rendered = render_paper(
        PaperConfig(
            journal="apj",
            title="Symbols ★ ♀ ✓",
            authors=[],
            abstract="Abstract",
            sections=[Section(title="Intro", content="Symbols ★ ♀ ✓")],
        )
    )

    assert "\\usepackage{amssymb}" in rendered
    assert "\\usepackage{wasysym}" in rendered
    assert "\\bigstar" in rendered
    assert "\\venus" in rendered
    assert "\\checkmark" in rendered


def test_render_paper_jfm_includes_packages_for_unicode_sanitization_macros() -> None:
    rendered = render_paper(
        PaperConfig(
            journal="jfm",
            title="Symbols ★ ♀ ✓",
            authors=[],
            abstract="Abstract",
            sections=[Section(title="Intro", content="Symbols ★ ♀ ✓")],
        )
    )

    assert "\\usepackage{amssymb}" in rendered
    assert "\\usepackage{wasysym}" in rendered
    assert "\\bigstar" in rendered
    assert "\\venus" in rendered
    assert "\\checkmark" in rendered


@pytest.mark.parametrize("journal", ["prl", "nature", "jhep", "mnras"])
def test_render_paper_adds_wasysym_support_for_planet_macros(journal: str) -> None:
    rendered = render_paper(
        PaperConfig(
            journal=journal,
            title="Symbols ♀",
            authors=[],
            abstract="Abstract",
            sections=[Section(title="Intro", content="Symbols ♀")],
        )
    )

    assert "\\usepackage{wasysym}" in rendered
    assert "\\venus" in rendered


class TestEscapeUserTextForLatex:
    """Tests for BUG-068: LaTeX special character escaping in user metadata."""

    def test_tilde_escaped_in_plain_text(self) -> None:
        from gpd.utils.latex import escape_user_text_for_latex

        assert r"\textasciitilde{}" in escape_user_text_for_latex("accuracy ~0.1%")

    def test_hash_escaped(self) -> None:
        from gpd.utils.latex import escape_user_text_for_latex

        assert r"\#" in escape_user_text_for_latex("C# implementation")

    def test_percent_escaped(self) -> None:
        from gpd.utils.latex import escape_user_text_for_latex

        assert r"\%" in escape_user_text_for_latex("improved by 10%")

    def test_ampersand_escaped(self) -> None:
        from gpd.utils.latex import escape_user_text_for_latex

        assert r"\&" in escape_user_text_for_latex("AT&T Labs")

    def test_already_escaped_not_doubled(self) -> None:
        from gpd.utils.latex import escape_user_text_for_latex

        result = escape_user_text_for_latex(r"costs \$10 and \#1 at \~100\% by A\&B")
        assert r"\\#" not in result  # \# should stay as \#, not become \\#
        assert r"\\%" not in result  # \% should stay as \%
        assert r"\\&" not in result  # \& should stay as \&
        assert r"\\textasciitilde{}" not in result  # \~ should stay as \~

    def test_math_mode_preserved(self) -> None:
        from gpd.utils.latex import escape_user_text_for_latex

        # Tilde inside math mode ($\tilde{x} \sim 0.1$) must NOT be touched
        text = r"We find $\tilde{x} \sim 0.1$ with ~10% error"
        result = escape_user_text_for_latex(text)
        assert r"$\tilde{x} \sim 0.1$" in result
        assert r"\textasciitilde{}" in result
        assert r"\%" in result

    def test_multiple_specials_in_one_string(self) -> None:
        from gpd.utils.latex import escape_user_text_for_latex

        text = "C# at AT&T: ~100% success"
        result = escape_user_text_for_latex(text)
        assert r"\#" in result
        assert r"\&" in result
        assert r"\textasciitilde{}" in result
        assert r"\%" in result

    def test_empty_string(self) -> None:
        from gpd.utils.latex import escape_user_text_for_latex

        assert escape_user_text_for_latex("") == ""

    def test_no_specials_unchanged(self) -> None:
        from gpd.utils.latex import escape_user_text_for_latex

        text = "A perfectly normal title"
        assert escape_user_text_for_latex(text) == text


class TestRenderPaperEscapesUserFields:
    """Integration tests: special chars in user fields are escaped in rendered output."""

    def test_tilde_in_abstract_escaped(self) -> None:
        from gpd.mcp.paper.models import PaperConfig, Section
        from gpd.mcp.paper.template_registry import render_paper

        rendered = render_paper(
            PaperConfig(
                journal="prl",
                title="Test",
                authors=[],
                abstract="accuracy ~0.1",
                sections=[Section(title="Intro", content="Body")],
            )
        )
        # The abstract should contain the escaped tilde, not a bare ~
        # (bare ~ would be non-breaking space in LaTeX)
        assert r"\textasciitilde{}" in rendered

    def test_percent_in_title_escaped(self) -> None:
        from gpd.mcp.paper.models import PaperConfig, Section
        from gpd.mcp.paper.template_registry import render_paper

        rendered = render_paper(
            PaperConfig(
                journal="prl",
                title="10% Improvement in Efficiency",
                authors=[],
                abstract="Abstract",
                sections=[Section(title="Intro", content="Body")],
            )
        )
        assert r"\%" in rendered

    def test_ampersand_in_affiliation_escaped(self) -> None:
        from gpd.mcp.paper.models import Author, PaperConfig, Section
        from gpd.mcp.paper.template_registry import render_paper

        rendered = render_paper(
            PaperConfig(
                journal="prl",
                title="Test",
                authors=[Author(name="J. Smith", affiliation="AT&T Labs")],
                abstract="Abstract",
                sections=[Section(title="Intro", content="Body")],
            )
        )
        assert r"AT\&T Labs" in rendered

    def test_section_content_tilde_NOT_escaped(self) -> None:
        """Agent-generated LaTeX in section.content must preserve ~ for Fig.~\\ref."""
        from gpd.mcp.paper.models import PaperConfig, Section
        from gpd.mcp.paper.template_registry import render_paper

        rendered = render_paper(
            PaperConfig(
                journal="prl",
                title="Test",
                authors=[],
                abstract="Abstract",
                sections=[Section(title="Intro", content=r"See Fig.~\ref{fig:velocity}.")],
            )
        )
        # The ~ in section content should be preserved (non-breaking space for LaTeX)
        assert r"Fig.~\ref{fig:velocity}" in rendered
        assert r"Fig.\textasciitilde{}" not in rendered
