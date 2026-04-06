"""Tests for arXiv source fallback mechanism."""

from __future__ import annotations

import gzip
import io
import tarfile
from unittest.mock import MagicMock, patch

import pytest

from gpd.core.arxiv_source_fallback import (
    ArxivSourceResult,
    _identify_main_tex,
    _validate_arxiv_id,
    extract_tex_from_tarball,
    fetch_arxiv_paper_text,
    fetch_arxiv_source,
    tex_to_text,
)


# ---------------------------------------------------------------------------
# arXiv ID validation
# ---------------------------------------------------------------------------


class TestValidateArxivId:
    def test_new_style_id(self):
        assert _validate_arxiv_id("2301.12345") == "2301.12345"

    def test_new_style_id_with_version(self):
        assert _validate_arxiv_id("2301.12345v2") == "2301.12345v2"

    def test_old_style_id(self):
        assert _validate_arxiv_id("hep-th/9901001") == "hep-th/9901001"

    def test_strips_arxiv_prefix(self):
        assert _validate_arxiv_id("arXiv:2301.12345") == "2301.12345"

    def test_strips_url_prefix(self):
        assert _validate_arxiv_id("https://arxiv.org/abs/2301.12345") == "2301.12345"

    def test_strips_whitespace(self):
        assert _validate_arxiv_id("  2301.12345  ") == "2301.12345"

    def test_rejects_invalid_id(self):
        with pytest.raises(ValueError, match="Invalid arXiv ID"):
            _validate_arxiv_id("not-an-id")

    def test_rejects_empty(self):
        with pytest.raises(ValueError, match="Invalid arXiv ID"):
            _validate_arxiv_id("")

    def test_rejects_partial_id(self):
        with pytest.raises(ValueError, match="Invalid arXiv ID"):
            _validate_arxiv_id("2301")


# ---------------------------------------------------------------------------
# tarball extraction
# ---------------------------------------------------------------------------


