"""Tests for gpd.core.phases — phase lifecycle and roadmap management."""

from __future__ import annotations

import json
import textwrap
from contextlib import contextmanager
from pathlib import Path

import pytest

import gpd.core.phases as phases_module
from gpd.core.phases import (
    MilestoneIncompleteError,
    PhaseIncompleteError,
    PhaseNotFoundError,
    PhaseValidationError,
    PlanEntry,
    ProgressJsonResult,
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
    validate_phase_waves,
    validate_waves,
)
from gpd.core.state import default_state_dict, generate_state_markdown

# ─── Helpers ───────────────────────────────────────────────────────────────────


def _setup_project(tmp_path: Path) -> Path:
    """Create a minimal GPD project structure and return project root."""
    planning = tmp_path / "GPD"
    planning.mkdir()
    (planning / "phases").mkdir()
    return tmp_path


def _create_phase_dir(tmp_path: Path, name: str) -> Path:
    """Create a phase directory and return its path."""
    phase_dir = tmp_path / "GPD" / "phases" / name
    phase_dir.mkdir(parents=True, exist_ok=True)
    return phase_dir


def _create_roadmap(tmp_path: Path, content: str) -> Path:
    """Write ROADMAP.md and return its path."""
    roadmap = tmp_path / "GPD" / "ROADMAP.md"
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text(textwrap.dedent(content), encoding="utf-8")
    return roadmap


def _create_state(tmp_path: Path, content: str) -> Path:
    """Write STATE.md and return its path."""
    state = tmp_path / "GPD" / "STATE.md"
    state.parent.mkdir(parents=True, exist_ok=True)
    state.write_text(textwrap.dedent(content), encoding="utf-8")
    return state


