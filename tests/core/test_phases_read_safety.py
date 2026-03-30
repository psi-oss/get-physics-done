"""Behavioral safety checks for phase reads around frontmatter parsing."""

from __future__ import annotations

from pathlib import Path

from gpd.core.phases import phase_plan_index, validate_phase_waves


def _write_phase_plan(path: Path, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_validate_phase_waves_collects_frontmatter_errors_without_raising(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-test-phase"
    _write_phase_plan(
        phase_dir / "01-PLAN.md",
        "---\nphase: 01\nplan: 01\nwave: [\n---\nBody\n",
    )

    result = validate_phase_waves(tmp_path, "1")

    assert result.phase == "01"
    assert result.validation.valid is False
    assert any("01-PLAN.md:" in error and "wave: [" in error for error in result.validation.errors)


def test_phase_plan_index_collects_frontmatter_errors_without_raising(tmp_path: Path) -> None:
    phase_dir = tmp_path / "GPD" / "phases" / "01-test-phase"
    _write_phase_plan(
        phase_dir / "01-PLAN.md",
        "---\nphase: 01\nplan: 01\nwave: [\n---\nBody\n",
    )

    index = phase_plan_index(tmp_path, "1")

    assert index.phase == "01"
    assert index.validation.valid is False
    assert any("01-PLAN.md:" in error and "wave: [" in error for error in index.validation.errors)
