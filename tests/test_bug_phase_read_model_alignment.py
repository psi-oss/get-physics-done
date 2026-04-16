"""Phase 15 contract for the phase/read-model alignment family."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from gpd.core.frontmatter import verify_phase_completeness
from gpd.core.phases import phase_plan_index, progress_render, roadmap_analyze
from gpd.mcp.servers.state_server import get_phase_info

REPO_ROOT = Path(__file__).resolve().parents[1]
HANDOFF_BUNDLE_ROOT = REPO_ROOT / "tests" / "fixtures" / "handoff-bundle"


def _copy_fixture_workspace(fixture_relpath: str, tmp_path: Path) -> Path:
    source = HANDOFF_BUNDLE_ROOT / fixture_relpath / "workspace"
    destination = tmp_path / fixture_relpath.replace("/", "-")
    shutil.copytree(source, destination)
    return destination


@pytest.mark.parametrize(
    (
        "fixture_relpath",
        "phase_number",
        "expected_roadmap",
        "expected_progress",
        "expected_completeness",
        "expected_phase_info",
    ),
    [
        pytest.param(
            "completed-phase/positive",
            "1",
            {
                "phase_count": 4,
                "current_phase": "2",
                "next_phase": "4",
                "total_plans": 2,
                "total_summaries": 2,
                "progress_percent": 100,
                "completed_phases": 2,
            },
            {
                "total_plans": 2,
                "total_summaries": 2,
                "percent": 100,
                "state_progress_percent": 100,
                "diverged": False,
                "warnings": [],
            },
            {
                "complete": True,
                "phase_number": "01",
                "plan_count": 1,
                "summary_count": 1,
                "incomplete_plans": [],
                "orphan_summaries": [],
            },
            {
                "phase_number": "01",
                "phase_name": "literature-anchors-and-entangled-cft-setup",
                "directory": "GPD/phases/01-literature-anchors-and-entangled-cft-setup",
                "phase_slug": "literature-anchors-and-entangled-cft-setup",
                "plan_count": 1,
                "summary_count": 1,
                "complete": True,
                "schema_version": 1,
            },
            id="completed-phase-positive",
        ),
        pytest.param(
            "plan-only/mutation",
            "1",
            {
                "phase_count": 4,
                "current_phase": "1",
                "next_phase": "2",
                "total_plans": 2,
                "total_summaries": 0,
                "progress_percent": 0,
                "completed_phases": 0,
            },
            {
                "total_plans": 2,
                "total_summaries": 0,
                "percent": 0,
                "state_progress_percent": 0,
                "diverged": False,
                "warnings": [],
            },
            {
                "complete": False,
                "phase_number": "01",
                "plan_count": 1,
                "summary_count": 0,
                "incomplete_plans": ["01"],
                "orphan_summaries": [],
            },
            {
                "phase_number": "01",
                "phase_name": "literature-anchors-and-entangled-cft-setup",
                "directory": "GPD/phases/01-literature-anchors-and-entangled-cft-setup",
                "phase_slug": "literature-anchors-and-entangled-cft-setup",
                "plan_count": 1,
                "summary_count": 0,
                "complete": False,
                "schema_version": 1,
            },
            id="plan-only-mutation",
        ),
        pytest.param(
            "empty-phase/positive",
            "1",
            {
                "phase_count": 3,
                "current_phase": "1",
                "next_phase": "2",
                "total_plans": 0,
                "total_summaries": 0,
                "progress_percent": 0,
                "completed_phases": 0,
            },
            {
                "total_plans": 0,
                "total_summaries": 0,
                "percent": 0,
                "state_progress_percent": 0,
                "diverged": False,
                "warnings": [],
            },
            {
                "complete": False,
                "phase_number": "",
                "plan_count": 0,
                "summary_count": 0,
                "incomplete_plans": [],
                "orphan_summaries": [],
            },
            {
                "error": "Phase 01 not found",
                "schema_version": 1,
            },
            id="empty-phase-positive",
        ),
    ],
)
def test_phase_read_model_alignment_contract(
    fixture_relpath: str,
    phase_number: str,
    expected_roadmap: dict[str, object],
    expected_progress: dict[str, object],
    expected_completeness: dict[str, object],
    expected_phase_info: dict[str, object],
    tmp_path: Path,
) -> None:
    workspace = _copy_fixture_workspace(fixture_relpath, tmp_path)

    # Exact repro:
    # The archived handoff-bundle anchors expose the historical mismatch
    # between phase completeness, roadmap projection, and the state-server
    # phase read-model. This fixture-backed contract keeps that repro surface
    # explicit while using the current fixed behavior as the pass condition.
    roadmap = roadmap_analyze(workspace)
    progress = progress_render(workspace)
    completeness = verify_phase_completeness(workspace, phase_number)
    plan_index = phase_plan_index(workspace, phase_number)
    phase_info = get_phase_info(str(workspace), phase_number.zfill(2))

    # Exact fix:
    # The read-model surfaces now agree on counts and completeness for the
    # completed and plan-only anchors, and fail closed for the empty-phase
    # anchor instead of inventing a synthetic phase record.
    assert roadmap.phase_count == expected_roadmap["phase_count"]
    assert roadmap.current_phase == expected_roadmap["current_phase"]
    assert roadmap.next_phase == expected_roadmap["next_phase"]
    assert roadmap.total_plans == expected_roadmap["total_plans"]
    assert roadmap.total_summaries == expected_roadmap["total_summaries"]
    assert roadmap.progress_percent == expected_roadmap["progress_percent"]
    assert roadmap.completed_phases == expected_roadmap["completed_phases"]
    assert roadmap.completed_phases == sum(1 for phase in roadmap.phases if phase.disk_status == "complete")

    assert progress.total_plans == expected_progress["total_plans"]
    assert progress.total_summaries == expected_progress["total_summaries"]
    assert progress.percent == expected_progress["percent"]
    assert progress.state_progress_percent == expected_progress["state_progress_percent"]
    assert progress.diverged is expected_progress["diverged"]
    assert progress.warnings == expected_progress["warnings"]

    assert completeness.complete is expected_completeness["complete"]
    assert completeness.phase_number == expected_completeness["phase_number"]
    assert completeness.plan_count == expected_completeness["plan_count"]
    assert completeness.summary_count == expected_completeness["summary_count"]
    assert completeness.incomplete_plans == expected_completeness["incomplete_plans"]
    assert completeness.orphan_summaries == expected_completeness["orphan_summaries"]

    assert plan_index.phase == phase_number.zfill(2)
    assert plan_index.incomplete == expected_completeness["incomplete_plans"]
    assert plan_index.has_checkpoints is False
    assert plan_index.validation is not None
    assert plan_index.validation.valid is True
    assert len(plan_index.plans) == expected_completeness["plan_count"]

    if "error" in expected_phase_info:
        assert phase_info == expected_phase_info
    else:
        for key, value in expected_phase_info.items():
            assert phase_info[key] == value

    # Adjacent checks:
    # These surfaces are the neighboring projections that previously drifted.
    # Keep them in lockstep so the family stays closed as a regression contract.
    assert progress.total_plans == roadmap.total_plans
    assert progress.total_summaries == roadmap.total_summaries
    assert roadmap.progress_percent == progress.percent == progress.state_progress_percent
    assert completeness.complete == (completeness.plan_count > 0 and completeness.summary_count >= completeness.plan_count)
