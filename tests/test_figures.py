"""Tests for figure pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from gpd.mcp.paper.figures import (
    check_figure_resolution,
    detect_format,
    generate_figure_latex,
    get_dpi_for_journal,
    get_figure_width,
    normalize_figure,
    prepare_figures,
)
from gpd.mcp.paper.models import FigureRef

# ---- Format detection ----


class TestFormatDetection:
    def test_detect_png(self):
        assert detect_format(Path("fig.png")) == "png"

    def test_detect_pdf_uppercase(self):
        assert detect_format(Path("fig.PDF")) == "pdf"

    def test_detect_unsupported_raises(self):
        with pytest.raises(ValueError, match="Unsupported figure format"):
            detect_format(Path("fig.docx"))


# ---- Normalization ----


class TestNormalization:
    def test_normalize_png_passthrough(self, tmp_path):
        # Create a real 10x10 PNG
        src = tmp_path / "input" / "fig.png"
        src.parent.mkdir()
        Image.new("RGB", (10, 10), color="red").save(src)

        out = tmp_path / "output"
        result = normalize_figure(src, out)
        assert result.exists()
        assert result.parent == out

    def test_normalize_tiff_to_png(self, tmp_path):
        src = tmp_path / "input" / "fig.tiff"
        src.parent.mkdir()
        Image.new("RGB", (10, 10), color="blue").save(src, "TIFF")

        out = tmp_path / "output"
        result = normalize_figure(src, out)
        assert result.exists()
        assert result.suffix == ".png"

    def test_normalize_svg_no_converter(self, tmp_path, monkeypatch):
        src = tmp_path / "input" / "fig.svg"
        src.parent.mkdir()
        src.write_text("<svg></svg>")

        out = tmp_path / "output"

        # Monkeypatch cairosvg to not be available
        import sys

        monkeypatch.setitem(sys.modules, "cairosvg", None)
        # Also make inkscape not found
        monkeypatch.setattr("shutil.which", lambda x: None)

        with pytest.raises(RuntimeError, match="SVG conversion requires"):
            normalize_figure(src, out)


# ---- Sizing ----


class TestSizing:
    def test_figure_width_single_column(self):
        assert "columnwidth" in get_figure_width("prl")

    def test_figure_width_double_column(self):
        assert "textwidth" in get_figure_width("prl", double_column=True)

    def test_dpi_for_journal(self):
        assert get_dpi_for_journal("prl") == 600
        assert get_dpi_for_journal("apj") == 300


# ---- Resolution check ----


class TestResolutionCheck:
    def test_check_resolution_vector_always_passes(self, tmp_path):
        pdf = tmp_path / "fig.pdf"
        pdf.write_bytes(b"%PDF-1.4 fake")
        passes, msg = check_figure_resolution(pdf, "prl")
        assert passes is True
        assert "vector" in msg

    def test_check_resolution_low_res_warns(self, tmp_path):
        # PRL requires 600 DPI, column 8.6cm = ~2031 px minimum
        # A 50x50 PNG should fail
        png = tmp_path / "tiny.png"
        Image.new("RGB", (50, 50)).save(png)
        passes, msg = check_figure_resolution(png, "prl")
        assert passes is False


# ---- LaTeX generation ----


class TestLatexGeneration:
    def test_generate_figure_latex_single(self):
        fig = FigureRef(path=Path("figures/fig01.pdf"), caption="Velocity field.", label="velocity")
        latex = generate_figure_latex(fig, "prl")
        assert r"\begin{figure}" in latex
        assert r"\includegraphics" in latex
        assert r"\caption{Velocity field.}" in latex
        assert r"\label{fig:velocity}" in latex
        assert r"\end{figure}" in latex

    def test_generate_figure_latex_double(self):
        fig = FigureRef(
            path=Path("figures/fig02.pdf"),
            caption="Wide figure.",
            label="wide",
            double_column=True,
        )
        latex = generate_figure_latex(fig, "prl")
        assert r"\begin{figure*}" in latex
        assert r"\end{figure*}" in latex

    def test_generate_figure_latex_caption_escaped(self):
        fig = FigureRef(path=Path("fig.pdf"), caption="Value of $\\alpha$ vs time.", label="alpha")
        latex = generate_figure_latex(fig, "prl")
        assert r"\caption{Value of $\alpha$ vs time.}" in latex


# ---- Batch processing ----


class TestPrepare:
    def test_prepare_figures_batch(self, tmp_path):
        # Create 2 real PNG files
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        for i in range(2):
            Image.new("RGB", (100, 100), color="green").save(input_dir / f"fig{i}.png")

        figures = [
            FigureRef(path=input_dir / "fig0.png", caption="Fig 0", label="f0"),
            FigureRef(path=input_dir / "fig1.png", caption="Fig 1", label="f1"),
        ]

        out = tmp_path / "output"
        result = prepare_figures(figures, out, "prl")
        assert len(result) == 2
        for fig in result:
            assert fig.path.exists()
            assert fig.path.parent == out
