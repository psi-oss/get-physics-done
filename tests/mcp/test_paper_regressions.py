"""Behavior-focused paper regression coverage."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
from pydantic import ValidationError


def test_prl_and_apj_skip_empty_affiliations() -> None:
    from gpd.mcp.paper.models import Author, PaperConfig, Section
    from gpd.mcp.paper.template_registry import render_paper

    prl = PaperConfig(
        title="Test Paper",
        authors=[Author(name="John Doe", email="john@example.com", affiliation="")],
        abstract="Test abstract.",
        sections=[Section(title="Introduction", content="Hello.")],
        journal="prl",
    )
    apj = PaperConfig(
        title="Test Paper",
        authors=[Author(name="Jane Doe", affiliation="")],
        abstract="Abstract.",
        sections=[Section(title="Intro", content="Content.")],
        journal="apj",
    )

    assert "\\affiliation{}" not in render_paper(prl)
    assert "\\affiliation{}" not in render_paper(apj)


def test_mnras_running_header_uses_author_names() -> None:
    from gpd.mcp.paper.models import Author, PaperConfig, Section
    from gpd.mcp.paper.template_registry import render_paper

    config = PaperConfig(
        title="Test Paper",
        authors=[
            Author(name="Alice Smith", affiliation="MIT"),
            Author(name="Bob Jones", affiliation="Stanford"),
            Author(name="Carol White", affiliation="Caltech"),
        ],
        abstract="Test abstract.",
        sections=[Section(title="Introduction", content="Hello.")],
        journal="mnras",
    )

    tex = render_paper(config)
    match = re.search(r"\\author\[([^\]]*)\]", tex)

    assert match is not None
    assert "Alice Smith, Bob Jones, Carol White" in match.group(1)


def test_templates_handle_empty_authors_without_dangling_breaks() -> None:
    from gpd.mcp.paper.models import PaperConfig, Section
    from gpd.mcp.paper.template_registry import render_paper

    mnras = PaperConfig(
        title="Test Paper",
        authors=[],
        abstract="Abstract.",
        sections=[Section(title="Intro", content="Content.")],
        journal="mnras",
    )
    nature = PaperConfig(
        title="Test Paper",
        authors=[],
        abstract="Abstract.",
        sections=[Section(title="Intro", content="Content.")],
        journal="nature",
    )

    mnras_tex = render_paper(mnras)
    mnras_match = re.search(r"\\author\[]\{(.*?)\}", mnras_tex, re.DOTALL)
    assert mnras_match is not None
    assert "\\\\" not in mnras_match.group(1).strip()

    nature_tex = render_paper(nature)
    nature_match = re.search(r"\\author\{(.*?)\}", nature_tex, re.DOTALL)
    assert nature_match is not None
    assert "\\\\[6pt]" not in nature_match.group(1).strip()


def test_render_paper_injects_required_acknowledgment_even_if_validation_was_bypassed() -> None:
    from gpd.mcp.paper.models import REQUIRED_GPD_ACKNOWLEDGMENT, Author, PaperConfig, Section
    from gpd.mcp.paper.template_registry import render_paper

    config = PaperConfig.model_construct(
        title="Constructed Paper",
        authors=[Author(name="Jane Doe")],
        abstract="Abstract.",
        sections=[Section(title="Intro", content="Content.")],
        figures=[],
        acknowledgments="",
        bib_file="references",
        journal="prl",
        appendix_sections=[],
        attribution_footer="Generated with Get Physics Done",
        output_filename=None,
    )

    tex = render_paper(config)
    assert REQUIRED_GPD_ACKNOWLEDGMENT in tex


def test_build_artifact_manifest_captures_tex_and_optional_bib(tmp_path) -> None:
    from gpd.mcp.paper.artifact_manifest import build_artifact_manifest
    from gpd.mcp.paper.models import Author, PaperConfig, Section

    tex_path = tmp_path / "paper.tex"
    tex_path.write_text("\\documentclass{article}\\begin{document}\\bibliography{refs}\\end{document}", encoding="utf-8")
    bib_path = tmp_path / "refs.bib"
    bib_path.write_text("@article{test2024, author={Test}, title={Title}, year={2024}}", encoding="utf-8")

    config = PaperConfig(
        title="Test Paper",
        authors=[Author(name="Test Author", affiliation="Test Univ")],
        abstract="Abstract text.",
        sections=[Section(title="Intro", content="Content")],
        journal="mnras",
    )

    manifest = build_artifact_manifest(config, tmp_path, tex_path=tex_path, bib_path=bib_path)

    tex_artifact = next(artifact for artifact in manifest.artifacts if artifact.artifact_id == "tex-paper")
    assert len(tex_artifact.sha256) == 64
    assert any(artifact.category == "bib" for artifact in manifest.artifacts)


def test_artifact_manifest_models_reject_extra_fields_and_invalid_sha256() -> None:
    from gpd.mcp.paper.models import ArtifactManifest

    with pytest.raises(ValidationError):
        ArtifactManifest.model_validate(
            {
                "version": 1,
                "paper_title": "Strict Manifest",
                "journal": "prl",
                "created_at": "2026-03-17T00:00:00+00:00",
                "artifacts": [
                    {
                        "artifact_id": "tex-paper",
                        "category": "tex",
                        "path": "paper.tex",
                        "sha256": "deadbeef",
                        "produced_by": "build_paper:render_tex",
                        "unexpected": "boom",
                    }
                ],
            }
        )


def test_artifact_manifest_rejects_unsupported_builder_journal() -> None:
    from gpd.mcp.paper.models import ArtifactManifest

    with pytest.raises(ValidationError, match="journal"):
        ArtifactManifest.model_validate(
            {
                "version": 1,
                "paper_title": "Strict Manifest",
                "journal": "prd",
                "created_at": "2026-03-17T00:00:00+00:00",
                "artifacts": [],
            }
        )


def test_artifact_manifest_models_reject_blank_titles_and_invalid_timestamps() -> None:
    from gpd.mcp.paper.models import ArtifactManifest

    with pytest.raises(ValidationError, match=r"paper_title[\s\S]*non-empty string"):
        ArtifactManifest.model_validate(
            {
                "version": 1,
                "paper_title": "   ",
                "journal": "prl",
                "created_at": "2026-03-17T00:00:00+00:00",
                "artifacts": [],
            }
        )

    with pytest.raises(ValidationError, match=r"created_at[\s\S]*ISO 8601 timestamp"):
        ArtifactManifest.model_validate(
            {
                "version": 1,
                "paper_title": "Strict Manifest",
                "journal": "prl",
                "created_at": "not-a-timestamp",
                "artifacts": [],
            }
        )


def test_build_artifact_manifest_preserves_absolute_source_paths(tmp_path) -> None:
    from gpd.mcp.paper.artifact_manifest import build_artifact_manifest
    from gpd.mcp.paper.models import Author, FigureRef, PaperConfig, Section

    source_dir = tmp_path / "sources"
    source_dir.mkdir()
    original_path = source_dir / "input-figure.pdf"
    original_path.write_text("source figure", encoding="utf-8")

    prepared_dir = tmp_path / "figures"
    prepared_dir.mkdir()
    prepared_path = prepared_dir / "prepared-figure.pdf"
    prepared_path.write_text("prepared figure", encoding="utf-8")

    tex_path = tmp_path / "paper.tex"
    tex_path.write_text("\\documentclass{article}\\begin{document}\\end{document}", encoding="utf-8")

    config = PaperConfig(
        title="Portable Manifest",
        authors=[Author(name="Test Author", affiliation="Test Univ")],
        abstract="Abstract text.",
        sections=[Section(title="Intro", content="Content")],
        journal="jhep",
    )

    manifest = build_artifact_manifest(
        config,
        tmp_path,
        tex_path=tex_path,
        figure_source_pairs=[
            (
                FigureRef(path=original_path, caption="Source", label="source"),
                FigureRef(path=Path("figures/prepared-figure.pdf"), caption="Prepared", label="prepared"),
            )
        ],
    )

    figure_artifact = next(artifact for artifact in manifest.artifacts if artifact.category == "figure")
    assert figure_artifact.sources[0].path == str(original_path)


def test_prepare_figures_returns_relative_paths(tmp_path) -> None:
    from PIL import Image

    from gpd.mcp.paper.figures import prepare_figures
    from gpd.mcp.paper.models import FigureRef

    input_dir = tmp_path / "input"
    input_dir.mkdir()
    Image.new("RGB", (100, 100)).save(input_dir / "fig.png")

    output_dir = tmp_path / "output"
    figures = [FigureRef(path=input_dir / "fig.png", caption="Test", label="test")]
    result, errors = prepare_figures(figures, output_dir, "prl")

    assert errors == []
    assert len(result) == 1
    assert result[0].path.is_absolute() is False
    assert (output_dir / result[0].path).exists()


def test_render_paper_cleans_title_fences() -> None:
    from gpd.mcp.paper.models import PaperConfig, Section
    from gpd.mcp.paper.template_registry import render_paper

    rendered = render_paper(
        PaperConfig(
            journal="prl",
            title="```My Test Paper```",
            authors=[],
            abstract="Abstract text",
            sections=[Section(title="Intro", content="Body text")],
        )
    )

    assert "```" not in rendered
    assert "My Test Paper" in rendered


def test_render_paper_cleans_fenced_author_section_appendix_and_caption_fields() -> None:
    from pathlib import Path

    from gpd.mcp.paper.models import Author, FigureRef, PaperConfig, Section
    from gpd.mcp.paper.template_registry import render_paper

    rendered = render_paper(
        PaperConfig(
            journal="prl",
            title="Paper",
            authors=[Author(name="```Alice Example```", email="```alice@example.com```", affiliation="```MIT```")],
            abstract="Abstract text",
            sections=[Section(title="```Intro```", content="Body text")],
            appendix_sections=[Section(title="```Appendix A```", content="Appendix text")],
            figures=[FigureRef(path=Path("figures/fig01.pdf"), caption="```Velocity caption```", label="velocity")],
        )
    )

    assert "```" not in rendered
    assert "\\author{Alice Example}" in rendered
    assert "\\email{alice@example.com}" in rendered
    assert "\\affiliation{MIT}" in rendered
    assert "\\section{Intro}" in rendered
    assert "\\section{Appendix A}" in rendered
    assert "\\caption{Velocity caption}" in rendered


def test_latex_autofix_preserves_documentclass_and_texttt_underscores() -> None:
    from gpd.utils.latex import _fix_unbalanced_braces, _fix_unescaped_underscores

    broken_doc = "\\documentclass{article}\n\\begin{document}\nHello}\n\\end{document}"
    texttt_doc = "The variable \\texttt{my_var} is important."

    assert not _fix_unbalanced_braces(broken_doc).startswith("{\\documentclass")
    assert "\\texttt{my_var}" in _fix_unescaped_underscores(texttt_doc)


def test_clean_latex_fences_leaves_unmatched_fences_unchanged() -> None:
    from gpd.utils.latex import clean_latex_fences

    content = "Some text ```latex\\section{Intro} and no closing fence"

    assert clean_latex_fences(content) == content


def test_journal_spec_is_exported_from_paper_package() -> None:
    import gpd.mcp.paper as paper_pkg
    from gpd.mcp.paper import JournalSpec

    assert JournalSpec is not None
    assert "JournalSpec" in paper_pkg.__all__
