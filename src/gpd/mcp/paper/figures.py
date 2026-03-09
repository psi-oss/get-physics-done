"""Figure pipeline: format normalization, journal sizing, captions.

Accepts images in various formats from MCP outputs, normalizes them
to PDF (vector) or PNG (raster), sizes them for the target journal,
and generates LaTeX embedding snippets.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path

from gpd.mcp.paper.journal_map import get_journal_spec
from gpd.mcp.paper.models import FigureRef

logger = logging.getLogger(__name__)

SUPPORTED_FORMATS: set[str] = {"pdf", "png", "jpg", "jpeg", "svg", "tiff", "tif", "eps"}
PASSTHROUGH_FORMATS: set[str] = {"pdf", "png", "jpg", "jpeg"}


def detect_format(path: Path) -> str:
    """Return the lowercase file extension.

    Raises:
        ValueError: If the format is not in SUPPORTED_FORMATS.
    """
    ext = path.suffix.lstrip(".").lower()
    if ext not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported figure format: {ext!r} (from {path}). Supported: {SUPPORTED_FORMATS}")
    return ext


def normalize_figure(source: Path, output_dir: Path, target_format: str = "png") -> Path:
    """Normalize a figure to a pdflatex-compatible format.

    - PDF/PNG/JPG: copy as-is (passthrough)
    - SVG: convert to PDF via cairosvg or inkscape
    - TIFF/TIF: convert to PNG via Pillow
    - EPS: copy as-is (epstopdf handles conversion)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    fmt = detect_format(source)

    if fmt in PASSTHROUGH_FORMATS:
        dest = output_dir / source.name
        shutil.copy2(source, dest)
        return dest

    if fmt in ("svg",):
        return _convert_svg(source, output_dir)

    if fmt in ("tiff", "tif"):
        return _convert_tiff(source, output_dir)

    if fmt == "eps":
        # pdflatex auto-converts EPS via epstopdf
        dest = output_dir / source.name
        shutil.copy2(source, dest)
        logger.info("EPS file copied; epstopdf will handle conversion during compilation: %s", source.name)
        return dest

    raise ValueError(f"No conversion path for format: {fmt}")


def _convert_svg(source: Path, output_dir: Path) -> Path:
    """Convert SVG to PDF using cairosvg or inkscape."""
    dest = output_dir / f"{source.stem}.pdf"

    # Try cairosvg first
    try:
        import cairosvg

        cairosvg.svg2pdf(url=str(source), write_to=str(dest))
        return dest
    except ImportError:
        pass

    # Fall back to inkscape
    try:
        subprocess.run(
            ["inkscape", str(source), f"--export-filename={dest}"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        return dest
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        pass

    raise RuntimeError(f"SVG conversion requires cairosvg (pip install cairosvg) or inkscape. Cannot convert: {source}")


def _convert_tiff(source: Path, output_dir: Path) -> Path:
    """Convert TIFF to PNG using Pillow."""
    from PIL import Image

    dest = output_dir / f"{source.stem}.png"
    with Image.open(source) as img:
        img.save(dest, "PNG")
    return dest


# ---- Journal-specific sizing ----


def get_figure_width(journal: str, double_column: bool = False) -> str:
    """Return LaTeX width command string for the journal."""
    if double_column:
        return r"\textwidth"
    return r"\columnwidth"


def get_dpi_for_journal(journal: str) -> int:
    """Return the minimum DPI requirement for the journal."""
    spec = get_journal_spec(journal)
    return spec.dpi


def check_figure_resolution(path: Path, journal: str) -> tuple[bool, str]:
    """Check if a raster figure meets the journal's resolution requirement.

    For vector formats (PDF, SVG, EPS), always passes.
    For raster formats, checks if pixel width >= column_width_cm * dpi / 2.54.

    Returns:
        (passes, message) tuple.
    """
    fmt = detect_format(path)
    if fmt in ("pdf", "svg", "eps"):
        return True, "vector format"

    spec = get_journal_spec(journal)
    min_width_px = int(spec.column_width_cm * spec.dpi / 2.54)

    try:
        from PIL import Image

        with Image.open(path) as img:
            width_px = img.size[0]
            if width_px >= min_width_px:
                return True, f"width {width_px}px >= {min_width_px}px required"
            return False, f"width {width_px}px < {min_width_px}px required for {journal} at {spec.dpi} DPI"
    except (ImportError, OSError) as exc:
        return True, f"cannot check resolution: {exc}"


# ---- LaTeX figure snippet generation ----


def generate_figure_latex(fig: FigureRef, journal: str) -> str:
    """Generate a LaTeX figure block for a FigureRef."""
    env = "figure*" if fig.double_column else "figure"
    return (
        f"\\begin{{{env}}}\n"
        f"\\includegraphics[width={fig.width}]{{{fig.path}}}\n"
        f"\\caption{{{fig.caption}}}\n"
        f"\\label{{fig:{fig.label}}}\n"
        f"\\end{{{env}}}"
    )


# ---- Batch processing ----


def prepare_figures(figures: list[FigureRef], output_dir: Path, journal: str) -> list[FigureRef]:
    """Normalize and size all figures for a given journal.

    For each figure:
    1. Normalize format to output_dir
    2. Check resolution, log warning if below journal minimum
    3. Update FigureRef.path to normalized file
    4. Set FigureRef.width based on journal and double_column flag
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    result: list[FigureRef] = []

    for fig in figures:
        # Normalize
        normalized_path = normalize_figure(fig.path, output_dir)

        # Check resolution
        passes, msg = check_figure_resolution(normalized_path, journal)
        if not passes:
            logger.warning("Figure %s below resolution requirement: %s", fig.label, msg)

        # Update width
        width = get_figure_width(journal, fig.double_column)

        updated = fig.model_copy(
            update={
                "path": normalized_path,
                "width": width,
            }
        )
        result.append(updated)

    return result
