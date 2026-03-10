"""Tests for gpd.core.phases — phase lifecycle and roadmap management."""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from gpd.core.phases import (
    MilestoneIncompleteError,
    PhaseIncompleteError,
    PhaseNotFoundError,
    PhaseValidationError,
    PlanEntry,
    RoadmapNotFoundError,
    find_phase,
    get_milestone_info,
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


def _create_state(tmp_path: Path, content: str) -> Path:
    """Write STATE.md and return its path."""
    state = tmp_path / ".gpd" / "STATE.md"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(textwrap.dedent(content))
    return state


# ─── find_phase ────────────────────────────────────────────────────────────────


def test_find_phase_exact_match(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    phase_dir = _create_phase_dir(tmp_path, "01-setup")
    (phase_dir / "a-PLAN.md").write_text("plan content")

    result = find_phase(tmp_path, "1")
    assert result is not None
    assert result.found is True
    assert result.phase_number == "01"
    assert result.phase_name == "setup"
    assert result.plans == ["a-PLAN.md"]
    assert result.summaries == []
    assert result.incomplete_plans == ["a-PLAN.md"]


def test_find_phase_with_summary(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    phase_dir = _create_phase_dir(tmp_path, "02-compute")
    (phase_dir / "a-PLAN.md").write_text("plan")
    (phase_dir / "a-SUMMARY.md").write_text("summary")

    result = find_phase(tmp_path, "2")
    assert result is not None
    assert result.plans == ["a-PLAN.md"]
    assert result.summaries == ["a-SUMMARY.md"]
    assert result.incomplete_plans == []


def test_find_phase_not_found(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    result = find_phase(tmp_path, "99")
    assert result is None


def test_find_phase_empty_string(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    result = find_phase(tmp_path, "")
    assert result is None


def test_find_phase_no_phases_dir(tmp_path: Path) -> None:
    result = find_phase(tmp_path, "1")
    assert result is None


def test_find_phase_research_and_context(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    phase_dir = _create_phase_dir(tmp_path, "03-analysis")
    (phase_dir / "RESEARCH.md").write_text("research")
    (phase_dir / "CONTEXT.md").write_text("context")

    result = find_phase(tmp_path, "3")
    assert result is not None
    assert result.has_research is True
    assert result.has_context is True
    assert result.has_verification is False


def test_find_phase_decimal(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_phase_dir(tmp_path, "03.1-hotfix")

    result = find_phase(tmp_path, "3.1")
    assert result is not None
    assert result.phase_number == "03.1"
    assert result.phase_name == "hotfix"


# ─── list_phases ────────────────────────────────────────────────────────────────


def test_list_phases_sorted(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_phase_dir(tmp_path, "03-third")
    _create_phase_dir(tmp_path, "01-first")
    _create_phase_dir(tmp_path, "02-second")

    result = list_phases(tmp_path)
    assert result.count == 3
    assert result.directories == ["01-first", "02-second", "03-third"]


def test_list_phases_empty(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    result = list_phases(tmp_path)
    assert result.count == 0
    assert result.directories == []


# ─── validate_waves ─────────────────────────────────────────────────────────────


def test_validate_waves_valid(tmp_path: Path) -> None:
    plans = [
        PlanEntry(id="a", wave=1),
        PlanEntry(id="b", wave=2, depends_on=["a"]),
    ]
    result = validate_waves(plans)
    assert result.valid is True
    assert result.errors == []


def test_validate_waves_missing_dep(tmp_path: Path) -> None:
    plans = [
        PlanEntry(id="a", wave=1, depends_on=["nonexistent"]),
    ]
    result = validate_waves(plans)
    assert result.valid is False
    assert len(result.errors) == 1
    assert "nonexistent" in result.errors[0]


def test_validate_waves_same_wave_dependency(tmp_path: Path) -> None:
    plans = [
        PlanEntry(id="a", wave=1),
        PlanEntry(id="b", wave=1, depends_on=["a"]),
    ]
    result = validate_waves(plans)
    assert result.valid is False
    assert any("earlier wave" in e for e in result.errors)


def test_validate_waves_cycle_detection(tmp_path: Path) -> None:
    plans = [
        PlanEntry(id="a", wave=1, depends_on=["b"]),
        PlanEntry(id="b", wave=1, depends_on=["a"]),
    ]
    result = validate_waves(plans)
    assert result.valid is False
    assert any("Circular" in e or "earlier wave" in e for e in result.errors)


def test_validate_waves_gap_in_numbering(tmp_path: Path) -> None:
    plans = [
        PlanEntry(id="a", wave=1),
        PlanEntry(id="b", wave=3),
    ]
    result = validate_waves(plans)
    assert result.valid is False
    assert any("Gap" in e for e in result.errors)


# ─── roadmap_analyze ─────────────────────────────────────────────────────────────


def test_roadmap_analyze_basic(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ## Milestone v1.0: Initial Setup

        ### Phase 1: Setup
        **Goal:** Get started
        **Plans:** 1 plans

        ### Phase 2: Implementation
        **Goal:** Build the thing
        **Plans:** 0 plans
        """,
    )

    phase_dir = _create_phase_dir(tmp_path, "01-setup")
    (phase_dir / "a-PLAN.md").write_text("plan")
    (phase_dir / "a-SUMMARY.md").write_text("summary")

    result = roadmap_analyze(tmp_path)
    assert result.phase_count == 2
    assert result.completed_phases == 1
    assert len(result.milestones) == 1
    assert result.milestones[0]["version"] == "v1.0"


def test_roadmap_analyze_no_roadmap(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    result = roadmap_analyze(tmp_path)
    assert result.phase_count == 0


# ─── roadmap_get_phase ──────────────────────────────────────────────────────────


def test_roadmap_get_phase_found(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ### Phase 1: Setup Phase
        **Goal:** Initialize the project
        Some details here.

        ### Phase 2: Next Phase
        **Goal:** Do more
        """,
    )

    result = roadmap_get_phase(tmp_path, "1")
    assert result.found is True
    assert result.phase_name == "Setup Phase"
    assert result.goal == "Initialize the project"


def test_roadmap_get_phase_not_found(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(tmp_path, "### Phase 1: Only Phase\n")

    result = roadmap_get_phase(tmp_path, "99")
    assert result.found is False


def test_roadmap_get_phase_no_roadmap(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    result = roadmap_get_phase(tmp_path, "1")
    assert result.found is False
    assert result.error == "ROADMAP.md not found"


def test_roadmap_get_phase_invalid_number(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    with pytest.raises(PhaseValidationError):
        roadmap_get_phase(tmp_path, "abc")


# ─── phase_add ──────────────────────────────────────────────────────────────────


def test_phase_add(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ## Milestone v1.0: Test

        ### Phase 1: Existing Phase
        **Goal:** exist

        ---
        Progress tracking table
        """,
    )

    result = phase_add(tmp_path, "New Feature")
    assert result.phase_number == 2
    assert result.padded == "02"
    assert "new-feature" in result.slug
    assert (tmp_path / result.directory).is_dir()

    roadmap = (tmp_path / ".gpd" / "ROADMAP.md").read_text()
    assert "Phase 2: New Feature" in roadmap


def test_phase_add_empty_description(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(tmp_path, "### Phase 1: X\n")

    with pytest.raises(PhaseValidationError, match="description required"):
        phase_add(tmp_path, "")


def test_phase_add_no_roadmap(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    with pytest.raises(RoadmapNotFoundError):
        phase_add(tmp_path, "Something")


# ─── phase_insert ────────────────────────────────────────────────────────────────


def test_phase_insert(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ### Phase 1: First
        **Goal:** do first

        ### Phase 2: Second
        **Goal:** do second
        """,
    )

    result = phase_insert(tmp_path, "1", "Hotfix")
    assert result.phase_number == "01.1"
    assert result.after_phase == "1"
    assert (tmp_path / result.directory).is_dir()


def test_phase_insert_invalid_phase(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(tmp_path, "### Phase 1: X\n")
    with pytest.raises(PhaseValidationError):
        phase_insert(tmp_path, "abc", "Fix")


# ─── next_decimal_phase ──────────────────────────────────────────────────────────


def test_next_decimal_no_existing(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_phase_dir(tmp_path, "03-analysis")

    result = next_decimal_phase(tmp_path, "3")
    assert result.found is True
    assert result.next == "03.1"
    assert result.existing == []


def test_next_decimal_with_existing(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_phase_dir(tmp_path, "03-analysis")
    _create_phase_dir(tmp_path, "03.1-fix")
    _create_phase_dir(tmp_path, "03.2-patch")

    result = next_decimal_phase(tmp_path, "3")
    assert result.next == "03.3"
    assert len(result.existing) == 2


# ─── phase_remove ────────────────────────────────────────────────────────────────


def test_phase_remove_basic(tmp_path: Path) -> None:
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

    result = phase_remove(tmp_path, "2")
    assert result.removed == "2"
    assert result.roadmap_updated is True

    roadmap = (tmp_path / ".gpd" / "ROADMAP.md").read_text()
    assert "Phase 2: Second" not in roadmap


def test_phase_remove_renumber_same_slug(tmp_path: Path) -> None:
    """Removing a phase when siblings share the same slug must not collide.

    Before the fix both _renumber_integer_phases and _renumber_decimal_phases
    sorted descending, which caused an OSError (Directory not empty) when the
    destination directory already existed because its occupant had not yet been
    moved out of the way.  Ascending sort ensures each rename lands in the slot
    just vacated by the previous rename or the deleted directory.
    """
    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ### Phase 1: Work
        **Goal:** first

        ### Phase 2: Work
        **Goal:** second

        ### Phase 3: Work
        **Goal:** third
        """,
    )
    phases_dir = tmp_path / ".gpd" / "phases"
    for i in range(1, 4):
        d = _create_phase_dir(tmp_path, f"{str(i).zfill(2)}-work")
        (d / f"{str(i).zfill(2)}-PLAN.md").write_text("plan")

    result = phase_remove(tmp_path, "1")

    remaining = sorted(d.name for d in phases_dir.iterdir() if d.is_dir())
    assert remaining == ["01-work", "02-work"]
    assert len(result.renamed_directories) == 2
    # Verify files were also renumbered
    assert (phases_dir / "01-work" / "01-PLAN.md").exists()
    assert (phases_dir / "02-work" / "02-PLAN.md").exists()


def test_phase_remove_decimal_renumber_same_slug(tmp_path: Path) -> None:
    """Decimal sub-phase renumbering must not collide when slugs match."""
    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ### Phase 3: Base
        **Goal:** base

        ### Phase 3.1: Fix
        **Goal:** fix1

        ### Phase 3.2: Fix
        **Goal:** fix2

        ### Phase 3.3: Fix
        **Goal:** fix3
        """,
    )
    phases_dir = tmp_path / ".gpd" / "phases"
    _create_phase_dir(tmp_path, "03-base")
    for i in range(1, 4):
        d = _create_phase_dir(tmp_path, f"03.{i}-fix")
        (d / f"03.{i}-PLAN.md").write_text("plan")

    phase_remove(tmp_path, "3.1", force=True)

    remaining = sorted(d.name for d in phases_dir.iterdir() if d.is_dir())
    assert remaining == ["03-base", "03.1-fix", "03.2-fix"]
    assert (phases_dir / "03.1-fix" / "03.1-PLAN.md").exists()
    assert (phases_dir / "03.2-fix" / "03.2-PLAN.md").exists()


def test_phase_remove_with_summaries_needs_force(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(tmp_path, "### Phase 1: X\n**Goal:** x\n")
    phase_dir = _create_phase_dir(tmp_path, "01-x")
    (phase_dir / "a-SUMMARY.md").write_text("done")

    with pytest.raises(PhaseValidationError, match="force"):
        phase_remove(tmp_path, "1")


# ─── phase_complete ──────────────────────────────────────────────────────────────


def test_phase_complete_success(tmp_path: Path) -> None:
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

    phase_dir = _create_phase_dir(tmp_path, "01-setup")
    (phase_dir / "a-PLAN.md").write_text("plan")
    (phase_dir / "a-SUMMARY.md").write_text("done")
    _create_phase_dir(tmp_path, "02-build")

    result = phase_complete(tmp_path, "1")
    assert result.completed_phase == "1"
    assert result.all_plans_complete is True
    assert result.next_phase == "02"
    assert result.is_last_phase is False


def test_phase_complete_uses_roadmap_for_unscaffolded_next_phase(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ### Phase 1: Setup
        **Goal:** setup
        **Plans:** 1 plans

        ### Phase 2: Build
        **Goal:** build
        **Plans:** 0 plans
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
        **Status:** in_progress
        **Last Activity:** 2026-03-01
        **Last Activity Description:** Working
        """,
    )

    phase_dir = _create_phase_dir(tmp_path, "01-setup")
    (phase_dir / "a-PLAN.md").write_text("plan")
    (phase_dir / "a-SUMMARY.md").write_text("done")

    result = phase_complete(tmp_path, "1")

    assert result.next_phase == "02"
    assert result.next_phase_name == "Build"
    assert result.is_last_phase is False

    state = (tmp_path / ".gpd" / "STATE.md").read_text()
    assert "**Current Phase:** 02" in state
    assert "**Current Phase Name:** Build" in state
    assert "**Status:** Ready to plan" in state


def test_phase_complete_not_found(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    with pytest.raises(PhaseNotFoundError):
        phase_complete(tmp_path, "99")


def test_phase_complete_incomplete(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    phase_dir = _create_phase_dir(tmp_path, "01-setup")
    (phase_dir / "a-PLAN.md").write_text("plan")

    with pytest.raises(PhaseIncompleteError):
        phase_complete(tmp_path, "1")


# ─── milestone_complete ──────────────────────────────────────────────────────────


def test_milestone_complete_success(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(tmp_path, "## Milestone v1.0: Test\n### Phase 1: X\n**Goal:** x\n")

    phase_dir = _create_phase_dir(tmp_path, "01-x")
    (phase_dir / "a-PLAN.md").write_text("plan")
    (phase_dir / "a-SUMMARY.md").write_text("---\none-liner: Did the thing\n---\n## Task 1\nDone")

    result = milestone_complete(tmp_path, "v1.0", name="Test Milestone")
    assert result.version == "v1.0"
    assert result.name == "Test Milestone"
    assert result.phases == 1
    assert result.plans == 1
    assert result.archived.roadmap is True
    assert result.milestones_updated is True


def test_milestone_complete_counts_unscaffolded_roadmap_phases(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ## Milestone v1.0: Test

        ### Phase 1: Setup
        **Goal:** setup

        ### Phase 2: Build
        **Goal:** build
        """,
    )

    phase_dir = _create_phase_dir(tmp_path, "01-setup")
    (phase_dir / "a-PLAN.md").write_text("plan")
    (phase_dir / "a-SUMMARY.md").write_text("---\none-liner: Done\n---\n")

    with pytest.raises(MilestoneIncompleteError):
        milestone_complete(tmp_path, "v1.0", name="Test")


def test_milestone_complete_incomplete_phases(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(tmp_path, "## v1.0\n")

    phase_dir = _create_phase_dir(tmp_path, "01-x")
    (phase_dir / "a-PLAN.md").write_text("plan")

    with pytest.raises(MilestoneIncompleteError):
        milestone_complete(tmp_path, "v1.0")


def test_milestone_complete_empty_version(tmp_path: Path) -> None:
    with pytest.raises(PhaseValidationError, match="version required"):
        milestone_complete(tmp_path, "")


def test_phase_remove_remaps_current_phase_state_after_renumbering(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ### Phase 1: Setup
        **Goal:** setup

        ### Phase 2: Derivation
        **Goal:** derive

        ### Phase 3: Validation
        **Goal:** validate
        """,
    )
    _create_state(
        tmp_path,
        """\
        **Current Phase:** 2
        **Current Phase Name:** Derivation
        **Total Phases:** 3
        **Current Plan:** 2
        **Total Plans in Phase:** 2
        **Status:** in_progress
        **Last Activity:** 2026-03-01
        **Last Activity Description:** Deriving
        """,
    )

    _create_phase_dir(tmp_path, "01-setup")
    derivation_dir = _create_phase_dir(tmp_path, "02-derivation")
    (derivation_dir / "02-01-PLAN.md").write_text("plan")
    (derivation_dir / "02-02-PLAN.md").write_text("plan")
    validation_dir = _create_phase_dir(tmp_path, "03-validation")
    (validation_dir / "03-01-PLAN.md").write_text("plan")

    phase_remove(tmp_path, "2")

    state = (tmp_path / ".gpd" / "STATE.md").read_text()
    assert "**Current Phase:** 02" in state
    assert "**Current Phase Name:** Validation" in state
    assert "**Total Phases:** 2" in state
    assert "**Current Plan:** Not started" in state
    assert "**Total Plans in Phase:** 1" in state

    state_json = json.loads((tmp_path / ".gpd" / "state.json").read_text())
    assert state_json["position"]["current_phase"] == "02"
    assert state_json["position"]["current_phase_name"] == "Validation"
    assert state_json["position"]["total_phases"] == 2


def test_phase_remove_integer_renumbers_decimal_roadmap_references(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ## Phase Overview

        - [ ] Phase 1: Setup
        - [ ] Phase 2: Main
        - [ ] Phase 2.1: Hotfix

        | Phase | Status | Updated |
        |---|---|---|
        | 1. Setup | Ready | - |
        | 2. Main | Ready | - |
        | 2.1. Hotfix | Ready | - |

        ### Phase 1: Setup
        **Goal:** setup
        **Artifact:** 01-01-PLAN.md

        ### Phase 2: Main
        **Goal:** main
        **Artifact:** 02-01-PLAN.md

        ### Phase 2.1: Hotfix
        **Goal:** fix
        **Depends on:** Phase 2
        **Artifact:** 02.1-01-PLAN.md
        """,
    )

    _create_phase_dir(tmp_path, "01-setup")
    main_dir = _create_phase_dir(tmp_path, "02-main")
    (main_dir / "02-01-PLAN.md").write_text("plan")
    hotfix_dir = _create_phase_dir(tmp_path, "02.1-hotfix")
    (hotfix_dir / "02.1-01-PLAN.md").write_text("plan")

    phase_remove(tmp_path, "1")

    roadmap = (tmp_path / ".gpd" / "ROADMAP.md").read_text()
    assert "### Phase 1: Main" in roadmap
    assert "### Phase 1.1: Hotfix" in roadmap
    assert "- [ ] Phase 1.1: Hotfix" in roadmap
    assert "| 1.1. Hotfix | Ready | - |" in roadmap
    assert "**Depends on:** Phase 1" in roadmap
    assert "01.1-01-PLAN.md" in roadmap
    assert "02.1-01-PLAN.md" not in roadmap


# ─── get_milestone_info ──────────────────────────────────────────────────────────


def test_get_milestone_info(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(tmp_path, "## Milestone v2.0: Advanced Features\n")

    result = get_milestone_info(tmp_path)
    assert result.version == "v2.0"
    assert result.name == "Advanced Features"


def test_get_milestone_info_no_roadmap(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    result = get_milestone_info(tmp_path)
    assert result.version == "v1.0"
    assert result.name == "milestone"


# ─── progress_render ─────────────────────────────────────────────────────────────


def test_progress_render_json(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(tmp_path, "## v1.0: Test\n")

    phase_dir = _create_phase_dir(tmp_path, "01-x")
    (phase_dir / "a-PLAN.md").write_text("plan")
    (phase_dir / "a-SUMMARY.md").write_text("done")

    result = progress_render(tmp_path, "json")
    assert result.percent == 100
    assert result.total_plans_in_phase == 1
    assert result.total_summaries == 1
    assert len(result.phases) == 1


def test_progress_render_bar(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(tmp_path, "## v1.0: Test\n")
    phase_dir = _create_phase_dir(tmp_path, "01-x")
    (phase_dir / "a-PLAN.md").write_text("plan")

    result = progress_render(tmp_path, "bar")
    assert result.percent == 0
    assert result.total == 1


def test_progress_render_table(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(tmp_path, "## v1.0: Test\n")
    phase_dir = _create_phase_dir(tmp_path, "01-x")
    (phase_dir / "a-PLAN.md").write_text("plan")
    (phase_dir / "a-SUMMARY.md").write_text("done")

    result = progress_render(tmp_path, "table")
    assert "| Phase |" in result.rendered
    assert "Complete" in result.rendered


# ─── phase_plan_index ────────────────────────────────────────────────────────────


def test_phase_plan_index_basic(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    phase_dir = _create_phase_dir(tmp_path, "01-setup")
    (phase_dir / "a-PLAN.md").write_text("---\nwave: 1\n---\n## Task 1\nDo stuff")
    (phase_dir / "b-PLAN.md").write_text("---\nwave: 2\ndepends_on: a\n---\n## Task 1\nMore stuff")

    result = phase_plan_index(tmp_path, "1")
    assert result.phase == "01"
    assert len(result.plans) == 2
    assert "1" in result.waves
    assert "2" in result.waves
    assert result.validation.valid is True


def test_phase_plan_index_not_found(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    result = phase_plan_index(tmp_path, "99")
    assert result.plans == []
