"""Render the scorecard timeseries to a PNG chart.

Kept separate from ``scorecard.py`` so the core engine — imported by the notify
hook on every usage event — stays free of the Pillow dependency. Pillow is
imported lazily inside :func:`render_chart_png`.

The chart has two stacked panels: output quality and dollar efficiency
(quality per USD), both plotted against cumulative tokens when usage telemetry
exists, or against snapshot ordinal otherwise. It degrades gracefully: missing
quality points are skipped, and when no efficiency is available (e.g. a runtime
with no cost telemetry) the efficiency panel shows an explanatory note instead
of an empty plot.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from gpd.core.scorecard import ScorecardSnapshot

__all__ = ["render_chart_png"]

_W, _H, _MARGIN = 920, 660, 70
_QUALITY_COLOR = "#1f77b4"
_EFFICIENCY_COLOR = "#d62728"


def _load_fonts():
    from PIL import ImageFont

    candidates = (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    )
    try:
        bold = ImageFont.truetype(candidates[0], 18)
        normal = ImageFont.truetype(candidates[1], 13)
        small = ImageFont.truetype(candidates[1], 11)
        return bold, normal, small
    except OSError:
        default = ImageFont.load_default()
        return default, default, default


def _x_axis(snapshots: list[ScorecardSnapshot]) -> tuple[list[float], str, list[str]]:
    """Return (x-values, axis label, per-point tick labels).

    Uses cumulative tokens when any snapshot carries a token count, else falls
    back to snapshot ordinal so the chart still renders without telemetry.
    """
    if any(s.total_tokens for s in snapshots):
        xs = [float(s.total_tokens) for s in snapshots]
        ticks = [f"{int(s.total_tokens) // 1000}k" for s in snapshots]
        return xs, "cumulative tokens spent", ticks
    xs = [float(i + 1) for i in range(len(snapshots))]
    return xs, "snapshot #", [str(i + 1) for i in range(len(snapshots))]


def render_chart_png(
    snapshots: list[ScorecardSnapshot],
    output_path: Path,
    *,
    last: int | None = None,
) -> Path:
    """Render the scorecard timeseries to ``output_path`` as a PNG. Returns the path.

    Raises ``ValueError`` when there are no snapshots to plot.
    """
    from PIL import Image, ImageDraw

    if last is not None and last > 0:
        snapshots = snapshots[-last:]
    if not snapshots:
        raise ValueError("no scorecard snapshots to chart")

    bold, normal, small = _load_fonts()
    img = Image.new("RGB", (_W, _H), "white")
    draw = ImageDraw.Draw(img)

    xs, x_label, x_ticks = _x_axis(snapshots)
    qualities = [s.quality for s in snapshots]
    efficiencies = [s.efficiency_per_usd for s in snapshots]

    draw.text((_MARGIN, 16), "Research Scorecard — quality & dollar efficiency", font=bold, fill="black")
    has_cost = any(e is not None for e in efficiencies)
    subtitle = f"x-axis: {x_label}" + ("" if has_cost else "   (no usage telemetry — dollar efficiency unavailable)")
    draw.text((_MARGIN, 40), subtitle, font=small, fill="#777")

    def panel(top: float, bottom: float, ys: list[float | None], color: str, fmt, title: str, note: str | None) -> None:
        x0, x1 = _MARGIN, _W - _MARGIN
        draw.text((x0, top - 24), title, font=bold, fill="black")
        draw.line([(x0, top), (x0, bottom)], fill="#888", width=1)
        draw.line([(x0, bottom), (x1, bottom)], fill="#888", width=1)

        present = [(x, y) for x, y in zip(xs, ys, strict=True) if y is not None]
        if not present:
            draw.text((x0 + 20, (top + bottom) / 2 - 8), note or "no data", font=normal, fill="#999")
            return

        x_lo, x_hi = min(xs), max(xs)
        x_span = (x_hi - x_lo) or 1.0
        y_hi = max(y for _, y in present) * 1.15 or 1.0
        y_lo = 0.0

        def px(x: float) -> float:
            return x0 + (x - x_lo) / x_span * (x1 - x0)

        def py(y: float) -> float:
            return bottom - (y - y_lo) / (y_hi - y_lo) * (bottom - top)

        for k in range(5):
            v = y_hi * k / 4
            yy = py(v)
            draw.line([(x0, yy), (x1, yy)], fill="#eee", width=1)
            draw.text((8, yy - 7), fmt(v), font=small, fill="#555")
        for x, tick in zip(xs, x_ticks, strict=True):
            draw.text((px(x) - 12, bottom + 6), tick, font=small, fill="#555")

        pts = [(px(x), py(y)) for x, y in present]
        if len(pts) > 1:
            draw.line(pts, fill=color, width=3)
        for (xx, yy), (_, y) in zip(pts, present, strict=True):
            draw.ellipse([xx - 4, yy - 4, xx + 4, yy + 4], fill=color)
            draw.text((xx - 10, yy - 20), fmt(y), font=small, fill="black")

    panel(95, 300, qualities, _QUALITY_COLOR, lambda v: f"{v:.2f}", "Output quality", "no quality recorded")
    panel(
        380,
        590,
        efficiencies,
        _EFFICIENCY_COLOR,
        lambda v: f"{v:.2f}",
        "Dollar efficiency (quality / $)",
        "Dollar efficiency unavailable — no usage telemetry recorded for this project.",
    )

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path)
    return output_path
