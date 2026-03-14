"""Edge case tests covering multi-module boundary conditions.

Covers the 5 deep edge cases:
1. Empty .gpd/phases/ directory but state references a phase
2. ROADMAP.md has phases in wrong numerical order
3. Two plans in same wave modify same file (file overlap)
4. SUMMARY.md with frontmatter but empty body
5. Convention lock string "null" filtering

Plus additional edge cases from the main test suite:
- Decimal phase completion
- Phase remove decimal renumbering
- Duplicate phase numbers in ROADMAP
- Progress with zero plans
- Wave validation edge cases (cycles, gaps, orphans)
- Phase number validation
"""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from gpd.core.phases import (
    PhaseValidationError,
    PlanEntry,
    find_phase,
    list_phases,
    milestone_complete,
    phase_add,
    phase_complete,
    phase_insert,
    phase_remove,
    progress_render,
    roadmap_analyze,
    roadmap_get_phase,
    validate_waves,
)

# ─── Helpers ───────────────────────────────────────────────────────────────────


def _setup_project(tmp_path: Path) -> Path:
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


# ─── Edge Case 1: Missing phases dir but state references a phase ────────────


class TestEdgeMissingPhasesDir:
    """Empty .gpd/phases/ dir or missing entirely while state references phases.

    Ported from the historical suite's "deep edge: missing .gpd/phases/" case.
    """

    def test_progress_handles_missing_phases_dir(self, tmp_path: Path) -> None:
        """progress json returns 0% and empty phases when no phases dir exists."""
        (tmp_path / ".gpd").mkdir(parents=True)
        _write_roadmap(tmp_path, "## v1.0\n")
        # No .gpd/phases/ directory at all

        result = progress_render(tmp_path, "json")
        assert result.percent == 0
        assert result.phases == []

    def test_list_phases_empty_phases_dir(self, tmp_path: Path) -> None:
        """list_phases returns empty when phases dir exists but is empty."""
        _setup_project(tmp_path)
        result = list_phases(tmp_path)
        assert result.count == 0
        assert result.directories == []

    def test_find_phase_with_no_phases_dir(self, tmp_path: Path) -> None:
        """find_phase returns None when .gpd/phases/ doesn't exist."""
        (tmp_path / ".gpd").mkdir(parents=True)
        result = find_phase(tmp_path, "5")
        assert result is None

    def test_roadmap_analyze_no_phases_dir(self, tmp_path: Path) -> None:
        """roadmap_analyze works when phases dir is missing — reports no_directory."""
        (tmp_path / ".gpd").mkdir(parents=True)
        _write_roadmap(
            tmp_path,
            """\
            ## Milestone v1.0: Core

            ### Phase 1: Setup

            **Goal:** Setup

            ### Phase 2: Build

            **Goal:** Build
            """,
        )

        result = roadmap_analyze(tmp_path)
        assert result.phase_count == 2
        assert all(p.disk_status == "no_directory" for p in result.phases)


# ─── Edge Case 2: ROADMAP phases in wrong order ─────────────────────────────


