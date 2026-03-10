"""End-to-end integration tests for the paper build utilities."""

from __future__ import annotations

import json

import pytest
from PIL import Image
from pybtex.database import BibliographyData, Entry

from gpd.mcp.paper.compiler import CompilationResult, _get_tlmgr_package, check_class_file
from gpd.mcp.paper.bibliography import CitationSource
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

        assert (tmp_path / "main.tex").exists()
        tex_content = (tmp_path / "main.tex").read_text()
        assert r"\documentclass" in tex_content
        assert "Generated with Get Physics Done" in tex_content
        assert (tmp_path / "references.bib").exists()
        bib_content = (tmp_path / "references.bib").read_text()
        assert len(bib_content) > 0
        assert output.tex_content != ""
        assert output.success is True
        assert output.manifest_path == tmp_path / "ARTIFACT-MANIFEST.json"
        assert output.manifest is not None
        manifest_content = json.loads(output.manifest_path.read_text(encoding="utf-8"))
        artifact_ids = {artifact["artifact_id"] for artifact in manifest_content["artifacts"]}
        assert "tex-paper" in artifact_ids
        assert "bib-references" in artifact_ids
        assert "pdf-paper" in artifact_ids

    @pytest.mark.asyncio
    async def test_build_paper_prepares_config_figures(self, tmp_path, monkeypatch):
        from gpd.mcp.paper.compiler import build_paper

        fig_path = tmp_path / "velocity.png"
        Image.new("RGB", (200, 200), color="blue").save(fig_path)

        config = PaperConfig(
            title="Figure Paper",
            authors=[Author(name="A. Einstein", affiliation="ETH Zurich")],
            abstract="A test abstract.",
            sections=[Section(title="Introduction", content="See Fig.~\\ref{fig:velocity}.")],
            figures=[FigureRef(path=fig_path, caption="Velocity field.", label="velocity")],
        )

        mock_result = CompilationResult(success=True, pdf_path=tmp_path / "paper.pdf")
        (tmp_path / "paper.pdf").write_bytes(b"%PDF-fake")

        async def mock_compile(tex_path, output_dir, compiler="pdflatex"):
            return mock_result

        monkeypatch.setattr("gpd.mcp.paper.compiler.check_class_file", lambda dc, install_hint=None: (True, "ok"))
        monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", mock_compile)

        output = await build_paper(config, tmp_path)

        prepared_path = tmp_path / "figures" / fig_path.name
        assert output.success is True
        assert output.figures_dir == tmp_path / "figures"
        assert prepared_path.exists()
        assert str(prepared_path) in output.tex_content
        assert output.manifest is not None
        figure_artifact = next(artifact for artifact in output.manifest.artifacts if artifact.category == "figure")
        assert figure_artifact.path == "figures/velocity.png"
        assert figure_artifact.sources[0].path == str(fig_path)
        assert figure_artifact.metadata["label"] == "velocity"

    @pytest.mark.asyncio
    async def test_build_paper_writes_bibliography_audit_from_sources(self, tmp_path, monkeypatch):
        from gpd.mcp.paper.compiler import build_paper

        config = PaperConfig(
            title="Audit Paper",
            authors=[Author(name="A. Einstein", affiliation="ETH Zurich")],
            abstract="A test abstract.",
            sections=[Section(title="Introduction", content="Hello world.")],
        )

        mock_result = CompilationResult(success=True, pdf_path=tmp_path / "paper.pdf")
        (tmp_path / "paper.pdf").write_bytes(b"%PDF-fake")

        async def mock_compile(tex_path, output_dir, compiler="pdflatex"):
            return mock_result

        monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", mock_compile)

        output = await build_paper(
            config,
            tmp_path,
            citation_sources=[
                CitationSource(
                    source_type="paper",
                    title="Relativity",
                    authors=["A. Einstein"],
                    year="1905",
                    doi="10.1002/andp.19053221004",
                )
            ],
            enrich_bibliography=False,
        )

        assert output.success is True
        assert output.bibliography_audit_path == tmp_path / "BIBLIOGRAPHY-AUDIT.json"
        assert output.bibliography_audit is not None
        assert output.bibliography_audit.total_sources == 1
        manifest_ids = {artifact.artifact_id for artifact in output.manifest.artifacts}
        assert "audit-bibliography" in manifest_ids

    @pytest.mark.asyncio
    async def test_build_paper_manifest_keeps_figure_source_alignment_when_some_figures_are_skipped(
        self, tmp_path, monkeypatch
    ):
        from gpd.mcp.paper.compiler import build_paper

        existing_figure = tmp_path / "existing.png"
        Image.new("RGB", (200, 200), color="green").save(existing_figure)

        config = PaperConfig(
            title="Figure Alignment",
            authors=[Author(name="A. Einstein", affiliation="ETH Zurich")],
            abstract="A test abstract.",
            sections=[Section(title="Introduction", content="See Fig.~\\ref{fig:existing}.")],
            figures=[
                FigureRef(path=tmp_path / "missing.png", caption="Missing figure.", label="missing"),
                FigureRef(path=existing_figure, caption="Existing figure.", label="existing"),
            ],
        )

        monkeypatch.setattr(
            "gpd.mcp.paper.compiler.check_journal_dependencies",
            lambda spec: (False, ["missing TeX dependency"]),
        )

        output = await build_paper(config, tmp_path / "output")

        assert output.success is False
        assert any(error.startswith("Figure not found:") for error in output.errors)
        assert output.manifest is not None

        figure_artifact = next(artifact for artifact in output.manifest.artifacts if artifact.category == "figure")
        assert figure_artifact.metadata["label"] == "existing"
        assert figure_artifact.sources[0].path == str(existing_figure)


