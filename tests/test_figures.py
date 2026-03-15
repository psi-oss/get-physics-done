"""Tests for figure pipeline."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from gpd.mcp.paper.figures import (
    check_figure_resolution,
    detect_format,
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

    def test_normalize_passthrough_same_file_is_noop(self, tmp_path):
        out = tmp_path / "output"
        out.mkdir()
        src = out / "fig.png"
        Image.new("RGB", (10, 10), color="purple").save(src)

        result = normalize_figure(src, out)

        assert result == src
        assert result.exists()

    def test_normalize_svg_no_converter(self, tmp_path, monkeypatch):
        src = tmp_path / "input" / "fig.svg"
        src.parent.mkdir()
        src.write_text("<svg></svg>")

        out = tmp_path / "output"

        # Monkeypatch cairosvg to not be available
        import subprocess
        import sys

        monkeypatch.setitem(sys.modules, "cairosvg", None)

        # Mock subprocess.run to simulate inkscape not found
        _original_run = subprocess.run

        def _mock_run(args, **kwargs):
            if args and args[0] == "inkscape":
                raise FileNotFoundError("inkscape not found")
            return _original_run(args, **kwargs)

        monkeypatch.setattr("subprocess.run", _mock_run)

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

    def test_check_resolution_double_column_uses_double_width(self, tmp_path):
        png = tmp_path / "wide-ish.png"
        Image.new("RGB", (2500, 50)).save(png)

        single_passes, single_msg = check_figure_resolution(png, "prl")
        double_passes, double_msg = check_figure_resolution(png, "prl", double_column=True)

        assert single_passes is True
        assert "single-column" in single_msg
        assert double_passes is False
        assert "double-column" in double_msg

    def test_check_resolution_rejects_corrupt_raster(self, tmp_path):
        png = tmp_path / "corrupt.png"
        png.write_bytes(b"not-a-real-png")

        passes, msg = check_figure_resolution(png, "prl")

        assert passes is False
        assert "cannot decode raster image" in msg


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
        result, errs = prepare_figures(figures, out, "prl")
        assert len(result) == 2
        assert errs == []
        for fig in result:
            resolved = out / fig.path if not fig.path.is_absolute() else fig.path
            assert resolved.exists()
            assert resolved.parent == out

    def test_prepare_figures_warns_for_underresolved_double_column(self, tmp_path, caplog):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        src = input_dir / "wide-ish.png"
        Image.new("RGB", (2500, 100), color="green").save(src)

        figures = [
            FigureRef(path=src, caption="Wide Fig", label="wide", double_column=True),
        ]

        with caplog.at_level("WARNING"):
            result, errs = prepare_figures(figures, tmp_path / "output", "prl")

        assert len(result) == 1
        assert any("double-column width" in message for message in caplog.messages)

    def test_prepare_figures_keeps_valid_figures_when_one_fails_normalization(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        good = input_dir / "good.png"
        Image.new("RGB", (100, 100), color="green").save(good)
        bad = input_dir / "bad.gif"
        bad.write_bytes(b"GIF89a")

        figures = [
            FigureRef(path=good, caption="Good figure", label="good"),
            FigureRef(path=bad, caption="Bad figure", label="bad"),
        ]

        result, errs = prepare_figures(figures, tmp_path / "output", "prl")

        assert len(result) == 1
        assert result[0].label == "good"
        assert any("Figure preparation failed for" in err for err in errs)
        assert any("Unsupported figure format" in err for err in errs)

    def test_prepare_figures_drops_corrupt_raster_inputs(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()

        good = input_dir / "good.png"
        Image.new("RGB", (2100, 100), color="green").save(good)
        corrupt = input_dir / "corrupt.png"
        corrupt.write_bytes(b"not-a-real-png")

        figures = [
            FigureRef(path=good, caption="Good figure", label="good"),
            FigureRef(path=corrupt, caption="Corrupt figure", label="corrupt"),
        ]

        result, errs = prepare_figures(figures, tmp_path / "output", "prl")

        assert len(result) == 1
        assert result[0].label == "good"
        assert any("cannot decode raster image" in err for err in errs)


# ---- Exception chaining regression ----


class TestTiffConversionExceptionChaining:
    def test_tiff_missing_pillow_raises_from_none(self, tmp_path, monkeypatch):
        """When Pillow is missing, _convert_tiff should raise RuntimeError
        *without* chaining the original ImportError (from None), so the
        traceback stays clean (Issue 3)."""
        import sys

        # Make 'from PIL import Image' raise ImportError
        monkeypatch.setitem(sys.modules, "PIL", None)
        monkeypatch.setitem(sys.modules, "PIL.Image", None)

        source = tmp_path / "fig.tiff"
        source.write_bytes(b"fake-tiff-data")

        from gpd.mcp.paper.figures import _convert_tiff

        with pytest.raises(RuntimeError, match="TIFF conversion requires Pillow") as exc_info:
            _convert_tiff(source, tmp_path / "output")

        # __cause__ is None when 'from None' is used
        assert exc_info.value.__cause__ is None
        # __suppress_context__ is True when 'from None' is used
        assert exc_info.value.__suppress_context__ is True
