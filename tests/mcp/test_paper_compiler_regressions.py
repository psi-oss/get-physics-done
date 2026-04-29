"""MCP-facing paper compiler regression coverage."""

from __future__ import annotations

import json

import pytest

from gpd.mcp.paper.compiler import CompilationResult, build_paper
from gpd.mcp.paper.models import Author, FigureRef, PaperConfig, Section


def _minimal_paper_config(
    title: str,
    *,
    output_filename: str | None = None,
    figures: list[FigureRef] | None = None,
) -> PaperConfig:
    kwargs: dict[str, object] = {
        "title": title,
        "authors": [Author(name="A. Researcher")],
        "abstract": "Abstract.",
        "sections": [Section(title="Intro", content="No citations here.")],
    }
    if output_filename is not None:
        kwargs["output_filename"] = output_filename
    if figures is not None:
        kwargs["figures"] = figures
    return PaperConfig(**kwargs)


def _assert_failure_manifest_excludes_pdf(manifest, *, stage: str) -> None:
    assert manifest is not None
    assert all(artifact.category != "pdf" for artifact in manifest.artifacts)
    assert any(
        artifact.artifact_id == f"build-failure-{stage}"
        and artifact.metadata["build_success"] is False
        and artifact.metadata["failure_stage"] == stage
        for artifact in manifest.artifacts
    )


def _assert_failure_manifest_payload_excludes_pdf(manifest_path, *, stage: str) -> None:
    assert manifest_path is not None
    manifest_payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert all(artifact["category"] != "pdf" for artifact in manifest_payload["artifacts"])
    assert any(
        artifact["artifact_id"] == f"build-failure-{stage}"
        and artifact["metadata"]["build_success"] is False
        and artifact["metadata"]["failure_stage"] == stage
        for artifact in manifest_payload["artifacts"]
    )


