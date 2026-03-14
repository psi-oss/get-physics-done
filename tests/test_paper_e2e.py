"""End-to-end integration tests for the paper build utilities."""

from __future__ import annotations

import json

import pytest
from PIL import Image
from pybtex.database import BibliographyData, Entry

from gpd.mcp.paper.bibliography import CitationSource
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
        pdf_path = tmp_path / "main.pdf"
        mock_result = CompilationResult(success=True, pdf_path=pdf_path)
        # Write a fake PDF so the path exists
        pdf_path.write_bytes(b"%PDF-fake")

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
        assert output.pdf_path == pdf_path
        assert output.success is True
        assert output.manifest_path == tmp_path / "ARTIFACT-MANIFEST.json"
        assert output.manifest is not None
        manifest_content = json.loads(output.manifest_path.read_text(encoding="utf-8"))
        artifact_ids = {artifact["artifact_id"] for artifact in manifest_content["artifacts"]}
        assert "tex-paper" in artifact_ids
        assert "bib-references" in artifact_ids
        assert "pdf-main" in artifact_ids
        bib_artifact = next(artifact for artifact in manifest_content["artifacts"] if artifact["artifact_id"] == "bib-references")
        assert bib_artifact["metadata"]["entry_source"] == "bib_data"

    @pytest.mark.asyncio
    async def test_build_paper_merges_bib_data_and_citation_sources(self, tmp_path, monkeypatch):
        from gpd.mcp.paper.compiler import build_paper

        config = PaperConfig(
            title="Merged Bibliography Paper",
            authors=[Author(name="A. Einstein", affiliation="ETH Zurich")],
            abstract="A test abstract.",
            sections=[Section(title="Introduction", content="Hello world.")],
        )

        explicit_bib = BibliographyData()
        explicit_bib.entries["einstein1905"] = Entry(
            "article",
            [("author", "Einstein"), ("title", "Zur Elektrodynamik"), ("year", "1905")],
        )

        pdf_path = tmp_path / "main.pdf"
        mock_result = CompilationResult(success=True, pdf_path=pdf_path)
        pdf_path.write_bytes(b"%PDF-fake")

        async def mock_compile(tex_path, output_dir, compiler="pdflatex"):
            return mock_result

        monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", mock_compile)

        output = await build_paper(
            config,
            tmp_path,
            bib_data=explicit_bib,
            citation_sources=[
                CitationSource(
                    source_type="paper",
                    title="Relativity Follow-up",
                    authors=["N. Bohr"],
                    year="1913",
                    doi="10.1000/bohr1913",
                )
            ],
            enrich_bibliography=False,
        )

        bib_content = (tmp_path / "references.bib").read_text(encoding="utf-8")
        assert "einstein1905" in bib_content
        assert "bohr1913" in bib_content
        assert output.bibliography_audit is not None
        assert output.bibliography_audit.entries[0].key == "bohr1913"
        assert output.manifest is not None
        bib_artifact = next(artifact for artifact in output.manifest.artifacts if artifact.artifact_id == "bib-references")
        assert bib_artifact.metadata["entry_source"] == "bib_data+citation_sources"

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

        pdf_path = tmp_path / "main.pdf"
        mock_result = CompilationResult(success=True, pdf_path=pdf_path)
        pdf_path.write_bytes(b"%PDF-fake")

        async def mock_compile(tex_path, output_dir, compiler="pdflatex"):
            return mock_result

        monkeypatch.setattr("gpd.mcp.paper.compiler.check_class_file", lambda dc, install_hint=None: (True, "ok"))
        monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", mock_compile)

        output = await build_paper(config, tmp_path)

        prepared_path = tmp_path / "figures" / fig_path.name
        assert output.success is True
        assert output.figures_dir == tmp_path / "figures"
        assert prepared_path.exists()
        relative_fig = f"figures/{fig_path.name}"
        assert relative_fig in output.tex_content
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

        pdf_path = tmp_path / "main.pdf"
        mock_result = CompilationResult(success=True, pdf_path=pdf_path)
        pdf_path.write_bytes(b"%PDF-fake")

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
        bib_artifact = next(artifact for artifact in output.manifest.artifacts if artifact.artifact_id == "bib-references")
        assert bib_artifact.metadata["entry_source"] == "citation_sources"

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

    @pytest.mark.asyncio
    async def test_build_paper_fails_when_some_figures_cannot_be_prepared_but_keeps_valid_figures(
        self, tmp_path, monkeypatch
    ):
        from gpd.mcp.paper.compiler import build_paper

        good_figure = tmp_path / "good.png"
        Image.new("RGB", (200, 200), color="purple").save(good_figure)
        bad_figure = tmp_path / "bad.gif"
        bad_figure.write_bytes(b"GIF89a")

        config = PaperConfig(
            title="Mixed Figure Quality",
            authors=[Author(name="A. Einstein", affiliation="ETH Zurich")],
            abstract="A test abstract.",
            sections=[Section(title="Introduction", content="See Fig.~\\ref{fig:good}.")],
            figures=[
                FigureRef(path=good_figure, caption="Good figure.", label="good"),
                FigureRef(path=bad_figure, caption="Bad figure.", label="bad"),
            ],
        )

        pdf_path = tmp_path / "main.pdf"
        pdf_path.write_bytes(b"%PDF-fake")
        mock_result = CompilationResult(success=True, pdf_path=pdf_path)

        async def mock_compile(tex_path, output_dir, compiler="pdflatex"):
            return mock_result

        monkeypatch.setattr("gpd.mcp.paper.compiler.check_journal_dependencies", lambda spec: (True, []))
        monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", mock_compile)

        output = await build_paper(config, tmp_path)

        assert output.success is False
        assert output.pdf_path == pdf_path
        assert any("Figure preparation failed for" in error for error in output.errors)
        assert "figures/good.png" in output.tex_content
        assert "bad.gif" not in output.tex_content
        assert output.manifest is not None
        figure_artifacts = [artifact for artifact in output.manifest.artifacts if artifact.category == "figure"]
        assert len(figure_artifacts) == 1
        assert figure_artifacts[0].metadata["label"] == "good"
        assert figure_artifacts[0].sources[0].path == str(good_figure)


