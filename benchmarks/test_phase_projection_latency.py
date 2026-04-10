"""Explicit latency benchmark for the Phase 16 projection read models.

The benchmark stays out of default pytest discovery because ``benchmarks/`` is
an opt-in tree. It measures the hot projection bundle only, while keeping
fixture copying plus normalization/diffing outside the timed region.
"""

from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path
from time import perf_counter_ns

import pytest

from gpd.core.frontmatter import verify_phase_completeness
from gpd.core.phases import phase_plan_index, progress_render, roadmap_analyze
from gpd.core.state import state_snapshot
from gpd.core.utils import phase_normalize

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tests.phase16_projection_oracle_helpers import (  # noqa: E402
    assert_projection_records_match,
    copy_case_workspace,
    phase16_cases,
)

try:
    from benchmarks.phase17_benchmark_helpers import measure_ns, summarize_ns
except (FileNotFoundError, ImportError, ValueError):  # pragma: no cover - helper lands in a later worker.

    def measure_ns(
        func: Callable[[], object],
        *,
        warmup_rounds: int = 1,
        sample_rounds: int = 7,
    ) -> tuple[int, ...]:
        for _ in range(warmup_rounds):
            func()

        samples: list[int] = []
        for _ in range(sample_rounds):
            start = perf_counter_ns()
            func()
            samples.append(perf_counter_ns() - start)
        return tuple(samples)

    def summarize_ns(samples: tuple[int, ...]) -> dict[str, int]:
        if not samples:
            raise ValueError("benchmark samples cannot be empty")
        ordered = tuple(sorted(samples))
        p95_index = max(0, min(len(ordered) - 1, int((len(ordered) * 95 + 99) // 100) - 1))
        return {
            "count": len(ordered),
            "min_ns": ordered[0],
            "median_ns": ordered[len(ordered) // 2],
            "p95_ns": ordered[p95_index],
            "max_ns": ordered[-1],
        }


STATE_PROJECTION_CASES = phase16_cases(family="state")
SAMPLE_ROUNDS = 7
WARMUP_ROUNDS = 2


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


def _projection_bundle(workspace: Path, phase_token: str) -> dict[str, object]:
    return {
        "state": state_snapshot(workspace),
        "roadmap": roadmap_analyze(workspace),
        "progress": progress_render(workspace, "json"),
        "phase_completeness": verify_phase_completeness(workspace, phase_token),
        "phase_index": phase_plan_index(workspace, phase_token),
    }


def _projection_record(workspace: Path, bundle: dict[str, object]) -> dict[str, object]:
    state = bundle["state"]
    roadmap = bundle["roadmap"]
    progress = bundle["progress"]
    phase_completeness = bundle["phase_completeness"]
    phase_index = bundle["phase_index"]
    current_phase = _roadmap_current_phase(roadmap)
    phase_token = phase_normalize(str(current_phase.number))

    return {
        "workspace_root": workspace.resolve(strict=False).as_posix(),
        "phase_token": phase_token,
        "state": {
            "current_phase": phase_normalize(str(state.current_phase)) if state.current_phase is not None else None,
            "current_phase_name": state.current_phase_name,
            "current_plan": state.current_plan,
            "total_phases": state.total_phases,
            "status": state.status,
            "progress_percent_state": state.progress_percent,
        },
        "roadmap": {
            "current_phase": phase_token,
            "current_phase_name": current_phase.name,
            "phase_count": roadmap.phase_count,
            "completed_phases": roadmap.completed_phases,
            "total_plans": roadmap.total_plans,
            "total_summaries": roadmap.total_summaries,
            "progress_percent_disk": roadmap.progress_percent,
            "next_phase": roadmap.next_phase,
            "total_plans_in_phase": current_phase.plan_count,
        },
        "progress": {
            "total_plans": progress.total_plans,
            "total_summaries": progress.total_summaries,
            "progress_percent_disk": progress.percent,
            "progress_percent_state": progress.state_progress_percent,
            "diverged": progress.diverged,
            "warnings": _sorted_unique_warnings(progress.warnings),
        },
        "phase_completeness": {
            "phase_number": phase_normalize(str(phase_completeness.phase_number)),
            "complete": phase_completeness.complete,
            "plan_count": phase_completeness.plan_count,
            "summary_count": phase_completeness.summary_count,
            "incomplete_plans": tuple(phase_completeness.incomplete_plans),
            "orphan_summaries": tuple(phase_completeness.orphan_summaries),
            "errors": tuple(phase_completeness.errors),
            "warnings": tuple(phase_completeness.warnings),
        },
        "phase_index": {
            "phase": phase_normalize(str(phase_index.phase)),
            "plan_count": len(phase_index.plans),
            "incomplete": tuple(phase_index.incomplete),
            "has_checkpoints": phase_index.has_checkpoints,
            "validation_valid": phase_index.validation.valid if phase_index.validation else False,
            "validation_errors": tuple(phase_index.validation.errors) if phase_index.validation else (),
        },
    }


def _normalize_projection_record(record: dict[str, object]) -> dict[str, object]:
    return {
        "workspace_root": record["workspace_root"],
        "phase_token": record["phase_token"],
        "state": dict(record["state"]),
        "roadmap": dict(record["roadmap"]),
        "progress": dict(record["progress"]),
        "phase_completeness": dict(record["phase_completeness"]),
        "phase_index": dict(record["phase_index"]),
    }


@pytest.mark.parametrize("case", STATE_PROJECTION_CASES, ids=lambda case: case.case_key)
def test_phase_projection_latency(case, tmp_path: Path) -> None:
    workspace = copy_case_workspace(case, tmp_path)

    probe_roadmap = roadmap_analyze(workspace)
    current_phase = _roadmap_current_phase(probe_roadmap)
    phase_token = phase_normalize(str(current_phase.number))

    baseline_bundle = _projection_bundle(workspace, phase_token)
    baseline_record = _normalize_projection_record(_projection_record(workspace, baseline_bundle))

    samples_ns = measure_ns(
        lambda: _projection_bundle(workspace, phase_token),
        warmup_rounds=WARMUP_ROUNDS,
        sample_rounds=SAMPLE_ROUNDS,
    )

    final_bundle = _projection_bundle(workspace, phase_token)
    final_record = _normalize_projection_record(_projection_record(workspace, final_bundle))

    assert_projection_records_match(baseline_record, final_record)

    summary = summarize_ns(samples_ns)
    assert summary["count"] == SAMPLE_ROUNDS
    assert summary["min_ns"] > 0
    assert summary["p95_ns"] >= summary["median_ns"] >= summary["min_ns"]
