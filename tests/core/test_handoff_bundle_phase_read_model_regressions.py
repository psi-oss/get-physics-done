"""Fixture-backed regressions for handoff-bundle phase read-model agreement."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from gpd.core.frontmatter import verify_phase_completeness
from gpd.core.phases import phase_plan_index, progress_render, roadmap_analyze

REPO_ROOT = Path(__file__).resolve().parents[2]
HANDOFF_BUNDLE_ROOT = REPO_ROOT / "tests" / "fixtures" / "handoff-bundle"


def _copy_fixture_workspace(slug: str, variant: str, tmp_path: Path) -> Path:
    source = HANDOFF_BUNDLE_ROOT / slug / variant / "workspace"
    target = tmp_path / f"{slug}-{variant}"
    shutil.copytree(source, target)
    return target


def _phase_by_number(phases: list[object], number: str):
    return next(phase for phase in phases if phase.number == number)


def _progress_phase_rows(phases: list[object]) -> list[tuple[str, int, int, str]]:
    return [(phase.number, phase.plans, phase.summaries, phase.status) for phase in phases]


@pytest.mark.parametrize(
    (
        "slug",
        "variant",
        "expected_complete",
        "expected_total_plans",
        "expected_total_summaries",
        "expected_completed_phases",
        "expected_current_phase",
        "expected_progress_phases",
    ),
    [
        (
            "completed-phase",
            "positive",
            True,
            2,
            2,
            2,
            "2",
            [
                ("01", 1, 1, "Complete"),
                ("02", 0, 0, "Pending"),
                ("03", 1, 1, "Complete"),
                ("04", 0, 0, "Pending"),
            ],
        ),
        (
            "plan-only",
            "mutation",
            False,
            2,
            0,
            0,
            "1",
            [
                ("01", 1, 0, "Planned"),
                ("02", 0, 0, "Pending"),
                ("03", 1, 0, "Planned"),
                ("04", 0, 0, "Pending"),
            ],
        ),
    ],
    ids=["completed-phase-positive", "plan-only-mutation"],
)
def test_handoff_bundle_workspaces_keep_read_models_in_sync(
    slug: str,
    variant: str,
    expected_complete: bool,
    expected_total_plans: int,
    expected_total_summaries: int,
    expected_completed_phases: int,
    expected_current_phase: str | None,
    expected_progress_phases: list[tuple[str, int, int, str]],
    tmp_path: Path,
) -> None:
    root = _copy_fixture_workspace(slug, variant, tmp_path)

    roadmap = roadmap_analyze(root)
    progress = progress_render(root)
    completeness = verify_phase_completeness(root, "1")
    plan_index = phase_plan_index(root, "1")

    roadmap_phase = _phase_by_number(roadmap.phases, "1")
    progress_phase = _phase_by_number(progress.phases, "01")

    assert _progress_phase_rows(progress.phases) == expected_progress_phases
    assert roadmap.phase_count == len(progress.phases)
    assert roadmap.total_plans == progress.total_plans == expected_total_plans
    assert roadmap.total_summaries == progress.total_summaries == expected_total_summaries
    assert roadmap.progress_percent == progress.percent == progress.state_progress_percent
    assert roadmap.completed_phases == expected_completed_phases
    assert roadmap.completed_phases == sum(1 for phase in roadmap.phases if phase.disk_status == "complete")
    assert roadmap.current_phase == expected_current_phase

    assert roadmap_phase.plan_count == progress_phase.plans == completeness.plan_count
    assert roadmap_phase.summary_count == progress_phase.summaries == completeness.summary_count
    assert roadmap_phase.disk_status == ("complete" if expected_complete else "planned")

    assert completeness.complete is expected_complete
    assert completeness.incomplete_plans == plan_index.incomplete
    assert plan_index.plans and plan_index.plans[0].has_summary == expected_complete
    assert plan_index.validation.valid is True

    assert progress.diverged is False
    assert progress.warnings == []
