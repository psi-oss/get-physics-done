"""Regression tests for paper compilation error handling."""

from __future__ import annotations

import pytest

from gpd.mcp.paper.compiler import _compile_manual_multipass, _compile_with_latexmk
from gpd.utils.latex import AutoFixResult


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

    result = await _compile_with_latexmk(tex_path, tmp_path, "pdflatex")

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
    monkeypatch.setattr("gpd.mcp.paper.compiler.shutil.which", fake_which)

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
    monkeypatch.setattr("gpd.mcp.paper.compiler.shutil.which", fake_which)
    monkeypatch.setattr("gpd.utils.latex.try_autofix", lambda tex, log: AutoFixResult())

    result = await _compile_manual_multipass(tex_path, tmp_path, "pdflatex")

    assert result.success is False
    assert result.pdf_path is None
    assert result.error == "bibtex exited with code 2"
    assert result.log is not None
    assert "compile output" in result.log


@pytest.mark.asyncio
async def test_manual_multipass_rejects_stale_preexisting_pdf(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
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
    monkeypatch.setattr("gpd.mcp.paper.compiler.shutil.which", fake_which)
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
    monkeypatch.setattr("gpd.mcp.paper.compiler.shutil.which", fake_which)

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
    monkeypatch.setattr("gpd.mcp.paper.compiler.shutil.which", fake_which)
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
    monkeypatch.setattr("gpd.mcp.paper.compiler.shutil.which", fake_which)
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


# ---- Regression tests for import and dead-code fixes ----


def test_figureref_is_importable_from_compiler_module() -> None:
    """FigureRef must be imported in compiler.py so the type annotation
    ``list[tuple[FigureRef, FigureRef]]`` resolves at runtime (Issue 1)."""
    import gpd.mcp.paper.compiler as compiler_mod

    assert hasattr(compiler_mod, "FigureRef"), (
        "FigureRef should be importable from compiler module"
    )


def test_no_original_figures_dead_code() -> None:
    """The local variable ``original_figures`` was assigned but never used.
    Verify it no longer appears in the build_paper source (Issue 2)."""
    import inspect

    from gpd.mcp.paper.compiler import build_paper

    source = inspect.getsource(build_paper)
    assert "original_figures" not in source, (
        "Dead-code variable 'original_figures' should have been removed"
    )
