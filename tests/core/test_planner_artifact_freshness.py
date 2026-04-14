"""Focused regressions for planner artifact freshness reconciliation helpers."""

from __future__ import annotations

from pathlib import Path

from gpd.core.planner_artifacts import resolve_planner_artifact_freshness


def test_resolve_planner_artifact_freshness_accepts_exact_match_and_normalizes_reported_paths(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "GPD" / "phases" / "01-foundations" / "01-PLAN.md"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("# Plan\n", encoding="utf-8")

    result = resolve_planner_artifact_freshness(
        tmp_path,
        ["GPD/phases/01-foundations/01-PLAN.md"],
        ["GPD\\phases\\01-foundations\\01-PLAN.md"],
    )

    assert result.passed is True
    assert result.state == "fresh"
    assert result.expected_paths == (artifact.resolve(strict=False),)
    assert result.reported_paths == (artifact.resolve(strict=False),)
    assert result.missing_on_disk == ()
    assert result.missing_from_return == ()
    assert result.unexpected_reported_paths == ()


def test_resolve_planner_artifact_freshness_ignores_blank_reported_paths(tmp_path: Path) -> None:
    artifact = tmp_path / "GPD" / "phases" / "01-foundations" / "01-PLAN.md"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("# Plan\n", encoding="utf-8")

    result = resolve_planner_artifact_freshness(
        tmp_path,
        ["GPD/phases/01-foundations/01-PLAN.md"],
        ["  ", "GPD/phases/01-foundations/01-PLAN.md"],
    )

    assert result.passed is True
    assert result.state == "fresh"
    assert result.reported_paths == (artifact.resolve(strict=False),)


def test_resolve_planner_artifact_freshness_fails_closed_when_artifact_is_missing_from_return(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "GPD" / "phases" / "01-foundations" / "01-PLAN.md"
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text("# Plan\n", encoding="utf-8")

    result = resolve_planner_artifact_freshness(
        tmp_path,
        [artifact],
        [],
    )

    assert result.passed is False
    assert result.state == "stale"
    assert result.expected_paths == (artifact.resolve(strict=False),)
    assert result.missing_on_disk == ()
    assert result.missing_from_return == (artifact.resolve(strict=False),)
    assert "gpd_return.files_written" in result.detail


def test_resolve_planner_artifact_freshness_fails_closed_when_return_names_unexpected_artifacts(
    tmp_path: Path,
) -> None:
    expected = tmp_path / "GPD" / "phases" / "01-foundations" / "01-PLAN.md"
    unexpected = tmp_path / "GPD" / "phases" / "01-foundations" / "01-SUMMARY.md"
    expected.parent.mkdir(parents=True, exist_ok=True)
    expected.write_text("# Plan\n", encoding="utf-8")
    unexpected.write_text("# Summary\n", encoding="utf-8")

    result = resolve_planner_artifact_freshness(
        tmp_path,
        [expected],
        ["GPD/phases/01-foundations/01-PLAN.md", "GPD/phases/01-foundations/01-SUMMARY.md"],
    )

    assert result.passed is False
    assert result.state == "stale"
    assert result.missing_on_disk == ()
    assert result.missing_from_return == ()
    assert result.unexpected_reported_paths == (unexpected.resolve(strict=False),)
    assert "unexpected files_written entries" in result.detail


def test_resolve_planner_artifact_freshness_fails_closed_when_reported_path_is_missing_on_disk(
    tmp_path: Path,
) -> None:
    artifact = tmp_path / "GPD" / "phases" / "01-foundations" / "01-PLAN.md"

    result = resolve_planner_artifact_freshness(
        tmp_path,
        [artifact],
        ["GPD/phases/01-foundations/01-PLAN.md"],
    )

    assert result.passed is False
    assert result.state == "missing"
    assert result.expected_paths == (artifact.resolve(strict=False),)
    assert result.missing_on_disk == (artifact.resolve(strict=False),)
    assert result.missing_from_return == ()
    assert result.unexpected_reported_paths == ()
    assert "missing on disk" in result.detail
