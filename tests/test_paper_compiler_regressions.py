"""Assertions for paper compilation error handling."""

from __future__ import annotations

from pathlib import Path

import pytest
from pybtex.database import BibliographyData, Entry

from gpd.mcp.paper.bibliography import BibliographyAudit, CitationAuditRecord
from gpd.mcp.paper.compiler import (
    CompilationResult,
    _compile_manual_multipass,
    _compile_with_latexmk,
    _reference_bibtex_keys_from_audit,
    build_paper,
    compile_paper,
)
from gpd.mcp.paper.models import Author, PaperConfig, Section, derive_output_filename
from gpd.utils.latex import AutoFixResult


def test_reference_bibtex_keys_rejects_duplicate_reference_id() -> None:
    audit = BibliographyAudit(
        generated_at="2026-04-18T00:00:00+00:00",
        total_sources=2,
        resolved_sources=2,
        partial_sources=0,
        unverified_sources=0,
        failed_sources=0,
        entries=[
            CitationAuditRecord(
                key="first2024",
                source_type="paper",
                reference_id="ref-duplicate",
                title="First",
                resolution_status="provided",
                verification_status="verified",
            ),
            CitationAuditRecord(
                key="second2025",
                source_type="paper",
                reference_id="ref-duplicate",
                title="Second",
                resolution_status="provided",
                verification_status="verified",
            ),
        ],
    )

    with pytest.raises(ValueError, match="duplicate bibliography reference_id 'ref-duplicate'"):
        _reference_bibtex_keys_from_audit(audit)


