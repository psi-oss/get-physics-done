"""Figure pipeline: format normalization, journal sizing, captions.

Accepts images in various formats from MCP outputs, normalizes them
to PDF (vector) or PNG (raster), sizes them for the target journal,
and generates LaTeX embedding snippets.
"""

from __future__ import annotations

import logging
import math
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


def _unique_dest(output_dir: Path, source: Path) -> Path:
    """Return a unique destination path, adding a numeric suffix if needed."""
    dest = output_dir / source.name
    if not dest.exists() or source.resolve() == dest.resolve():
        return dest
    stem = source.stem
    suffix = source.suffix
    counter = 1
    while dest.exists():
        dest = output_dir / f"{stem}_{counter}{suffix}"
        counter += 1
    return dest


def normalize_figure(source: Path, output_dir: Path) -> Path:
    """Normalize a figure to a pdflatex-compatible format.

    - PDF/PNG/JPG: copy as-is (passthrough)
    - SVG: convert to PDF via cairosvg or inkscape
    - TIFF/TIF: convert to PNG via Pillow
    - EPS: copy as-is (epstopdf handles conversion)
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    fmt = detect_format(source)

    if fmt in PASSTHROUGH_FORMATS:
        dest = _unique_dest(output_dir, source)
        if source.resolve() == dest.resolve():
            return dest
        shutil.copy2(source, dest)
        return dest

    if fmt in ("svg",):
        return _convert_svg(source, output_dir)

    if fmt in ("tiff", "tif"):
        return _convert_tiff(source, output_dir)

    if fmt == "eps":
        # pdflatex auto-converts EPS via epstopdf
        dest = _unique_dest(output_dir, source)
        if source.resolve() == dest.resolve():
            return dest
        shutil.copy2(source, dest)
        logger.info("EPS file copied; epstopdf will handle conversion during compilation: %s", source.name)
        return dest

    raise ValueError(f"No conversion path for format: {fmt}")


def _convert_svg(source: Path, output_dir: Path) -> Path:
    """Convert SVG to PDF using cairosvg or inkscape."""
    dest = _unique_dest(output_dir, Path(f"{source.stem}.pdf"))

    # Try cairosvg first
    try:
        import cairosvg

        cairosvg.svg2pdf(url=str(source), write_to=str(dest))
        return dest
    except ImportError:
        pass
    except Exception:
        if dest.exists():
            dest.unlink()

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
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError(f"TIFF conversion requires Pillow (pip install Pillow). Cannot convert: {source}") from None

    dest = _unique_dest(output_dir, Path(f"{source.stem}.png"))
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


def check_figure_resolution(path: Path, journal: str, double_column: bool = False) -> tuple[bool, str]:
    """Check if a raster figure meets the journal's resolution requirement.

    For vector formats (PDF, SVG, EPS), always passes.
    For raster formats, checks against the single- or double-column target width.

    Returns:
        (passes, message) tuple.
    """
    fmt = detect_format(path)
    if fmt in ("pdf", "svg", "eps"):
        return True, "vector format"

    spec = get_journal_spec(journal)
    target_width_cm = spec.double_width_cm if double_column else spec.column_width_cm
    layout = "double-column" if double_column else "single-column"
    min_width_px = math.ceil(target_width_cm * spec.dpi / 2.54)

    try:
        from PIL import Image

        with Image.open(path) as img:
            width_px = img.size[0]
            if width_px >= min_width_px:
                return True, f"{layout} width {width_px}px >= {min_width_px}px required"
            return False, f"{layout} width {width_px}px < {min_width_px}px required for {journal} at {spec.dpi} DPI"
    except ImportError as exc:
        return True, f"cannot check resolution: {exc}"
    except OSError as exc:
        return False, f"cannot decode raster image: {exc}"


# ---- Batch processing ----


def _prepare_figures_with_sources(
    figures: list[FigureRef],
    output_dir: Path,
    journal: str,
) -> tuple[list[FigureRef], list[str], list[tuple[FigureRef, FigureRef]]]:
    """Prepare figures while preserving the original-to-output mapping."""
    output_dir.mkdir(parents=True, exist_ok=True)
    result: list[FigureRef] = []
    errors: list[str] = []
    source_pairs: list[tuple[FigureRef, FigureRef]] = []

    for fig in figures:
        if not fig.path.exists():
            errors.append(f"Figure not found: {fig.path}")
            continue

        try:
            normalized_path = normalize_figure(fig.path, output_dir)
        except (OSError, RuntimeError, ValueError) as exc:
            errors.append(f"Figure preparation failed for {fig.path}: {exc}")
            continue

        passes, msg = check_figure_resolution(normalized_path, journal, double_column=fig.double_column)
        if not passes:
            if msg.startswith("cannot decode raster image:"):
                errors.append(f"Figure preparation failed for {fig.path}: {msg}")
                continue
            logger.warning("Figure %s below resolution requirement: %s", fig.label, msg)

        try:
            relative_path = normalized_path.relative_to(output_dir)
        except ValueError:
            relative_path = normalized_path
        updated = fig.model_copy(
            update={
                "path": relative_path,
                "width": get_figure_width(journal, fig.double_column),
            }
        )
        result.append(updated)
        source_pairs.append((fig, updated))

    for err in errors:
        logger.warning(err)

    return result, errors, source_pairs


def prepare_figures(figures: list[FigureRef], output_dir: Path, journal: str) -> tuple[list[FigureRef], list[str]]:
    """Normalize and size all figures for a given journal.

    For each figure:
    1. Normalize format to output_dir
    2. Check resolution, log warning if below journal minimum
    3. Update FigureRef.path to normalized file
    4. Set FigureRef.width based on journal and double_column flag
    """
    prepared, errors, _ = _prepare_figures_with_sources(figures, output_dir, journal)
    return prepared, errors
