"""Round-trip integration tests that exercise multiple gpd/core modules together.

These tests span phase create→list→complete, roadmap analyze→phase add→re-analyze,
phase remove with renumbering, milestone lifecycle, multi-level decimal phase handling,
and phase-complete state transitions.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from gpd.core.phases import (
    MilestoneIncompleteError,
    find_phase,
    list_phases,
    milestone_complete,
    next_decimal_phase,
    phase_add,
    phase_complete,
    phase_insert,
    phase_plan_index,
    phase_remove,
    progress_render,
    roadmap_analyze,
    roadmap_get_phase,
)

# ─── Helpers ───────────────────────────────────────────────────────────────────


def _setup_project(tmp_path: Path) -> Path:
    """Create a minimal GPD project structure."""
    (tmp_path / ".gpd" / "phases").mkdir(parents=True)
    return tmp_path


def _create_phase(tmp_path: Path, name: str) -> Path:
    d = tmp_path / ".gpd" / "phases" / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def _write_roadmap(tmp_path: Path, content: str) -> Path:
    p = tmp_path / ".gpd" / "ROADMAP.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content))
    return p


def _write_state(tmp_path: Path, content: str) -> Path:
    p = tmp_path / ".gpd" / "STATE.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(textwrap.dedent(content))
    return p


# ─── Phase Create → List → Complete Lifecycle ────────────────────────────────


class TestPhaseLifecycle:
    """Phase create→list→complete→next-phase round-trip.

    Ported from: "phase complete" describe block (~line 4807)
    """

    def _create_fixture(self, tmp_path: Path) -> Path:
        """3 phases, each with 1 plan + 1 summary."""
        _setup_project(tmp_path)
        _write_roadmap(
            tmp_path,
            """\
            # Research Roadmap v1.0

            ## Phase Overview

            - [ ] Phase 1: Setup
            - [ ] Phase 2: Derivation
            - [ ] Phase 3: Validation

            ### Phase 1: Setup

            **Goal:** Set up the theoretical framework
            **Plans:** 1 plans

            ### Phase 2: Derivation

            **Goal:** Derive the Hamiltonian
            **Plans:** 1 plans

            ### Phase 3: Validation

            **Goal:** Validate results
            **Plans:** 1 plans
            """,
        )
        _write_state(
            tmp_path,
            """\
            # Research State

            ## Current Position

            **Current Phase:** 1
            **Current Phase Name:** Setup
            **Total Phases:** 3
            **Current Plan:** 1
            **Total Plans in Phase:** 1
            **Status:** in_progress
            **Last Activity:** 2026-02-23
            **Last Activity Description:** Started
            """,
        )
        for num, name in [("01", "setup"), ("02", "derivation"), ("03", "validation")]:
            d = _create_phase(tmp_path, f"{num}-{name}")
            (d / f"{num}-01-PLAN.md").write_text("# Plan 1")
            (d / f"{num}-01-SUMMARY.md").write_text("# Summary 1")
        return tmp_path

    def test_completing_a_phase_updates_roadmap_and_advances_state(self, tmp_path: Path) -> None:
        self._create_fixture(tmp_path)
        result = phase_complete(tmp_path, "1")

        assert result.completed_phase == "1"
        assert result.next_phase == "02"
        assert result.is_last_phase is False

        # Roadmap should have a checked checkbox
        roadmap = (tmp_path / ".gpd" / "ROADMAP.md").read_text()
        assert "[x]" in roadmap

        # STATE.md should reflect transition
        state = (tmp_path / ".gpd" / "STATE.md").read_text()
        assert "Ready to plan" in state

    def test_completing_last_phase_marks_milestone_complete(self, tmp_path: Path) -> None:
        self._create_fixture(tmp_path)
        phase_complete(tmp_path, "1")
        phase_complete(tmp_path, "2")
        result = phase_complete(tmp_path, "3")

        assert result.is_last_phase is True
        assert result.next_phase is None

        state = (tmp_path / ".gpd" / "STATE.md").read_text()
        assert "Milestone complete" in state

    def test_sequential_phase_completion_preserves_history(self, tmp_path: Path) -> None:
        """Complete 3 phases sequentially and verify all checkboxes are marked."""
        self._create_fixture(tmp_path)
        phase_complete(tmp_path, "1")
        phase_complete(tmp_path, "2")
        phase_complete(tmp_path, "3")

        roadmap = (tmp_path / ".gpd" / "ROADMAP.md").read_text()
        # All 3 checkboxes should be checked
        assert roadmap.count("[x]") == 3


# ─── Phase Remove and Renumber ───────────────────────────────────────────────


class TestPhaseRemoveRenumber:
    """Phase removal with renumbering of subsequent phases.

    Ported from: "phase remove and renumber" describe block (~line 4930)
    """

    def _create_fixture(self, tmp_path: Path) -> Path:
        _setup_project(tmp_path)
        for num, name in [("01", "setup"), ("02", "derivation"), ("03", "validation")]:
            d = _create_phase(tmp_path, f"{num}-{name}")
            (d / f"{num}-01-PLAN.md").write_text("# Plan")
        _write_roadmap(
            tmp_path,
            """\
            # Research Roadmap v1.0

            ## Phase Overview

            - [ ] Phase 1: Setup
            - [ ] Phase 2: Derivation
            - [ ] Phase 3: Validation

            ### Phase 1: Setup

            **Goal:** Set up framework

            ### Phase 2: Derivation

            **Goal:** Derive equations

            ### Phase 3: Validation

            **Goal:** Validate results
            """,
        )
        return tmp_path

    def test_removes_phase_and_renumbers_subsequent(self, tmp_path: Path) -> None:
        self._create_fixture(tmp_path)
        result = phase_remove(tmp_path, "2")

        assert result.removed == "2"
        assert result.roadmap_updated is True

        phases = list_phases(tmp_path)
        assert phases.count == 2

        # Phase 01 should exist, former 03 should now be 02
        dirs = phases.directories
        assert any(d.startswith("01-") for d in dirs)
        assert any(d.startswith("02-validation") for d in dirs)

        # Files inside renamed directory should also be renumbered
        renamed_dir = next(d for d in dirs if d.startswith("02-validation"))
        files = list((tmp_path / ".gpd" / "phases" / renamed_dir).iterdir())
        assert any(f.name.startswith("02-") for f in files)

        # ROADMAP.md should no longer mention Phase 2: Derivation
        roadmap = (tmp_path / ".gpd" / "ROADMAP.md").read_text()
        assert "Phase 2: Derivation" not in roadmap

    def test_refuses_remove_with_summaries_without_force(self, tmp_path: Path) -> None:
        self._create_fixture(tmp_path)
        d = tmp_path / ".gpd" / "phases" / "02-derivation"
        (d / "02-01-SUMMARY.md").write_text("# Summary")

        with pytest.raises(Exception, match="force"):
            phase_remove(tmp_path, "2")

        # With force=True should succeed
        result = phase_remove(tmp_path, "2", force=True)
        assert result.removed == "2"


# ─── Roadmap Analyze → Phase Add → Re-Analyze Round-Trip ──────────────────


class TestRoadmapAddAnalyze:
    """Add phases and verify roadmap-analyze reflects them.

    Ported from: "roadmap analyze command" + "phase add command" describe blocks
    """

    def test_add_phase_then_analyze(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_roadmap(
            tmp_path,
            """\
            # Roadmap v1.0

            ## Milestone v1.0: Core

            ### Phase 1: Foundation

            **Goal:** Set up basics

            ---
            Progress tracking
            """,
        )
        _create_phase(tmp_path, "01-foundation")

        # Analyze before adding
        analysis1 = roadmap_analyze(tmp_path)
        assert analysis1.phase_count == 1

        # Add a new phase
        added = phase_add(tmp_path, "Analysis Step")
        assert added.phase_number == 2

        # Analyze again — should now have 2 phases
        analysis2 = roadmap_analyze(tmp_path)
        assert analysis2.phase_count == 2
        assert any(p.name == "Analysis Step" for p in analysis2.phases)

    def test_insert_then_analyze(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_roadmap(
            tmp_path,
            """\
            ### Phase 1: Setup

            **Goal:** Setup

            ### Phase 2: Final

            **Goal:** Wrap up
            """,
        )

        inserted = phase_insert(tmp_path, "1", "Urgent Fix")
        assert inserted.phase_number == "01.1"

        analysis = roadmap_analyze(tmp_path)
        assert any(p.number in ("1.1", "01.1") for p in analysis.phases)


# ─── Multi-Level Decimal Phase Handling ──────────────────────────────────────


class TestMultiLevelDecimalPhases:
    """Multi-level decimal phase creation and sorting.

    Ported from: "multi-level decimal phase handling" describe block (~line 9628)
    """

    def test_next_decimal_creates_second_level(self, tmp_path: Path) -> None:
        """Phase next-decimal creates X.Y.Z from X.Y base."""
        _setup_project(tmp_path)
        _create_phase(tmp_path, "02-derivation")
        _create_phase(tmp_path, "02.1-correction")
        _create_phase(tmp_path, "02.2-extension")

        result = next_decimal_phase(tmp_path, "02.1")
        assert result.next == "02.1.1"

    def test_next_decimal_increments_second_level(self, tmp_path: Path) -> None:
        """Phase next-decimal increments existing X.Y.Z."""
        _setup_project(tmp_path)
        _create_phase(tmp_path, "02-derivation")
        _create_phase(tmp_path, "02.1-correction")
        _create_phase(tmp_path, "02.1.1-detail")
        _create_phase(tmp_path, "02.1.2-detail2")

        result = next_decimal_phase(tmp_path, "02.1")
        assert result.next == "02.1.3"

    def test_phases_list_sorts_multi_level_decimals(self, tmp_path: Path) -> None:
        """Mixed integer and decimal phases sort correctly."""
        _setup_project(tmp_path)
        for name in [
            "02.2-extension",
            "01-foundation",
            "02-derivation",
            "02.1.1-sub-detail",
            "02.1-correction",
            "03-results",
        ]:
            d = _create_phase(tmp_path, name)
            (d / "PLAN.md").write_text("---\n---\n# Plan\n")

        result = list_phases(tmp_path)
        dirs = result.directories
        assert dirs.index("01-foundation") < dirs.index("02-derivation")
        assert dirs.index("02-derivation") < dirs.index("02.1-correction")
        assert dirs.index("02.1-correction") < dirs.index("02.1.1-sub-detail")
        assert dirs.index("02.1.1-sub-detail") < dirs.index("02.2-extension")
        assert dirs.index("02.2-extension") < dirs.index("03-results")

    def test_phases_sort_mixed_integer_and_decimal(self, tmp_path: Path) -> None:
        """From Batch 18: phases sorting with decimals."""
        _setup_project(tmp_path)
        for name in ["03-third", "01-first", "02-second", "01.1-decimal"]:
            _create_phase(tmp_path, name)

        result = list_phases(tmp_path)
        assert result.directories == ["01-first", "01.1-decimal", "02-second", "03-third"]


# ─── Milestone Complete Lifecycle ────────────────────────────────────────────


class TestMilestoneLifecycle:
    """Milestone complete: archive files, gather stats, update state.

    Ported from: "milestone complete command" + integration lifecycle test
    """

    def test_full_milestone_lifecycle(self, tmp_path: Path) -> None:
        """Complete all phases then archive milestone."""
        _setup_project(tmp_path)
        _write_roadmap(
            tmp_path,
            """\
            # Roadmap v1.0

            ## Milestone v1.0: Core Framework

            ### Phase 1: Setup

            **Goal:** Initialize
            **Plans:** 1 plans

            ### Phase 2: Build

            **Goal:** Build
            **Plans:** 1 plans
            """,
        )
        _write_state(
            tmp_path,
            """\
            # Research State

            ## Current Position

            **Current Phase:** 1
            **Status:** in_progress
            **Last Activity:** 2026-02-23
            **Last Activity Description:** Started
            """,
        )

        # Create phases with plans and summaries
        for num, name in [("01", "setup"), ("02", "build")]:
            d = _create_phase(tmp_path, f"{num}-{name}")
            (d / f"{num}-01-PLAN.md").write_text("---\nwave: 1\n---\n# Plan\n## Task 1\nDo it")
            (d / f"{num}-01-SUMMARY.md").write_text(
                f'---\none-liner: "Phase {num} done"\ncompleted: 2026-02-23\n---\n# Summary'
            )

        # Complete phases
        phase_complete(tmp_path, "1")
        phase_complete(tmp_path, "2")

        # Complete milestone
        result = milestone_complete(tmp_path, "v1.0", name="Core Framework")
        assert result.version == "v1.0"
        assert result.name == "Core Framework"
        assert result.phases == 2
        assert result.plans == 2
        assert result.milestones_updated is True
        assert result.archived.roadmap is True

        # Milestones file should exist
        milestones = (tmp_path / ".gpd" / "MILESTONES.md").read_text()
        assert "v1.0 Core Framework" in milestones

        # Archive should have ROADMAP copy
        archive = tmp_path / ".gpd" / "milestones" / "v1.0-ROADMAP.md"
        assert archive.exists()

    def test_milestone_incomplete_raises(self, tmp_path: Path) -> None:
        """Cannot complete milestone with incomplete phases."""
        _setup_project(tmp_path)
        _write_roadmap(tmp_path, "## v1.0\n")

        d = _create_phase(tmp_path, "01-x")
        (d / "a-PLAN.md").write_text("plan")
        # No summary — phase incomplete

        with pytest.raises(MilestoneIncompleteError):
            milestone_complete(tmp_path, "v1.0")

    def test_milestone_accomplishments_from_summaries(self, tmp_path: Path) -> None:
        """Milestone extracts one-liner accomplishments from summaries."""
        _setup_project(tmp_path)
        _write_roadmap(tmp_path, "## Milestone v1.0: Core\n### Phase 1: X\n**Goal:** x\n")

        d = _create_phase(tmp_path, "01-x")
        (d / "a-PLAN.md").write_text("plan")
        (d / "a-SUMMARY.md").write_text(
            '---\none-liner: "Established ground state framework"\ncompleted: 2026-02-23\n---\n'
        )

        result = milestone_complete(tmp_path, "v1.0", name="Core")
        assert "Established ground state framework" in result.accomplishments


# ─── Progress Render Round-Trip ──────────────────────────────────────────────


class TestProgressRoundTrip:
    """Progress rendering across all formats reflects phase state accurately."""

    def test_progress_reflects_phase_completion(self, tmp_path: Path) -> None:
        """Complete 1 of 2 phases → 50% progress."""
        _setup_project(tmp_path)
        _write_roadmap(tmp_path, "## v1.0: Test\n")

        d1 = _create_phase(tmp_path, "01-first")
        (d1 / "a-PLAN.md").write_text("plan")
        (d1 / "a-SUMMARY.md").write_text("done")

        d2 = _create_phase(tmp_path, "02-second")
        (d2 / "a-PLAN.md").write_text("plan")

        json_result = progress_render(tmp_path, "json")
        assert json_result.percent == 50
        assert json_result.total_plans == 2
        assert json_result.total_summaries == 1
        assert len(json_result.phases) == 2

        bar_result = progress_render(tmp_path, "bar")
        assert bar_result.percent == 50
        assert bar_result.completed == 1
        assert bar_result.total == 2

        table_result = progress_render(tmp_path, "table")
        assert "Complete" in table_result.rendered
        assert "Planned" in table_result.rendered


# ─── Phase Plan Index → Validate Waves Round-Trip ────────────────────────────


class TestPlanIndexWaveValidation:
    """Build plan index and validate wave dependencies together.

    Ported from: "phase-plan-index command" + "validate-waves" describe blocks
    """

    def test_index_and_validate_multi_wave_plan(self, tmp_path: Path) -> None:
        """3 plans across 2 waves with dependencies."""
        _setup_project(tmp_path)
        d = _create_phase(tmp_path, "01-setup")

        # Wave 1: two independent plans
        (d / "a-PLAN.md").write_text("---\nwave: 1\ndepends_on: []\n---\n## Task 1\nFirst")
        (d / "b-PLAN.md").write_text("---\nwave: 1\ndepends_on: []\n---\n## Task 1\nSecond")

        # Wave 2: depends on both wave 1 plans
        (d / "c-PLAN.md").write_text("---\nwave: 2\ndepends_on:\n  - a\n  - b\n---\n## Task 1\nThird")

        index = phase_plan_index(tmp_path, "1")
        assert len(index.plans) == 3
        assert "1" in index.waves
        assert "2" in index.waves
        assert len(index.waves["1"]) == 2
        assert len(index.waves["2"]) == 1
        assert index.validation.valid is True

    def test_index_detects_file_overlap_warning(self, tmp_path: Path) -> None:
        """Two plans in same wave modifying same file should produce warning.

        Ported from edge case 3: "same-wave file overlap in phase-plan-index"
        """
        _setup_project(tmp_path)
        d = _create_phase(tmp_path, "01-setup")
        (d / "a-PLAN.md").write_text('---\nwave: 1\ndepends_on: []\nfiles_modified: ["src/main.py"]\n---\n# A\n')
        (d / "b-PLAN.md").write_text(
            '---\nwave: 1\ndepends_on: []\nfiles_modified: ["src/main.py", "src/test.py"]\n---\n# B\n'
        )

        index = phase_plan_index(tmp_path, "1")
        assert any("src/main.py" in w for w in index.validation.warnings)

    def test_three_plans_overlapping_all_pairs_warned(self, tmp_path: Path) -> None:
        """3 plans touching same file in same wave = C(3,2)=3 overlap warnings."""
        _setup_project(tmp_path)
        d = _create_phase(tmp_path, "01-setup")
        for name in ["a", "b", "c"]:
            (d / f"{name}-PLAN.md").write_text(
                f'---\nwave: 1\ndepends_on: []\nfiles_modified: ["shared.py"]\n---\n# {name.upper()}\n'
            )

        index = phase_plan_index(tmp_path, "1")
        overlap_warnings = [w for w in index.validation.warnings if "shared.py" in w]
        assert len(overlap_warnings) >= 3


# ─── Find Phase → Roadmap Get Phase → Progress Consistency ───────────────────


class TestCrossModuleConsistency:
    """Verify find_phase, roadmap_get_phase, and progress_render return consistent data."""

    def test_find_and_roadmap_agree_on_phase_data(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_roadmap(
            tmp_path,
            """\
            ### Phase 1: Quantum Setup

            **Goal:** Initialize quantum framework
            """,
        )
        d = _create_phase(tmp_path, "01-quantum-setup")
        (d / "a-PLAN.md").write_text("plan")

        found = find_phase(tmp_path, "1")
        assert found is not None
        assert found.phase_number == "01"

        roadmap = roadmap_get_phase(tmp_path, "1")
        assert roadmap.found is True
        assert roadmap.phase_name == "Quantum Setup"
        assert roadmap.goal == "Initialize quantum framework"

    def test_find_phase_number_round_trips_into_roadmap_lookup(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_roadmap(
            tmp_path,
            """\
            ### Phase 1: Quantum Setup

            **Goal:** Initialize quantum framework
            """,
        )
        d = _create_phase(tmp_path, "01-quantum-setup")
        (d / "a-PLAN.md").write_text("plan")

        found = find_phase(tmp_path, "1")
        assert found is not None
        assert found.phase_number == "01"

        roadmap = roadmap_get_phase(tmp_path, found.phase_number)
        assert roadmap.found is True
        assert roadmap.phase_number == "1"
        assert roadmap.phase_name == "Quantum Setup"
        assert roadmap.goal == "Initialize quantum framework"

    def test_progress_and_analyze_agree_on_completion(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_roadmap(
            tmp_path,
            """\
            ## Milestone v1.0: Test

            ### Phase 1: Done Phase

            **Goal:** Finish

            ### Phase 2: Pending Phase

            **Goal:** Not done
            """,
        )

        d1 = _create_phase(tmp_path, "01-done")
        (d1 / "a-PLAN.md").write_text("plan")
        (d1 / "a-SUMMARY.md").write_text("done")

        _create_phase(tmp_path, "02-pending")

        progress = progress_render(tmp_path, "json")
        analysis = roadmap_analyze(tmp_path)

        assert progress.total_summaries == analysis.total_summaries
        assert progress.total_plans == analysis.total_plans
        assert analysis.completed_phases == 1