@pytest.mark.asyncio
async def test_compile_paper_resolves_relative_tex_and_output_paths_once(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    paper_dir = tmp_path / "paper"
    paper_dir.mkdir()
    tex_path = paper_dir / "main.tex"
    tex_path.write_text(r"\documentclass{article}\begin{document}test\end{document}", encoding="utf-8")
    captured: dict[str, object] = {}

    async def fake_manual_multipass(resolved_tex_path, resolved_output_dir, compiler):
        captured["tex_path"] = resolved_tex_path
        captured["output_dir"] = resolved_output_dir
        captured["compiler"] = compiler
        return CompilationResult(success=False, error="stopped before subprocess")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("gpd.mcp.paper.compiler.find_tectonic", lambda: None)
    monkeypatch.setattr(
        "gpd.mcp.paper.compiler.find_latex_compiler",
        lambda name: "/usr/bin/pdflatex" if name == "pdflatex" else None,
    )
    monkeypatch.setattr("gpd.mcp.paper.compiler._compile_manual_multipass", fake_manual_multipass)

    result = await compile_paper(Path("paper/main.tex"), Path("build"))

    assert result.error == "stopped before subprocess"
    assert captured == {
        "tex_path": tex_path.resolve(strict=False),
        "output_dir": (tmp_path / "build").resolve(strict=False),
        "compiler": "pdflatex",
    }


class _FakeProcess:
    def __init__(self, returncode: int, stdout: bytes = b"", stderr: bytes = b"") -> None:
        self.returncode = returncode
        self._stdout = stdout
        self._stderr = stderr

    async def communicate(self) -> tuple[bytes, bytes]:
        return self._stdout, self._stderr


@pytest.mark.asyncio
async def test_latexmk_rejects_pdf_when_exit_code_is_nonzero(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    tex_path = tmp_path / "paper.tex"
    tex_path.write_text(r"\documentclass{article}\begin{document}test\end{document}", encoding="utf-8")
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-fake")

    async def fake_create_subprocess_exec(*args, **kwargs):
        return _FakeProcess(returncode=2, stdout=b"latexmk stdout", stderr=b"latexmk stderr")

    monkeypatch.setattr("gpd.mcp.paper.compiler.asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    result = await _compile_with_latexmk(tex_path, tmp_path, "pdflatex", latexmk_path="/usr/bin/latexmk")

    assert result.success is False
    assert result.pdf_path is not None  # PDF returned even on non-zero exit
    assert result.error == "latexmk exited with code 2"
    assert result.log is not None
    assert "latexmk stdout" in result.log


@pytest.mark.asyncio
async def test_manual_multipass_succeeds_when_early_pass_fails_but_last_pass_ok(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Pass 1 often exits non-zero (unresolved citations). If the last pass
    succeeds and a PDF exists, compilation should be treated as success."""
    tex_path = tmp_path / "paper.tex"
    tex_path.write_text(r"\documentclass{article}\begin{document}test\end{document}", encoding="utf-8")
    pdf_path = tmp_path / "paper.pdf"
    call_count = 0

    returncodes = iter([1, 0, 0])

    async def fake_create_subprocess_exec(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 3:
            pdf_path.write_bytes(b"%PDF-fresh")
        return _FakeProcess(returncode=next(returncodes), stdout=b"pdflatex output", stderr=b"")

    def fake_which(binary: str) -> str | None:
        if binary == "pdflatex":
            return "/usr/bin/pdflatex"
        return None

    monkeypatch.setattr("gpd.mcp.paper.compiler.asyncio.create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr("gpd.mcp.paper.compiler._which", fake_which)

    result = await _compile_manual_multipass(tex_path, tmp_path, "pdflatex")

    assert result.success is True
    assert result.pdf_path == pdf_path


@pytest.mark.asyncio
async def test_manual_multipass_rejects_bibtex_failure_even_when_final_pass_succeeds(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tex_path = tmp_path / "paper.tex"
    tex_path.write_text(r"\documentclass{article}\begin{document}test\end{document}", encoding="utf-8")
    (tmp_path / "paper.aux").write_text(r"\citation{ref}", encoding="utf-8")
    pdf_path = tmp_path / "paper.pdf"
    call_count = 0

    returncodes = iter([0, 2, 0, 0])

    async def fake_create_subprocess_exec(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 4:
            pdf_path.write_bytes(b"%PDF-fresh")
        return _FakeProcess(returncode=next(returncodes), stdout=b"compile output", stderr=b"")

    def fake_which(binary: str) -> str | None:
        if binary == "pdflatex":
            return "/usr/bin/pdflatex"
        if binary == "bibtex":
            return "/usr/bin/bibtex"
        return None

    monkeypatch.setattr("gpd.mcp.paper.compiler.asyncio.create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr("gpd.mcp.paper.compiler._which", fake_which)
    monkeypatch.setattr("gpd.utils.latex.try_autofix", lambda tex, log: AutoFixResult())

    result = await _compile_manual_multipass(tex_path, tmp_path, "pdflatex")

    assert result.success is False
    assert result.pdf_path is None
    assert result.error == "bibtex exited with code 2"
    assert result.log is not None
    assert "compile output" in result.log


@pytest.mark.asyncio
async def test_manual_multipass_rejects_missing_bibtex_when_citations_require_it(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tex_path = tmp_path / "paper.tex"
    tex_path.write_text(r"\documentclass{article}\begin{document}test\cite{ref}\end{document}", encoding="utf-8")
    (tmp_path / "paper.aux").write_text(r"\citation{ref}", encoding="utf-8")
    pdf_path = tmp_path / "paper.pdf"
    call_count = 0

    returncodes = iter([0, 0, 0])

    async def fake_create_subprocess_exec(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 3:
            pdf_path.write_bytes(b"%PDF-fresh")
        return _FakeProcess(returncode=next(returncodes), stdout=b"compile output", stderr=b"")

    def fake_find_compiler(name: str) -> str | None:
        if name == "pdflatex":
            return "/usr/bin/pdflatex"
        return None

    monkeypatch.setattr("gpd.mcp.paper.compiler.asyncio.create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr("gpd.mcp.paper.compiler.find_latex_compiler", fake_find_compiler)
    monkeypatch.setattr("gpd.utils.latex.try_autofix", lambda tex, log: AutoFixResult())

    result = await _compile_manual_multipass(tex_path, tmp_path, "pdflatex")

    assert result.success is False
    assert result.pdf_path is None
    assert result.error == "bibtex not found but citations require bibliography processing"


@pytest.mark.asyncio
async def test_manual_multipass_rejects_missing_bibtex_even_after_autofix(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tex_path = tmp_path / "paper.tex"
    tex_path.write_text("broken content", encoding="utf-8")
    aux_path = tmp_path / "paper.aux"
    pdf_path = tmp_path / "paper.pdf"
    call_count = 0

    returncodes = iter([1, 0, 0, 0, 0, 0])

    async def fake_create_subprocess_exec(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count >= 4:
            aux_path.write_text(r"\citation{ref}", encoding="utf-8")
            pdf_path.write_bytes(b"%PDF-fresh")
        return _FakeProcess(returncode=next(returncodes), stdout=b"compile output", stderr=b"")

    def fake_find_compiler(name: str) -> str | None:
        if name == "pdflatex":
            return "/usr/bin/pdflatex"
        return None

    monkeypatch.setattr("gpd.mcp.paper.compiler.asyncio.create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr("gpd.mcp.paper.compiler.find_latex_compiler", fake_find_compiler)
    monkeypatch.setattr(
        "gpd.utils.latex.try_autofix",
        lambda tex, log: AutoFixResult(
            fixed_content=r"\documentclass{article}\begin{document}fixed\cite{ref}\end{document}",
            fixes_applied=("fixed",),
            was_modified=True,
        ),
    )

    result = await _compile_manual_multipass(tex_path, tmp_path, "pdflatex")

    assert result.success is False
    assert result.pdf_path is None
    assert result.error == "bibtex not found but citations require bibliography processing"


@pytest.mark.asyncio
async def test_manual_multipass_rejects_stale_preexisting_pdf(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    tex_path = tmp_path / "paper.tex"
    tex_path.write_text(r"\documentclass{article}\begin{document}test\end{document}", encoding="utf-8")
    pdf_path = tmp_path / "paper.pdf"
    pdf_path.write_bytes(b"%PDF-stale")

    returncodes = iter([1, 0, 0])

    async def fake_create_subprocess_exec(*args, **kwargs):
        return _FakeProcess(returncode=next(returncodes), stdout=b"pdflatex output", stderr=b"")

    def fake_which(binary: str) -> str | None:
        if binary == "pdflatex":
            return "/usr/bin/pdflatex"
        return None

    monkeypatch.setattr("gpd.mcp.paper.compiler.asyncio.create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr("gpd.mcp.paper.compiler._which", fake_which)
    monkeypatch.setattr("gpd.utils.latex.try_autofix", lambda tex, log: AutoFixResult())

    result = await _compile_manual_multipass(tex_path, tmp_path, "pdflatex")

    assert result.success is False
    assert result.pdf_path is None
    assert result.error == "pdflatex pass 1 exited with code 1"


@pytest.mark.asyncio
async def test_manual_multipass_fails_when_last_pass_nonzero_and_no_pdf(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the last pass exits non-zero and no PDF exists, compilation fails."""
    tex_path = tmp_path / "paper.tex"
    tex_path.write_text(r"\documentclass{article}\begin{document}test\end{document}", encoding="utf-8")

    returncodes = iter([1, 0, 1])

    async def fake_create_subprocess_exec(*args, **kwargs):
        return _FakeProcess(returncode=next(returncodes), stdout=b"pdflatex output", stderr=b"")

    def fake_which(binary: str) -> str | None:
        if binary == "pdflatex":
            return "/usr/bin/pdflatex"
        return None

    monkeypatch.setattr("gpd.mcp.paper.compiler.asyncio.create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr("gpd.mcp.paper.compiler._which", fake_which)

    result = await _compile_manual_multipass(tex_path, tmp_path, "pdflatex")

    assert result.success is False
    assert result.pdf_path is None
    assert result.log is not None
    assert "pdflatex output" in result.log


@pytest.mark.asyncio
async def test_manual_multipass_applies_autofix_even_after_compile_errors(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tex_path = tmp_path / "paper.tex"
    tex_path.write_text("broken content", encoding="utf-8")
    pdf_path = tmp_path / "paper.pdf"
    call_count = 0

    async def fake_create_subprocess_exec(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count >= 4:
            pdf_path.write_bytes(b"%PDF-fake")
            return _FakeProcess(returncode=0, stdout=b"autofix ok", stderr=b"")
        return _FakeProcess(returncode=1 if call_count == 1 else 0, stdout=b"Missing $ inserted", stderr=b"")

    def fake_which(binary: str) -> str | None:
        if binary == "pdflatex":
            return "/usr/bin/pdflatex"
        return None

    monkeypatch.setattr("gpd.mcp.paper.compiler.asyncio.create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr("gpd.mcp.paper.compiler.find_latex_compiler", fake_which)
    monkeypatch.setattr(
        "gpd.utils.latex.try_autofix",
        lambda tex, log: AutoFixResult(
            fixed_content=r"\documentclass{article}\begin{document}fixed\end{document}",
            fixes_applied=("fixed",),
            was_modified=True,
        ),
    )

    result = await _compile_manual_multipass(tex_path, tmp_path, "pdflatex")

    assert result.success is True
    assert result.pdf_path == pdf_path
    assert tex_path.read_text(encoding="utf-8") == r"\documentclass{article}\begin{document}fixed\end{document}"


@pytest.mark.asyncio
async def test_manual_multipass_autofix_requires_fresh_pdf_after_fix(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tex_path = tmp_path / "paper.tex"
    tex_path.write_text("broken content", encoding="utf-8")
    pdf_path = tmp_path / "paper.pdf"
    call_count = 0

    returncodes = iter([1, 0, 1, 0, 0, 0])

    async def fake_create_subprocess_exec(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            pdf_path.write_bytes(b"%PDF-from-broken-first-attempt")
        return _FakeProcess(returncode=next(returncodes), stdout=b"compile output", stderr=b"")

    def fake_which(binary: str) -> str | None:
        if binary == "pdflatex":
            return "/usr/bin/pdflatex"
        return None

    monkeypatch.setattr("gpd.mcp.paper.compiler.asyncio.create_subprocess_exec", fake_create_subprocess_exec)
    monkeypatch.setattr("gpd.mcp.paper.compiler.find_latex_compiler", fake_which)
    monkeypatch.setattr(
        "gpd.utils.latex.try_autofix",
        lambda tex, log: AutoFixResult(
            fixed_content=r"\documentclass{article}\begin{document}fixed\end{document}",
            fixes_applied=("fixed",),
            was_modified=True,
        ),
    )

    result = await _compile_manual_multipass(tex_path, tmp_path, "pdflatex")

    assert result.success is False
    assert result.pdf_path is None
    assert result.error == "Compilation failed"
    assert tex_path.read_text(encoding="utf-8") == r"\documentclass{article}\begin{document}fixed\end{document}"


@pytest.mark.asyncio
async def test_build_paper_routes_sidecars_to_independent_output_paths(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "paper"
    hidden_sidecar_dir = output_dir / ".paper-meta"
    manifest_path = output_dir / "ARTIFACT-MANIFEST.json"
    audit_path = hidden_sidecar_dir / "BIBLIOGRAPHY-AUDIT.json"
    config = PaperConfig(
        title="Sidecar Routing Paper",
        authors=[Author(name="A. Researcher")],
        abstract="Abstract.",
        sections=[Section(title="Intro", content="No citations here.")],
    )
    bibliography = BibliographyData()
    bibliography.entries["ref2026"] = Entry(
        "article",
        [("author", "Doe"), ("title", "Reference"), ("year", "2026")],
    )
    pdf_path = output_dir / f"{derive_output_filename(config)}.pdf"

    async def fake_compile(tex_path, output_dir, compiler="pdflatex"):
        pdf_path.write_bytes(b"%PDF-fake")
        return CompilationResult(success=True, pdf_path=pdf_path)

    monkeypatch.setattr("gpd.mcp.paper.compiler.check_journal_dependencies", lambda spec: (True, []))
    monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", fake_compile)

    result = await build_paper(
        config,
        output_dir,
        bib_data=bibliography,
        sidecar_root=hidden_sidecar_dir,
        artifact_manifest_output_path=manifest_path,
        bibliography_audit_output_path=audit_path,
    )

    assert result.success is True
    assert result.manifest_path == manifest_path
    assert result.bibliography_audit_path == audit_path
    assert manifest_path.is_file()
    assert audit_path.is_file()
    assert not (hidden_sidecar_dir / "ARTIFACT-MANIFEST.json").exists()
    assert not (output_dir / "BIBLIOGRAPHY-AUDIT.json").exists()
    audit_artifact = next(
        artifact for artifact in result.manifest.artifacts if artifact.artifact_id == "audit-bibliography"
    )
    assert audit_artifact.path == ".paper-meta/BIBLIOGRAPHY-AUDIT.json"


# ---- Assertions for compiler imports and dead-code invariants ----


def test_figureref_is_importable_from_compiler_module() -> None:
    """FigureRef must be imported in compiler.py so the type annotation
    ``list[tuple[FigureRef, FigureRef]]`` resolves at runtime (Issue 1)."""
    import gpd.mcp.paper.compiler as compiler_mod

    assert hasattr(compiler_mod, "FigureRef"), "FigureRef should be importable from compiler module"
