"""Behavior-focused state regression coverage."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest

_SAMPLE_STATE_MD = """\
# Research State

## Project Reference

See: GPD/PROJECT.md (updated 2026-03-08)

**Core research question:** What is the mass gap in Yang-Mills theory?
**Current focus:** Lattice simulations

## Current Position

**Current Phase:** 2
**Current Phase Name:** Formulate Hamiltonian
**Total Phases:** 6
**Current Plan:** 1
**Total Plans in Phase:** 3
**Status:** Executing
**Last Activity:** 2026-03-08
**Last Activity Description:** Set up lattice parameters

**Progress:** [####......] 40%

## Active Calculations

None yet.

## Intermediate Results

None yet.

## Open Questions

None yet.

## Performance Metrics

| Label | Duration | Tasks | Files |
| ----- | -------- | ----- | ----- |

## Accumulated Context

### Decisions

None yet.

### Active Approximations

None yet.

**Convention Lock:**

No conventions locked yet.

### Propagated Uncertainties

None yet.

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

**Last session:** 2026-03-08T14:00:00+00:00
**Stopped at:** Phase 2 P1
**Resume file:** —
"""


def _make_state_md(tmp_path: Path) -> Path:
    gpd_dir = tmp_path / "GPD"
    gpd_dir.mkdir(parents=True)
    state_md = gpd_dir / "STATE.md"
    state_md.write_text(
        "# State\n\n"
        "## Current Position\n\n"
        "**Status:** Active\n\n"
        "### Decisions\nNone yet.\n\n"
        "### Blockers/Concerns\nNone.\n",
        encoding="utf-8",
    )
    (gpd_dir / "state.json").write_text("{}", encoding="utf-8")
    return state_md


def test_decision_newlines_are_sanitized(tmp_path: Path) -> None:
    from gpd.core.state import state_add_decision

    state_md = _make_state_md(tmp_path)
    result = state_add_decision(
        tmp_path,
        summary="Line one\nLine two\nLine three",
        phase="1",
        rationale="Because\nof\nthis",
    )

    assert result.added is True
    content = state_md.read_text(encoding="utf-8")
    assert "Line one Line two Line three" in content


def test_blocker_newlines_are_sanitized(tmp_path: Path) -> None:
    from gpd.core.state import state_add_blocker

    state_md = _make_state_md(tmp_path)
    result = state_add_blocker(tmp_path, "Problem\nwith\nspacing")

    assert result.added is True
    assert "Problem with spacing" in state_md.read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("exc", "expected_level"),
    [
        (FileNotFoundError("missing continuation data"), logging.DEBUG),
        (RuntimeError("unexpected continuation failure"), logging.WARNING),
    ],
)
def test_recent_project_projection_logs_missing_cache_quietly_and_surfaces_unexpected_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    exc: BaseException,
    expected_level: int,
) -> None:
    from gpd.core import state as state_module

    def _boom(*args, **kwargs):
        raise exc

    monkeypatch.setattr(state_module, "resolve_continuation", _boom)

    with caplog.at_level(logging.DEBUG, logger="gpd.core.state"):
        assert state_module._project_recent_project_entry(tmp_path, {}, existing=None) is None

    projection_records = [record for record in caplog.records if "recent-project projection" in record.message.lower()]
    assert projection_records
    assert any(record.levelno == expected_level for record in projection_records)
    if expected_level == logging.DEBUG:
        assert all(record.levelno < logging.WARNING for record in projection_records)


def test_recent_project_projection_prefers_active_handoff_over_completed_bounded_segment(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from gpd.core.constants import ENV_DATA_DIR
    from gpd.core.recent_projects import load_recent_projects_index
    from gpd.core.state import default_state_dict, save_state_json

    data_dir = tmp_path / "data"
    project_root = tmp_path / "project"
    handoff_rel = "GPD/phases/01/.continue-here.md"
    bounded_rel = "GPD/phases/02/.continue-here.md"
    handoff_file = project_root / handoff_rel
    bounded_file = project_root / bounded_rel
    handoff_file.parent.mkdir(parents=True)
    bounded_file.parent.mkdir(parents=True)
    handoff_file.write_text("resume handoff\n", encoding="utf-8")
    bounded_file.write_text("completed segment\n", encoding="utf-8")
    monkeypatch.setenv(ENV_DATA_DIR, str(data_dir))

    state = default_state_dict()
    state["continuation"] = {
        "schema_version": 1,
        "handoff": {
            "resume_file": handoff_rel,
            "stopped_at": "Phase 1 Plan 1",
            "last_result_id": "handoff-result",
            "recorded_at": "2026-04-19T10:00:00Z",
        },
        "bounded_segment": {
            "resume_file": bounded_rel,
            "phase": "02",
            "plan": "03",
            "segment_id": "completed-segment",
            "segment_status": "completed",
            "transition_id": "transition-completed",
            "last_result_id": "bounded-result",
            "updated_at": "2026-04-19T11:00:00Z",
            "source_session_id": "session-completed",
        },
        "machine": {},
    }

    save_state_json(project_root, state)

    index = load_recent_projects_index()
    assert len(index.rows) == 1
    row = index.rows[0]
    assert row.resume_target_kind == "handoff"
    assert row.resume_file == handoff_rel
    assert row.source_kind == "continuation.handoff"
    assert row.last_result_id == "handoff-result"
    assert row.stopped_at == "Phase 1 Plan 1"
    assert row.resumable is True