# ---- Public API surface test ----


class TestPublicAPI:
    def test_public_api_imports(self):
        from gpd.mcp.paper import (
            ArtifactManifest,
            Author,
            BibliographyAudit,
            CitationAuditRecord,
            CitationSource,
            FigureRef,
            PaperConfig,
            PaperOutput,
            Section,
            build_bibliography,
            build_bibliography_with_audit,
            build_paper,
            compile_paper,
            get_journal_for_domain,
            get_journal_spec,
            list_journals,
            write_bibliography_audit,
        )

        assert callable(build_paper)
        assert callable(compile_paper)
        assert callable(build_bibliography)
        assert callable(build_bibliography_with_audit)
        assert callable(get_journal_for_domain)
        assert callable(get_journal_spec)
        assert callable(list_journals)
        assert callable(write_bibliography_audit)
        assert ArtifactManifest is not None
        assert Author is not None
        assert BibliographyAudit is not None
        assert CitationAuditRecord is not None
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
            lambda dc, install_hint=None: (False, f"{dc}.cls not found. Install via: tlmgr install revtex"),
        )

        output = await build_paper(config, tmp_path)
        assert output.success is False
        assert len(output.errors) > 0
        assert "not found" in output.errors[0]
        assert output.manifest_path == tmp_path / "ARTIFACT-MANIFEST.json"
        assert output.manifest is not None
        manifest_content = json.loads(output.manifest_path.read_text(encoding="utf-8"))
        artifact_ids = {artifact["artifact_id"] for artifact in manifest_content["artifacts"]}
        assert "tex-paper" in artifact_ids
        assert "pdf-paper" not in artifact_ids

    @pytest.mark.asyncio
    async def test_build_paper_missing_jhep_support_file(self, tmp_path, monkeypatch):
        from gpd.mcp.paper.compiler import build_paper

        config = PaperConfig(
            title="Test",
            authors=[Author(name="A")],
            abstract="Abstract.",
            sections=[Section(title="Intro", content="Hello.")],
            journal="jhep",
        )

        monkeypatch.setattr("gpd.mcp.paper.compiler.check_class_file", lambda dc, install_hint=None: (True, "ok"))
        monkeypatch.setattr(
            "gpd.mcp.paper.compiler.check_tex_file",
            lambda resource_name, install_hint=None: (
                (False, "jheppub.sty not found. Install via: tlmgr install jhep")
                if resource_name == "jheppub.sty"
                else (True, "ok")
            ),
        )

        output = await build_paper(config, tmp_path)
        assert output.success is False
        assert len(output.errors) > 0
        assert "jheppub.sty not found" in output.errors[0]
        assert output.manifest_path == tmp_path / "ARTIFACT-MANIFEST.json"
        assert output.manifest is not None
