"""End-to-end integration tests for the paper pipeline."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from PIL import Image
from pybtex.database import BibliographyData, Entry

from gpd.mcp.paper.compiler import CompilationResult, _get_tlmgr_package, check_class_file
from gpd.mcp.paper.models import Author, FigureRef, PaperConfig, Section

# ---- Compiler wrapper tests ----


class TestCompilerWrapper:
    def test_check_class_file_article(self):
        available, msg = check_class_file("article")
        # On systems with TeX: (True, path). Without kpsewhich: (True, "assuming...")
        assert available is True

    def test_check_class_file_nonexistent(self):
        available, msg = check_class_file("nonexistent_class_xyz_99999")
        if not available:
            assert "not found" in msg
            assert "tlmgr install" in msg
        # If kpsewhich not available, available will be True

    def test_get_tlmgr_package_mapping(self):
        assert _get_tlmgr_package("revtex4-2") == "revtex"
        assert _get_tlmgr_package("aastex631") == "aastex"
        assert _get_tlmgr_package("mnras") == "mnras"
        assert _get_tlmgr_package("article") == "latex-base"


# ---- build_paper integration test ----


class TestBuildPaper:
    @pytest.mark.asyncio
    async def test_build_paper_renders_tex(self, tmp_path, monkeypatch):
        from gpd.mcp.paper.compiler import build_paper

        config = PaperConfig(
            title="Test Paper",
            authors=[Author(name="A. Einstein", affiliation="ETH Zurich")],
            abstract="A test abstract.",
            sections=[Section(title="Introduction", content="Hello world.")],
        )

        # Create a simple bib entry
        bib = BibliographyData()
        bib.entries["einstein1905"] = Entry("article", [("author", "Einstein"), ("title", "SR"), ("year", "1905")])

        # Mock compile_paper to avoid needing actual TeX
        mock_result = CompilationResult(success=True, pdf_path=tmp_path / "paper.pdf")
        # Write a fake PDF so the path exists
        (tmp_path / "paper.pdf").write_bytes(b"%PDF-fake")

        async def mock_compile(tex_path, output_dir, compiler="pdflatex"):
            return mock_result

        monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", mock_compile)

        output = await build_paper(config, tmp_path, bib_data=bib)

        assert (tmp_path / "paper.tex").exists()
        tex_content = (tmp_path / "paper.tex").read_text()
        assert r"\documentclass" in tex_content
        assert (tmp_path / "references.bib").exists()
        bib_content = (tmp_path / "references.bib").read_text()
        assert len(bib_content) > 0
        assert output.tex_content != ""
        assert output.success is True


# ---- Full pipeline smoke test ----


class TestFullPipeline:
    @pytest.mark.asyncio
    async def test_full_pipeline_smoke(self, tmp_path, monkeypatch):
        import gpd.mcp.paper.generator as gen_mod
        from gpd.mcp.paper.compiler import build_paper
        from gpd.mcp.paper.generator import (
            FigureCaption,
            SectionContent,
            SectionPlan,
            generate_paper,
        )

        # Mock PydanticAI agents via the lazy getter functions
        plan = SectionPlan(sections=[{"title": "Results", "key_points": ["Data"]}])
        mock_plan_result = MagicMock()
        mock_plan_result.output = plan
        mock_planner = MagicMock()
        mock_planner.run = AsyncMock(return_value=mock_plan_result)
        monkeypatch.setattr(gen_mod, "_get_section_planner", lambda: mock_planner)

        mock_sec_result = MagicMock()
        mock_sec_result.output = SectionContent(content="Results content.")
        mock_writer = MagicMock()
        mock_writer.run = AsyncMock(return_value=mock_sec_result)
        monkeypatch.setattr(gen_mod, "_get_section_writer", lambda: mock_writer)

        mock_cap_result = MagicMock()
        mock_cap_result.output = FigureCaption(caption="Generated caption.")
        mock_captioner = MagicMock()
        mock_captioner.run = AsyncMock(return_value=mock_cap_result)
        monkeypatch.setattr(gen_mod, "_get_caption_writer", lambda: mock_captioner)

        # Create a real PNG figure
        fig_dir = tmp_path / "figs"
        fig_dir.mkdir()
        fig_path = fig_dir / "velocity.png"
        Image.new("RGB", (200, 200), color="blue").save(fig_path)

        # Generate paper config via mocked LLM
        from gpd.mcp.paper.bibliography import CitationSource

        config = await generate_paper(
            research_summary="Turbulence study results.",
            title="Turbulence",
            authors=[Author(name="A")],
            abstract="Abstract.",
            figures=[FigureRef(path=fig_path, caption="hint", label="velocity")],
            citations=[CitationSource(source_type="paper", title="Ref1", authors=["B"], year="2020")],
        )

        # Mock compile to avoid needing TeX
        mock_compile_result = CompilationResult(success=True, pdf_path=tmp_path / "paper.pdf")
        (tmp_path / "paper.pdf").write_bytes(b"%PDF-fake")

        async def mock_compile(tex_path, output_dir, compiler="pdflatex"):
            return mock_compile_result

        monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", mock_compile)

        from gpd.mcp.paper.bibliography import build_bibliography

        bib = build_bibliography(
            [CitationSource(source_type="paper", title="Ref1", authors=["B"], year="2020")],
            enrich=False,
        )

        output = await build_paper(config, tmp_path, bib_data=bib, figures=config.figures)
        assert output.success is True
        assert output.tex_content != ""


# ---- Public API surface test ----


class TestPublicAPI:
    def test_public_api_imports(self):
        from gpd.mcp.paper import (
            Author,
            CitationSource,
            FigureRef,
            PaperConfig,
            PaperOutput,
            Section,
            build_bibliography,
            build_paper,
            compile_paper,
            generate_paper,
            get_journal_for_domain,
            get_journal_spec,
            list_journals,
        )

        assert callable(generate_paper)
        assert callable(build_paper)
        assert callable(compile_paper)
        assert callable(build_bibliography)
        assert callable(get_journal_for_domain)
        assert callable(get_journal_spec)
        assert callable(list_journals)
        assert Author is not None
        assert FigureRef is not None
        assert PaperConfig is not None
        assert PaperOutput is not None
        assert Section is not None
        assert CitationSource is not None


# ---- Class file check fallback ----


class TestClassFileFallback:
    @pytest.mark.asyncio
    async def test_build_paper_missing_class_file(self, tmp_path, monkeypatch):
        from gpd.mcp.paper.compiler import build_paper

        config = PaperConfig(
            title="Test",
            authors=[Author(name="A")],
            abstract="Abstract.",
            sections=[Section(title="Intro", content="Hello.")],
        )

        monkeypatch.setattr(
            "gpd.mcp.paper.compiler.check_class_file",
            lambda dc: (False, f"{dc}.cls not found. Install via: tlmgr install revtex"),
        )

        output = await build_paper(config, tmp_path)
        assert output.success is False
        assert len(output.errors) > 0
        assert "not found" in output.errors[0]
