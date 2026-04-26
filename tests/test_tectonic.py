"""Tests for Tectonic TeX engine support.

Verifies:
- find_tectonic() returns a path when tectonic is on PATH
- detect_latex_toolchain(prefer_tectonic=True) reports readiness_state="ready"
  when Tectonic is available, even without separate bibtex
- compile_paper routes through _compile_with_tectonic when tectonic is found
- compile_paper falls back to the pdflatex path when tectonic is absent
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

from gpd.mcp.paper.compiler import (
    compile_paper,
    detect_latex_toolchain,
    find_tectonic,
)
from gpd.mcp.paper.models import PaperToolchainCapability

# ---------------------------------------------------------------------------
# find_tectonic
# ---------------------------------------------------------------------------


class TestFindTectonic:
    def test_returns_path_when_on_path(self):
        with patch("gpd.mcp.paper.compiler._which", return_value="/usr/local/bin/tectonic"):
            result = find_tectonic()
        assert result == "/usr/local/bin/tectonic"

    def test_returns_none_when_not_found_on_non_windows(self):
        with (
            patch("gpd.mcp.paper.compiler._which", return_value=None),
            patch("gpd.mcp.paper.compiler.platform.system", return_value="Darwin"),
        ):
            result = find_tectonic()
        assert result is None

    def test_windows_localappdata_fallback(self, tmp_path):
        fake_exe = tmp_path / "Programs" / "Tectonic" / "tectonic.exe"
        fake_exe.parent.mkdir(parents=True)
        fake_exe.touch()

        with (
            patch("gpd.mcp.paper.compiler._which", return_value=None),
            patch("gpd.mcp.paper.compiler.platform.system", return_value="Windows"),
            patch.dict("os.environ", {"LOCALAPPDATA": str(tmp_path)}, clear=False),
        ):
            result = find_tectonic()
        assert result == str(fake_exe)

    def test_windows_cargo_bin_fallback(self, tmp_path):
        cargo_bin = tmp_path / ".cargo" / "bin"
        cargo_bin.mkdir(parents=True)
        fake_exe = cargo_bin / "tectonic.exe"
        fake_exe.touch()

        with (
            patch("gpd.mcp.paper.compiler._which", return_value=None),
            patch("gpd.mcp.paper.compiler.platform.system", return_value="Windows"),
            patch.dict("os.environ", {"LOCALAPPDATA": ""}, clear=False),
            patch("os.path.expanduser", return_value=str(tmp_path)),
        ):
            result = find_tectonic()
        assert result == str(fake_exe)


# ---------------------------------------------------------------------------
# detect_latex_toolchain with prefer_tectonic=True
# ---------------------------------------------------------------------------


class TestDetectLatexToolchainTectonic:
    def test_ready_when_tectonic_found_without_bibtex(self):
        """Tectonic alone should yield readiness_state='ready'."""
        with (
            patch("gpd.mcp.paper.compiler.find_tectonic", return_value="/usr/bin/tectonic"),
            patch("gpd.mcp.paper.compiler.find_latex_compiler", return_value=None),
        ):
            status = detect_latex_toolchain(prefer_tectonic=True)

        assert status.tectonic_available is True
        assert status.tectonic_path == "/usr/bin/tectonic"
        assert status.readiness_state == "ready"
        assert status.compiler == "tectonic"
        assert status.compiler_available is True
        assert status.distribution == "Tectonic"

    def test_tectonic_fields_on_model_validator(self):
        """PaperToolchainCapability.available reflects Tectonic even without pdflatex."""
        capability = PaperToolchainCapability(
            compiler="tectonic",
            compiler_available=True,
            compiler_path="/usr/bin/tectonic",
            distribution="Tectonic",
            tectonic_available=True,
            tectonic_path="/usr/bin/tectonic",
            bibtex_available=False,
            latexmk_available=False,
            kpsewhich_available=False,
            pdftotext_available=False,
            readiness_state="ready",
            message="Tectonic found",
        )
        assert capability.available is True
        assert capability.paper_build_ready is True
        assert capability.bibliography_support_available is True
        assert capability.readiness_state == "ready"

    def test_prefer_tectonic_false_ignores_tectonic(self):
        """When prefer_tectonic=False, Tectonic is not checked."""
        with (
            patch("gpd.mcp.paper.compiler.find_tectonic", return_value="/usr/bin/tectonic") as mock_tectonic,
            patch("gpd.mcp.paper.compiler.find_latex_compiler", return_value=None),
        ):
            status = detect_latex_toolchain(prefer_tectonic=False)

        mock_tectonic.assert_not_called()
        assert status.readiness_state == "blocked"

    def test_falls_back_to_pdflatex_when_tectonic_absent(self):
        """When Tectonic is absent and pdflatex+bibtex are present, use normal path."""
        def _fake_find(binary="pdflatex"):
            return f"/usr/bin/{binary}"

        with (
            patch("gpd.mcp.paper.compiler.find_tectonic", return_value=None),
            patch("gpd.mcp.paper.compiler.find_latex_compiler", side_effect=_fake_find),
        ):
            status = detect_latex_toolchain(prefer_tectonic=True)

        assert status.tectonic_available is False
        assert status.compiler == "pdflatex"
        assert status.readiness_state == "ready"


# ---------------------------------------------------------------------------
# compile_paper routing
# ---------------------------------------------------------------------------


class TestCompilePaperRouting:
    def test_routes_to_tectonic_when_available(self, tmp_path):
        """compile_paper should call _compile_with_tectonic when tectonic is found."""
        tex_file = tmp_path / "paper.tex"
        tex_file.write_text(r"\documentclass{article}\begin{document}Hello\end{document}")

        from gpd.mcp.paper.compiler import CompilationResult

        fake_result = CompilationResult(success=True, pdf_path=tmp_path / "paper.pdf")

        with (
            patch("gpd.mcp.paper.compiler.find_tectonic", return_value="/usr/bin/tectonic"),
            patch("gpd.mcp.paper.compiler._compile_with_tectonic", new=AsyncMock(return_value=fake_result)) as mock_tec,
        ):
            result = asyncio.run(compile_paper(tex_file, tmp_path, prefer_tectonic=True))

        mock_tec.assert_called_once_with(tex_file, tmp_path, tectonic_path="/usr/bin/tectonic")
        assert result.success is True

    def test_falls_back_to_pdflatex_when_tectonic_absent(self, tmp_path):
        """compile_paper should use the pdflatex path when tectonic is not found."""
        tex_file = tmp_path / "paper.tex"
        tex_file.write_text(r"\documentclass{article}\begin{document}Hello\end{document}")

        from gpd.mcp.paper.compiler import CompilationResult

        fake_result = CompilationResult(success=True, pdf_path=tmp_path / "paper.pdf")

        with (
            patch("gpd.mcp.paper.compiler.find_tectonic", return_value=None),
            patch("gpd.mcp.paper.compiler.find_latex_compiler", return_value="/usr/bin/pdflatex"),
            patch("gpd.mcp.paper.compiler._compile_with_latexmk", new=AsyncMock(return_value=fake_result)) as mock_lmk,
        ):
            result = asyncio.run(compile_paper(tex_file, tmp_path, prefer_tectonic=True))

        mock_lmk.assert_called_once()
        assert result.success is True

    def test_prefer_tectonic_false_skips_tectonic(self, tmp_path):
        """When prefer_tectonic=False, tectonic is never consulted."""
        tex_file = tmp_path / "paper.tex"
        tex_file.write_text(r"\documentclass{article}\begin{document}Hello\end{document}")

        from gpd.mcp.paper.compiler import CompilationResult

        fake_result = CompilationResult(success=True, pdf_path=tmp_path / "paper.pdf")

        with (
            patch("gpd.mcp.paper.compiler.find_tectonic", return_value="/usr/bin/tectonic") as mock_find_tec,
            patch("gpd.mcp.paper.compiler.find_latex_compiler", return_value="/usr/bin/pdflatex"),
            patch("gpd.mcp.paper.compiler._compile_with_latexmk", new=AsyncMock(return_value=fake_result)),
        ):
            asyncio.run(compile_paper(tex_file, tmp_path, prefer_tectonic=False))

        mock_find_tec.assert_not_called()

    def test_returns_error_when_no_compiler_at_all(self, tmp_path):
        """Returns a failure result when neither tectonic nor pdflatex is found."""
        tex_file = tmp_path / "paper.tex"
        tex_file.write_text(r"\documentclass{article}\begin{document}Hello\end{document}")

        with (
            patch("gpd.mcp.paper.compiler.find_tectonic", return_value=None),
            patch("gpd.mcp.paper.compiler.find_latex_compiler", return_value=None),
        ):
            result = asyncio.run(compile_paper(tex_file, tmp_path, prefer_tectonic=True))

        assert result.success is False
        assert result.error is not None
