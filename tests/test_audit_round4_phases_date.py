"""Regression test for date inconsistency bug in phases.py.

Bug: ``phase_complete`` and ``milestone_complete`` used ``date.today().isoformat()``
which returns the **local** date, while ``state.py`` uses
``datetime.now(tz=UTC).strftime("%Y-%m-%d")`` which returns the **UTC** date.
Near midnight the two could disagree.

Fix: both call sites now use ``datetime.now(tz=UTC).strftime("%Y-%m-%d")``.
"""

from __future__ import annotations

import inspect
import json
import textwrap
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from gpd.core.phases import (
    milestone_complete,
    phase_complete,
)
from gpd.core.state import default_state_dict

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_project(tmp_path: Path) -> Path:
    """Create a minimal GPD project structure."""
    planning = tmp_path / ".gpd"
    planning.mkdir()
    (planning / "phases").mkdir()
    return tmp_path


def _create_roadmap(tmp_path: Path, content: str) -> Path:
    roadmap = tmp_path / ".gpd" / "ROADMAP.md"
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text(textwrap.dedent(content))
    return roadmap


def _create_state(tmp_path: Path, content: str) -> Path:
    state = tmp_path / ".gpd" / "STATE.md"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(textwrap.dedent(content))
    return state


def _create_state_json(tmp_path: Path, *, current_phase: str = "01") -> Path:
    state = default_state_dict()
    pos = state.setdefault("position", {})
    pos["current_phase"] = current_phase
    pos["status"] = "Executing"
    pos["current_plan"] = "1"
    pos["total_plans_in_phase"] = 1
    pos["progress_percent"] = 50
    state_json_path = tmp_path / ".gpd" / "state.json"
    state_json_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return state_json_path


def _create_phase_dir(tmp_path: Path, name: str) -> Path:
    phase_dir = tmp_path / ".gpd" / "phases" / name
    phase_dir.mkdir(parents=True, exist_ok=True)
    return phase_dir


# ---------------------------------------------------------------------------
# Tests: phase_complete uses UTC date
# ---------------------------------------------------------------------------


class TestPhaseCompleteDateUTC:
    """phase_complete must use UTC date, not local date."""

    def test_phase_complete_uses_utc_date_near_midnight(self, tmp_path: Path) -> None:
        """Simulate 11:30 PM UTC on Jan 15 -- UTC date should be 2026-01-15."""
        _setup_project(tmp_path)
        _create_roadmap(
            tmp_path,
            """\
            ### Phase 1: Setup
            **Goal:** setup
            **Plans:** 1 plans

            ### Phase 2: Build
            **Goal:** build
            """,
        )
        _create_state(
            tmp_path,
            """\
            **Current Phase:** 1
            **Current Phase Name:** Setup
            **Total Phases:** 2
            **Current Plan:** 1
            **Total Plans in Phase:** 1
            **Status:** Executing
            **Last Activity:** 2026-01-01
            **Last Activity Description:** Working
            """,
        )
        _create_state_json(tmp_path, current_phase="01")

        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "a-PLAN.md").write_text("plan")
        (phase_dir / "a-SUMMARY.md").write_text("done")
        _create_phase_dir(tmp_path, "02-build")

        # 2026-01-15 23:30 UTC
        fake_utc = datetime(2026, 1, 15, 23, 30, 0, tzinfo=UTC)

        with patch("gpd.core.phases.datetime") as mock_dt:
            mock_dt.now.return_value = fake_utc
            result = phase_complete(tmp_path, "1")

        assert result.date == "2026-01-15", (
            f"Expected UTC date 2026-01-15 but got {result.date}"
        )

    def test_phase_complete_date_matches_state_format(self, tmp_path: Path) -> None:
        """Verify phase_complete produces dates in the same YYYY-MM-DD format as state.py."""
        _setup_project(tmp_path)
        _create_roadmap(
            tmp_path,
            """\
            ### Phase 1: Alpha
            **Goal:** alpha work
            **Plans:** 1 plans
            """,
        )

        phase_dir = _create_phase_dir(tmp_path, "01-alpha")
        (phase_dir / "a-PLAN.md").write_text("plan")
        (phase_dir / "a-SUMMARY.md").write_text("done")

        fake_utc = datetime(2026, 7, 4, 12, 0, 0, tzinfo=UTC)

        with patch("gpd.core.phases.datetime") as mock_dt:
            mock_dt.now.return_value = fake_utc
            result = phase_complete(tmp_path, "1")

        # Same format that state.py uses: YYYY-MM-DD
        assert result.date == "2026-07-04"


# ---------------------------------------------------------------------------
# Tests: milestone_complete uses UTC date
# ---------------------------------------------------------------------------


class TestMilestoneCompleteDateUTC:
    """milestone_complete must use UTC date, not local date."""

    def test_milestone_complete_uses_utc_date_near_midnight(self, tmp_path: Path) -> None:
        """Near-midnight UTC scenario for milestone_complete."""
        _setup_project(tmp_path)
        _create_roadmap(
            tmp_path,
            """\
            ## v1.0: First Release

            ### Phase 1: Setup
            **Goal:** setup
            **Plans:** 1 plans
            """,
        )
        _create_state(
            tmp_path,
            """\
            **Current Phase:** 1
            **Current Phase Name:** Setup
            **Total Phases:** 1
            **Current Plan:** 1
            **Total Plans in Phase:** 1
            **Status:** Executing
            **Last Activity:** 2026-01-01
            **Last Activity Description:** Working
            """,
        )
        _create_state_json(tmp_path, current_phase="01")

        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "a-PLAN.md").write_text("plan")
        (phase_dir / "a-SUMMARY.md").write_text("done")

        # Also need a REQUIREMENTS.md
        (tmp_path / ".gpd" / "REQUIREMENTS.md").write_text("# Requirements\n")

        fake_utc = datetime(2026, 3, 31, 23, 59, 0, tzinfo=UTC)

        with patch("gpd.core.phases.datetime") as mock_dt:
            mock_dt.now.return_value = fake_utc
            result = milestone_complete(tmp_path, version="v1.0")

        assert result.date == "2026-03-31", (
            f"Expected UTC date 2026-03-31 but got {result.date}"
        )


# ---------------------------------------------------------------------------
# Tests: import-level consistency
# ---------------------------------------------------------------------------


class TestDateImportConsistency:
    """Verify phases.py uses the same date mechanism as state.py."""

    def test_phases_imports_utc_and_datetime(self) -> None:
        """phases.py must import UTC and datetime from datetime module."""
        import gpd.core.phases as phases_mod

        assert hasattr(phases_mod, "datetime"), (
            "phases.py must import datetime from the datetime module"
        )
        assert hasattr(phases_mod, "UTC"), (
            "phases.py must import UTC from the datetime module"
        )

    def test_phases_does_not_use_date_today(self) -> None:
        """Verify phases.py source does not contain date.today() calls."""
        import gpd.core.phases as phases_mod

        source = inspect.getsource(phases_mod)
        assert "date.today()" not in source, (
            "phases.py should not use date.today(); use datetime.now(tz=UTC) instead"
        )
