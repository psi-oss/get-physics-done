"""Tests for gpd.core.scorecard_chart — PNG rendering of the timeseries."""

from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from gpd.core.scorecard import ScorecardSnapshot
from gpd.core.scorecard_chart import render_chart_png


def _snap(
    snapshot_id: str,
    *,
    quality: float | None,
    total_tokens: int = 0,
    cost_usd: float | None = None,
    efficiency_per_usd: float | None = None,
) -> ScorecardSnapshot:
    return ScorecardSnapshot(
        snapshot_id=snapshot_id,
        recorded_at="2026-06-04T10:00:00Z",
        quality=quality,
        objective_quality=quality,
        total_tokens=total_tokens,
        cost_usd=cost_usd,
        efficiency_per_usd=efficiency_per_usd,
    )


def _is_png(path: Path) -> tuple[int, int]:
    with Image.open(path) as im:
        assert im.format == "PNG"
        return im.size


def test_renders_valid_png_with_cost(tmp_path: Path) -> None:
    snaps = [
        _snap("s1", quality=0.3, total_tokens=25000, cost_usd=0.5, efficiency_per_usd=0.6),
        _snap("s2", quality=0.6, total_tokens=60000, cost_usd=1.2, efficiency_per_usd=0.5),
        _snap("s3", quality=1.0, total_tokens=110000, cost_usd=2.2, efficiency_per_usd=0.45),
    ]
    out = tmp_path / "chart.png"

    written = render_chart_png(snaps, out)

    assert written == out
    assert _is_png(out) == (920, 660)


def test_renders_when_cost_unavailable(tmp_path: Path) -> None:
    # No tokens / cost -> x-axis falls back to ordinal, efficiency panel shows a note.
    snaps = [_snap("s1", quality=0.68), _snap("s2", quality=0.68), _snap("s3", quality=1.0)]
    out = tmp_path / "chart.png"

    render_chart_png(snaps, out)

    assert out.exists()
    _is_png(out)  # still a valid image, no crash


def test_renders_single_snapshot(tmp_path: Path) -> None:
    out = tmp_path / "chart.png"
    render_chart_png([_snap("s1", quality=0.5, total_tokens=10000, cost_usd=0.1, efficiency_per_usd=5.0)], out)
    assert out.exists()


def test_skips_none_quality_points(tmp_path: Path) -> None:
    snaps = [_snap("s1", quality=None), _snap("s2", quality=0.7, total_tokens=5000)]
    out = tmp_path / "chart.png"
    render_chart_png(snaps, out)
    assert out.exists()


def test_last_trims_series(tmp_path: Path) -> None:
    snaps = [_snap(f"s{i}", quality=0.1 * i, total_tokens=1000 * i) for i in range(1, 6)]
    out = tmp_path / "chart.png"
    # Should not raise and should render using only the last 2 points.
    render_chart_png(snaps, out, last=2)
    assert out.exists()


def test_creates_parent_directory(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "dir" / "chart.png"
    render_chart_png([_snap("s1", quality=0.5)], out)
    assert out.exists()


def test_empty_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="no scorecard snapshots"):
        render_chart_png([], tmp_path / "chart.png")
