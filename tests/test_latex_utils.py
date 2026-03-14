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
