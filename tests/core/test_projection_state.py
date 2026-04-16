"""Phase 16 state/progress/roadmap projection oracle."""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from gpd.core.phases import progress_render, roadmap_analyze
from gpd.core.state import state_snapshot, state_validate
from gpd.core.utils import phase_normalize

try:  # Prefer the shared helper when it is available.
    import tests.phase16_projection_oracle_helpers as _phase16_helpers
except ImportError:  # pragma: no cover - worker 6 may land later.
    _phase16_helpers = None


REPO_ROOT = Path(__file__).resolve().parents[2]
HANDOFF_BUNDLE_ROOT = REPO_ROOT / "tests" / "fixtures" / "handoff-bundle"


@dataclass(frozen=True, slots=True)
class ProjectionCase:
    fixture_slug: str
    variant: str

    @property
    def case_id(self) -> str:
        return f"{self.fixture_slug}-{self.variant}"


PROJECTION_CASES = (
    ProjectionCase("completed-phase", "positive"),
    ProjectionCase("plan-only", "positive"),
    ProjectionCase("plan-only", "mutation"),
    ProjectionCase("empty-phase", "positive"),
    ProjectionCase("empty-phase", "mutation"),
)


def _helper(*names: str):
    if _phase16_helpers is None:
        return None
    for name in names:
        candidate = getattr(_phase16_helpers, name, None)
        if candidate is not None:
            return candidate
    return None


def _copy_fixture_workspace(case: ProjectionCase, tmp_path: Path) -> Path:
    helper = _helper("copy_fixture_workspace", "copy_handoff_bundle_workspace", "copy_projection_workspace")
    if helper is not None:
        return helper(tmp_path, case.fixture_slug, case.variant)

    source = HANDOFF_BUNDLE_ROOT / case.fixture_slug / case.variant / "workspace"
    destination = tmp_path / case.case_id
    shutil.copytree(source, destination)
    return destination


def _roadmap_current_phase(roadmap: object):
    normalized_current = phase_normalize(str(roadmap.current_phase))
    for phase in roadmap.phases:
        if phase_normalize(str(phase.number)) == normalized_current:
            return phase
    raise AssertionError(f"roadmap phase {roadmap.current_phase!r} was not present in the phase list")


def _sorted_unique_warnings(*warning_lists: object) -> tuple[str, ...]:
    warnings: set[str] = set()
    for warning_list in warning_lists:
        for warning in warning_list or []:
            warnings.add(str(warning))
    return tuple(sorted(warnings))


def _canonical_projection_record(workspace: Path, state: object, roadmap: object, progress: object) -> dict[str, object]:
    current_phase = _roadmap_current_phase(roadmap)
    return {
        "project_root": workspace.resolve(strict=False).as_posix(),
        "current_phase": phase_normalize(str(current_phase.number)),
        "current_phase_name": current_phase.name,
        "current_plan": state.current_plan,
        "total_phases": roadmap.phase_count,
        "total_plans_in_phase": current_phase.plan_count,
        "status": state.status,
        "progress_percent_state": state.progress_percent,
        "phase_count": roadmap.phase_count,
        "completed_phases": roadmap.completed_phases,
        "total_plans": roadmap.total_plans,
        "total_summaries": roadmap.total_summaries,
        "progress_percent_disk": progress.percent,
        "next_phase": roadmap.next_phase,
        "diverged": progress.diverged,
        "warnings": _sorted_unique_warnings(progress.warnings),
    }


def _state_projection_view(state: object) -> dict[str, object]:
    return {
        "current_phase": phase_normalize(str(state.current_phase)) if state.current_phase is not None else None,
        "current_phase_name": state.current_phase_name,
        "current_plan": state.current_plan,
        "total_phases": state.total_phases,
        "status": state.status,
        "progress_percent_state": state.progress_percent,
    }


def _roadmap_projection_view(roadmap: object) -> dict[str, object]:
    current_phase = _roadmap_current_phase(roadmap)
    return {
        "current_phase": phase_normalize(str(current_phase.number)),
        "current_phase_name": current_phase.name,
        "phase_count": roadmap.phase_count,
        "completed_phases": roadmap.completed_phases,
        "total_plans": roadmap.total_plans,
        "total_summaries": roadmap.total_summaries,
        "progress_percent_disk": roadmap.progress_percent,
        "next_phase": roadmap.next_phase,
        "total_plans_in_phase": current_phase.plan_count,
    }


