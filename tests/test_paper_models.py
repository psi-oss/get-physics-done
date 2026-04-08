"""Tests for paper models, journal map, and templates."""

from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from gpd.mcp.paper.models import (
    REQUIRED_GPD_ACKNOWLEDGMENT,
    Author,
    FigureRef,
    JournalSpec,
    PaperConfig,
    Section,
)

# ---- Model validation tests ----


class TestModels:
    def test_author_defaults(self):
        author = Author(name="Alice")
        assert author.name == "Alice"
        assert author.email == ""
        assert author.affiliation == ""

    def test_author_rejects_blank_name(self):
        with pytest.raises(ValidationError, match=r"name[\s\S]*non-empty string"):
            Author(name="   ")

    @pytest.mark.parametrize(
        ("payload", "expected_fragment"),
        [
            (
                {
                    "title": "Test",
                    "authors": [{"name": "Bob", "legacy_note": "stale"}],
                    "abstract": "Abstract.",
                    "sections": [{"title": "Intro", "content": "Hello."}],
                },
                r"authors\.0\.legacy_note[\s\S]*Extra inputs are not permitted",
            ),
            (
                {
                    "title": "Test",
                    "authors": [{"name": "Bob"}],
                    "abstract": "Abstract.",
                    "sections": [{"title": "Intro", "content": "Hello.", "legacy_note": "stale"}],
                },
                r"sections\.0\.legacy_note[\s\S]*Extra inputs are not permitted",
            ),
            (
                {
                    "title": "Test",
                    "authors": [{"name": "Bob"}],
                    "abstract": "Abstract.",
                    "sections": [{"title": "Intro", "content": "Hello."}],
                    "figures": [
                        {
                            "path": "figures/fig01.pdf",
                            "caption": "Caption",
                            "label": "fig1",
                            "legacy_note": "stale",
                        }
                    ],
                },
                r"figures\.0\.legacy_note[\s\S]*Extra inputs are not permitted",
            ),
        ],
    )
    def test_paper_config_rejects_nested_extra_keys(
        self,
        payload: dict[str, object],
        expected_fragment: str,
    ) -> None:
        with pytest.raises(ValidationError, match=expected_fragment):
            PaperConfig.model_validate(payload)

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
        assert config.acknowledgments == REQUIRED_GPD_ACKNOWLEDGMENT
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
        assert config.sections[0].label == "intro"
        assert config.figures[0].label == "fig1"
        assert config.acknowledgments.startswith("Thanks.")
        assert config.acknowledgments.count(REQUIRED_GPD_ACKNOWLEDGMENT) == 1

    def test_paper_config_rejects_unknown_journal(self):
        with pytest.raises(ValidationError):
            PaperConfig(
                title="Invalid Journal",
                authors=[Author(name="A")],
                abstract="Abstract.",
                sections=[Section(title="Intro", content="Hello.")],
                journal="physical-review-letters",
            )

    def test_figure_ref_defaults(self):
        fig = FigureRef(path=Path("fig.pdf"), caption="Cap", label="f1")
        assert fig.width == r"\columnwidth"
        assert fig.double_column is False

    def test_figure_ref_rejects_quoted_boolean(self) -> None:
        with pytest.raises(ValidationError):
            FigureRef.model_validate(
                {
                    "path": Path("fig.pdf"),
                    "caption": "Cap",
                    "label": "f1",
                    "double_column": "false",
                }
            )

    @pytest.mark.parametrize(
        ("payload", "expected_fragment"),
        [
            (
                {
                    "title": "   ",
                    "authors": [{"name": "Bob"}],
                    "abstract": "Abstract.",
                    "sections": [{"heading": "Intro", "content": "Hello."}],
                },
                r"title[\s\S]*non-empty string",
            ),
            (
                {
                    "title": "Test",
                    "authors": [{"name": "Bob"}],
                    "abstract": "   ",
                    "sections": [{"heading": "Intro", "content": "Hello."}],
                },
                r"abstract[\s\S]*non-empty string",
            ),
            (
                {
                    "title": "Test",
                    "authors": [{"name": "Bob"}],
                    "abstract": "Abstract.",
                    "sections": [{"heading": "Intro", "content": "Hello."}],
                    "bib_file": "references.bib",
                },
                r"bib_file[\s\S]*stem-safe filename",
            ),
        ],
    )
    def test_paper_config_rejects_blank_required_text_and_legacy_bib_stems(
        self,
        payload: dict[str, object],
        expected_fragment: str,
    ) -> None:
        with pytest.raises(ValidationError, match=expected_fragment):
            PaperConfig.model_validate(payload)

    @pytest.mark.parametrize(
        ("payload", "expected_fragment"),
        [
            (
                {"heading": "   ", "content": "Hello."},
                r"title[\s\S]*non-empty string",
            ),
            (
                {"heading": "Intro", "content": "   "},
                r"content[\s\S]*non-empty string",
            ),
        ],
    )
    def test_section_rejects_blank_title_and_body(
        self,
        payload: dict[str, object],
        expected_fragment: str,
    ) -> None:
        with pytest.raises(ValidationError, match=expected_fragment):
            Section.model_validate(payload)

    @pytest.mark.parametrize(
        ("payload", "expected_fragment"),
        [
            (
                {"path": Path("fig.pdf"), "caption": "   ", "label": "velocity"},
                r"caption[\s\S]*non-empty string",
            ),
            (
                {"path": Path("fig.pdf"), "caption": "Cap", "label": "   "},
                r"label[\s\S]*non-empty string",
            ),
        ],
    )
    def test_figure_ref_rejects_blank_caption_and_label(
        self,
        payload: dict[str, object],
        expected_fragment: str,
    ) -> None:
        with pytest.raises(ValidationError, match=expected_fragment):
            FigureRef.model_validate(payload)

    @pytest.mark.parametrize(
        ("model_cls", "payload", "expected_fragment"),
        [
            (
                Section,
                {"heading": "Intro", "content": "Hello.", "label": "sec:intro"},
                r"label[\s\S]*omit the legacy 'sec:' prefix",
            ),
            (
                FigureRef,
                {"path": Path("fig.pdf"), "caption": "Cap", "label": "fig:velocity"},
                r"label[\s\S]*omit the legacy 'fig:' prefix",
            ),
        ],
    )
    def test_paper_models_reject_legacy_label_prefixes(
        self,
        model_cls: type[Section] | type[FigureRef],
        payload: dict[str, object],
        expected_fragment: str,
    ) -> None:
        with pytest.raises(ValidationError, match=expected_fragment):
            model_cls.model_validate(payload)

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
            sections=[Section(title="Introduction", content="Hello world.", label="introduction")],
        )
        tex = render_paper(config)
        assert r"\documentclass" in tex
        assert "revtex4-2" in tex
        assert r"\title{Test Paper}" in tex
        assert r"\author{Test Author}" in tex
        assert r"\begin{abstract}" in tex
        assert r"\section{Introduction}" in tex
        assert r"\label{sec:introduction}" in tex
        assert "sec:sec:introduction" not in tex
        assert REQUIRED_GPD_ACKNOWLEDGMENT in tex
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
        assert "fig:fig:velocity" not in tex

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

    def test_render_appends_required_acknowledgment_once(self):
        from gpd.mcp.paper.template_registry import render_paper

        config = PaperConfig(
            title="Custom Acknowledgments",
            authors=[Author(name="C")],
            abstract="Abstract.",
            sections=[Section(title="Intro", content="Main.")],
            acknowledgments="We thank our collaborators.",
        )

        tex = render_paper(config)
        assert "We thank our collaborators." in tex
        assert tex.count(REQUIRED_GPD_ACKNOWLEDGMENT) == 1

    def test_acknowledgment_normalizer_deduplicates_whitespace_variants(self):
        wrapped = (
            "We thank our collaborators.\n\n"
            "This research made use of Get Physics Done (GPD)\n"
            "and was supported in part by a GPD Research Grant from\n"
            "Physical Superintelligence PBC (PSI)."
        )

        config = PaperConfig(
            title="Wrapped Acknowledgments",
            authors=[Author(name="C")],
            abstract="Abstract.",
            sections=[Section(title="Intro", content="Main.")],
            acknowledgments=wrapped,
        )

        assert config.acknowledgments == wrapped.strip()

    def test_unknown_template_raises(self):
        from gpd.mcp.paper.template_registry import load_template

        with pytest.raises(FileNotFoundError):
            load_template("nonexistent")
