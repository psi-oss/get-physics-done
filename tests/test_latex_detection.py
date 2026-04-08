"""Tests for cross-platform LaTeX toolchain detection."""

from __future__ import annotations

import pytest

from gpd.mcp.paper.compiler import (
    detect_latex_toolchain,
    find_latex_compiler,
    get_latex_install_guidance,
)
from gpd.mcp.paper.models import PaperToolchainCapability


class TestFindLatexCompiler:
    def test_returns_path_when_compiler_on_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("gpd.mcp.paper.compiler._which", lambda _: "/usr/bin/pdflatex")
        assert find_latex_compiler("pdflatex") == "/usr/bin/pdflatex"

    def test_returns_none_when_not_found_on_non_windows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("gpd.mcp.paper.compiler._which", lambda _: None)
        monkeypatch.setattr("gpd.mcp.paper.compiler.platform.system", lambda: "Linux")
        assert find_latex_compiler("pdflatex") is None

    def test_searches_windows_paths_when_not_on_path(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("gpd.mcp.paper.compiler._which", lambda _: None)
        monkeypatch.setattr("gpd.mcp.paper.compiler.platform.system", lambda: "Windows")

        # Create a fake MiKTeX install directory
        miktex_bin = tmp_path / "MiKTeX" / "miktex" / "bin" / "x64"
        miktex_bin.mkdir(parents=True)
        (miktex_bin / "pdflatex.exe").write_text("fake", encoding="utf-8")

        monkeypatch.setattr(
            "gpd.mcp.paper.compiler._WINDOWS_LATEX_SEARCH_DIRS",
            [str(tmp_path / "MiKTeX" / "miktex" / "bin" / "x64")],
        )

        result = find_latex_compiler("pdflatex")
        assert result is not None
        assert "pdflatex.exe" in result

    def test_searches_texlive_year_dirs_on_windows(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("gpd.mcp.paper.compiler._which", lambda _: None)
        monkeypatch.setattr("gpd.mcp.paper.compiler.platform.system", lambda: "Windows")

        # Create a fake TeX Live install directory with year subdir
        tl_bin = tmp_path / "texlive" / "2024" / "bin" / "windows"
        tl_bin.mkdir(parents=True)
        (tl_bin / "pdflatex.exe").write_text("fake", encoding="utf-8")

        monkeypatch.setattr(
            "gpd.mcp.paper.compiler._WINDOWS_LATEX_SEARCH_DIRS",
            [str(tmp_path / "texlive")],
        )

        result = find_latex_compiler("pdflatex")
        assert result is not None
        assert "pdflatex.exe" in result


class TestDetectLatexToolchain:
    def test_available_on_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "gpd.mcp.paper.compiler._which",
            lambda compiler: "/usr/bin/pdflatex" if compiler == "pdflatex" else None,
        )
        status = detect_latex_toolchain()
        assert status.available is True
        assert status.compiler_path == "/usr/bin/pdflatex"
        assert status.distribution is not None

    def test_not_available(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("gpd.mcp.paper.compiler._which", lambda _: None)
        status = detect_latex_toolchain()
        assert status.available is False
        assert status.compiler_path is None
        assert "No LaTeX compiler found" in status.message

    def test_reports_full_readiness_when_core_and_helper_tools_are_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_find(binary: str) -> str | None:
            mapping = {
                "pdflatex": "/usr/bin/pdflatex",
                "bibtex": "/usr/bin/bibtex",
                "latexmk": "/usr/bin/latexmk",
                "kpsewhich": "/usr/bin/kpsewhich",
            }
            return mapping.get(binary)

        monkeypatch.setattr("gpd.mcp.paper.compiler._which", fake_find)

        status = detect_latex_toolchain()

        assert status.compiler_available is True
        assert status.available is True
        assert status.bibtex_available is True
        assert status.bibliography_support_available is True
        assert status.latexmk_available is True
        assert status.kpsewhich_available is True
        assert status.readiness_state == "ready"
        assert status.paper_build_ready is True
        assert status.arxiv_submission_ready is True
        assert "readiness=ready" in status.message

    def test_degrades_when_bibtex_is_missing_but_compiler_is_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_find(binary: str) -> str | None:
            mapping = {
                "pdflatex": "/usr/bin/pdflatex",
                "bibtex": None,
                "latexmk": None,
                "kpsewhich": None,
            }
            return mapping.get(binary)

        monkeypatch.setattr("gpd.mcp.paper.compiler._which", fake_find)

        status = detect_latex_toolchain()

        assert status.compiler_available is True
        assert status.available is True
        assert status.bibtex_available is False
        assert status.bibliography_support_available is False
        assert status.latexmk_available is False
        assert status.kpsewhich_available is False
        assert status.readiness_state == "degraded"
        assert status.paper_build_ready is True
        assert status.arxiv_submission_ready is False
        assert "BibTeX missing" in status.message
        assert status.warnings
        assert any("citation-bearing builds" in warning for warning in status.warnings)


class TestPaperToolchainCapability:
    def test_paper_build_requires_compiler_and_bibliography_support_is_tracked_separately(self) -> None:
        status = PaperToolchainCapability(
            compiler_available=True,
            bibtex_available=False,
            latexmk_available=True,
            kpsewhich_available=True,
        )

        assert status.paper_build_ready is True
        assert status.bibliography_support_available is False
        assert status.arxiv_submission_ready is False

        readiness = PaperToolchainCapability.model_validate(
            {
                **status.model_dump(mode="python"),
                "bibtex_available": True,
                "kpsewhich_available": False,
            }
        )

        assert readiness.bibliography_support_available is True
        assert readiness.paper_build_ready is True
        assert readiness.arxiv_submission_ready is False

    def test_blocks_when_compiler_is_missing_even_if_helpers_are_present(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        def fake_find(binary: str) -> str | None:
            mapping = {
                "pdflatex": None,
                "bibtex": "/usr/bin/bibtex",
                "latexmk": "/usr/bin/latexmk",
                "kpsewhich": "/usr/bin/kpsewhich",
            }
            return mapping.get(binary)

        monkeypatch.setattr("gpd.mcp.paper.compiler._which", fake_find)

        status = detect_latex_toolchain()

        assert status.compiler_available is False
        assert status.available is False
        assert status.bibtex_available is True
        assert status.bibliography_support_available is False
        assert status.latexmk_available is True
        assert status.kpsewhich_available is True
        assert status.readiness_state == "blocked"
        assert status.paper_build_ready is False
        assert status.arxiv_submission_ready is False
        assert "No LaTeX compiler found" in status.message

    def test_detects_miktex_distribution(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "gpd.mcp.paper.compiler._which",
            lambda compiler: "C:\\Users\\user\\AppData\\Local\\Programs\\MiKTeX\\miktex\\bin\\x64\\pdflatex.exe"
            if compiler == "pdflatex"
            else None,
        )
        status = detect_latex_toolchain()
        assert status.available is True
        assert status.distribution == "MiKTeX"

    def test_detects_texlive_distribution(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "gpd.mcp.paper.compiler._which",
            lambda compiler: "C:\\texlive\\2024\\bin\\windows\\pdflatex.exe" if compiler == "pdflatex" else None,
        )
        status = detect_latex_toolchain()
        assert status.available is True
        assert status.distribution == "TeX Live"

    def test_detects_mactex_distribution(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "gpd.mcp.paper.compiler._which",
            lambda compiler: "/Library/TeX/texbin/pdflatex" if compiler == "pdflatex" else None,
        )
        status = detect_latex_toolchain()
        assert status.available is True
        assert status.distribution == "MacTeX"


class TestGetLatexInstallGuidance:
    def test_windows_guidance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("gpd.mcp.paper.compiler.platform.system", lambda: "Windows")
        msg = get_latex_install_guidance()
        assert "MiKTeX" in msg
        assert "miktex.org" in msg
        assert "TeX Live" in msg

    def test_macos_guidance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("gpd.mcp.paper.compiler.platform.system", lambda: "Darwin")
        msg = get_latex_install_guidance()
        assert "MacTeX" in msg or "mactex" in msg
        assert "brew" in msg

    def test_linux_guidance(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("gpd.mcp.paper.compiler.platform.system", lambda: "Linux")
        msg = get_latex_install_guidance()
        assert "texlive" in msg
        assert "apt" in msg


class TestCompilePaperMissingCompiler:
    def test_compile_paper_returns_guidance_when_compiler_missing(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """compile_paper returns install guidance when no compiler is found."""
        import asyncio

        from gpd.mcp.paper.compiler import compile_paper

        tex_path = tmp_path / "paper.tex"
        tex_path.write_text(r"\documentclass{article}\begin{document}test\end{document}", encoding="utf-8")

        monkeypatch.setattr("gpd.mcp.paper.compiler.find_latex_compiler", lambda compiler: None)
        monkeypatch.setattr("gpd.mcp.paper.compiler.platform.system", lambda: "Windows")

        result = asyncio.run(compile_paper(tex_path, tmp_path))
        assert result.success is False
        assert "not found" in result.error
        assert "MiKTeX" in result.error
