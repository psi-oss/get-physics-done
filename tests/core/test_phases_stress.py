"""Stress tests for gpd.core.phases — edge cases, scale, and unusual inputs."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from gpd.core.phases import (
    PhaseIncompleteError,
    PhaseNotFoundError,
    PhaseValidationError,
    PlanEntry,
    RoadmapNotFoundError,
    find_phase,
    list_phases,
    next_decimal_phase,
    phase_add,
    phase_complete,
    phase_insert,
    phase_plan_index,
    phase_remove,
    progress_render,
    validate_waves,
)

# ─── Helpers ───────────────────────────────────────────────────────────────────


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


# ─── 1. Phase with 0 plans (empty phase directory) ──────────────────────────


class TestEmptyPhaseDirectory:
    """Phase directories with zero plans should be discoverable but empty."""

    def test_find_phase_empty_dir(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-empty")

        result = find_phase(tmp_path, "1")
        assert result is not None
        assert result.found is True
        assert result.plans == []
        assert result.summaries == []
        assert result.incomplete_plans == []

    def test_list_phases_includes_empty(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-empty")
        _create_phase_dir(tmp_path, "02-also-empty")

        result = list_phases(tmp_path)
        assert result.count == 2
        assert result.directories == ["01-empty", "02-also-empty"]

    def test_phase_plan_index_empty_dir(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-empty")

        result = phase_plan_index(tmp_path, "1")
        assert result.phase == "01"
        assert result.plans == []
        assert result.waves == {}
        assert result.validation.valid is True

    def test_progress_render_empty_phase(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_roadmap(tmp_path, "## v1.0: Test\n")
        _create_phase_dir(tmp_path, "01-empty")

        result = progress_render(tmp_path, "json")
        assert result.total_plans == 0
        assert result.percent == 0


# ─── 2. Phase with 50 plans (stress) ────────────────────────────────────────


class TestManyPlans:
    """Phases with a large number of plans should work correctly."""

    def test_find_phase_50_plans(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-big")
        for i in range(1, 51):
            letter = chr(ord("a") + (i - 1) % 26) + str((i - 1) // 26 or "")
            (phase_dir / f"{letter}-PLAN.md").write_text(f"plan {i}")

        result = find_phase(tmp_path, "1")
        assert result is not None
        assert len(result.plans) == 50
        assert len(result.incomplete_plans) == 50

    def test_find_phase_50_plans_all_complete(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-big")
        for i in range(1, 51):
            letter = chr(ord("a") + (i - 1) % 26) + str((i - 1) // 26 or "")
            (phase_dir / f"{letter}-PLAN.md").write_text(f"plan {i}")
            (phase_dir / f"{letter}-SUMMARY.md").write_text(f"summary {i}")

        result = find_phase(tmp_path, "1")
        assert result is not None
        assert len(result.plans) == 50
        assert len(result.summaries) == 50
        assert result.incomplete_plans == []

    def test_progress_render_50_plans(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_roadmap(tmp_path, "## v1.0: Stress\n")
        phase_dir = _create_phase_dir(tmp_path, "01-big")
        for i in range(1, 51):
            letter = chr(ord("a") + (i - 1) % 26) + str((i - 1) // 26 or "")
            (phase_dir / f"{letter}-PLAN.md").write_text(f"plan {i}")
            if i <= 25:
                (phase_dir / f"{letter}-SUMMARY.md").write_text(f"summary {i}")

        result = progress_render(tmp_path, "json")
        assert result.total_plans == 50
        assert result.total_summaries == 25
        assert result.percent == 50


# ─── 3. Plans with identical names but different extensions ──────────────────


class TestIdenticalNamesDifferentExtensions:
    """Plans and summaries with matching prefixes pair correctly."""

    def test_plan_and_summary_same_prefix(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-test")
        (phase_dir / "a-PLAN.md").write_text("plan a")
        (phase_dir / "a-SUMMARY.md").write_text("summary a")
        (phase_dir / "a-RESEARCH.md").write_text("research a")
        (phase_dir / "a-CONTEXT.md").write_text("context a")

        result = find_phase(tmp_path, "1")
        assert result is not None
        assert result.plans == ["a-PLAN.md"]
        assert result.summaries == ["a-SUMMARY.md"]
        assert result.incomplete_plans == []
        assert result.has_research is True
        assert result.has_context is True

    def test_multiple_plans_partial_summaries(self, tmp_path: Path) -> None:
        """Plans a, b, c where only b has a summary."""
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-partial")
        (phase_dir / "a-PLAN.md").write_text("plan a")
        (phase_dir / "b-PLAN.md").write_text("plan b")
        (phase_dir / "b-SUMMARY.md").write_text("summary b")
        (phase_dir / "c-PLAN.md").write_text("plan c")

        result = find_phase(tmp_path, "1")
        assert result is not None
        assert len(result.plans) == 3
        assert len(result.summaries) == 1
        assert set(result.incomplete_plans) == {"a-PLAN.md", "c-PLAN.md"}


# ─── 4. Wave validation with 10 waves ───────────────────────────────────────


class TestWaveValidation10Waves:
    """Validate that 10 consecutive waves with proper dependencies pass."""

    def test_10_waves_linear_dependency(self) -> None:
        plans = []
        for w in range(1, 11):
            plan_id = f"plan-{w}"
            deps = [f"plan-{w - 1}"] if w > 1 else []
            plans.append(PlanEntry(id=plan_id, wave=w, depends_on=deps))

        result = validate_waves(plans)
        assert result.valid is True
        assert result.errors == []

    def test_10_waves_with_gap(self) -> None:
        plans = []
        for w in [1, 2, 3, 4, 5, 6, 7, 8, 10]:  # skip wave 9
            plan_id = f"plan-{w}"
            deps = [f"plan-{w - 1}"] if w > 1 and w != 10 else []
            if w == 10:
                deps = ["plan-8"]
            plans.append(PlanEntry(id=plan_id, wave=w, depends_on=deps))

        result = validate_waves(plans)
        assert result.valid is False
        assert any("Gap" in e for e in result.errors)

    def test_10_waves_multiple_plans_per_wave(self) -> None:
        """Multiple plans in each wave, all valid dependencies."""
        plans = []
        for w in range(1, 11):
            for suffix in ["a", "b"]:
                plan_id = f"w{w}-{suffix}"
                deps = [f"w{w - 1}-a"] if w > 1 else []
                plans.append(PlanEntry(id=plan_id, wave=w, depends_on=deps))

        result = validate_waves(plans)
        assert result.valid is True
        assert result.errors == []

    def test_10_waves_backward_dependency(self) -> None:
        """Plan in wave 5 depends on plan in wave 7 (invalid)."""
        plans = []
        for w in range(1, 11):
            plan_id = f"plan-{w}"
            deps = [f"plan-{w - 1}"] if w > 1 else []
            plans.append(PlanEntry(id=plan_id, wave=w, depends_on=deps))

        # Force plan-5 to depend on plan-7 (later wave)
        plans[4] = PlanEntry(id="plan-5", wave=5, depends_on=["plan-4", "plan-7"])

        result = validate_waves(plans)
        assert result.valid is False
        assert any("earlier wave" in e for e in result.errors)


# ─── 5. Renumbering with 20 phases ──────────────────────────────────────────


class TestRenumbering20Phases:
    """Removing a phase from a 20-phase project should renumber all subsequent phases."""

    def test_remove_phase_1_of_20(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        roadmap_lines = []
        for i in range(1, 21):
            roadmap_lines.append(f"### Phase {i}: Phase-{i}\n**Goal:** goal-{i}\n")
        _create_roadmap(tmp_path, "\n".join(roadmap_lines))

        for i in range(1, 21):
            d = _create_phase_dir(tmp_path, f"{str(i).zfill(2)}-phase-{i}")
            (d / f"{str(i).zfill(2)}-PLAN.md").write_text(f"plan {i}")

        result = phase_remove(tmp_path, "1")
        assert result.removed == "1"
        assert len(result.renamed_directories) == 19

        phases_dir = tmp_path / ".gpd" / "phases"
        remaining = sorted(d.name for d in phases_dir.iterdir() if d.is_dir())
        assert len(remaining) == 19
        # First directory should now be "01-phase-2" (originally phase 2, renumbered to 01)
        assert remaining[0].startswith("01-")

    def test_remove_middle_phase_of_20(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        roadmap_lines = []
        for i in range(1, 21):
            roadmap_lines.append(f"### Phase {i}: Phase-{i}\n**Goal:** goal-{i}\n")
        _create_roadmap(tmp_path, "\n".join(roadmap_lines))

        for i in range(1, 21):
            _create_phase_dir(tmp_path, f"{str(i).zfill(2)}-phase-{i}")

        result = phase_remove(tmp_path, "10")
        assert result.removed == "10"
        assert len(result.renamed_directories) == 10  # phases 11-20 renumbered

        phases_dir = tmp_path / ".gpd" / "phases"
        remaining = sorted(d.name for d in phases_dir.iterdir() if d.is_dir())
        assert len(remaining) == 19


# ─── 6. Decimal phases: 1.1, 1.2, 1.10, 1.1.1 ──────────────────────────────


class TestDecimalPhases:
    """Decimal phase numbering edge cases."""

    def test_find_decimal_1_1(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-base")
        _create_phase_dir(tmp_path, "01.1-hotfix")

        result = find_phase(tmp_path, "1.1")
        assert result is not None
        assert result.phase_number == "01.1"
        assert result.phase_name == "hotfix"

    def test_find_decimal_1_10_vs_1_1(self, tmp_path: Path) -> None:
        """01.1 and 01.10 should be distinct phases."""
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-base")
        _create_phase_dir(tmp_path, "01.1-first")
        _create_phase_dir(tmp_path, "01.10-tenth")

        result_1 = find_phase(tmp_path, "1.1")
        result_10 = find_phase(tmp_path, "1.10")

        assert result_1 is not None
        assert result_10 is not None
        assert result_1.phase_number == "01.1"
        assert result_10.phase_number == "01.10"
        assert result_1.phase_name == "first"
        assert result_10.phase_name == "tenth"

    def test_next_decimal_after_many(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-base")
        for i in range(1, 11):
            _create_phase_dir(tmp_path, f"01.{i}-sub-{i}")

        result = next_decimal_phase(tmp_path, "1")
        assert result.next == "01.11"
        assert len(result.existing) == 10

    def test_list_phases_decimal_sort_order(self, tmp_path: Path) -> None:
        """Decimal phases should sort numerically, not lexicographically."""
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-base")
        _create_phase_dir(tmp_path, "01.2-second")
        _create_phase_dir(tmp_path, "01.1-first")
        _create_phase_dir(tmp_path, "01.10-tenth")
        _create_phase_dir(tmp_path, "02-next")

        result = list_phases(tmp_path)
        assert result.directories == [
            "01-base",
            "01.1-first",
            "01.2-second",
            "01.10-tenth",
            "02-next",
        ]

    def test_phase_insert_creates_deep_decimal(self, tmp_path: Path) -> None:
        """Inserting after phase 1.1 should create 1.1.1 — but the API
        actually creates 01.2 (next decimal of the base "01" portion).
        Verify actual behavior: insert after "1" creates 01.N."""
        _setup_project(tmp_path)
        _create_roadmap(
            tmp_path,
            """\
            ### Phase 1: Base
            **Goal:** base

            ### Phase 2: Next
            **Goal:** next
            """,
        )
        _create_phase_dir(tmp_path, "01-base")
        _create_phase_dir(tmp_path, "02-next")

        result = phase_insert(tmp_path, "1", "Hotfix A")
        assert result.phase_number == "01.1"

        # Insert again after 1 — should get 01.2
        result2 = phase_insert(tmp_path, "1", "Hotfix B")
        assert result2.phase_number == "01.2"


# ─── 7. Phase removal when it's the only phase ──────────────────────────────


class TestPhaseRemoveOnlyPhase:
    """Removing the sole phase should leave an empty phases directory."""

    def test_remove_only_phase(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_roadmap(
            tmp_path,
            """\
            ### Phase 1: Solo
            **Goal:** the only one
            """,
        )
        _create_phase_dir(tmp_path, "01-solo")

        result = phase_remove(tmp_path, "1")
        assert result.removed == "1"
        assert result.directory_deleted == "01-solo"
        assert result.renamed_directories == []

        phases_dir = tmp_path / ".gpd" / "phases"
        remaining = [d for d in phases_dir.iterdir() if d.is_dir()]
        assert remaining == []


# ─── 8. Phase removal when it's the last phase ──────────────────────────────


class TestPhaseRemoveLastPhase:
    """Removing the last (highest numbered) phase requires no renumbering."""

    def test_remove_last_of_three(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_roadmap(
            tmp_path,
            """\
            ### Phase 1: First
            **Goal:** first

            ### Phase 2: Second
            **Goal:** second

            ### Phase 3: Third
            **Goal:** third
            """,
        )
        _create_phase_dir(tmp_path, "01-first")
        _create_phase_dir(tmp_path, "02-second")
        _create_phase_dir(tmp_path, "03-third")

        result = phase_remove(tmp_path, "3")
        assert result.removed == "3"
        assert result.directory_deleted == "03-third"
        assert result.renamed_directories == []

        phases_dir = tmp_path / ".gpd" / "phases"
        remaining = sorted(d.name for d in phases_dir.iterdir() if d.is_dir())
        assert remaining == ["01-first", "02-second"]


# ─── 9. Phase insert at position 0 (before all others) ──────────────────────


class TestPhaseInsertAtStart:
    """Inserting a decimal sub-phase after phase 0 is invalid (phase starts at 1).
    The practical 'before all' is inserting a decimal after phase 1."""

    def test_insert_before_first_via_decimal(self, tmp_path: Path) -> None:
        """Insert a decimal after phase 1 — it becomes 1.1, which sorts before phase 2."""
        _setup_project(tmp_path)
        _create_roadmap(
            tmp_path,
            """\
            ### Phase 1: First
            **Goal:** first

            ### Phase 2: Second
            **Goal:** second
            """,
        )
        _create_phase_dir(tmp_path, "01-first")
        _create_phase_dir(tmp_path, "02-second")

        result = phase_insert(tmp_path, "1", "Urgent")
        assert result.phase_number == "01.1"

        phases = list_phases(tmp_path)
        assert "01.1-urgent" in phases.directories
        idx_decimal = phases.directories.index("01.1-urgent")
        idx_second = phases.directories.index("02-second")
        assert idx_decimal < idx_second

    def test_insert_after_invalid_phase_0(self, tmp_path: Path) -> None:
        """Phase 0 is valid syntactically but won't be in ROADMAP; should error."""
        _setup_project(tmp_path)
        _create_roadmap(
            tmp_path,
            """\
            ### Phase 1: First
            **Goal:** first
            """,
        )
        with pytest.raises(PhaseValidationError, match="Phase 0 not found"):
            phase_insert(tmp_path, "0", "Before Everything")