def _seed_state_pair(
    tmp_path: Path,
    *,
    current_phase: str = "01",
    current_phase_name: str = "Existing Phase",
    total_phases: int = 1,
    status: str = "Ready to plan",
) -> dict:
    state = default_state_dict()
    state["position"]["current_phase"] = current_phase
    state["position"]["current_phase_name"] = current_phase_name
    state["position"]["total_phases"] = total_phases
    state["position"]["status"] = status
    _create_state(tmp_path, generate_state_markdown(state))
    (tmp_path / "GPD" / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    return state


def _write_state_pair(tmp_path: Path, state: dict[str, object]) -> None:
    state_md = generate_state_markdown(state)
    _create_state(tmp_path, state_md)
    (tmp_path / "GPD" / "state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")


def _recording_file_lock(lock_calls: list[Path]):
    real_file_lock = phases_module.file_lock

    @contextmanager
    def _wrapper(path: Path, *args, **kwargs):
        lock_calls.append(Path(path))
        with real_file_lock(path, *args, **kwargs):
            yield

    return _wrapper


# ─── find_phase ────────────────────────────────────────────────────────────────


def test_find_phase_exact_match(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    phase_dir = _create_phase_dir(tmp_path, "01-setup")
    (phase_dir / "a-PLAN.md").write_text("plan content", encoding="utf-8")

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
    (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
    (phase_dir / "SUMMARY.md").write_text("summary", encoding="utf-8")

    result = find_phase(tmp_path, "2")
    assert result is not None
    assert result.plans == ["a-PLAN.md"]
    assert result.summaries == ["SUMMARY.md"]
    assert result.incomplete_plans == ["a-PLAN.md"]


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
    (phase_dir / "RESEARCH.md").write_text("research", encoding="utf-8")
    (phase_dir / "CONTEXT.md").write_text("context", encoding="utf-8")

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
    (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
    (phase_dir / "a-SUMMARY.md").write_text("summary", encoding="utf-8")

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


def test_roadmap_get_phase_accepts_padded_query(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ### Phase 3: Analysis Phase
        **Goal:** Analyze the phase
        """,
    )

    result = roadmap_get_phase(tmp_path, "03")
    assert result.found is True
    assert result.phase_number == "3"
    assert result.phase_name == "Analysis Phase"
    assert result.goal == "Analyze the phase"


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

    roadmap = (tmp_path / "GPD" / "ROADMAP.md").read_text()
    assert "Phase 2: New Feature" in roadmap


def test_phase_add_updates_total_phases_when_roadmap_contains_decimal_phases(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ### Phase 1: Setup
        **Goal:** setup

        ### Phase 1.1: Calibration
        **Goal:** calibrate

        ### Phase 2: Build
        **Goal:** build
        """,
    )
    _seed_state_pair(tmp_path, current_phase="01", current_phase_name="Setup", total_phases=3)

    phase_add(tmp_path, "Validation")

    state = (tmp_path / "GPD" / "STATE.md").read_text(encoding="utf-8")
    state_json = json.loads((tmp_path / "GPD" / "state.json").read_text(encoding="utf-8"))
    assert "**Total Phases:** 4" in state
    assert state_json["position"]["total_phases"] == 4


def test_phase_add_rebuilds_state_markdown_when_only_state_json_exists(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ### Phase 1: Setup
        **Goal:** setup
        """,
    )
    _seed_state_pair(tmp_path, total_phases=1)
    (tmp_path / "GPD" / "STATE.md").unlink()

    phase_add(tmp_path, "Validation")

    state = (tmp_path / "GPD" / "STATE.md").read_text(encoding="utf-8")
    state_json = json.loads((tmp_path / "GPD" / "state.json").read_text(encoding="utf-8"))
    assert "**Total Phases:** 2" in state
    assert state_json["position"]["total_phases"] == 2


def test_phase_add_empty_description(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(tmp_path, "### Phase 1: X\n")

    with pytest.raises(PhaseValidationError, match="description required"):
        phase_add(tmp_path, "")


def test_phase_add_no_roadmap(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    with pytest.raises(RoadmapNotFoundError):
        phase_add(tmp_path, "Something")


def test_phase_add_leaves_state_files_unchanged_when_atomic_state_save_fails(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ## Milestone v1.0: Test

        ### Phase 1: Existing Phase
        **Goal:** exist
        """,
    )
    _seed_state_pair(tmp_path)

    before_md = (tmp_path / "GPD" / "STATE.md").read_text(encoding="utf-8")
    before_json = (tmp_path / "GPD" / "state.json").read_text(encoding="utf-8")
    before_roadmap = (tmp_path / "GPD" / "ROADMAP.md").read_text(encoding="utf-8")

    def _boom(_cwd: Path, _state_content: str) -> None:
        raise RuntimeError("sync exploded")

    monkeypatch.setattr("gpd.core.state.save_state_markdown_locked", _boom)

    with pytest.raises(RuntimeError, match="sync exploded"):
        phase_add(tmp_path, "New Feature")

    assert (tmp_path / "GPD" / "STATE.md").read_text(encoding="utf-8") == before_md
    assert (tmp_path / "GPD" / "state.json").read_text(encoding="utf-8") == before_json
    assert (tmp_path / "GPD" / "ROADMAP.md").read_text(encoding="utf-8") == before_roadmap
    assert sorted(d.name for d in (tmp_path / "GPD" / "phases").iterdir() if d.is_dir()) == []


def test_phase_insert_rolls_back_roadmap_and_directory_when_atomic_state_save_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ### Phase 1: Existing Phase
        **Goal:** exist
        """,
    )
    _seed_state_pair(tmp_path)

    before_roadmap = (tmp_path / "GPD" / "ROADMAP.md").read_text(encoding="utf-8")

    def _boom(_cwd: Path, _state_content: str) -> None:
        raise RuntimeError("sync exploded")

    monkeypatch.setattr("gpd.core.state.save_state_markdown_locked", _boom)

    with pytest.raises(RuntimeError, match="sync exploded"):
        phase_insert(tmp_path, "1", "Hotfix")

    assert (tmp_path / "GPD" / "ROADMAP.md").read_text(encoding="utf-8") == before_roadmap
    assert sorted(d.name for d in (tmp_path / "GPD" / "phases").iterdir() if d.is_dir()) == []


def _assert_canonical_state_lock_and_locked_writer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> list[Path]:
    lock_calls: list[Path] = []
    monkeypatch.setattr("gpd.core.phases.file_lock", _recording_file_lock(lock_calls))
    monkeypatch.setattr(
        "gpd.core.state.save_state_markdown",
        lambda *_args, **_kwargs: pytest.fail("public save_state_markdown() should not be used"),
    )
    return lock_calls


def test_phase_add_uses_canonical_state_lock_and_locked_writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _create_roadmap(
        tmp_path,
        """\
        ## Milestone v1.0: Test

        ### Phase 1: Existing Phase
        **Goal:** exist
        """,
    )
    state = default_state_dict()
    state["position"]["current_phase"] = "01"
    state["position"]["current_phase_name"] = "Existing Phase"
    state["position"]["total_phases"] = 1
    state["position"]["status"] = "Ready to plan"
    _write_state_pair(tmp_path, state)

    lock_calls = _assert_canonical_state_lock_and_locked_writer(tmp_path, monkeypatch)
    result = phase_add(tmp_path, "New Feature")

    assert result.phase_number == 2
    assert any(path.name == "state.json" for path in lock_calls)
    assert not any(path.name == "STATE.md" for path in lock_calls)


def test_phase_insert_uses_canonical_state_lock_and_locked_writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _create_roadmap(
        tmp_path,
        """\
        ### Phase 1: First
        **Goal:** do first

        ### Phase 2: Second
        **Goal:** do second
        """,
    )
    state = default_state_dict()
    state["position"]["current_phase"] = "01"
    state["position"]["current_phase_name"] = "First"
    state["position"]["total_phases"] = 2
    state["position"]["status"] = "Ready to plan"
    _write_state_pair(tmp_path, state)

    lock_calls = _assert_canonical_state_lock_and_locked_writer(tmp_path, monkeypatch)
    result = phase_insert(tmp_path, "1", "Hotfix")

    assert result.phase_number == "01.1"
    assert any(path.name == "state.json" for path in lock_calls)
    assert not any(path.name == "STATE.md" for path in lock_calls)


def test_phase_remove_uses_canonical_state_lock_and_locked_writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    state = default_state_dict()
    state["position"]["current_phase"] = "02"
    state["position"]["current_phase_name"] = "Second"
    state["position"]["total_phases"] = 3
    state["position"]["current_plan"] = "2"
    state["position"]["total_plans_in_phase"] = 2
    state["position"]["status"] = "in_progress"
    state["position"]["last_activity"] = "2026-03-01"
    state["position"]["last_activity_description"] = "Removing"
    _write_state_pair(tmp_path, state)
    _create_phase_dir(tmp_path, "01-first")
    _create_phase_dir(tmp_path, "02-second")
    _create_phase_dir(tmp_path, "03-third")

    lock_calls = _assert_canonical_state_lock_and_locked_writer(tmp_path, monkeypatch)
    result = phase_remove(tmp_path, "2")

    assert result.removed == "2"
    assert any(path.name == "state.json" for path in lock_calls)
    assert not any(path.name == "STATE.md" for path in lock_calls)


def test_phase_remove_rolls_back_roadmap_and_phase_tree_when_atomic_state_save_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    _seed_state_pair(tmp_path, current_phase="02", current_phase_name="Second", total_phases=3, status="in_progress")
    first_dir = _create_phase_dir(tmp_path, "01-first")
    (first_dir / "01-01-PLAN.md").write_text("plan", encoding="utf-8")
    second_dir = _create_phase_dir(tmp_path, "02-second")
    (second_dir / "02-01-PLAN.md").write_text("plan", encoding="utf-8")
    third_dir = _create_phase_dir(tmp_path, "03-third")
    (third_dir / "03-01-PLAN.md").write_text("plan", encoding="utf-8")

    before_roadmap = (tmp_path / "GPD" / "ROADMAP.md").read_text(encoding="utf-8")
    before_md = (tmp_path / "GPD" / "STATE.md").read_text(encoding="utf-8")
    before_json = (tmp_path / "GPD" / "state.json").read_text(encoding="utf-8")
    before_dirs = sorted(d.name for d in (tmp_path / "GPD" / "phases").iterdir() if d.is_dir())

    def _boom(_cwd: Path, _state_content: str) -> None:
        raise RuntimeError("sync exploded")

    monkeypatch.setattr("gpd.core.state.save_state_markdown_locked", _boom)

    with pytest.raises(RuntimeError, match="sync exploded"):
        phase_remove(tmp_path, "2")

    assert (tmp_path / "GPD" / "ROADMAP.md").read_text(encoding="utf-8") == before_roadmap
    assert (tmp_path / "GPD" / "STATE.md").read_text(encoding="utf-8") == before_md
    assert (tmp_path / "GPD" / "state.json").read_text(encoding="utf-8") == before_json
    assert sorted(d.name for d in (tmp_path / "GPD" / "phases").iterdir() if d.is_dir()) == before_dirs


def test_phase_complete_uses_canonical_state_lock_and_locked_writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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
    state = default_state_dict()
    state["position"]["current_phase"] = "01"
    state["position"]["current_phase_name"] = "Setup"
    state["position"]["total_phases"] = 2
    state["position"]["current_plan"] = "1"
    state["position"]["total_plans_in_phase"] = 1
    state["position"]["status"] = "in_progress"
    state["position"]["last_activity"] = "2026-03-01"
    state["position"]["last_activity_description"] = "Working"
    _write_state_pair(tmp_path, state)

    phase_dir = _create_phase_dir(tmp_path, "01-setup")
    (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
    (phase_dir / "a-SUMMARY.md").write_text("done", encoding="utf-8")
    _create_phase_dir(tmp_path, "02-build")

    lock_calls = _assert_canonical_state_lock_and_locked_writer(tmp_path, monkeypatch)
    result = phase_complete(tmp_path, "1")

    assert result.next_phase == "02"
    assert any(path.name == "state.json" for path in lock_calls)
    assert not any(path.name == "STATE.md" for path in lock_calls)


def test_phase_complete_rolls_back_roadmap_when_atomic_state_save_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    _seed_state_pair(tmp_path, current_phase="01", current_phase_name="Setup", total_phases=2, status="in_progress")
    phase_dir = _create_phase_dir(tmp_path, "01-setup")
    (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
    (phase_dir / "a-SUMMARY.md").write_text("done", encoding="utf-8")
    _create_phase_dir(tmp_path, "02-build")

    before_roadmap = (tmp_path / "GPD" / "ROADMAP.md").read_text(encoding="utf-8")

    def _boom(_cwd: Path, _state_content: str) -> None:
        raise RuntimeError("sync exploded")

    monkeypatch.setattr("gpd.core.state.save_state_markdown_locked", _boom)

    with pytest.raises(RuntimeError, match="sync exploded"):
        phase_complete(tmp_path, "1")

    assert (tmp_path / "GPD" / "ROADMAP.md").read_text(encoding="utf-8") == before_roadmap


def test_milestone_complete_uses_canonical_state_lock_and_locked_writer(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _create_roadmap(tmp_path, "## Milestone v1.0: Test\n### Phase 1: X\n**Goal:** x\n")
    state = default_state_dict()
    state["status"] = "in_progress"
    state["last_activity"] = "2026-03-01"
    state["last_activity_description"] = "Working"
    _write_state_pair(tmp_path, state)

    phase_dir = _create_phase_dir(tmp_path, "01-x")
    (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
    (phase_dir / "a-SUMMARY.md").write_text("---\none-liner: Did the thing\n---\n## Task 1\nDone", encoding="utf-8")

    lock_calls = _assert_canonical_state_lock_and_locked_writer(tmp_path, monkeypatch)
    result = milestone_complete(tmp_path, "v1.0", name="Test Milestone")

    assert result.version == "v1.0"
    assert any(path.name == "state.json" for path in lock_calls)
    assert not any(path.name == "STATE.md" for path in lock_calls)


def test_milestone_complete_rolls_back_archives_when_atomic_state_save_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ### Phase 1: Setup
        **Goal:** setup
        """,
    )
    _seed_state_pair(tmp_path, total_phases=1)
    phase_dir = _create_phase_dir(tmp_path, "01-setup")
    (phase_dir / "01-PLAN.md").write_text("plan", encoding="utf-8")
    (phase_dir / "01-SUMMARY.md").write_text("---\none-liner: Finished setup\n---\n\n# Summary\n", encoding="utf-8")
    audit_file = tmp_path / "GPD" / "v1.0-MILESTONE-AUDIT.md"
    audit_file.write_text("# Audit\n", encoding="utf-8")

    archive_dir = tmp_path / "GPD" / "milestones"

    def _boom(_cwd: Path, _state_content: str) -> None:
        raise RuntimeError("sync exploded")

    monkeypatch.setattr("gpd.core.state.save_state_markdown_locked", _boom)

    with pytest.raises(RuntimeError, match="sync exploded"):
        milestone_complete(tmp_path, "v1.0", name="Test Milestone")

    assert audit_file.exists()
    assert not (archive_dir / "v1.0-ROADMAP.md").exists()
    assert not (archive_dir / "v1.0-REQUIREMENTS.md").exists()
    assert not (archive_dir / "v1.0-MILESTONE-AUDIT.md").exists()
    assert not (tmp_path / "GPD" / "MILESTONES.md").exists()


def test_milestone_complete_rolls_back_partial_archives_when_audit_move_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ### Phase 1: Setup
        **Goal:** setup
        """,
    )
    _seed_state_pair(tmp_path, total_phases=1)
    phase_dir = _create_phase_dir(tmp_path, "01-setup")
    (phase_dir / "01-PLAN.md").write_text("plan", encoding="utf-8")
    (phase_dir / "01-SUMMARY.md").write_text("---\none-liner: Finished setup\n---\n\n# Summary\n", encoding="utf-8")
    audit_file = tmp_path / "GPD" / "v1.0-MILESTONE-AUDIT.md"
    audit_file.write_text("# Audit\n", encoding="utf-8")
    archive_dir = tmp_path / "GPD" / "milestones"

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("archive exploded")

    monkeypatch.setattr("gpd.core.phases.shutil.move", _boom)

    with pytest.raises(RuntimeError, match="archive exploded"):
        milestone_complete(tmp_path, "v1.0", name="Test Milestone")

    assert audit_file.exists()
    assert not (archive_dir / "v1.0-ROADMAP.md").exists()
    assert not (archive_dir / "v1.0-REQUIREMENTS.md").exists()
    assert not (archive_dir / "v1.0-MILESTONE-AUDIT.md").exists()
    assert not (tmp_path / "GPD" / "MILESTONES.md").exists()



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

    roadmap = (tmp_path / "GPD" / "ROADMAP.md").read_text()
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
    phases_dir = tmp_path / "GPD" / "phases"
    for i in range(1, 4):
        d = _create_phase_dir(tmp_path, f"{str(i).zfill(2)}-work")
        (d / f"{str(i).zfill(2)}-PLAN.md").write_text("plan", encoding="utf-8")

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
    phases_dir = tmp_path / "GPD" / "phases"
    _create_phase_dir(tmp_path, "03-base")
    for i in range(1, 4):
        d = _create_phase_dir(tmp_path, f"03.{i}-fix")
        (d / f"03.{i}-PLAN.md").write_text("plan", encoding="utf-8")

    phase_remove(tmp_path, "3.1", force=True)

    remaining = sorted(d.name for d in phases_dir.iterdir() if d.is_dir())
    assert remaining == ["03-base", "03.1-fix", "03.2-fix"]
    assert (phases_dir / "03.1-fix" / "03.1-PLAN.md").exists()
    assert (phases_dir / "03.2-fix" / "03.2-PLAN.md").exists()


def test_phase_remove_integer_removes_descendant_subtree_and_clears_removed_current_plan(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ### Phase 1: Setup
        **Goal:** setup

        ### Phase 2: Main
        **Goal:** main

        ### Phase 2.1: Hotfix
        **Goal:** hotfix

        ### Phase 2.1.1: Detail
        **Goal:** detail

        ### Phase 3: Validation
        **Goal:** validate
        **Artifact:** 03-01-PLAN.md
        """,
    )
    _create_state(
        tmp_path,
        """\
        **Current Phase:** 2.1.1
        **Current Phase Name:** Detail
        **Total Phases:** 5
        **Current Plan:** 2
        **Total Plans in Phase:** 2
        **Status:** in_progress
        **Last Activity:** 2026-03-01
        **Last Activity Description:** Debugging
        """,
    )

    phases_dir = tmp_path / "GPD" / "phases"
    setup_dir = _create_phase_dir(tmp_path, "01-setup")
    (setup_dir / "01-01-PLAN.md").write_text("plan", encoding="utf-8")
    _create_phase_dir(tmp_path, "02-main")
    _create_phase_dir(tmp_path, "02.1-hotfix")
    _create_phase_dir(tmp_path, "02.1.1-detail")
    validation_dir = _create_phase_dir(tmp_path, "03-validation")
    (validation_dir / "03-01-PLAN.md").write_text("plan", encoding="utf-8")

    phase_remove(tmp_path, "2")

    remaining = sorted(d.name for d in phases_dir.iterdir() if d.is_dir())
    assert remaining == ["01-setup", "02-validation"]

    roadmap = (tmp_path / "GPD" / "ROADMAP.md").read_text()
    assert "### Phase 2: Validation" in roadmap
    assert "### Phase 2.1:" not in roadmap
    assert "### Phase 2.1.1:" not in roadmap

    state = (tmp_path / "GPD" / "STATE.md").read_text()
    assert "**Current Phase:** 02" in state
    assert "**Current Phase Name:** Validation" in state
    assert "**Current Plan:** \u2014" in state
    assert "**Total Plans in Phase:** 1" in state


def test_phase_remove_decimal_removes_descendants_and_renumbers_later_subtree_references(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ## Phase Overview

        - [ ] Phase 3: Base
        - [ ] Phase 3.1: Fix
        - [ ] Phase 3.1.1: Detail
        - [ ] Phase 3.2: Follow-up
        - [ ] Phase 3.2.1: Follow-up Detail

        | Phase | Status | Updated |
        |---|---|---|
        | 3. Base | Ready | - |
        | 3.1. Fix | Ready | - |
        | 3.1.1. Detail | Ready | - |
        | 3.2. Follow-up | Ready | - |
        | 3.2.1. Follow-up Detail | Ready | - |

        ### Phase 3: Base
        **Goal:** base

        ### Phase 3.1: Fix
        **Goal:** fix

        ### Phase 3.1.1: Detail
        **Goal:** detail

        ### Phase 3.2: Follow-up
        **Goal:** follow-up
        **Artifact:** 03.2-01-PLAN.md

        ### Phase 3.2.1: Follow-up Detail
        **Goal:** follow-up detail
        **Depends on:** Phase 3.2
        **Artifact:** 03.2.1-01-PLAN.md
        """,
    )
    phases_dir = tmp_path / "GPD" / "phases"
    _create_phase_dir(tmp_path, "03-base")
    _create_phase_dir(tmp_path, "03.1-fix")
    _create_phase_dir(tmp_path, "03.1.1-detail")
    followup_dir = _create_phase_dir(tmp_path, "03.2-follow-up")
    (followup_dir / "03.2-01-PLAN.md").write_text("plan", encoding="utf-8")
    detail_dir = _create_phase_dir(tmp_path, "03.2.1-follow-up-detail")
    (detail_dir / "03.2.1-01-PLAN.md").write_text("plan", encoding="utf-8")

    phase_remove(tmp_path, "3.1", force=True)

    remaining = sorted(d.name for d in phases_dir.iterdir() if d.is_dir())
    assert remaining == ["03-base", "03.1-follow-up", "03.1.1-follow-up-detail"]
    assert (phases_dir / "03.1-follow-up" / "03.1-01-PLAN.md").exists()
    assert (phases_dir / "03.1.1-follow-up-detail" / "03.1.1-01-PLAN.md").exists()

    roadmap = (tmp_path / "GPD" / "ROADMAP.md").read_text()
    assert "### Phase 3.1: Follow-up" in roadmap
    assert "### Phase 3.1.1: Follow-up Detail" in roadmap
    assert "- [ ] Phase 3.1.1: Follow-up Detail" in roadmap
    assert "| 3.1.1. Follow-up Detail | Ready | - |" in roadmap
    assert "**Depends on:** Phase 3.1" in roadmap
    assert "03.1.1-01-PLAN.md" in roadmap
    assert "Phase 3.2" not in roadmap
    assert "Phase 3.2.1" not in roadmap


def test_phase_remove_decimal_descendant_current_phase_falls_back_to_previous_phase(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ### Phase 3: Base
        **Goal:** base

        ### Phase 3.1: Fix
        **Goal:** fix

        ### Phase 3.1.1: Detail
        **Goal:** detail

        ### Phase 3.2: Follow-up
        **Goal:** follow-up

        ### Phase 3.2.1: Follow-up Detail
        **Goal:** follow-up detail
        """,
    )
    _create_state(
        tmp_path,
        """\
        **Current Phase:** 3.1.1
        **Current Phase Name:** Detail
        **Total Phases:** 5
        **Current Plan:** 2
        **Total Plans in Phase:** 2
        **Status:** in_progress
        **Last Activity:** 2026-03-01
        **Last Activity Description:** Debugging
        """,
    )
    _create_phase_dir(tmp_path, "03-base")
    _create_phase_dir(tmp_path, "03.1-fix")
    _create_phase_dir(tmp_path, "03.1.1-detail")
    _create_phase_dir(tmp_path, "03.2-follow-up")
    _create_phase_dir(tmp_path, "03.2.1-follow-up-detail")

    phase_remove(tmp_path, "3.1", force=True)

    state = (tmp_path / "GPD" / "STATE.md").read_text(encoding="utf-8")
    assert "**Current Phase:** 03" in state
    assert "**Current Phase Name:** Base" in state
    assert "**Current Plan:** \u2014" in state


def test_phase_remove_with_summaries_needs_force(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(tmp_path, "### Phase 1: X\n**Goal:** x\n")
    phase_dir = _create_phase_dir(tmp_path, "01-x")
    (phase_dir / "SUMMARY.md").write_text("done", encoding="utf-8")

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
    (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
    (phase_dir / "a-SUMMARY.md").write_text("done", encoding="utf-8")
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
    (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
    (phase_dir / "a-SUMMARY.md").write_text("done", encoding="utf-8")

    result = phase_complete(tmp_path, "1")

    assert result.next_phase == "02"
    assert result.next_phase_name == "Build"
    assert result.is_last_phase is False

    state = (tmp_path / "GPD" / "STATE.md").read_text()
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
    (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")

    with pytest.raises(PhaseIncompleteError):
        phase_complete(tmp_path, "1")


# ─── milestone_complete ──────────────────────────────────────────────────────────


def test_milestone_complete_success(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(tmp_path, "## Milestone v1.0: Test\n### Phase 1: X\n**Goal:** x\n")

    phase_dir = _create_phase_dir(tmp_path, "01-x")
    (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
    (phase_dir / "a-SUMMARY.md").write_text("---\none-liner: Did the thing\n---\n## Task 1\nDone", encoding="utf-8")

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
    (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
    (phase_dir / "a-SUMMARY.md").write_text("---\none-liner: Done\n---\n", encoding="utf-8")

    with pytest.raises(MilestoneIncompleteError):
        milestone_complete(tmp_path, "v1.0", name="Test")


def test_milestone_complete_incomplete_phases(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(tmp_path, "## v1.0\n")

    phase_dir = _create_phase_dir(tmp_path, "01-x")
    (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")

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
    (derivation_dir / "02-01-PLAN.md").write_text("plan", encoding="utf-8")
    (derivation_dir / "02-02-PLAN.md").write_text("plan", encoding="utf-8")
    validation_dir = _create_phase_dir(tmp_path, "03-validation")
    (validation_dir / "03-01-PLAN.md").write_text("plan", encoding="utf-8")

    phase_remove(tmp_path, "2")

    state = (tmp_path / "GPD" / "STATE.md").read_text()
    assert "**Current Phase:** 02" in state
    assert "**Current Phase Name:** Validation" in state
    assert "**Total Phases:** 2" in state
    assert "**Current Plan:** \u2014" in state
    assert "**Total Plans in Phase:** 1" in state

    state_json = json.loads((tmp_path / "GPD" / "state.json").read_text())
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
    (main_dir / "02-01-PLAN.md").write_text("plan", encoding="utf-8")
    hotfix_dir = _create_phase_dir(tmp_path, "02.1-hotfix")
    (hotfix_dir / "02.1-01-PLAN.md").write_text("plan", encoding="utf-8")

    phase_remove(tmp_path, "1")

    roadmap = (tmp_path / "GPD" / "ROADMAP.md").read_text()
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
    (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
    (phase_dir / "a-SUMMARY.md").write_text("done", encoding="utf-8")

    result = progress_render(tmp_path, "json")
    assert result.percent == 100
    assert result.total_plans == 1
    assert result.total_summaries == 1
    assert len(result.phases) == 1


def test_progress_render_bar(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(tmp_path, "## v1.0: Test\n")
    phase_dir = _create_phase_dir(tmp_path, "01-x")
    (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")

    result = progress_render(tmp_path, "bar")
    assert result.percent == 0
    assert result.total == 1


def test_progress_render_table(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    _create_roadmap(tmp_path, "## v1.0: Test\n")
    phase_dir = _create_phase_dir(tmp_path, "01-x")
    (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
    (phase_dir / "a-SUMMARY.md").write_text("done", encoding="utf-8")

    result = progress_render(tmp_path, "table")
    assert "| Phase |" in result.rendered
    assert "Complete" in result.rendered


# ─── phase_plan_index ────────────────────────────────────────────────────────────


def test_phase_plan_index_basic(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    phase_dir = _create_phase_dir(tmp_path, "01-setup")
    (phase_dir / "a-PLAN.md").write_text("---\nwave: 1\n---\n## Task 1\nDo stuff", encoding="utf-8")
    (phase_dir / "b-PLAN.md").write_text("---\nwave: 2\ndepends_on: [a]\n---\n## Task 1\nMore stuff", encoding="utf-8")

    result = phase_plan_index(tmp_path, "1")
    assert result.phase == "01"
    assert len(result.plans) == 2
    assert "1" in result.waves
    assert "2" in result.waves
    assert result.validation.valid is True


def test_phase_plan_index_rejects_scalar_dependency_fields(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    phase_dir = _create_phase_dir(tmp_path, "01-setup")
    (phase_dir / "a-PLAN.md").write_text("---\nwave: 1\ndepends_on: []\nfiles_modified: []\n---\n## Task 1\nDo stuff", encoding="utf-8")
    (phase_dir / "b-PLAN.md").write_text("---\nwave: 2\ndepends_on: a\nfiles_modified: []\n---\n## Task 1\nMore stuff", encoding="utf-8")

    result = phase_plan_index(tmp_path, "1")
    assert result.validation.valid is False
    assert any("depends_on" in error for error in result.validation.errors)


def test_phase_plan_index_detects_checkpoint_tasks_without_interactive_flag(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    phase_dir = _create_phase_dir(tmp_path, "01-setup")
    (phase_dir / "a-PLAN.md").write_text(
        textwrap.dedent(
            """\
            ---
            wave: 1
            ---
            <task type="checkpoint">
              <name>Review the checkpoint</name>
            </task>
            """
        ), encoding="utf-8"
    )

    result = phase_plan_index(tmp_path, "1")

    assert result.has_checkpoints is True


def test_validate_phase_waves_reports_malformed_frontmatter(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    phase_dir = _create_phase_dir(tmp_path, "01-setup")
    (phase_dir / "a-PLAN.md").write_text("---\nwave: [\n---\n## Task 1\nDo stuff", encoding="utf-8")

    result = validate_phase_waves(tmp_path, "1")
    assert result.validation.valid is False
    assert any("a-PLAN.md" in error for error in result.validation.errors)


def test_validate_phase_waves_rejects_coercive_wave_values(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    phase_dir = _create_phase_dir(tmp_path, "01-setup")
    (phase_dir / "a-PLAN.md").write_text("---\nwave: true\n---\n## Task 1\nDo stuff", encoding="utf-8")

    result = validate_phase_waves(tmp_path, "1")

    assert result.validation.valid is False
    assert any("wave must be an integer" in error for error in result.validation.errors)


def test_phase_plan_index_rejects_coercive_wave_values(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    phase_dir = _create_phase_dir(tmp_path, "01-setup")
    (phase_dir / "a-PLAN.md").write_text("---\nwave: 1.5\n---\n## Task 1\nDo stuff", encoding="utf-8")

    result = phase_plan_index(tmp_path, "1")

    assert result.validation.valid is False
    assert any("wave must be an integer" in error for error in result.validation.errors)


def test_phase_plan_index_not_found(tmp_path: Path) -> None:
    _setup_project(tmp_path)
    result = phase_plan_index(tmp_path, "99")
    assert result.plans == []


# ─── Bug-fix regression tests ────────────────────────────────────────────────


def test_phase_complete_sets_current_plan_to_em_dash(tmp_path: Path) -> None:
    """After phase_complete the Current Plan field must be the em-dash placeholder,
    not the string 'Not started', so that state_advance_plan can parse it correctly."""
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
        **Status:** in_progress
        **Last Activity:** 2026-03-01
        **Last Activity Description:** Working
        """,
    )

    phase_dir = _create_phase_dir(tmp_path, "01-setup")
    (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
    (phase_dir / "a-SUMMARY.md").write_text("done", encoding="utf-8")
    _create_phase_dir(tmp_path, "02-build")

    phase_complete(tmp_path, "1")

    state = (tmp_path / "GPD" / "STATE.md").read_text()
    assert "**Current Plan:** \u2014" in state
    assert "Not started" not in state


def test_progress_json_result_has_total_plans_attribute() -> None:
    """ProgressJsonResult must expose ``total_plans`` (not ``total_plans_in_phase``)."""
    result = ProgressJsonResult(
        milestone_version="v1.0",
        milestone_name="Test",
        total_plans=5,
        total_summaries=3,
        percent=60,
    )
    assert result.total_plans == 5
    assert not hasattr(result, "total_plans_in_phase")
