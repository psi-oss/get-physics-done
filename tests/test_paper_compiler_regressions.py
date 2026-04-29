"""Assertions for paper compilation error handling."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from pybtex.database import BibliographyData, Entry
from pydantic import ValidationError as PydanticValidationError

from gpd.core.manuscript_artifacts import locate_publication_artifact
from gpd.mcp.paper.artifact_manifest import validate_artifact_manifest_integrity
from gpd.mcp.paper.bibliography import BibliographyAudit, CitationAuditRecord
from gpd.mcp.paper.compiler import (
    CompilationResult,
    _compile_manual_multipass,
    _compile_with_latexmk,
    _compile_with_tectonic,
    _reference_bibtex_keys_from_audit,
    build_paper,
    compile_paper,
)
from gpd.mcp.paper.models import (
    ArtifactManifest,
    ArtifactRecord,
    Author,
    PaperConfig,
    Section,
    derive_output_filename,
)
from gpd.utils.latex import AutoFixResult


def _minimal_paper_config(
    title: str,
    *,
    section_content: str = "No citations here.",
    journal: str = "prl",
) -> PaperConfig:
    return PaperConfig(
        title=title,
        authors=[Author(name="A. Researcher")],
        abstract="Abstract.",
        sections=[Section(title="Intro", content=section_content)],
        journal=journal,
    )


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


class _PdfWritingFakeProcess(_FakeProcess):
    def __init__(self, returncode: int, pdf_path: Path, stdout: bytes = b"", stderr: bytes = b"") -> None:
        super().__init__(returncode=returncode, stdout=stdout, stderr=stderr)
        self._pdf_path = pdf_path

    async def communicate(self) -> tuple[bytes, bytes]:
        self._pdf_path.write_bytes(b"%PDF-fresh")
        return await super().communicate()


class _TimeoutProcess:
    def __init__(self) -> None:
        self.returncode = None
        self.killed = False

    async def communicate(self) -> tuple[bytes, bytes]:
        raise TimeoutError

    def kill(self) -> None:
        self.killed = True

    async def wait(self) -> int:
        return -9


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
async def test_tectonic_rejects_pdf_when_exit_code_is_nonzero(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    tex_path = tmp_path / "paper.tex"
    tex_path.write_text(r"\documentclass{article}\begin{document}test\end{document}", encoding="utf-8")
    pdf_path = tmp_path / "paper.pdf"

    async def fake_create_subprocess_exec(*args, **kwargs):
        return _PdfWritingFakeProcess(
            returncode=2, pdf_path=pdf_path, stdout=b"tectonic stdout", stderr=b"tectonic stderr"
        )

    monkeypatch.setattr("gpd.mcp.paper.compiler.asyncio.create_subprocess_exec", fake_create_subprocess_exec)

    result = await _compile_with_tectonic(tex_path, tmp_path, tectonic_path="/usr/bin/tectonic")

    assert result.success is False
    assert result.pdf_path == pdf_path
    assert result.error == "tectonic exited with code 2"
    assert result.log is not None
    assert "tectonic stdout" in result.log


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
    call_count = 0

    returncodes = iter([1, 0, 0, 0, 0, 0])

    async def fake_create_subprocess_exec(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count >= 4:
            input_tex_path = Path(args[-1])
            (tmp_path / f"{input_tex_path.stem}.aux").write_text(r"\citation{ref}", encoding="utf-8")
            (tmp_path / f"{input_tex_path.stem}.pdf").write_bytes(b"%PDF-fresh")
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

    result = await _compile_manual_multipass(tex_path, tmp_path, "pdflatex", apply_latex_autofix=True)

    assert result.success is False
    assert result.pdf_path is None
    assert result.error == "bibtex not found but citations require bibliography processing"
    assert tex_path.read_text(encoding="utf-8") == "broken content"


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
async def test_manual_multipass_does_not_apply_autofix_by_default(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tex_path = tmp_path / "paper.tex"
    tex_path.write_text("broken content", encoding="utf-8")
    call_count = 0

    async def fake_create_subprocess_exec(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count > 3:
            input_tex_path = Path(args[-1])
            (tmp_path / f"{input_tex_path.stem}.pdf").write_bytes(b"%PDF-fake")
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

    assert result.success is False
    assert result.pdf_path is None
    assert result.error == "pdflatex pass 1 exited with code 1"
    assert tex_path.read_text(encoding="utf-8") == "broken content"
    assert list(tmp_path.glob(".paper-gpd-autofix-*.tex")) == []
    assert call_count == 3


@pytest.mark.asyncio
async def test_manual_multipass_applies_autofix_when_explicitly_enabled(
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
            input_tex_path = Path(args[-1])
            (tmp_path / f"{input_tex_path.stem}.pdf").write_bytes(b"%PDF-fake")
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

    result = await _compile_manual_multipass(tex_path, tmp_path, "pdflatex", apply_latex_autofix=True)

    assert result.success is True
    assert result.pdf_path == pdf_path
    assert pdf_path.read_bytes() == b"%PDF-fake"
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

    result = await _compile_manual_multipass(tex_path, tmp_path, "pdflatex", apply_latex_autofix=True)

    assert result.success is False
    assert result.pdf_path is None
    assert result.error == "Compilation failed"
    assert tex_path.read_text(encoding="utf-8") == "broken content"


@pytest.mark.asyncio
async def test_manual_multipass_cleans_autofix_scratch_after_timeout(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tex_path = tmp_path / "paper.tex"
    tex_path.write_text("broken content", encoding="utf-8")
    call_count = 0

    async def fake_create_subprocess_exec(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 4:
            return _TimeoutProcess()
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

    result = await _compile_manual_multipass(tex_path, tmp_path, "pdflatex", apply_latex_autofix=True)

    assert result.success is False
    assert result.error == "Compilation timed out"
    assert list(tmp_path.glob(".paper-gpd-autofix-*.tex")) == []
    assert tex_path.read_text(encoding="utf-8") == "broken content"


@pytest.mark.asyncio
async def test_build_paper_routes_sidecars_to_independent_output_paths(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "paper"
    hidden_sidecar_dir = output_dir / ".paper-meta"
    manifest_path = output_dir / "ARTIFACT-MANIFEST.json"
    audit_path = hidden_sidecar_dir / "BIBLIOGRAPHY-AUDIT.json"
    config = _minimal_paper_config("Sidecar Routing Paper")
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


@pytest.mark.asyncio
async def test_build_paper_writes_discoverable_manifest_in_nested_sidecar_root(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "paper"
    hidden_sidecar_dir = output_dir / ".paper-meta"
    config = _minimal_paper_config("Nested Sidecar Paper")
    pdf_path = output_dir / f"{derive_output_filename(config)}.pdf"
    captured_compile_kwargs: dict[str, object] = {}

    async def fake_compile(tex_path, output_dir, compiler="pdflatex", **kwargs):
        captured_compile_kwargs.update(kwargs)
        pdf_path.write_bytes(b"%PDF-fake")
        return CompilationResult(success=True, pdf_path=pdf_path)

    monkeypatch.setattr("gpd.mcp.paper.compiler.find_tectonic", lambda: None)
    monkeypatch.setattr("gpd.mcp.paper.compiler.check_journal_dependencies", lambda spec: (True, []))
    monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", fake_compile)

    result = await build_paper(config, output_dir, sidecar_root=hidden_sidecar_dir)

    assert result.success is True
    assert captured_compile_kwargs.get("apply_latex_autofix") is True
    assert result.manifest_path == hidden_sidecar_dir / "ARTIFACT-MANIFEST.json"
    assert result.manifest is not None
    assert result.manifest_path.is_file()
    assert locate_publication_artifact(output_dir, "ARTIFACT-MANIFEST.json") == result.manifest_path
    integrity = validate_artifact_manifest_integrity(
        result.manifest,
        result.manifest_path.parent,
        selected_manuscript_path=result.tex_path,
    )
    assert integrity.passed is True


def test_artifact_manifest_integrity_accepts_hidden_sidecar_for_nested_entrypoint(tmp_path) -> None:
    output_dir = tmp_path / "paper"
    manuscript = output_dir / "sections" / "main.tex"
    manuscript.parent.mkdir(parents=True)
    manuscript_text = "\\documentclass{article}\\begin{document}Nested\\end{document}\n"
    manuscript.write_text(manuscript_text, encoding="utf-8")
    digest = hashlib.sha256(manuscript_text.encode("utf-8")).hexdigest()
    manifest = ArtifactManifest.model_validate(
        {
            "version": 1,
            "paper_title": "Nested Sidecar Paper",
            "journal": "jhep",
            "created_at": "2026-04-28T00:00:00+00:00",
            "manuscript_sha256": digest,
            "artifacts": [
                {
                    "artifact_id": "tex-paper",
                    "category": "tex",
                    "path": "sections/main.tex",
                    "sha256": digest,
                    "produced_by": "test",
                }
            ],
        }
    )

    integrity = validate_artifact_manifest_integrity(
        manifest,
        output_dir / ".paper-meta" / "build",
        selected_manuscript_path=manuscript,
    )

    assert integrity.passed is True


def test_artifact_manifest_rejects_non_portable_artifact_paths(tmp_path) -> None:
    output_dir = tmp_path / "paper"
    manuscript = output_dir / "main.tex"
    manuscript.parent.mkdir(parents=True)
    manuscript_text = "\\documentclass{article}\\begin{document}Main\\end{document}\n"
    manuscript.write_text(manuscript_text, encoding="utf-8")
    digest = hashlib.sha256(manuscript_text.encode("utf-8")).hexdigest()

    base_payload = {
        "version": 1,
        "paper_title": "Portable Paths",
        "journal": "jhep",
        "created_at": "2026-04-28T00:00:00+00:00",
        "manuscript_sha256": digest,
        "artifacts": [
            {
                "artifact_id": "tex-paper",
                "category": "tex",
                "path": "main.tex",
                "sha256": digest,
                "produced_by": "test",
            }
        ],
    }
    invalid_paths = [
        manuscript.as_posix(),
        "../paper/main.tex",
        r"sections\main.tex",
        "C:/paper/main.tex",
    ]

    for invalid_path in invalid_paths:
        payload = json.loads(json.dumps(base_payload))
        payload["artifacts"][0]["path"] = invalid_path
        with pytest.raises(PydanticValidationError):
            ArtifactManifest.model_validate(payload)


def test_artifact_manifest_integrity_rejects_absolute_in_root_artifact_path(tmp_path) -> None:
    output_dir = tmp_path / "paper"
    manuscript = output_dir / "main.tex"
    manuscript.parent.mkdir(parents=True)
    manuscript_text = "\\documentclass{article}\\begin{document}Main\\end{document}\n"
    manuscript.write_text(manuscript_text, encoding="utf-8")
    digest = hashlib.sha256(manuscript_text.encode("utf-8")).hexdigest()
    manifest = ArtifactManifest.model_construct(
        paper_title="Absolute Path",
        journal="jhep",
        created_at="2026-04-28T00:00:00+00:00",
        manuscript_sha256=digest,
        artifacts=[
            ArtifactRecord.model_construct(
                artifact_id="tex-paper",
                category="tex",
                path=manuscript.as_posix(),
                sha256=digest,
                produced_by="test",
                sources=[],
                metadata={},
            )
        ],
    )

    integrity = validate_artifact_manifest_integrity(
        manifest,
        output_dir,
        selected_manuscript_path=manuscript,
    )

    assert integrity.passed is False
    assert "tex artifact path does not resolve to the selected manuscript" in integrity.detail


@pytest.mark.asyncio
async def test_build_paper_rejects_non_hidden_nested_sidecar_root(tmp_path) -> None:
    config = _minimal_paper_config("Non Hidden Sidecar")
    output_dir = tmp_path / "paper"
    non_hidden_sidecar_root = output_dir / "meta"

    with pytest.raises(ValueError, match="non-hidden nested sidecars are not discoverable"):
        await build_paper(config, output_dir, sidecar_root=non_hidden_sidecar_root)

    assert not non_hidden_sidecar_root.exists()


@pytest.mark.asyncio
async def test_build_paper_marks_manifest_after_dependency_failure(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "paper"
    config = _minimal_paper_config("Dependency Failure Paper")

    async def fake_compile(*_args, **_kwargs):
        raise AssertionError("compile_paper should not run when dependencies are missing")

    monkeypatch.setattr(
        "gpd.mcp.paper.compiler.check_journal_dependencies",
        lambda spec: (False, ["missing revtex4-2.cls"]),
    )
    monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", fake_compile)

    result = await build_paper(config, output_dir)

    assert result.success is False
    assert result.errors == ["missing revtex4-2.cls"]
    assert result.manifest_path == output_dir / "ARTIFACT-MANIFEST.json"
    assert result.manifest is not None
    manifest_payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    artifact_ids = {artifact["artifact_id"] for artifact in manifest_payload["artifacts"]}
    assert "pdf-dependency-failure-paper" not in artifact_ids
    failure_artifact = next(
        artifact for artifact in manifest_payload["artifacts"] if artifact["artifact_id"] == "build-failure-dependency"
    )
    assert failure_artifact["metadata"]["build_success"] is False
    assert failure_artifact["metadata"]["failure_stage"] == "dependency"
    assert "missing revtex4-2.cls" in failure_artifact["metadata"]["errors"]


@pytest.mark.asyncio
async def test_build_paper_lets_tectonic_handle_missing_local_journal_dependencies(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "paper"
    config = _minimal_paper_config("Tectonic Resource Paper", journal="jhep")
    pdf_path = output_dir / f"{derive_output_filename(config)}.pdf"

    def fail_if_checked(_spec):
        raise AssertionError("Tectonic builds should not preflight-block on kpsewhich resources")

    async def fake_compile(tex_path, output_dir, compiler="pdflatex"):
        pdf_path.write_bytes(b"%PDF-fake")
        return CompilationResult(success=True, pdf_path=pdf_path)

    monkeypatch.setattr("gpd.mcp.paper.compiler.find_tectonic", lambda: "/usr/bin/tectonic")
    monkeypatch.setattr("gpd.mcp.paper.compiler.check_journal_dependencies", fail_if_checked)
    monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", fake_compile)

    result = await build_paper(config, output_dir)

    assert result.success is True
    assert result.pdf_path == pdf_path


@pytest.mark.asyncio
async def test_build_paper_still_blocks_on_local_dependencies_when_tectonic_not_preferred(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "paper"
    config = _minimal_paper_config("Local Resource Paper", journal="jhep")

    async def fake_compile(*_args, **_kwargs):
        raise AssertionError("compile_paper should not run after dependency preflight failure")

    monkeypatch.setattr("gpd.mcp.paper.compiler.find_tectonic", lambda: "/usr/bin/tectonic")
    monkeypatch.setattr(
        "gpd.mcp.paper.compiler.check_journal_dependencies",
        lambda _spec: (False, ["missing jheppub.sty"]),
    )
    monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", fake_compile)

    result = await build_paper(config, output_dir, prefer_tectonic=False)

    assert result.success is False
    assert result.errors == ["missing jheppub.sty"]


@pytest.mark.asyncio
async def test_build_paper_marks_manifest_after_compile_failure(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "paper"
    config = _minimal_paper_config("Compile Failure Paper")

    async def fake_compile(tex_path, output_dir, compiler="pdflatex"):
        return CompilationResult(success=False, error="pdflatex exited with code 1")

    monkeypatch.setattr("gpd.mcp.paper.compiler.check_journal_dependencies", lambda spec: (True, []))
    monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", fake_compile)

    result = await build_paper(config, output_dir)

    assert result.success is False
    assert result.errors == ["pdflatex exited with code 1"]
    assert result.manifest_path == output_dir / "ARTIFACT-MANIFEST.json"
    assert result.manifest is not None
    manifest_payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    artifact_ids = {artifact["artifact_id"] for artifact in manifest_payload["artifacts"]}
    assert "pdf-compile-failure-paper" not in artifact_ids
    failure_artifact = next(
        artifact for artifact in manifest_payload["artifacts"] if artifact["artifact_id"] == "build-failure-compile"
    )
    assert failure_artifact["metadata"]["build_success"] is False
    assert failure_artifact["metadata"]["failure_stage"] == "compile"
    assert "pdflatex exited with code 1" in failure_artifact["metadata"]["errors"]


@pytest.mark.asyncio
async def test_build_paper_does_not_refresh_manifest_for_preserved_stale_tex(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "paper"
    output_dir.mkdir()
    config = _minimal_paper_config("Stale Manifest Paper", section_content="Fresh config content.")
    tex_path = output_dir / f"{derive_output_filename(config)}.tex"
    tex_path.write_text(
        "\\documentclass{article}\n\\begin{document}\nPreserved manual content.\n\\end{document}\n",
        encoding="utf-8",
    )
    existing_manifest = {
        "version": 1,
        "paper_title": "Old Manifest",
        "journal": "prl",
        "created_at": "2026-04-02T00:00:00+00:00",
        "artifacts": [],
    }
    manifest_path = output_dir / "ARTIFACT-MANIFEST.json"
    manifest_path.write_text(json.dumps(existing_manifest, indent=2) + "\n", encoding="utf-8")
    pdf_path = output_dir / f"{derive_output_filename(config)}.pdf"

    captured_compile_kwargs: dict[str, object] = {}

    async def fake_compile(tex_path, output_dir, compiler="pdflatex", **kwargs):
        captured_compile_kwargs.update(kwargs)
        pdf_path.write_bytes(b"%PDF-fake")
        return CompilationResult(success=True, pdf_path=pdf_path)

    monkeypatch.setattr("gpd.mcp.paper.compiler.check_journal_dependencies", lambda spec: (True, []))
    monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", fake_compile)

    result = await build_paper(config, output_dir)

    assert result.success is False
    assert result.manifest_path is None
    assert result.manifest is None
    assert json.loads(manifest_path.read_text(encoding="utf-8")) == existing_manifest
    assert any("ARTIFACT-MANIFEST.json was not refreshed" in error for error in result.errors)
    assert captured_compile_kwargs.get("apply_latex_autofix") is None


@pytest.mark.asyncio
async def test_build_paper_does_not_return_in_memory_manifest_for_preserved_stale_tex_when_sidecars_disabled(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "paper"
    output_dir.mkdir()
    config = _minimal_paper_config("Stale Manifest Paper", section_content="Fresh config content.")
    tex_path = output_dir / f"{derive_output_filename(config)}.tex"
    tex_path.write_text(
        "\\documentclass{article}\n\\begin{document}\nPreserved manual content.\n\\end{document}\n",
        encoding="utf-8",
    )
    pdf_path = output_dir / f"{derive_output_filename(config)}.pdf"

    async def fake_compile(tex_path, output_dir, compiler="pdflatex"):
        pdf_path.write_bytes(b"%PDF-fake")
        return CompilationResult(success=True, pdf_path=pdf_path)

    monkeypatch.setattr("gpd.mcp.paper.compiler.check_journal_dependencies", lambda spec: (True, []))
    monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", fake_compile)

    result = await build_paper(config, output_dir, emit_artifact_manifest=False)

    assert result.success is True
    assert result.manifest_path is None
    assert result.manifest is None
    assert not (output_dir / "ARTIFACT-MANIFEST.json").exists()


@pytest.mark.asyncio
async def test_build_paper_does_not_return_in_memory_manifest_when_sidecars_disabled(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_dir = tmp_path / "paper"
    output_dir.mkdir()
    config = _minimal_paper_config("Minimal Paper", section_content="Fresh content.")
    pdf_path = output_dir / f"{derive_output_filename(config)}.pdf"

    async def fake_compile(tex_path, output_dir, compiler="pdflatex"):
        pdf_path.write_bytes(b"%PDF-fake")
        return CompilationResult(success=True, pdf_path=pdf_path)

    monkeypatch.setattr("gpd.mcp.paper.compiler.check_journal_dependencies", lambda spec: (True, []))
    monkeypatch.setattr("gpd.mcp.paper.compiler.compile_paper", fake_compile)

    result = await build_paper(config, output_dir, emit_artifact_manifest=False)

    assert result.success is True
    assert result.manifest_path is None
    assert result.manifest is None
    assert not (output_dir / "ARTIFACT-MANIFEST.json").exists()


@pytest.mark.asyncio
async def test_build_paper_rejects_external_sidecar_root_when_emitting_manifest(tmp_path) -> None:
    config = _minimal_paper_config("External Sidecars")
    output_dir = tmp_path / "paper"
    external_sidecar_root = tmp_path / "paper-sidecars"

    with pytest.raises(ValueError, match="sidecar_root must stay inside output_dir"):
        await build_paper(config, output_dir, sidecar_root=external_sidecar_root)

    assert not external_sidecar_root.exists()


@pytest.mark.asyncio
async def test_build_paper_rejects_external_manifest_referenced_audit_path(tmp_path) -> None:
    config = _minimal_paper_config("External Audit")
    output_dir = tmp_path / "paper"
    external_audit_path = tmp_path / "external-meta" / "BIBLIOGRAPHY-AUDIT.json"

    with pytest.raises(ValueError, match="bibliography_audit_output_path must stay inside output_dir"):
        await build_paper(config, output_dir, bibliography_audit_output_path=external_audit_path)

    assert not external_audit_path.parent.exists()


# ---- Assertions for compiler imports and dead-code invariants ----


def test_figureref_is_importable_from_compiler_module() -> None:
    """FigureRef must be imported in compiler.py so the type annotation
    ``list[tuple[FigureRef, FigureRef]]`` resolves at runtime (Issue 1)."""
    import gpd.mcp.paper.compiler as compiler_mod

    assert hasattr(compiler_mod, "FigureRef"), "FigureRef should be importable from compiler module"
