"""End-to-end integration tests for the paper build utilities."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from PIL import Image
from pybtex.database import BibliographyData, Entry
from pydantic import ConfigDict

from gpd.mcp.paper.bibliography import CitationSource
from gpd.mcp.paper.compiler import (
    CompilationResult,
    _get_tlmgr_package,
    check_class_file,
    check_journal_dependencies,
)
from gpd.mcp.paper.journal_map import get_journal_spec
from gpd.mcp.paper.models import (
    REQUIRED_GPD_ACKNOWLEDGMENT,
    Author,
    FigureRef,
    PaperConfig,
    Section,
    derive_output_filename,
)


def _allow_journal_dependencies(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep happy-path build tests focused on build orchestration, not TeX setup."""
    monkeypatch.setattr("gpd.mcp.paper.compiler.check_journal_dependencies", lambda spec: (True, []))


class CitationSourceWithReferenceId(CitationSource):
    """Test helper that carries a stable project reference ID through the pipeline."""

    model_config = ConfigDict(extra="allow")
    reference_id: str | None = None


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

    def test_check_class_file_uses_resolved_kpsewhich_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        observed_commands: list[list[str]] = []

        monkeypatch.setattr(
            "gpd.mcp.paper.compiler.find_latex_compiler",
            lambda binary: "/opt/tex/bin/kpsewhich" if binary == "kpsewhich" else None,
        )

        def fake_run(command: list[str], capture_output: bool, text: bool, timeout: int) -> SimpleNamespace:
            observed_commands.append(command)
            return SimpleNamespace(returncode=0, stdout="/opt/tex/texmf-dist/tex/latex/base/article.cls\n")

        monkeypatch.setattr("gpd.mcp.paper.compiler.subprocess.run", fake_run)

        available, msg = check_class_file("article")

        assert available is True
        assert msg.endswith("article.cls")
        assert observed_commands == [["/opt/tex/bin/kpsewhich", "article.cls"]]

    def test_check_journal_dependencies_keep_best_effort_when_kpsewhich_is_unavailable(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(
            "gpd.mcp.paper.compiler.find_latex_compiler",
            lambda binary: None if binary == "kpsewhich" else f"/usr/bin/{binary}",
        )

        available, errors = check_journal_dependencies(get_journal_spec("jhep"))

        assert available is True
        assert errors == []


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
        output_stem = derive_output_filename(config)
        pdf_path = tmp_path / f"{output_stem}.pdf"
        mock_result = CompilationResult(success=True, pdf_path=pdf_path)
        # Write a fake PDF so the path exists
        pdf_path.write_bytes(b"%PDF-fake")

        async def mock_compile(tex_path, output_dir, compiler="pdflatex"):
            return mock_result

        _allow_journal_dependencies(monkeypatch)
        monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", mock_compile)

        output = await build_paper(config, tmp_path, bib_data=bib)

        assert output.tex_path == tmp_path / f"{output_stem}.tex"
        assert output.tex_path.exists()
        tex_content = output.tex_path.read_text()
        assert r"\documentclass" in tex_content
        assert REQUIRED_GPD_ACKNOWLEDGMENT in tex_content
        assert "Generated with Get Physics Done" in tex_content
        assert (tmp_path / "references.bib").exists()
        bib_content = (tmp_path / "references.bib").read_text()
        assert len(bib_content) > 0
        assert output.tex_content != ""
        assert output.pdf_path == pdf_path
        assert output.success is True
        assert output.bibliography_audit_path == tmp_path / "BIBLIOGRAPHY-AUDIT.json"
        assert output.bibliography_audit is not None
        assert output.bibliography_audit.total_sources == 1
        assert output.reference_bibtex_keys == {}
        assert output.manifest_path == tmp_path / "ARTIFACT-MANIFEST.json"
        assert output.manifest is not None
        manifest_content = json.loads(output.manifest_path.read_text(encoding="utf-8"))
        artifact_ids = {artifact["artifact_id"] for artifact in manifest_content["artifacts"]}
        assert "tex-paper" in artifact_ids
        assert "bib-references" in artifact_ids
        assert f"pdf-{output_stem}" in artifact_ids
        assert "audit-bibliography" in artifact_ids
        bib_artifact = next(artifact for artifact in manifest_content["artifacts"] if artifact["artifact_id"] == "bib-references")
        assert bib_artifact["metadata"]["entry_source"] == "bib_data"
        audit_artifact = next(artifact for artifact in manifest_content["artifacts"] if artifact["artifact_id"] == "audit-bibliography")
        assert audit_artifact["path"] == "BIBLIOGRAPHY-AUDIT.json"

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

        pdf_path = tmp_path / f"{derive_output_filename(config)}.pdf"
        mock_result = CompilationResult(success=True, pdf_path=pdf_path)
        pdf_path.write_bytes(b"%PDF-fake")

        async def mock_compile(tex_path, output_dir, compiler="pdflatex"):
            return mock_result

        _allow_journal_dependencies(monkeypatch)
        monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", mock_compile)

        output = await build_paper(
            config,
            tmp_path,
            bib_data=explicit_bib,
            citation_sources=[
                CitationSourceWithReferenceId(
                    source_type="paper",
                    title="Relativity Follow-up",
                    authors=["N. Bohr"],
                    year="1913",
                    doi="10.1000/bohr1913",
                    reference_id="lit-ref-bohr-1913",
                )
            ],
            enrich_bibliography=False,
        )

        bib_content = (tmp_path / "references.bib").read_text(encoding="utf-8")
        assert "einstein1905" in bib_content
        assert "bohr1913" in bib_content
        assert output.success is True
        assert output.pdf_path == pdf_path
        assert output.bibliography_audit_path == tmp_path / "BIBLIOGRAPHY-AUDIT.json"
        assert output.bibliography_audit is not None
        assert output.bibliography_audit.total_sources == 2
        assert {entry.key for entry in output.bibliography_audit.entries} == {"einstein1905", "bohr1913"}
        assert output.reference_bibtex_keys == {"lit-ref-bohr-1913": "bohr1913"}
        assert output.manifest is not None
        bib_artifact = next(artifact for artifact in output.manifest.artifacts if artifact.artifact_id == "bib-references")
        assert bib_artifact.metadata["entry_source"] == "bib_data+citation_sources"
        audit_artifact = next(artifact for artifact in output.manifest.artifacts if artifact.artifact_id == "audit-bibliography")
        assert audit_artifact.path == "BIBLIOGRAPHY-AUDIT.json"

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

        pdf_path = tmp_path / f"{derive_output_filename(config)}.pdf"
        mock_result = CompilationResult(success=True, pdf_path=pdf_path)
        pdf_path.write_bytes(b"%PDF-fake")

        async def mock_compile(tex_path, output_dir, compiler="pdflatex"):
            return mock_result

        _allow_journal_dependencies(monkeypatch)
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

        pdf_path = tmp_path / f"{derive_output_filename(config)}.pdf"
        mock_result = CompilationResult(success=True, pdf_path=pdf_path)
        pdf_path.write_bytes(b"%PDF-fake")

        async def mock_compile(tex_path, output_dir, compiler="pdflatex"):
            return mock_result

        _allow_journal_dependencies(monkeypatch)
        monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", mock_compile)

        output = await build_paper(
            config,
            tmp_path,
            citation_sources=[
                CitationSourceWithReferenceId(
                    source_type="paper",
                    title="Relativity",
                    authors=["A. Einstein"],
                    year="1905",
                    doi="10.1002/andp.19053221004",
                    reference_id="lit-ref-einstein-1905",
                )
            ],
            enrich_bibliography=False,
        )

        assert output.success is True
        assert output.bibliography_audit_path == tmp_path / "BIBLIOGRAPHY-AUDIT.json"
        assert output.bibliography_audit is not None
        assert output.bibliography_audit.total_sources == 1
        assert (tmp_path / "BIBLIOGRAPHY-AUDIT.json").exists()
        assert output.reference_bibtex_keys == {"lit-ref-einstein-1905": "einstein1905"}
        manifest_ids = {artifact.artifact_id for artifact in output.manifest.artifacts}
        assert "audit-bibliography" in manifest_ids
        bib_artifact = next(artifact for artifact in output.manifest.artifacts if artifact.artifact_id == "bib-references")
        assert bib_artifact.metadata["entry_source"] == "citation_sources"

    @pytest.mark.asyncio
    async def test_build_paper_surfaces_preferred_bibtex_key_mapping(self, tmp_path, monkeypatch):
        from gpd.mcp.paper import bibliography as paper_bibliography
        from gpd.mcp.paper.compiler import build_paper

        config = PaperConfig(
            title="Preferred Key Paper",
            authors=[Author(name="A. Einstein", affiliation="ETH Zurich")],
            abstract="A test abstract.",
            sections=[Section(title="Introduction", content="Hello world.")],
        )

        source = CitationSourceWithReferenceId(
            source_type="paper",
            title="Relativity",
            authors=["A. Einstein"],
            year="1905",
            doi="10.1002/andp.19053221004",
            reference_id="lit-ref-einstein-1905",
        )

        pdf_path = tmp_path / f"{derive_output_filename(config)}.pdf"
        mock_result = CompilationResult(success=True, pdf_path=pdf_path)
        pdf_path.write_bytes(b"%PDF-fake")

        async def mock_compile(tex_path, output_dir, compiler="pdflatex"):
            return mock_result

        real_create_bib_key = paper_bibliography._create_bib_key

        def mock_create_bib_key(source, existing_keys):
            if source.title == "Relativity":
                return "preferred1905"
            return real_create_bib_key(source, existing_keys)

        _allow_journal_dependencies(monkeypatch)
        monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", mock_compile)
        monkeypatch.setattr("gpd.mcp.paper.bibliography._create_bib_key", mock_create_bib_key)

        output = await build_paper(
            config,
            tmp_path,
            citation_sources=[source],
            enrich_bibliography=False,
        )

        assert output.success is True
        assert output.bibliography_audit is not None
        assert output.bibliography_audit.entries[0].key == "preferred1905"
        assert output.reference_bibtex_keys == {"lit-ref-einstein-1905": "preferred1905"}
        bib_content = (tmp_path / "references.bib").read_text(encoding="utf-8")
        assert "@article{preferred1905" in bib_content

    @pytest.mark.asyncio
    async def test_build_paper_preserves_stable_reference_ids_in_bibliography_hook(
        self, tmp_path, monkeypatch
    ):
        from gpd.mcp.paper import compiler as paper_compiler
        from gpd.mcp.paper.compiler import build_paper

        config = PaperConfig(
            title="Reference ID Paper",
            authors=[Author(name="A. Einstein", affiliation="ETH Zurich")],
            abstract="A test abstract.",
            sections=[Section(title="Introduction", content="Hello world.")],
        )

        source = CitationSourceWithReferenceId(
            source_type="paper",
            title="Relativity",
            authors=["A. Einstein"],
            year="1905",
            doi="10.1002/andp.19053221004",
            reference_id="lit-ref-einstein-1905",
        )

        pdf_path = tmp_path / f"{derive_output_filename(config)}.pdf"
        mock_result = CompilationResult(success=True, pdf_path=pdf_path)
        pdf_path.write_bytes(b"%PDF-fake")

        async def mock_compile(tex_path, output_dir, compiler="pdflatex"):
            return mock_result

        observed_reference_ids: list[str | None] = []
        real_build_bibliography_with_audit = paper_compiler.build_bibliography_with_audit

        def spy_build_bibliography_with_audit(sources, enrich, reserved_bib_keys=None):
            observed_reference_ids.extend(getattr(item, "reference_id", None) for item in sources)
            return real_build_bibliography_with_audit(sources, enrich, reserved_bib_keys)

        _allow_journal_dependencies(monkeypatch)
        monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", mock_compile)
        monkeypatch.setattr("gpd.mcp.paper.compiler.build_bibliography_with_audit", spy_build_bibliography_with_audit)

        output = await build_paper(
            config,
            tmp_path,
            citation_sources=[source],
            enrich_bibliography=False,
        )

        assert output.success is True
        assert observed_reference_ids == ["lit-ref-einstein-1905"]
        assert output.bibliography_audit is not None
        assert output.bibliography_audit.entries[0].key == "einstein1905"
        assert output.reference_bibtex_keys == {"lit-ref-einstein-1905": "einstein1905"}
        assert "einstein1905" in (tmp_path / "references.bib").read_text(encoding="utf-8")

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

        pdf_path = tmp_path / f"{derive_output_filename(config)}.pdf"
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
            read_stage_review_report,
            write_bibliography_audit,
            write_claim_index,
            write_review_ledger,
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
        assert ReviewRecommendation is not None
        assert ReviewStageKind is not None
        assert ReviewSupportStatus is not None
        assert Section is not None
        assert StageReviewReport is not None
        assert CitationSource is not None
        assert callable(read_claim_index)
        assert callable(read_review_ledger)
        assert callable(read_stage_review_report)
        assert callable(write_claim_index)
        assert callable(write_review_ledger)
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
            ReviewRecommendation,
            ReviewStageKind,
            ReviewSupportStatus,
            StageReviewReport,
            read_claim_index,
            read_review_ledger,
            read_stage_review_report,
            write_claim_index,
            write_review_ledger,
            write_stage_review_report,
        )

        claim_index = ClaimIndex(
            manuscript_path="paper/curvature_flow_bounds.tex",
            manuscript_sha256="a" * 64,
            claims=[
                ClaimRecord(
                    claim_id="CLM-001",
                    claim_type=ClaimType.main_result,
                    text="A bounded result is established.",
                    artifact_path="paper/curvature_flow_bounds.tex",
                    section="Results",
                )
            ],
        )
        stage_report = StageReviewReport(
            stage_id="physics",
            stage_kind=ReviewStageKind.physics,
            manuscript_path="paper/curvature_flow_bounds.tex",
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
            manuscript_path="paper/curvature_flow_bounds.tex",
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

        claims_path = tmp_path / "CLAIMS.json"
        stage_path = tmp_path / "STAGE-physics.json"
        ledger_path = tmp_path / "REVIEW-LEDGER.json"

        write_claim_index(claim_index, claims_path)
        write_stage_review_report(stage_report, stage_path)
        write_review_ledger(ledger, ledger_path)

        assert read_claim_index(claims_path) == claim_index
        assert read_stage_review_report(stage_path) == stage_report
        assert read_review_ledger(ledger_path) == ledger


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
            lambda dc, install_hint=None, assume_present_when_unavailable=True: (
                False,
                f"{dc}.cls not found. Install via: tlmgr install revtex",
            ),
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

        monkeypatch.setattr(
            "gpd.mcp.paper.compiler.check_class_file",
            lambda dc, install_hint=None, assume_present_when_unavailable=True: (True, "ok"),
        )
        monkeypatch.setattr(
            "gpd.mcp.paper.compiler.check_tex_file",
            lambda resource_name, install_hint=None, assume_present_when_unavailable=True: (
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

    @pytest.mark.asyncio
    async def test_build_paper_warns_on_zero_citations(self, tmp_path, monkeypatch):
        """BUG-076: build_paper warns when bib has entries but tex has no citations."""
        from gpd.mcp.paper.compiler import build_paper

        config = PaperConfig(
            title="Test Paper",
            authors=[Author(name="Test Author")],
            abstract="Abstract text.",
            sections=[Section(title="Introduction", content="No citations here.")],
        )
        bib = BibliographyData()
        bib.entries["ref2020"] = Entry(
            "article", [("title", "Ref"), ("author", "Doe"), ("year", "2020")]
        )

        output_stem = derive_output_filename(config)
        pdf_path = tmp_path / f"{output_stem}.pdf"
        mock_result = CompilationResult(success=True, pdf_path=pdf_path)
        pdf_path.write_bytes(b"%PDF-fake")

        async def mock_compile(tex_path, output_dir, compiler="pdflatex"):
            return mock_result

        _allow_journal_dependencies(monkeypatch)
        monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", mock_compile)

        output = await build_paper(config, tmp_path, bib_data=bib)

        assert output.citation_warnings
        assert any("zero" in w.lower() for w in output.citation_warnings)