@pytest.mark.asyncio
async def test_build_paper_does_not_publish_stale_pdf_after_failed_rebuild(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "paper"
    output_dir.mkdir()
    stale_pdf_path = output_dir / "stale-rebuild.pdf"
    stale_pdf_path.write_bytes(b"%PDF-old")
    config = _minimal_paper_config("Stale Rebuild", output_filename="stale-rebuild")

    async def fake_compile(tex_path, output_dir, compiler="pdflatex"):
        return CompilationResult(
            success=False,
            pdf_path=stale_pdf_path,
            error="latexmk exited with code 2",
        )

    monkeypatch.setattr("gpd.mcp.paper.compiler.check_journal_dependencies", lambda spec: (True, []))
    monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", fake_compile)

    result = await build_paper(config, output_dir)

    assert result.success is False
    assert result.pdf_path is None
    assert not stale_pdf_path.exists()
    assert result.errors == ["latexmk exited with code 2"]
    _assert_failure_manifest_excludes_pdf(result.manifest, stage="compile")
    _assert_failure_manifest_payload_excludes_pdf(result.manifest_path, stage="compile")


@pytest.mark.asyncio
async def test_build_paper_removes_expected_pdf_when_failed_rebuild_returns_no_pdf_path(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "paper"
    output_dir.mkdir()
    stale_pdf_path = output_dir / "stale-rebuild.pdf"
    stale_pdf_path.write_bytes(b"%PDF-old")
    config = _minimal_paper_config("Stale Rebuild", output_filename="stale-rebuild")

    async def fake_compile(tex_path, output_dir, compiler="pdflatex"):
        return CompilationResult(
            success=False,
            pdf_path=None,
            error="pdflatex pass 1 exited with code 1",
        )

    monkeypatch.setattr("gpd.mcp.paper.compiler.check_journal_dependencies", lambda spec: (True, []))
    monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", fake_compile)

    result = await build_paper(config, output_dir)

    assert result.success is False
    assert result.pdf_path is None
    assert not stale_pdf_path.exists()
    assert result.errors == ["pdflatex pass 1 exited with code 1"]
    _assert_failure_manifest_excludes_pdf(result.manifest, stage="compile")


@pytest.mark.asyncio
async def test_build_paper_does_not_publish_pdf_when_earlier_errors_exist_despite_compile_success(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "paper"
    output_dir.mkdir()
    pdf_path = output_dir / "figure-error.pdf"
    config = _minimal_paper_config(
        "Figure Error",
        figures=[FigureRef(path=tmp_path / "missing.png", caption="Missing", label="missing")],
        output_filename="figure-error",
    )

    def fake_prepare_figures(*_args, **_kwargs):
        return [], ["Figure preparation failed: missing.png"], []

    async def fake_compile(tex_path, output_dir, compiler="pdflatex"):
        pdf_path.write_bytes(b"%PDF-fake")
        return CompilationResult(success=True, pdf_path=pdf_path)

    monkeypatch.setattr("gpd.mcp.paper.compiler._prepare_figures_with_sources", fake_prepare_figures)
    monkeypatch.setattr("gpd.mcp.paper.compiler.check_journal_dependencies", lambda spec: (True, []))
    monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", fake_compile)

    result = await build_paper(config, output_dir)

    assert result.success is False
    assert result.pdf_path is None
    assert not pdf_path.exists()
    assert result.errors == ["Figure preparation failed: missing.png"]
    _assert_failure_manifest_excludes_pdf(result.manifest, stage="build")


@pytest.mark.asyncio
async def test_tectonic_launch_oserror_returns_compilation_result(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from gpd.mcp.paper import compiler as compiler_module

    tex_path = tmp_path / "paper.tex"
    tex_path.write_text("\\documentclass{article}\\begin{document}x\\end{document}", encoding="utf-8")

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        raise PermissionError("permission denied")

    monkeypatch.setattr(compiler_module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    result = await compiler_module._compile_with_tectonic(
        tex_path,
        tmp_path,
        tectonic_path="/usr/bin/tectonic",
    )

    assert result.success is False
    assert result.pdf_path is None
    assert result.error is not None
    assert "failed to launch tectonic" in result.error
    assert "permission denied" in result.error


@pytest.mark.asyncio
async def test_latexmk_launch_oserror_returns_compilation_result(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    from gpd.mcp.paper import compiler as compiler_module

    tex_path = tmp_path / "paper.tex"
    tex_path.write_text("\\documentclass{article}\\begin{document}x\\end{document}", encoding="utf-8")

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        raise PermissionError("permission denied")

    monkeypatch.setattr(compiler_module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    result = await compiler_module._compile_with_latexmk(
        tex_path,
        tmp_path,
        "pdflatex",
        latexmk_path="/usr/bin/latexmk",
    )

    assert result.success is False
    assert result.pdf_path is None
    assert result.error is not None
    assert "failed to launch latexmk" in result.error
    assert "permission denied" in result.error


@pytest.mark.asyncio
async def test_manual_multipass_launch_oserror_returns_compilation_result(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gpd.mcp.paper import compiler as compiler_module

    tex_path = tmp_path / "paper.tex"
    tex_path.write_text("\\documentclass{article}\\begin{document}x\\end{document}", encoding="utf-8")

    def fake_find_latex_compiler(name: str):
        return "/opt/tex/pdflatex" if name == "pdflatex" else None

    async def fake_create_subprocess_exec(*_args, **_kwargs):
        raise PermissionError("permission denied")

    monkeypatch.setattr(compiler_module, "find_latex_compiler", fake_find_latex_compiler)
    monkeypatch.setattr(compiler_module.asyncio, "create_subprocess_exec", fake_create_subprocess_exec)

    result = await compiler_module._compile_manual_multipass(tex_path, tmp_path, "pdflatex")

    assert result.success is False
    assert result.pdf_path is None
    assert result.error is not None
    assert "failed to launch pdflatex" in result.error
    assert "permission denied" in result.error