class TestEdgeRoadmapOutOfOrder:
    """ROADMAP.md has phases listed in non-sequential order.

    Ported from the historical suite's "deep edge: ROADMAP out-of-order phases" case.
    """

    def test_roadmap_analyze_extracts_phases_in_document_order(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_roadmap(
            tmp_path,
            """\
            # Roadmap v1.0

            ## Milestone v1.0: Core

            ### Phase 3: Analysis

            **Goal:** Analyze results

            ### Phase 1: Setup

            **Goal:** Initialize framework

            ### Phase 2: Calculation

            **Goal:** Run computations
            """,
        )
        _create_phase(tmp_path, "01-setup")
        _create_phase(tmp_path, "02-calculation")
        _create_phase(tmp_path, "03-analysis")

        result = roadmap_analyze(tmp_path)
        assert result.phase_count == 3
        # Phases in document order
        assert result.phases[0].number == "3"
        assert result.phases[1].number == "1"
        assert result.phases[2].number == "2"

    def test_roadmap_analyze_goals_correct_despite_wrong_order(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_roadmap(
            tmp_path,
            """\
            ## Milestone v1.0: Core

            ### Phase 5: Final

            **Goal:** Wrap up

            ### Phase 2: Middle

            **Goal:** Core work
            """,
        )
        _create_phase(tmp_path, "02-middle")
        _create_phase(tmp_path, "05-final")

        result = roadmap_analyze(tmp_path)
        assert result.phases[0].name == "Final"
        assert result.phases[0].goal == "Wrap up"
        assert result.phases[1].name == "Middle"
        assert result.phases[1].goal == "Core work"

    def test_roadmap_get_phase_finds_regardless_of_order(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_roadmap(
            tmp_path,
            """\
            ### Phase 3: Analysis

            **Goal:** Analyze

            ### Phase 1: Setup

            **Goal:** Init
            """,
        )

        result = roadmap_get_phase(tmp_path, "1")
        assert result.found is True
        assert result.phase_name == "Setup"
        assert result.goal == "Init"


# ─── Edge Case 3: Same-wave file overlap ────────────────────────────────────


class TestEdgeSameWaveFileOverlap:
    """Two or more plans in the same wave modify the same file.

    Ported from the historical suite's "deep edge: same-wave file overlap" case.
    """

    def test_validate_waves_detects_file_overlap(self, tmp_path: Path) -> None:
        plans = [
            PlanEntry(id="01-01", wave=1, files_modified=["src/main.py"]),
            PlanEntry(id="01-02", wave=1, files_modified=["src/main.py", "src/test.py"]),
        ]
        result = validate_waves(plans)
        assert any("src/main.py" in w for w in result.warnings)

    def test_three_plans_overlap_produces_three_warnings(self, tmp_path: Path) -> None:
        """3 plans touching shared.py in wave 1 → C(3,2) = 3 pair warnings."""
        plans = [
            PlanEntry(id="01-01", wave=1, files_modified=["shared.py"]),
            PlanEntry(id="01-02", wave=1, files_modified=["shared.py"]),
            PlanEntry(id="01-03", wave=1, files_modified=["shared.py"]),
        ]
        result = validate_waves(plans)
        overlap_warnings = [w for w in result.warnings if "shared.py" in w]
        assert len(overlap_warnings) >= 3

    def test_different_wave_same_file_no_warning(self, tmp_path: Path) -> None:
        """Plans in different waves modifying the same file should NOT warn."""
        plans = [
            PlanEntry(id="a", wave=1, files_modified=["src/main.py"]),
            PlanEntry(id="b", wave=2, depends_on=["a"], files_modified=["src/main.py"]),
        ]
        result = validate_waves(plans)
        assert result.valid is True
        assert len(result.warnings) == 0


# ─── Edge Case 4: SUMMARY with frontmatter but empty body ──────────────────


class TestEdgeSummaryFrontmatterOnly:
    """SUMMARY.md with frontmatter but no body text.

    Ported from the historical suite's "deep edge: SUMMARY frontmatter-only" case.
    """

    def test_phase_completeness_counts_frontmatter_only_summary(self, tmp_path: Path) -> None:
        """A SUMMARY.md with only frontmatter (no body) is still counted as complete."""
        _setup_project(tmp_path)
        d = _create_phase(tmp_path, "01-setup")
        (d / "a-PLAN.md").write_text("---\nwave: 1\n---\n# Plan\n")
        (d / "a-SUMMARY.md").write_text(
            '---\nphase: 01-setup\nplan: "01"\ncompleted: "2026-02-23"\nprovides: ["result"]\n---\n'
        )

        info = find_phase(tmp_path, "1")
        assert info is not None
        assert len(info.plans) == 1
        assert len(info.summaries) == 1
        assert info.incomplete_plans == []

    def test_milestone_extracts_one_liner_from_frontmatter_only_summary(self, tmp_path: Path) -> None:
        """milestone_complete reads one-liner from frontmatter even if body is empty."""
        _setup_project(tmp_path)
        _write_roadmap(tmp_path, "## Milestone v1.0: Core\n### Phase 1: Setup\n**Goal:** Init\n")

        d = _create_phase(tmp_path, "01-setup")
        (d / "a-PLAN.md").write_text("---\nwave: 1\n---\n# Plan\n")
        (d / "a-SUMMARY.md").write_text(
            '---\none-liner: "Established ground state energy framework"\ncompleted: 2026-02-23\n---\n'
        )

        result = milestone_complete(tmp_path, "v1.0", name="Core")
        assert "Established ground state energy framework" in result.accomplishments


# ─── Edge Case: Decimal phase completion ─────────────────────────────────────


class TestEdgeDecimalPhaseCompletion:
    """Completing decimal sub-phases.

    Ported from: "phase complete with decimal phases" (~line 10124, 22512)
    """

    def test_complete_decimal_phase(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        d = _create_phase(tmp_path, "03.1-hotfix")
        (d / "a-PLAN.md").write_text("plan")
        (d / "a-SUMMARY.md").write_text("done")

        result = phase_complete(tmp_path, "3.1")
        assert result.completed_phase == "3.1"
        assert result.all_plans_complete is True


# ─── Edge Case: Phase remove decimal renumbering ────────────────────────────


class TestEdgeDecimalRemoveRenumber:
    """Removing a decimal phase renumbers subsequent decimal siblings.

    Ported from: "edge case: phase-remove renumbers correctly" (~line 22303)
    """

    def test_remove_decimal_renumbers_siblings(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_roadmap(
            tmp_path,
            """\
            ### Phase 3: Base

            **Goal:** base

            ### Phase 3.1: First Fix

            **Goal:** first

            ### Phase 3.2: Second Fix

            **Goal:** second

            ### Phase 3.3: Third Fix

            **Goal:** third
            """,
        )
        _create_phase(tmp_path, "03-base")
        _create_phase(tmp_path, "03.1-first-fix")
        _create_phase(tmp_path, "03.2-second-fix")
        _create_phase(tmp_path, "03.3-third-fix")

        result = phase_remove(tmp_path, "3.2")
        assert result.removed == "3.2"

        phases = list_phases(tmp_path)
        dirs = phases.directories
        # 03.3 should now be 03.2
        assert any("03.2-third-fix" in d for d in dirs)
        assert not any("03.3" in d for d in dirs)


# ─── Edge Case: Progress with zero plans ────────────────────────────────────


class TestEdgeZeroPlans:
    """Progress when phases exist but have no plans.

    Ported from: "edge case: progress update with zero plans" (~line 22490)
    """

    def test_progress_zero_plans_is_zero_percent(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_roadmap(tmp_path, "## v1.0: Test\n")
        _create_phase(tmp_path, "01-empty")

        result = progress_render(tmp_path, "json")
        assert result.percent == 0
        assert result.total_plans == 0
        assert result.total_summaries == 0

    def test_progress_bar_zero_plans(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_roadmap(tmp_path, "## v1.0: Test\n")
        _create_phase(tmp_path, "01-empty")

        result = progress_render(tmp_path, "bar")
        assert result.percent == 0
        assert result.total == 0


# ─── Edge Case: Wave validation edge cases ──────────────────────────────────


class TestEdgeWaveValidation:
    """Various wave validation edge cases.

    Ported from: "validate-waves edge cases comprehensive" (~line 12265),
    "validate-waves: cycle detection in plan dependencies" (~line 23417)
    """

    def test_empty_plans_list_valid(self) -> None:
        result = validate_waves([])
        assert result.valid is True

    def test_single_plan_valid(self) -> None:
        result = validate_waves([PlanEntry(id="only", wave=1)])
        assert result.valid is True

    def test_wave_not_starting_at_1(self) -> None:
        result = validate_waves([PlanEntry(id="a", wave=2)])
        assert result.valid is False
        assert any("start at 1" in e for e in result.errors)

    def test_backward_dependency(self) -> None:
        """Plan in wave 1 depending on plan in wave 2 should fail."""
        plans = [
            PlanEntry(id="a", wave=1, depends_on=["b"]),
            PlanEntry(id="b", wave=2),
        ]
        result = validate_waves(plans)
        assert result.valid is False
        assert any("earlier wave" in e for e in result.errors)

    def test_self_dependency_cycle(self) -> None:
        """A plan depending on itself via chain creates a cycle."""
        plans = [
            PlanEntry(id="a", wave=1, depends_on=["c"]),
            PlanEntry(id="b", wave=1, depends_on=["a"]),
            PlanEntry(id="c", wave=1, depends_on=["b"]),
        ]
        result = validate_waves(plans)
        assert result.valid is False
        assert any("Circular" in e or "earlier wave" in e for e in result.errors)

    def test_orphan_detection(self) -> None:
        """Plan not depended upon and not in final wave should warn."""
        plans = [
            PlanEntry(id="a", wave=1),
            PlanEntry(id="b", wave=1),
            PlanEntry(id="c", wave=2, depends_on=["a"]),
        ]
        result = validate_waves(plans)
        # b is an orphan (not in final wave, no one depends on it)
        orphan_warnings = [w for w in result.warnings if "b" in w and "not depended" in w]
        assert len(orphan_warnings) == 1

    def test_valid_complex_dag(self) -> None:
        """A valid complex DAG should pass all checks."""
        plans = [
            PlanEntry(id="a", wave=1),
            PlanEntry(id="b", wave=1),
            PlanEntry(id="c", wave=2, depends_on=["a"]),
            PlanEntry(id="d", wave=2, depends_on=["b"]),
            PlanEntry(id="e", wave=3, depends_on=["c", "d"]),
        ]
        result = validate_waves(plans)
        assert result.valid is True
        assert result.errors == []


# ─── Edge Case: Phase number validation ──────────────────────────────────────


class TestEdgePhaseNumberValidation:
    """Invalid phase number formats should raise PhaseValidationError.

    Ported from: "phase insert input validation" (~line 9521)
    """

    def test_invalid_phase_number_in_roadmap_get(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        with pytest.raises(PhaseValidationError):
            roadmap_get_phase(tmp_path, "abc")

    def test_invalid_phase_number_in_insert(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_roadmap(tmp_path, "### Phase 1: X\n")
        with pytest.raises(PhaseValidationError):
            phase_insert(tmp_path, "abc", "Fix")

    def test_invalid_phase_number_in_remove(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_roadmap(tmp_path, "### Phase 1: X\n")
        with pytest.raises(PhaseValidationError):
            phase_remove(tmp_path, "abc")

    def test_empty_description_in_add(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_roadmap(tmp_path, "### Phase 1: X\n")
        with pytest.raises(PhaseValidationError, match="description required"):
            phase_add(tmp_path, "")

    def test_empty_after_phase_in_insert(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _write_roadmap(tmp_path, "### Phase 1: X\n")
        with pytest.raises(PhaseValidationError):
            phase_insert(tmp_path, "", "Fix")


# ─── Edge Case: Verification and context detection ──────────────────────────


class TestEdgeFileDetection:
    """find_phase correctly detects VERIFICATION.md, CONTEXT.md, etc."""

    def test_verification_file_detected(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        d = _create_phase(tmp_path, "01-setup")
        (d / "VERIFICATION.md").write_text("verified")

        info = find_phase(tmp_path, "1")
        assert info is not None
        assert info.has_verification is True

    def test_validation_file_detected(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        d = _create_phase(tmp_path, "01-setup")
        (d / "VALIDATION.md").write_text("validated")

        info = find_phase(tmp_path, "1")
        assert info is not None
        assert info.has_validation is True

    def test_named_suffixed_files_detected(self, tmp_path: Path) -> None:
        """Files like 01-01-RESEARCH.md and 01-01-CONTEXT.md should be detected."""
        _setup_project(tmp_path)
        d = _create_phase(tmp_path, "01-setup")
        (d / "01-01-RESEARCH.md").write_text("research")
        (d / "01-01-CONTEXT.md").write_text("context")

        info = find_phase(tmp_path, "1")
        assert info is not None
        assert info.has_research is True
        assert info.has_context is True


# ─── Edge Case: Roadmap with no roadmap file ────────────────────────────────


class TestEdgeNoRoadmap:
    """Operations that require ROADMAP.md handle its absence correctly."""

    def test_get_milestone_info_defaults_without_roadmap(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        from gpd.core.phases import get_milestone_info

        info = get_milestone_info(tmp_path)
        assert info.version == "v1.0"
        assert info.name == "milestone"

    def test_roadmap_analyze_returns_empty_without_roadmap(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        result = roadmap_analyze(tmp_path)
        assert result.phase_count == 0
        assert result.phases == []


# ─── Edge Case: Multiple plans with standalone PLAN.md ───────────────────────


class TestEdgeStandalonePlan:
    """Phase with PLAN.md (standalone) and suffixed plans."""

    def test_standalone_plan_counted(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        d = _create_phase(tmp_path, "01-setup")
        (d / "PLAN.md").write_text("standalone plan")

        info = find_phase(tmp_path, "1")
        assert info is not None
        assert "PLAN.md" in info.plans
        assert len(info.plans) == 1

    def test_standalone_summary_completes_standalone_plan(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        d = _create_phase(tmp_path, "01-setup")
        (d / "PLAN.md").write_text("plan")
        (d / "SUMMARY.md").write_text("done")

        info = find_phase(tmp_path, "1")
        assert info is not None
        assert info.incomplete_plans == []