# ---- Public API surface test ----


class TestPublicAPI:
    def test_public_api_imports(self):
        from gpd.mcp.paper import (
            ArtifactManifest,
            Author,
            BibliographyAudit,
            CitationAuditRecord,
            CitationSource,
            ClaimIndex,
            ClaimRecord,
            ClaimType,
            FigureRef,
            PaperConfig,
            PaperOutput,
            ReviewConfidence,
            ReviewFinding,
            ReviewIssue,
            ReviewIssueSeverity,
            ReviewIssueStatus,
            ReviewLedger,
            ReviewPanelBundle,
            ReviewRecommendation,
            ReviewStageKind,
            ReviewSupportStatus,
            Section,
            StageReviewReport,
            build_bibliography,
            build_bibliography_with_audit,
            build_paper,
            compile_paper,
            get_journal_for_domain,
            get_journal_spec,
            list_journals,
            read_claim_index,
            read_review_ledger,
            read_review_panel_bundle,
            read_stage_review_report,
            write_bibliography_audit,
            write_claim_index,
            write_review_ledger,
            write_review_panel_bundle,
            write_stage_review_report,
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
        assert ClaimIndex is not None
        assert ClaimRecord is not None
        assert ClaimType is not None
        assert BibliographyAudit is not None
        assert CitationAuditRecord is not None
        assert FigureRef is not None
        assert PaperConfig is not None
        assert PaperOutput is not None
        assert ReviewConfidence is not None
        assert ReviewFinding is not None
        assert ReviewIssue is not None
        assert ReviewIssueSeverity is not None
        assert ReviewIssueStatus is not None
        assert ReviewLedger is not None
        assert ReviewPanelBundle is not None
        assert ReviewRecommendation is not None
        assert ReviewStageKind is not None
        assert ReviewSupportStatus is not None
        assert Section is not None
        assert StageReviewReport is not None
        assert CitationSource is not None
        assert callable(read_claim_index)
        assert callable(read_review_ledger)
        assert callable(read_review_panel_bundle)
        assert callable(read_stage_review_report)
        assert callable(write_claim_index)
        assert callable(write_review_ledger)
        assert callable(write_review_panel_bundle)
        assert callable(write_stage_review_report)

    def test_public_api_review_artifact_helpers_round_trip(self, tmp_path):
        from gpd.mcp.paper import (
            ClaimIndex,
            ClaimRecord,
            ClaimType,
            ReviewConfidence,
            ReviewFinding,
            ReviewIssue,
            ReviewIssueSeverity,
            ReviewLedger,
            ReviewPanelBundle,
            ReviewRecommendation,
            ReviewStageKind,
            ReviewSupportStatus,
            StageReviewReport,
            read_claim_index,
            read_review_ledger,
            read_review_panel_bundle,
            read_stage_review_report,
            write_claim_index,
            write_review_ledger,
            write_review_panel_bundle,
            write_stage_review_report,
        )

        claim_index = ClaimIndex(
            manuscript_path="paper/main.tex",
            manuscript_sha256="a" * 64,
            claims=[
                ClaimRecord(
                    claim_id="CLM-001",
                    claim_type=ClaimType.main_result,
                    text="A bounded result is established.",
                    artifact_path="paper/main.tex",
                    section="Results",
                )
            ],
        )
        stage_report = StageReviewReport(
            stage_id="physics",
            stage_kind=ReviewStageKind.physics,
            manuscript_path="paper/main.tex",
            manuscript_sha256="a" * 64,
            claims_reviewed=["CLM-001"],
            summary="Physics support is adequate.",
            findings=[
                ReviewFinding(
                    issue_id="REF-001",
                    claim_ids=["CLM-001"],
                    severity=ReviewIssueSeverity.minor,
                    summary="Clarify the regime of validity.",
                    support_status=ReviewSupportStatus.partially_supported,
                    required_action="Add one sentence narrowing the claim.",
                )
            ],
            confidence=ReviewConfidence.medium,
            recommendation_ceiling=ReviewRecommendation.minor_revision,
        )
        ledger = ReviewLedger(
            manuscript_path="paper/main.tex",
            issues=[
                ReviewIssue(
                    issue_id="REF-001",
                    opened_by_stage=ReviewStageKind.physics,
                    severity=ReviewIssueSeverity.minor,
                    claim_ids=["CLM-001"],
                    summary="Clarify the regime of validity.",
                    required_action="Add one sentence narrowing the claim.",
                )
            ],
        )
        bundle = ReviewPanelBundle(
            manuscript_path="paper/main.tex",
            claim_index_path=".gpd/review/CLAIMS.json",
            stage_reports=[".gpd/review/STAGE-physics.json"],
            review_ledger_path=".gpd/review/REVIEW-LEDGER.json",
            decision_path=".gpd/review/REFEREE-DECISION.json",
            final_recommendation=ReviewRecommendation.minor_revision,
            final_confidence=ReviewConfidence.medium,
            final_report_path=".gpd/REFEREE-REPORT.md",
            final_report_tex_path=".gpd/REFEREE-REPORT.tex",
        )

        claims_path = tmp_path / "CLAIMS.json"
        stage_path = tmp_path / "STAGE-physics.json"
        ledger_path = tmp_path / "REVIEW-LEDGER.json"
        bundle_path = tmp_path / "PANEL-BUNDLE.json"

        write_claim_index(claim_index, claims_path)
        write_stage_review_report(stage_report, stage_path)
        write_review_ledger(ledger, ledger_path)
        write_review_panel_bundle(bundle, bundle_path)

        assert read_claim_index(claims_path) == claim_index
        assert read_stage_review_report(stage_path) == stage_report
        assert read_review_ledger(ledger_path) == ledger
        assert read_review_panel_bundle(bundle_path) == bundle


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
        assert "pdf-main" not in artifact_ids

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