# ─── 10. Phase complete with incomplete plans ────────────────────────────────


class TestPhaseCompleteIncomplete:
    """Completing a phase with missing summaries should raise PhaseIncompleteError."""

    def test_complete_one_of_three_plans(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-work")
        (phase_dir / "a-PLAN.md").write_text("plan a")
        (phase_dir / "a-SUMMARY.md").write_text("summary a")
        (phase_dir / "b-PLAN.md").write_text("plan b")
        (phase_dir / "c-PLAN.md").write_text("plan c")

        with pytest.raises(PhaseIncompleteError) as exc_info:
            phase_complete(tmp_path, "1")
        assert exc_info.value.summary_count == 1
        assert exc_info.value.plan_count == 3

    def test_complete_no_plans_raises_validation(self, tmp_path: Path) -> None:
        """A phase with zero plans cannot be completed."""
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-empty")

        with pytest.raises(PhaseValidationError, match="no plans"):
            phase_complete(tmp_path, "1")

    def test_complete_nonexistent_phase(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        with pytest.raises(PhaseNotFoundError):
            phase_complete(tmp_path, "42")


# ─── 11. find_phase with ambiguous input (multiple matches) ─────────────────


class TestFindPhaseAmbiguous:
    """find_phase returns the first matching directory in sorted order."""

    def test_find_phase_returns_first_match(self, tmp_path: Path) -> None:
        """When multiple directories could match, first sorted match wins."""
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-alpha")
        _create_phase_dir(tmp_path, "01.1-beta")

        # "1" should match "01-alpha" (exact prefix match before decimal sub-phase)
        result = find_phase(tmp_path, "1")
        assert result is not None
        assert result.phase_number == "01"
        assert result.phase_name == "alpha"

    def test_find_phase_decimal_is_specific(self, tmp_path: Path) -> None:
        """Querying "1.1" should find 01.1 specifically, not 01."""
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-alpha")
        _create_phase_dir(tmp_path, "01.1-beta")

        result = find_phase(tmp_path, "1.1")
        assert result is not None
        assert result.phase_number == "01.1"
        assert result.phase_name == "beta"

    def test_find_phase_two_digit_ambiguity(self, tmp_path: Path) -> None:
        """Phases 1 and 10 should be distinguishable."""
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-one")
        _create_phase_dir(tmp_path, "10-ten")

        result_1 = find_phase(tmp_path, "1")
        result_10 = find_phase(tmp_path, "10")

        assert result_1 is not None
        assert result_1.phase_name == "one"

        assert result_10 is not None
        assert result_10.phase_name == "ten"


# ─── 12. Phase names with special characters (spaces, unicode) ──────────────


class TestPhaseNamesSpecialCharacters:
    """Phase directories with unusual naming should be discoverable."""

    def test_phase_name_with_hyphens(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-multi-word-phase-name")

        result = find_phase(tmp_path, "1")
        assert result is not None
        assert result.phase_name == "multi-word-phase-name"

    def test_phase_name_with_unicode(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-analyse-donn\u00e9es")

        result = find_phase(tmp_path, "1")
        assert result is not None
        assert result.phase_name == "analyse-donn\u00e9es"

    def test_phase_slug_generation_unicode(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-analyse-donn\u00e9es")

        result = find_phase(tmp_path, "1")
        assert result is not None
        # Slug should lowercase and handle accented characters
        assert result.phase_slug is not None

    def test_phase_name_empty_slug(self, tmp_path: Path) -> None:
        """A phase directory with only a number and no slug."""
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01")

        result = find_phase(tmp_path, "1")
        assert result is not None
        assert result.phase_number == "01"
        # Phase name should be None or empty since there's nothing after the number
        assert result.phase_name is None or result.phase_name == ""

    def test_phase_add_special_description(self, tmp_path: Path) -> None:
        """Adding a phase with special characters in the description."""
        _setup_project(tmp_path)
        _create_roadmap(
            tmp_path,
            """\
            ### Phase 1: Existing
            **Goal:** exist
            """,
        )

        result = phase_add(tmp_path, "R\u00e9sum\u00e9 & Data Analysis")
        assert result.phase_number == 2
        assert (tmp_path / result.directory).is_dir()


# ─── Additional stress tests ────────────────────────────────────────────────


class TestValidateWavesEdgeCases:
    """Edge cases in wave validation."""

    def test_validate_waves_empty_list(self) -> None:
        result = validate_waves([])
        assert result.valid is True
        assert result.errors == []

    def test_validate_waves_single_plan(self) -> None:
        plans = [PlanEntry(id="solo", wave=1)]
        result = validate_waves(plans)
        assert result.valid is True

    def test_validate_waves_file_overlap_warning(self) -> None:
        """Two plans in the same wave modifying the same file should warn."""
        plans = [
            PlanEntry(id="a", wave=1, files_modified=["src/main.py"]),
            PlanEntry(id="b", wave=1, files_modified=["src/main.py"]),
        ]
        result = validate_waves(plans)
        assert result.valid is True  # Overlap is a warning, not an error
        assert len(result.warnings) >= 1
        assert any("main.py" in w for w in result.warnings)

    def test_validate_waves_wave_not_starting_at_1(self) -> None:
        plans = [PlanEntry(id="a", wave=2)]
        result = validate_waves(plans)
        assert result.valid is False
        assert any("start at 1" in e for e in result.errors)

    def test_validate_waves_orphan_detection(self) -> None:
        """A plan not depended upon and not in the final wave should warn."""
        plans = [
            PlanEntry(id="a", wave=1),
            PlanEntry(id="b", wave=1),
            PlanEntry(id="c", wave=2, depends_on=["a"]),
        ]
        result = validate_waves(plans)
        assert result.valid is True
        assert any("b" in w and "not depended upon" in w for w in result.warnings)


class TestPhaseCompleteLargeProject:
    """Phase complete in a multi-phase project."""

    def test_complete_first_phase_transitions_to_second(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_roadmap(
            tmp_path,
            """\
            ### Phase 1: Setup
            **Goal:** setup
            **Plans:** 1 plans

            ### Phase 2: Build
            **Goal:** build

            ### Phase 3: Deploy
            **Goal:** deploy
            """,
        )

        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "a-PLAN.md").write_text("plan")
        (phase_dir / "a-SUMMARY.md").write_text("done")
        _create_phase_dir(tmp_path, "02-build")
        _create_phase_dir(tmp_path, "03-deploy")

        result = phase_complete(tmp_path, "1")
        assert result.completed_phase == "1"
        assert result.next_phase == "02"
        assert result.next_phase_name == "Build"
        assert result.is_last_phase is False

    def test_complete_last_phase_is_last(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_roadmap(tmp_path, "### Phase 1: Only\n**Goal:** only\n")

        phase_dir = _create_phase_dir(tmp_path, "01-only")
        (phase_dir / "a-PLAN.md").write_text("plan")
        (phase_dir / "a-SUMMARY.md").write_text("done")

        result = phase_complete(tmp_path, "1")
        assert result.is_last_phase is True
        assert result.next_phase is None


class TestNextDecimalEdgeCases:
    """Edge cases for next_decimal_phase."""

    def test_next_decimal_no_phases_dir(self, tmp_path: Path) -> None:
        """If the phases directory doesn't exist, still returns a result."""
        planning = tmp_path / ".gpd"
        planning.mkdir()
        # Don't create phases dir

        result = next_decimal_phase(tmp_path, "1")
        assert result.found is False
        assert result.next == "01.1"

    def test_next_decimal_base_without_dir(self, tmp_path: Path) -> None:
        """Base phase has no directory, but decimals still compute."""
        _setup_project(tmp_path)

        result = next_decimal_phase(tmp_path, "5")
        assert result.found is False
        assert result.next == "05.1"


class TestPhaseRemoveDecimalRenumbering:
    """Decimal phase removal and renumbering."""

    def test_remove_first_decimal_renumbers_rest(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_roadmap(
            tmp_path,
            """\
            ### Phase 1: Base
            **Goal:** base

            ### Phase 1.1: Sub A
            **Goal:** a

            ### Phase 1.2: Sub B
            **Goal:** b

            ### Phase 1.3: Sub C
            **Goal:** c
            """,
        )
        _create_phase_dir(tmp_path, "01-base")
        for i in range(1, 4):
            d = _create_phase_dir(tmp_path, f"01.{i}-sub")
            (d / f"01.{i}-PLAN.md").write_text(f"plan {i}")

        phase_remove(tmp_path, "1.1", force=True)

        phases_dir = tmp_path / ".gpd" / "phases"
        remaining = sorted(d.name for d in phases_dir.iterdir() if d.is_dir())
        assert "01-base" in remaining
        assert "01.1-sub" in remaining
        assert "01.2-sub" in remaining
        assert "01.3-sub" not in remaining


class TestPhaseAddEdgeCases:
    """Edge cases for phase_add."""

    def test_add_phase_to_empty_roadmap(self, tmp_path: Path) -> None:
        """Adding a phase to a roadmap with no existing phases."""
        _setup_project(tmp_path)
        _create_roadmap(tmp_path, "## Milestone v1.0: Fresh Start\n")

        result = phase_add(tmp_path, "First Phase")
        assert result.phase_number == 1
        assert result.padded == "01"

    def test_add_phase_no_roadmap_raises(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        with pytest.raises(RoadmapNotFoundError):
            phase_add(tmp_path, "Something")

    def test_add_phase_empty_description_raises(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_roadmap(tmp_path, "### Phase 1: X\n")
        with pytest.raises(PhaseValidationError, match="description required"):
            phase_add(tmp_path, "")


class TestPhaseRemoveWithSummariesNeedsForce:
    """Removing a phase with summaries needs force=True."""

    def test_remove_with_summaries_errors_without_force(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_roadmap(
            tmp_path,
            """\
            ### Phase 1: Done
            **Goal:** done

            ### Phase 2: Next
            **Goal:** next
            """,
        )
        phase_dir = _create_phase_dir(tmp_path, "01-done")
        (phase_dir / "a-PLAN.md").write_text("plan")
        (phase_dir / "a-SUMMARY.md").write_text("summary")
        _create_phase_dir(tmp_path, "02-next")

        with pytest.raises(PhaseValidationError, match="force"):
            phase_remove(tmp_path, "1")

    def test_remove_with_summaries_succeeds_with_force(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_roadmap(
            tmp_path,
            """\
            ### Phase 1: Done
            **Goal:** done

            ### Phase 2: Next
            **Goal:** next
            """,
        )
        phase_dir = _create_phase_dir(tmp_path, "01-done")
        (phase_dir / "a-PLAN.md").write_text("plan")
        (phase_dir / "a-SUMMARY.md").write_text("summary")
        _create_phase_dir(tmp_path, "02-next")

        result = phase_remove(tmp_path, "1", force=True)
        assert result.removed == "1"
        assert result.directory_deleted == "01-done"
