"""Tests for paper models, journal map, and templates."""

from __future__ import annotations

from pathlib import Path

import pytest

from gpd.mcp.paper.models import Author, FigureRef, JournalSpec, PaperConfig, Section

# ---- Model validation tests ----


class TestModels:
    def test_author_defaults(self):
        author = Author(name="Alice")
        assert author.name == "Alice"
        assert author.email == ""
        assert author.affiliation == ""

    def test_paper_config_minimal(self):
        config = PaperConfig(
            title="Test",
            authors=[Author(name="Bob")],
            abstract="Abstract.",
            sections=[Section(title="Intro", content="Hello.")],
        )
        assert config.journal == "prl"
        assert config.figures == []
        assert config.appendix_sections == []
        assert config.bib_file == "references"
        assert config.attribution_footer == "Generated with Get Physics Done"

    def test_paper_config_full(self):
        config = PaperConfig(
            title="Full Paper",
            authors=[Author(name="A", email="a@b.com", affiliation="MIT")],
            abstract="Abstract.",
            sections=[Section(title="Intro", content="Hello.", label="intro")],
            figures=[FigureRef(path=Path("fig.png"), caption="Caption", label="fig1")],
            acknowledgments="Thanks.",
            bib_file="refs",
            journal="apj",
            appendix_sections=[Section(title="App", content="Extra.")],
        )
        assert config.journal == "apj"
        assert len(config.figures) == 1
        assert len(config.appendix_sections) == 1

    def test_figure_ref_defaults(self):
        fig = FigureRef(path=Path("fig.pdf"), caption="Cap", label="f1")
        assert fig.width == r"\columnwidth"
        assert fig.double_column is False

    def test_journal_spec_fields(self):
        spec = JournalSpec(
            key="test",
            document_class="article",
            class_options=["12pt"],
            bib_style="plain",
            column_width_cm=8.0,
            double_width_cm=16.0,
            max_height_cm=24.0,
            dpi=300,
            preferred_formats=["pdf"],
            texlive_package="latex-base",
        )
        assert spec.compiler == "pdflatex"
        assert spec.dpi == 300
        assert spec.required_tex_files == []
        assert spec.install_hint == ""


# ---- Journal map tests ----


class TestJournalMap:
    def test_get_journal_spec_all_six(self):
        from gpd.mcp.paper.journal_map import get_journal_spec

        for key in ["prl", "apj", "mnras", "nature", "jhep", "jfm"]:
            spec = get_journal_spec(key)
            assert spec.key == key
            assert spec.column_width_cm > 0
            assert spec.dpi > 0
            assert f"{spec.bib_style}.bst" in spec.required_tex_files

    def test_get_journal_spec_unknown_raises(self):
        from gpd.mcp.paper.journal_map import get_journal_spec

        with pytest.raises(ValueError, match="Unknown journal"):
            get_journal_spec("nonexistent")

    def test_domain_journal_map_coverage(self):
        from gpd.mcp.paper.journal_map import DOMAIN_JOURNAL_MAP

        assert len(DOMAIN_JOURNAL_MAP) >= 15

    def test_astrophysics_maps_to_apj(self):
        from gpd.mcp.paper.journal_map import get_journal_for_domain

        assert get_journal_for_domain("astrophysics") == "apj"
        assert get_journal_for_domain("cosmology") == "apj"
        assert get_journal_for_domain("fluid_mechanics") == "jfm"
        assert get_journal_for_domain("biophysics") == "nature"
        assert get_journal_for_domain("particle_physics") == "prl"

    def test_default_is_prl(self):
        from gpd.mcp.paper.journal_map import get_journal_for_domain

        assert get_journal_for_domain("unknown_domain_xyz") == "prl"

    def test_list_journals(self):
        from gpd.mcp.paper.journal_map import list_journals

        journals = list_journals()
        assert len(journals) == 6
        assert set(journals) == {"prl", "apj", "mnras", "nature", "jhep", "jfm"}


# ---- Template tests ----


