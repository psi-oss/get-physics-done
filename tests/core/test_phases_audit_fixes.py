"""Regression tests for 4 bugs fixed in gpd.core.phases (audit batch).

Each test targets a specific fix:

1. progress_render JSON output must NOT include a stale ``total_plans_in_phase`` field.
2. validate_phase_waves must handle unreadable (invalid-UTF-8) plan files gracefully.
3. phase_plan_index must handle unreadable plan files gracefully.
4. milestone_complete must wrap unreadable summary files in PhaseValidationError.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from gpd.core.phases import (
    PhaseValidationError,
    ProgressJsonResult,
    milestone_complete,
    phase_plan_index,
    progress_render,
    validate_phase_waves,
)

# --- Helpers ----------------------------------------------------------------


def _setup_project(tmp_path: Path) -> Path:
    """Create a minimal GPD project structure and return project root."""
    planning = tmp_path / ".gpd"
    planning.mkdir()
    (planning / "phases").mkdir()
    return tmp_path


def _create_phase_dir(tmp_path: Path, name: str) -> Path:
    """Create a phase directory and return its path."""
    phase_dir = tmp_path / ".gpd" / "phases" / name
    phase_dir.mkdir(parents=True, exist_ok=True)
    return phase_dir


def _create_roadmap(tmp_path: Path, content: str) -> Path:
    """Write ROADMAP.md and return its path."""
    roadmap = tmp_path / ".gpd" / "ROADMAP.md"
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text(textwrap.dedent(content))
    return roadmap


def _create_state(tmp_path: Path, content: str) -> Path:
    """Write STATE.md and return its path."""
    state = tmp_path / ".gpd" / "STATE.md"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(textwrap.dedent(content))
    return state


# --- Bug 1: progress_render must not include total_plans_in_phase -----------


class TestProgressRenderNoMisleadingField:
    """progress_render JSON result must expose ``total_plans`` but never
    ``total_plans_in_phase``."""

    def test_progress_render_json_has_no_total_plans_in_phase(self, tmp_path: Path) -> None:
        """With two phases the JSON result must carry total_plans, not the
        removed total_plans_in_phase field."""
        _setup_project(tmp_path)
        _create_roadmap(
            tmp_path,
            """\
            ## Milestone v1.0: Test

            ### Phase 1: Setup
            **Goal:** Initialize
            **Plans:** 2 plans

            ### Phase 2: Work
            **Goal:** Do things
            **Plans:** 1 plans
            """,
        )

        # Phase 1 -- two plans, one completed
        p1 = _create_phase_dir(tmp_path, "01-setup")
        (p1 / "a-PLAN.md").write_text(
            "---\nwave: 1\nfiles_modified: []\ndepends_on: []\n---\n# Plan A\n"
        )
        (p1 / "a-SUMMARY.md").write_text(
            "---\none-liner: Done A\nstatus: complete\n---\n# Summary A\n"
        )
        (p1 / "b-PLAN.md").write_text(
            "---\nwave: 1\nfiles_modified: []\ndepends_on: []\n---\n# Plan B\n"
        )

        # Phase 2 -- one plan, not completed
        p2 = _create_phase_dir(tmp_path, "02-work")
        (p2 / "c-PLAN.md").write_text(
            "---\nwave: 1\nfiles_modified: []\ndepends_on: []\n---\n# Plan C\n"
        )

        result = progress_render(tmp_path, "json")

        # Must be the right type
        assert isinstance(result, ProgressJsonResult)

        # total_plans should aggregate across all phases
        assert result.total_plans == 3
        assert result.total_summaries == 1

        # The stale extra field must NOT be present
        assert not hasattr(result, "total_plans_in_phase"), (
            "ProgressJsonResult should not carry the misleading 'total_plans_in_phase' field"
        )
        dumped = result.model_dump()
        assert "total_plans_in_phase" not in dumped


# --- Bug 2: validate_phase_waves handles unreadable plan file gracefully ----


class TestValidatePhaseWavesUnreadablePlan:
    """validate_phase_waves must not raise on invalid-UTF-8 plan files; it
    should report validation errors instead."""

    def test_invalid_utf8_plan_produces_validation_error(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")

        # Write a valid plan so the phase is discovered
        (phase_dir / "a-PLAN.md").write_text(
            "---\nwave: 1\nfiles_modified: []\ndepends_on: []\n---\n# Valid plan\n"
        )

        # Write a binary-garbage plan that cannot be decoded as UTF-8
        (phase_dir / "b-PLAN.md").write_bytes(b"\x80\x81\x82")

        # Must NOT raise -- should return a result with invalid validation
        result = validate_phase_waves(tmp_path, "1")

        assert result.validation.valid is False
        assert any("b-PLAN.md" in err for err in result.validation.errors), (
            f"Expected an error mentioning 'b-PLAN.md', got: {result.validation.errors}"
        )


# --- Bug 3: phase_plan_index handles unreadable plan file gracefully --------


class TestPhasePlanIndexUnreadablePlan:
    """phase_plan_index must not raise on invalid-UTF-8 plan files; it should
    report validation errors instead."""

    def test_invalid_utf8_plan_produces_validation_error(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")

        # One valid plan
        (phase_dir / "a-PLAN.md").write_text(
            "---\nwave: 1\nfiles_modified: []\ndepends_on: []\n---\n# Valid plan\n"
        )

        # One corrupt plan
        (phase_dir / "b-PLAN.md").write_bytes(b"\x80\x81\x82")

        # Must NOT raise
        result = phase_plan_index(tmp_path, "1")

        assert result.validation.valid is False
        assert any("b-PLAN.md" in err for err in result.validation.errors), (
            f"Expected an error mentioning 'b-PLAN.md', got: {result.validation.errors}"
        )


# --- Bug 4: milestone_complete wraps unreadable summary in PhaseValidationError


class TestMilestoneCompleteUnreadableSummary:
    """milestone_complete must raise PhaseValidationError (not a raw
    OSError/UnicodeDecodeError) when a summary file contains invalid bytes."""

    def test_invalid_utf8_summary_raises_phase_validation_error(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_roadmap(
            tmp_path,
            """\
            ## Milestone v1.0: Test

            ### Phase 1: Setup
            **Goal:** Initialize
            **Plans:** 1 plans
            """,
        )

        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "a-PLAN.md").write_text(
            "---\nwave: 1\nfiles_modified: []\ndepends_on: []\n---\n# Plan\n"
        )

        # Write a summary that looks correct to the file-system (right name,
        # matched plan) but contains invalid UTF-8 bytes so read_text will fail.
        (phase_dir / "a-SUMMARY.md").write_bytes(b"\x80\x81\x82")

        # The function must wrap the decode error into PhaseValidationError,
        # not let the raw UnicodeDecodeError bubble up.
        with pytest.raises(PhaseValidationError) as exc_info:
            milestone_complete(tmp_path, "v1.0", name="Test")

        assert "a-SUMMARY.md" in str(exc_info.value)