def _progress_projection_view(progress: object) -> dict[str, object]:
    return {
        "total_plans": progress.total_plans,
        "total_summaries": progress.total_summaries,
        "progress_percent_disk": progress.percent,
        "progress_percent_state": progress.state_progress_percent,
        "diverged": progress.diverged,
        "warnings": _sorted_unique_warnings(progress.warnings),
    }


def _diff_records(expected: dict[str, object], actual: dict[str, object]) -> dict[str, tuple[object, object]]:
    helper = _helper("diff_projection_records", "projection_record_diff", "diff_projection_view")
    if helper is not None:
        return helper(expected, actual)

    return {
        key: (actual.get(key), expected.get(key))
        for key in expected
        if actual.get(key) != expected.get(key)
    }


def _filter_diff_keys(diffs: object, allowed_keys: set[str]) -> object:
    if isinstance(diffs, dict):
        return {key: value for key, value in diffs.items() if key not in allowed_keys}
    return tuple(diff for diff in diffs if getattr(diff, "path_text", None) not in allowed_keys)


def _allowed_state_drift(case: ProjectionCase) -> set[str]:
    if case.fixture_slug == "plan-only" and case.variant == "mutation":
        return {"current_phase", "current_phase_name"}
    return set()


def _assert_view_matches(
    label: str,
    expected: dict[str, object],
    actual: dict[str, object],
    *,
    allowed_keys: set[str] | None = None,
) -> None:
    allowed = allowed_keys or set()
    diffs = _filter_diff_keys(_diff_records(expected, actual), allowed)
    assert not diffs, f"{label} projection drift: {diffs}"


@pytest.mark.parametrize("case", PROJECTION_CASES, ids=lambda case: case.case_id)
def test_state_progress_roadmap_projection_oracle(case: ProjectionCase, tmp_path: Path) -> None:
    workspace = _copy_fixture_workspace(case, tmp_path)
    state_json = workspace / "GPD" / "state.json"
    before_validate = state_json.read_text(encoding="utf-8")

    state = state_snapshot(workspace)
    roadmap = roadmap_analyze(workspace)
    progress = progress_render(workspace, "json")

    canonical = _canonical_projection_record(workspace, state, roadmap, progress)

    assert canonical["project_root"] == workspace.resolve(strict=False).as_posix()
    assert canonical["current_phase"] == phase_normalize(str(_roadmap_current_phase(roadmap).number))
    assert canonical["current_phase_name"] == _roadmap_current_phase(roadmap).name
    assert canonical["phase_count"] == canonical["total_phases"] == roadmap.phase_count == state.total_phases
    assert canonical["total_plans"] == roadmap.total_plans == progress.total_plans
    assert canonical["total_summaries"] == roadmap.total_summaries == progress.total_summaries
    assert canonical["progress_percent_state"] == state.progress_percent == progress.state_progress_percent
    assert canonical["progress_percent_disk"] == roadmap.progress_percent == progress.percent
    assert canonical["diverged"] is False
    assert canonical["warnings"] == ()
    assert canonical["next_phase"] == roadmap.next_phase
    assert canonical["completed_phases"] == roadmap.completed_phases

    _assert_view_matches(
        "state",
        {
            "current_phase": canonical["current_phase"],
            "current_phase_name": canonical["current_phase_name"],
            "current_plan": canonical["current_plan"],
            "total_phases": canonical["total_phases"],
            "status": canonical["status"],
            "progress_percent_state": canonical["progress_percent_state"],
        },
        _state_projection_view(state),
        allowed_keys=_allowed_state_drift(case),
    )

    _assert_view_matches(
        "roadmap",
        {
            "current_phase": canonical["current_phase"],
            "current_phase_name": canonical["current_phase_name"],
            "phase_count": canonical["phase_count"],
            "completed_phases": canonical["completed_phases"],
            "total_plans": canonical["total_plans"],
            "total_summaries": canonical["total_summaries"],
            "progress_percent_disk": canonical["progress_percent_disk"],
            "next_phase": canonical["next_phase"],
            "total_plans_in_phase": canonical["total_plans_in_phase"],
        },
        _roadmap_projection_view(roadmap),
    )

    _assert_view_matches(
        "progress",
        {
            "total_plans": canonical["total_plans"],
            "total_summaries": canonical["total_summaries"],
            "progress_percent_disk": canonical["progress_percent_disk"],
            "progress_percent_state": canonical["progress_percent_state"],
            "diverged": canonical["diverged"],
            "warnings": canonical["warnings"],
        },
        _progress_projection_view(progress),
    )

    after_validate = state_json.read_text(encoding="utf-8")
    validation = state_validate(workspace)

    assert after_validate == before_validate
    assert state_json.read_text(encoding="utf-8") == before_validate
    assert validation is not None