def _make_tar_gz(files: dict[str, str]) -> bytes:
    """Create an in-memory gzipped tarball from a dict of filename -> content."""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w:gz") as tar:
        for name, content in files.items():
            data = content.encode("utf-8")
            info = tarfile.TarInfo(name=name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return buf.getvalue()


def _make_gzipped_file(content: str) -> bytes:
    """Create a gzipped single file."""
    return gzip.compress(content.encode("utf-8"))


class TestExtractTexFromTarball:
    def test_extract_single_tex(self):
        tex = r"\documentclass{article}\begin{document}Hello\end{document}"
        data = _make_tar_gz({"paper.tex": tex})
        result = extract_tex_from_tarball(data)
        assert "paper.tex" in result
        assert "Hello" in result["paper.tex"]

    def test_extract_multiple_tex_files(self):
        files = {
            "main.tex": r"\documentclass{article}\begin{document}\input{intro}\end{document}",
            "intro.tex": r"\section{Introduction}Some text here.",
            "refs.bbl": r"\begin{thebibliography}{1}\bibitem{a} Author.\end{thebibliography}",
        }
        data = _make_tar_gz(files)
        result = extract_tex_from_tarball(data)
        assert len(result) == 3
        assert "main.tex" in result
        assert "intro.tex" in result
        assert "refs.bbl" in result

    def test_ignores_non_tex_files(self):
        files = {
            "main.tex": r"\documentclass{article}\begin{document}Hello\end{document}",
            "figure.png": "not actually a PNG",
            "README": "Some readme text",
        }
        data = _make_tar_gz(files)
        result = extract_tex_from_tarball(data)
        assert "main.tex" in result
        assert "figure.png" not in result
        assert "README" not in result

    def test_single_gzipped_tex(self):
        tex = r"\documentclass{article}\begin{document}Single file\end{document}"
        data = _make_gzipped_file(tex)
        result = extract_tex_from_tarball(data)
        assert "main.tex" in result
        assert "Single file" in result["main.tex"]

    def test_plain_tex(self):
        tex = r"\documentclass{article}\begin{document}Plain file\end{document}"
        data = tex.encode("utf-8")
        result = extract_tex_from_tarball(data)
        assert "main.tex" in result
        assert "Plain file" in result["main.tex"]

    def test_empty_data(self):
        result = extract_tex_from_tarball(b"")
        assert result == {}

    def test_garbage_data(self):
        result = extract_tex_from_tarball(b"\x00\x01\x02\x03random garbage")
        assert result == {}


# ---------------------------------------------------------------------------
# main TeX identification
# ---------------------------------------------------------------------------


class TestIdentifyMainTex:
    def test_documentclass_wins(self):
        files = {
            "foo.tex": r"\section{Foo}",
            "bar.tex": r"\documentclass{article}\begin{document}Main\end{document}",
        }
        assert _identify_main_tex(files) == "bar.tex"

    def test_main_tex_name(self):
        files = {
            "main.tex": r"\section{Main}",
            "appendix.tex": r"\section{Appendix}",
        }
        assert _identify_main_tex(files) == "main.tex"

    def test_paper_tex_name(self):
        files = {
            "paper.tex": r"\section{Paper}",
            "appendix.tex": r"\section{Appendix}",
        }
        assert _identify_main_tex(files) == "paper.tex"

    def test_largest_file_fallback(self):
        files = {
            "short.tex": "x",
            "long.tex": "x" * 1000,
        }
        assert _identify_main_tex(files) == "long.tex"

    def test_empty_returns_none(self):
        assert _identify_main_tex({}) is None

    def test_bbl_only_returns_none(self):
        assert _identify_main_tex({"refs.bbl": "content"}) is None


# ---------------------------------------------------------------------------
# TeX to text conversion
# ---------------------------------------------------------------------------


class TestTexToText:
    def test_basic_document(self):
        tex = r"""
\documentclass{article}
\begin{document}
\section{Introduction}
This is the introduction.
\end{document}
"""
        text = tex_to_text(tex)
        assert "Introduction" in text
        assert "This is the introduction." in text
        assert "\\documentclass" not in text

    def test_strips_comments(self):
        tex = r"""
\begin{document}
Real text. % This is a comment
More text.
\end{document}
"""
        text = tex_to_text(tex)
        assert "Real text." in text
        assert "This is a comment" not in text
        assert "More text." in text

    def test_converts_formatting(self):
        tex = r"\textbf{bold text} and \emph{emphasis}"
        text = tex_to_text(tex)
        assert "bold text" in text
        assert "emphasis" in text
        assert "\\textbf" not in text

    def test_strips_cite_commands(self):
        tex = r"See Smith~\cite{smith2020} and also \citep{jones2021}."
        text = tex_to_text(tex)
        assert "See Smith~" in text
        assert "\\cite" not in text

    def test_section_headings(self):
        tex = r"""
\section{Methods}
We used a method.
\subsection{Details}
Here are details.
"""
        text = tex_to_text(tex)
        assert "=== Methods ===" in text
        assert "=== Details ===" in text
        assert "We used a method." in text

    def test_abstract_environment(self):
        tex = r"""
\begin{document}
\begin{abstract}
This paper studies X.
\end{abstract}
\end{document}
"""
        text = tex_to_text(tex)
        assert "Abstract" in text
        assert "This paper studies X." in text

    def test_strips_figure_environment(self):
        tex = r"""
Some text before.
\begin{figure}
\includegraphics{fig1.png}
\caption{A figure.}
\end{figure}
Some text after.
"""
        text = tex_to_text(tex)
        assert "Some text before." in text
        assert "Some text after." in text
        assert "includegraphics" not in text

    def test_itemize(self):
        tex = r"""
\begin{itemize}
\item First point
\item Second point
\end{itemize}
"""
        text = tex_to_text(tex)
        assert "First point" in text
        assert "Second point" in text

    def test_equation_placeholder(self):
        tex = r"""
The energy is
\begin{equation}
E = mc^2
\end{equation}
which is famous.
"""
        text = tex_to_text(tex)
        assert "[equation]" in text
        assert "which is famous." in text

    def test_empty_input(self):
        assert tex_to_text("") == ""

    def test_no_document_environment(self):
        """TeX without begin/end document should still extract text."""
        tex = r"\section{Foo} Some content."
        text = tex_to_text(tex)
        assert "Foo" in text
        assert "Some content." in text


# ---------------------------------------------------------------------------
# fetch_arxiv_source (network mocked)
# ---------------------------------------------------------------------------


class TestFetchArxivSource:
    def test_successful_fetch(self):
        mock_response = MagicMock()
        mock_response.read.return_value = b"fake tarball data"
        mock_response.headers = {"Content-Length": "17"}
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("gpd.core.arxiv_source_fallback.urlopen", return_value=mock_response):
            data = fetch_arxiv_source("2301.12345")
        assert data == b"fake tarball data"

    def test_invalid_id_raises(self):
        with pytest.raises(ValueError, match="Invalid arXiv ID"):
            fetch_arxiv_source("garbage")

    def test_http_error_raises_connection_error(self):
        from urllib.error import HTTPError

        http_error = HTTPError(
            url="https://arxiv.org/e-print/2301.99999",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=io.BytesIO(b""),
        )
        with patch("gpd.core.arxiv_source_fallback.urlopen", side_effect=http_error):
            with pytest.raises(ConnectionError, match="HTTP 404"):
                fetch_arxiv_source("2301.99999")

    def test_oversized_response_raises(self):
        mock_response = MagicMock()
        mock_response.headers = {"Content-Length": str(100 * 1024 * 1024)}
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("gpd.core.arxiv_source_fallback.urlopen", return_value=mock_response):
            with pytest.raises(ConnectionError, match="exceeds size limit"):
                fetch_arxiv_source("2301.12345")


# ---------------------------------------------------------------------------
# fetch_arxiv_paper_text (integration, network mocked)
# ---------------------------------------------------------------------------


class TestFetchArxivPaperText:
    def test_successful_end_to_end(self):
        tex = r"""
\documentclass{article}
\begin{document}
\section{Introduction}
This paper studies quantum field theory.
\section{Methods}
We use perturbation theory.
\end{document}
"""
        tarball = _make_tar_gz({"paper.tex": tex})
        mock_response = MagicMock()
        mock_response.read.return_value = tarball
        mock_response.headers = {"Content-Length": str(len(tarball))}
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("gpd.core.arxiv_source_fallback.urlopen", return_value=mock_response):
            result = fetch_arxiv_paper_text("2301.12345")

        assert result.success is True
        assert result.arxiv_id == "2301.12345"
        assert result.main_tex_file == "paper.tex"
        assert "quantum field theory" in result.extracted_text
        assert "perturbation theory" in result.extracted_text
        assert result.error is None

    def test_invalid_arxiv_id(self):
        result = fetch_arxiv_paper_text("not-valid")
        assert result.success is False
        assert "Invalid arXiv ID" in (result.error or "")

    def test_network_failure(self):
        with patch(
            "gpd.core.arxiv_source_fallback.urlopen",
            side_effect=ConnectionError("network down"),
        ):
            result = fetch_arxiv_paper_text("2301.12345")
        assert result.success is False
        assert result.error is not None

    def test_no_tex_files(self):
        """Source archive with no TeX files."""
        data = _make_tar_gz({"README.md": "# No TeX here"})
        mock_response = MagicMock()
        mock_response.read.return_value = data
        mock_response.headers = {"Content-Length": str(len(data))}
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("gpd.core.arxiv_source_fallback.urlopen", return_value=mock_response):
            result = fetch_arxiv_paper_text("2301.12345")
        assert result.success is False
        assert "No TeX files" in (result.error or "")

    def test_include_all_files(self):
        files = {
            "main.tex": (
                r"\documentclass{article}"
                "\n"
                r"\begin{document}"
                "\n"
                r"\section{Overview}"
                "\n"
                "This is the main document overview text."
                "\n"
                r"\input{chap1}"
                "\n"
                r"\end{document}"
            ),
            "chap1.tex": r"\section{Chapter One}" "\n" "Chapter content here.",
        }
        tarball = _make_tar_gz(files)
        mock_response = MagicMock()
        mock_response.read.return_value = tarball
        mock_response.headers = {"Content-Length": str(len(tarball))}
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=False)

        with patch("gpd.core.arxiv_source_fallback.urlopen", return_value=mock_response):
            result = fetch_arxiv_paper_text("2301.12345", include_all_files=True)

        assert result.success is True
        assert "Chapter content here." in result.extracted_text

    def test_result_dataclass_fields(self):
        result = ArxivSourceResult(arxiv_id="2301.12345")
        assert result.tex_files == {}
        assert result.main_tex_file is None
        assert result.extracted_text == ""
        assert result.success is False
        assert result.error is None