class TestTemplates:
    def test_load_all_templates(self):
        from gpd.mcp.paper.template_registry import load_template

        for j in ["prl", "apj", "mnras", "nature", "jhep", "jfm"]:
            t = load_template(j)
            assert t is not None

    def test_render_prl_paper(self):
        from gpd.mcp.paper.template_registry import render_paper

        config = PaperConfig(
            title="Test Paper",
            authors=[Author(name="Test Author", email="test@test.com", affiliation="Test Univ")],
            abstract="This is a test abstract.",
            sections=[Section(title="Introduction", content="Hello world.")],
        )
        tex = render_paper(config)
        assert r"\documentclass" in tex
        assert "revtex4-2" in tex
        assert r"\title{Test Paper}" in tex
        assert r"\author{Test Author}" in tex
        assert r"\begin{abstract}" in tex
        assert r"\section{Introduction}" in tex
        assert r"\bibliography{references}" in tex
        assert "Generated with Get Physics Done" in tex

    def test_render_apj_paper(self):
        from gpd.mcp.paper.template_registry import render_paper

        config = PaperConfig(
            title="Stellar Paper",
            authors=[Author(name="A")],
            abstract="Abstract.",
            sections=[Section(title="Intro", content="Intro.")],
            journal="apj",
        )
        tex = render_paper(config)
        assert "aastex631" in tex

    def test_render_keeps_full_document_when_section_content_is_fenced(self):
        from gpd.mcp.paper.template_registry import render_paper

        config = PaperConfig(
            title="Fenced Content",
            authors=[Author(name="Fence Tester")],
            abstract="Abstract.",
            sections=[Section(title="Intro", content="```latex\nE = mc^2\n```")],
        )
        tex = render_paper(config)
        assert r"\documentclass" in tex
        assert "```" not in tex
        assert "E = mc^2" in tex

    def test_render_jhep_paper(self):
        from gpd.mcp.paper.template_registry import render_paper

        config = PaperConfig(
            title="Loop Corrections",
            authors=[Author(name="A", email="a@example.com", affiliation="CERN")],
            abstract="Abstract.",
            sections=[Section(title="Setup", content="Details.")],
            journal="jhep",
        )
        tex = render_paper(config)
        assert r"\documentclass[a4paper,11pt]{article}" in tex
        assert r"\usepackage{jheppub}" in tex
        assert r"\author[1]{A}" in tex
        assert r"\affiliation[1]{CERN}" in tex
        assert r"\emailAdd{a@example.com}" in tex
        assert r"\bibliographystyle{JHEP}" in tex

    def test_render_nature_affiliation_does_not_concatenate_small_with_text(self):
        from gpd.mcp.paper.template_registry import render_paper

        config = PaperConfig(
            title="Nature Paper",
            authors=[Author(name="A", affiliation="Institute of Testing")],
            abstract="Abstract.",
            sections=[Section(title="Intro", content="Text.")],
            journal="nature",
        )
        tex = render_paper(config)
        assert r"{\small Institute of Testing}" in tex
        assert r"\smallInstitute" not in tex

    def test_render_with_figures(self):
        from gpd.mcp.paper.template_registry import render_paper

        config = PaperConfig(
            title="Fig Paper",
            authors=[Author(name="B")],
            abstract="Abstract.",
            sections=[Section(title="Intro", content="See figure.")],
            figures=[FigureRef(path=Path("figures/fig01.pdf"), caption="Velocity field.", label="velocity")],
        )
        tex = render_paper(config)
        assert r"\includegraphics" in tex
        assert r"\caption{Velocity field.}" in tex
        assert r"\label{fig:velocity}" in tex

    def test_render_with_appendix(self):
        from gpd.mcp.paper.template_registry import render_paper

        config = PaperConfig(
            title="App Paper",
            authors=[Author(name="C")],
            abstract="Abstract.",
            sections=[Section(title="Intro", content="Main.")],
            appendix_sections=[Section(title="Details", content="Extra info.")],
        )
        tex = render_paper(config)
        assert r"\appendix" in tex
        assert "Details" in tex

    def test_unknown_template_raises(self):
        from gpd.mcp.paper.template_registry import load_template

        with pytest.raises(FileNotFoundError):
            load_template("nonexistent")
