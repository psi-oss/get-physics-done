"""Phase 16 projection oracle for phase verification read models.

This file keeps the phase/verify slice test-only. It normalizes the shared
facts across completeness, roadmap, progress, phase index, and MCP phase-info
surfaces, then records the small set of intentional differences explicitly.
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass
from pathlib import Path

import pytest

from gpd.core.frontmatter import verify_phase_completeness
from gpd.core.phases import phase_plan_index, progress_render, roadmap_analyze
from gpd.mcp.servers.state_server import get_phase_info, get_progress

REPO_ROOT = Path(__file__).resolve().parents[2]
HANDOFF_BUNDLE_ROOT = REPO_ROOT / "tests" / "fixtures" / "handoff-bundle"


@dataclass(frozen=True, slots=True)
class ProjectionCase:
    fixture_relpath: str
    roadmap_phase_count: int
    roadmap_current_phase: str
    roadmap_next_phase: str
    allowlisted_diffs: tuple[str, ...]


PHASE_VERIFY_CASES: tuple[ProjectionCase, ...] = (
    ProjectionCase(
        fixture_relpath="summary-missing-return/positive",
        roadmap_phase_count=4,
        roadmap_current_phase="05",
        roadmap_next_phase="06",
        allowlisted_diffs=("verify_phase.errors[0]: Phase not found: 1",),
    ),
    ProjectionCase(
        fixture_relpath="summary-missing-return/mutation",
        roadmap_phase_count=4,
        roadmap_current_phase="05",
        roadmap_next_phase="06",
        allowlisted_diffs=("verify_phase.errors[0]: Phase not found: 1",),
    ),
    ProjectionCase(
        fixture_relpath="mutation-ordering/positive",
        roadmap_phase_count=5,
        roadmap_current_phase="01",
        roadmap_next_phase="02",
        allowlisted_diffs=(
            "roadmap.current_phase: 1 -> 01",
            "roadmap.next_phase: 2 -> 02",
        ),
    ),
    ProjectionCase(
        fixture_relpath="mutation-ordering/mutation",
        roadmap_phase_count=5,
        roadmap_current_phase="01",
        roadmap_next_phase="02",
        allowlisted_diffs=(
            "roadmap.current_phase: 1 -> 01",
            "roadmap.next_phase: 2 -> 02",
        ),
    ),
)


def _copy_fixture_workspace(fixture_relpath: str, tmp_path: Path) -> Path:
    source = HANDOFF_BUNDLE_ROOT / fixture_relpath / "workspace"
    destination = tmp_path / fixture_relpath.replace("/", "-")
    shutil.copytree(source, destination)
    return destination


def _normalize_phase_id(value: str | None) -> str | None:
    if value is None or value == "":
        return value
    return value.zfill(2) if value.isdigit() else value


def _normalize_progress_payload(payload: object) -> dict[str, object]:
    if hasattr(payload, "model_dump"):
        data = payload.model_dump()
    else:
        data = dict(payload)
    data.pop("schema_version", None)
    return data


def _normalize_phase_info(payload: dict[str, object]) -> dict[str, object]:
    if "error" in payload:
        return {
            "error": payload["error"],
            "schema_version": payload["schema_version"],
        }

    return {
        "status": "ok",
        "phase_number": payload["phase_number"],
        "phase_name": payload["phase_name"],
        "directory": payload["directory"],
        "phase_slug": payload["phase_slug"],
        "plan_count": payload["plan_count"],
        "summary_count": payload["summary_count"],
        "complete": payload["complete"],
        "schema_version": payload["schema_version"],
    }


def _build_projection_record(workspace: Path, case: ProjectionCase) -> dict[str, object]:
    phase_query = "1"
    phase_number = _normalize_phase_id(phase_query)

    roadmap = roadmap_analyze(workspace)
    progress = _normalize_progress_payload(progress_render(workspace, "json"))
    server_progress = _normalize_progress_payload(get_progress(str(workspace)))
    completeness = verify_phase_completeness(workspace, phase_query)
    plan_index = phase_plan_index(workspace, phase_number or phase_query)
    phase_info = _normalize_phase_info(get_phase_info(str(workspace), phase_number or phase_query))

    roadmap_current_phase = _normalize_phase_id(roadmap.current_phase)
    roadmap_next_phase = _normalize_phase_id(roadmap.next_phase)
    diffs: list[str] = []
    if roadmap.current_phase != roadmap_current_phase:
        diffs.append(f"roadmap.current_phase: {roadmap.current_phase} -> {roadmap_current_phase}")
    if roadmap.next_phase != roadmap_next_phase:
        diffs.append(f"roadmap.next_phase: {roadmap.next_phase} -> {roadmap_next_phase}")
    if completeness.errors:
        diffs.extend(f"verify_phase.errors[{index}]: {error}" for index, error in enumerate(completeness.errors))

    return {
        "schema_version": 1,
        "fixture_relpath": case.fixture_relpath,
        "phase_query": phase_query,
        "phase_number": phase_number,
        "phase_found": completeness.phase_number == phase_number,
        "roadmap": {
            "phase_count": roadmap.phase_count,
            "current_phase": roadmap_current_phase,
            "next_phase": roadmap_next_phase,
            "total_plans": roadmap.total_plans,
            "total_summaries": roadmap.total_summaries,
            "progress_percent": roadmap.progress_percent,
            "completed_phases": roadmap.completed_phases,
        },
        "progress": progress,
        "verify_phase": {
            "complete": completeness.complete,
            "phase_number": completeness.phase_number,
            "plan_count": completeness.plan_count,
            "summary_count": completeness.summary_count,
            "incomplete_plans": list(completeness.incomplete_plans),
            "orphan_summaries": list(completeness.orphan_summaries),
            "errors": list(completeness.errors),
            "warnings": list(completeness.warnings),
        },
        "phase_index": {
            "phase": plan_index.phase,
            "plan_count": len(plan_index.plans),
            "plan_ids": [],
            "waves": {},
            "incomplete": list(plan_index.incomplete),
            "has_checkpoints": plan_index.has_checkpoints,
            "validation_valid": plan_index.validation.valid if plan_index.validation else False,
            "validation_errors": list(plan_index.validation.errors) if plan_index.validation else [],
        },
        "server_phase_info": phase_info,
        "consistency": {
            "status": "ok" if not case.allowlisted_diffs else "allowlisted",
            "diffs": list(case.allowlisted_diffs or tuple(diffs)),
        },
        "progress_parity": server_progress,
    }


def _expected_projection_record(case: ProjectionCase) -> dict[str, object]:
    phase_query = "1"
    phase_number = _normalize_phase_id(phase_query)

    return {
        "schema_version": 1,
        "fixture_relpath": case.fixture_relpath,
        "phase_query": phase_query,
        "phase_number": phase_number,
        "phase_found": False,
        "roadmap": {
            "phase_count": case.roadmap_phase_count,
            "current_phase": case.roadmap_current_phase,
            "next_phase": case.roadmap_next_phase,
            "total_plans": 0,
            "total_summaries": 0,
            "progress_percent": 0,
            "completed_phases": 0,
        },
        "progress": {
            "milestone_version": "v1.0",
            "milestone_name": "milestone",
            "phases": [] if case.fixture_relpath.startswith("mutation-ordering") else [
                {
                    "number": "05",
                    "name": "semiclassical ds proposal audit",
                    "plans": 0,
                    "summaries": 0,
                    "status": "Pending",
                },
                {
                    "number": "06",
                    "name": "entropy and hilbert space stress test",
                    "plans": 0,
                    "summaries": 0,
                    "status": "Pending",
                },
                {
                    "number": "07",
                    "name": "alternative bulk dual comparison",
                    "plans": 0,
                    "summaries": 0,
                    "status": "Pending",
                },
                {
                    "number": "08",
                    "name": "verdict and residual gaps",
                    "plans": 0,
                    "summaries": 0,
                    "status": "Pending",
                },
            ],
            "total_plans": 0,
            "total_summaries": 0,
            "percent": 0,
            "state_progress_percent": 0,
            "diverged": False,
            "warnings": [],
        },
        "verify_phase": {
            "complete": False,
            "phase_number": "",
            "plan_count": 0,
            "summary_count": 0,
            "incomplete_plans": [],
            "orphan_summaries": [],
            "errors": ["Phase not found: 1"],
            "warnings": [],
        },
        "phase_index": {
            "phase": "01",
            "plan_count": 0,
            "plan_ids": [],
            "waves": {},
            "incomplete": [],
            "has_checkpoints": False,
            "validation_valid": True,
            "validation_errors": [],
        },
        "server_phase_info": {
            "error": "Phase 01 not found",
            "schema_version": 1,
        },
        "consistency": {
            "status": "ok" if not case.allowlisted_diffs else "allowlisted",
            "diffs": list(case.allowlisted_diffs),
        },
        "progress_parity": {
            "milestone_version": "v1.0",
            "milestone_name": "milestone",
            "phases": [] if case.fixture_relpath.startswith("mutation-ordering") else [
                {
                    "number": "05",
                    "name": "semiclassical ds proposal audit",
                    "plans": 0,
                    "summaries": 0,
                    "status": "Pending",
                },
                {
                    "number": "06",
                    "name": "entropy and hilbert space stress test",
                    "plans": 0,
                    "summaries": 0,
                    "status": "Pending",
                },
                {
                    "number": "07",
                    "name": "alternative bulk dual comparison",
                    "plans": 0,
                    "summaries": 0,
                    "status": "Pending",
                },
                {
                    "number": "08",
                    "name": "verdict and residual gaps",
                    "plans": 0,
                    "summaries": 0,
                    "status": "Pending",
                },
            ],
            "total_plans": 0,
            "total_summaries": 0,
            "percent": 0,
            "state_progress_percent": 0,
            "diverged": False,
            "warnings": [],
        },
    }


@pytest.mark.parametrize("case", PHASE_VERIFY_CASES, ids=lambda case: case.fixture_relpath.replace("/", "-"))
def test_projection_phase_verify_oracle(case: ProjectionCase, tmp_path: Path) -> None:
    workspace = _copy_fixture_workspace(case.fixture_relpath, tmp_path)

    record = _build_projection_record(workspace, case)
    expected = _expected_projection_record(case)

    assert record == expected
    assert _normalize_progress_payload(progress_render(workspace, "json")) == _normalize_progress_payload(
        get_progress(str(workspace))
    )
