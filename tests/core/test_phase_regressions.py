"""Behavior-focused phase regression coverage."""

from __future__ import annotations

import json
import textwrap
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch


def _setup_project(tmp_path: Path) -> Path:
    planning = tmp_path / "GPD"
    planning.mkdir(exist_ok=True)
    (planning / "phases").mkdir(exist_ok=True)
    return tmp_path


def _create_roadmap(tmp_path: Path, content: str) -> Path:
    roadmap = tmp_path / "GPD" / "ROADMAP.md"
    roadmap.write_text(textwrap.dedent(content), encoding="utf-8")
    return roadmap


def _create_state_md(tmp_path: Path, content: str) -> Path:
    state = tmp_path / "GPD" / "STATE.md"
    state.write_text(textwrap.dedent(content), encoding="utf-8")
    return state


def _create_state_json(tmp_path: Path, *, current_phase: str = "01") -> Path:
    from gpd.core.state import default_state_dict

    state = default_state_dict()
    position = state.setdefault("position", {})
    position["current_phase"] = current_phase
    position["status"] = "Executing"
    position["current_plan"] = "1"
    position["total_plans_in_phase"] = 1
    position["progress_percent"] = 50
    path = tmp_path / "GPD" / "state.json"
    path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    return path


def _create_phase_dir(tmp_path: Path, name: str) -> Path:
    phase_dir = tmp_path / "GPD" / "phases" / name
    phase_dir.mkdir(parents=True, exist_ok=True)
    return phase_dir


class TestRoadmapCheckboxMatching:
    def _make_project(self, tmp_path: Path, roadmap_content: str) -> Path:
        gpd_dir = tmp_path / "GPD"
        gpd_dir.mkdir()
        (gpd_dir / "phases").mkdir()
        (gpd_dir / "ROADMAP.md").write_text(roadmap_content, encoding="utf-8")
        return tmp_path

    def test_phase1_not_matched_by_phase10(self, tmp_path: Path) -> None:
        from gpd.core.phases import roadmap_analyze

        roadmap = (
            "# Roadmap\n\n"
            "- [ ] Phase 1: Setup\n"
            "- [x] Phase 10: Final\n\n"
            "## Phase 1: Setup\n\n"
            "**Goal:** Setup things\n"
            "**Depends on:** None\n\n"
            "## Phase 10: Final\n\n"
            "**Goal:** Wrap up\n"
            "**Depends on:** Phase 9\n"
        )
        result = roadmap_analyze(self._make_project(tmp_path, roadmap))

        phase1 = next((phase for phase in result.phases if phase.number == "1"), None)
        phase10 = next((phase for phase in result.phases if phase.number == "10"), None)

        assert phase1 is not None
        assert phase10 is not None
        assert phase1.roadmap_complete is False
        assert phase10.roadmap_complete is True

    def test_phase1_checked_independently_of_phase10(self, tmp_path: Path) -> None:
        from gpd.core.phases import roadmap_analyze

        roadmap = (
            "# Roadmap\n\n"
            "- [x] Phase 1: Setup\n"
            "- [ ] Phase 10: Final\n\n"
            "## Phase 1: Setup\n\n"
            "**Goal:** Setup\n\n"
            "## Phase 10: Final\n\n"
            "**Goal:** Final\n"
        )
        result = roadmap_analyze(self._make_project(tmp_path, roadmap))

        phase1 = next((phase for phase in result.phases if phase.number == "1"), None)
        phase10 = next((phase for phase in result.phases if phase.number == "10"), None)

        assert phase1 is not None
        assert phase10 is not None
        assert phase1.roadmap_complete is True
        assert phase10.roadmap_complete is False


def test_phase_add_does_not_emit_none_slug(tmp_path: Path) -> None:
    from gpd.core.phases import phase_add

    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """
        # Roadmap

        ## Phase 1: Existing
        **Goal:** Existing phase
        **Depends on:** None
        """,
    )

    with patch("gpd.core.phases.generate_slug", return_value=None):
        result = phase_add(tmp_path, "!!!")

    assert "None" not in result.directory
    created_dirs = [entry.name for entry in (tmp_path / "GPD" / "phases").iterdir() if entry.is_dir()]
    assert all("None" not in entry for entry in created_dirs)


def test_first_phase_depends_on_none(tmp_path: Path) -> None:
    from gpd.core.phases import phase_add

    _setup_project(tmp_path)
    _create_roadmap(tmp_path, "# Roadmap\n\n")

    result = phase_add(tmp_path, "First phase")

    assert result.phase_number == 1
    roadmap = (tmp_path / "GPD" / "ROADMAP.md").read_text(encoding="utf-8")
    assert "**Depends on:** None" in roadmap
    assert "Phase 0" not in roadmap


class TestProgressPercentCapping:
    def _setup_phases(self, tmp_path: Path, plan_counts: dict[str, int], summary_counts: dict[str, int]) -> None:
        gpd_dir = tmp_path / "GPD"
        phases_dir = gpd_dir / "phases"
        gpd_dir.mkdir(parents=True, exist_ok=True)
        (gpd_dir / "ROADMAP.md").write_text("## v1.0: Test\n\n", encoding="utf-8")

        for phase_name, plan_count in plan_counts.items():
            phase_dir = phases_dir / phase_name
            phase_dir.mkdir(parents=True, exist_ok=True)
            for idx in range(plan_count):
                (phase_dir / f"task-{idx}-PLAN.md").write_text(f"plan {idx}", encoding="utf-8")
            for idx in range(summary_counts.get(phase_name, 0)):
                (phase_dir / f"task-{idx}-SUMMARY.md").write_text(f"summary {idx}", encoding="utf-8")

    def test_progress_render_caps_at_100(self, tmp_path: Path) -> None:
        from gpd.core.phases import progress_render

        self._setup_phases(tmp_path, {"01-phase": 2}, {"01-phase": 4})
        result = progress_render(tmp_path, fmt="json")

        assert result.percent <= 100

    def test_roadmap_analyze_caps_at_100(self, tmp_path: Path) -> None:
        from gpd.core.phases import roadmap_analyze

        gpd = tmp_path / "GPD"
        phase_dir = gpd / "phases" / "01-setup"
        phase_dir.mkdir(parents=True)
        (phase_dir / "task-1-PLAN.md").write_text("plan", encoding="utf-8")
        (phase_dir / "task-1-SUMMARY.md").write_text("summary 1", encoding="utf-8")
        (phase_dir / "task-2-SUMMARY.md").write_text("summary 2", encoding="utf-8")
        (phase_dir / "task-3-SUMMARY.md").write_text("summary 3", encoding="utf-8")
        (gpd / "ROADMAP.md").write_text(
            "## v1.0: Test\n\n### Phase 1: Setup\n\n**Goal:** Set up things\n",
            encoding="utf-8",
        )

        result = roadmap_analyze(tmp_path)

        assert result.progress_percent <= 100


def test_phase_complete_uses_utc_date_near_midnight(tmp_path: Path) -> None:
    from gpd.core.phases import phase_complete

    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """
        ### Phase 1: Setup
        **Goal:** setup
        **Plans:** 1 plans

        ### Phase 2: Build
        **Goal:** build
        """,
    )
    _create_state_md(
        tmp_path,
        """
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
    (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
    (phase_dir / "a-SUMMARY.md").write_text("done", encoding="utf-8")
    _create_phase_dir(tmp_path, "02-build")

    fake_utc = datetime(2026, 1, 15, 23, 30, 0, tzinfo=UTC)
    with patch("gpd.core.phases.datetime") as mock_datetime:
        mock_datetime.now.return_value = fake_utc
        result = phase_complete(tmp_path, "1")

    assert result.date == "2026-01-15"


def test_milestone_complete_uses_utc_date_near_midnight(tmp_path: Path) -> None:
    from gpd.core.phases import milestone_complete

    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """
        ## v1.0: First Release

        ### Phase 1: Setup
        **Goal:** setup
        **Plans:** 1 plans
        """,
    )
    _create_state_md(
        tmp_path,
        """
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
    (phase_dir / "a-PLAN.md").write_text("plan", encoding="utf-8")
    (phase_dir / "a-SUMMARY.md").write_text("done", encoding="utf-8")
    (tmp_path / "GPD" / "REQUIREMENTS.md").write_text("# Requirements\n", encoding="utf-8")

    fake_utc = datetime(2026, 3, 31, 23, 59, 0, tzinfo=UTC)
    with patch("gpd.core.phases.datetime") as mock_datetime:
        mock_datetime.now.return_value = fake_utc
        result = milestone_complete(tmp_path, version="v1.0")

    assert result.date == "2026-03-31"


# ─── BUG-018: phase_add / phase_insert heading consistency ────────────────────


def test_phase_add_matches_existing_heading_level(tmp_path: Path) -> None:
    """phase_add should match the heading level of existing phases."""
    from gpd.core.phases import phase_add

    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ## Phase 1: Existing
        **Goal:** exist
        """,
    )

    phase_add(tmp_path, "New Phase")

    roadmap = (tmp_path / "GPD" / "ROADMAP.md").read_text(encoding="utf-8")
    assert "## Phase 2: New Phase" in roadmap
    assert "### Phase 2" not in roadmap


def test_phase_add_matches_existing_padding(tmp_path: Path) -> None:
    """phase_add should match zero-padding of existing phases."""
    from gpd.core.phases import phase_add

    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ### Phase 01: Existing
        **Goal:** exist
        """,
    )

    phase_add(tmp_path, "New Phase")

    roadmap = (tmp_path / "GPD" / "ROADMAP.md").read_text(encoding="utf-8")
    assert "### Phase 02: New Phase" in roadmap


def test_phase_add_matches_emdash_separator(tmp_path: Path) -> None:
    """phase_add should match em-dash separator of existing phases."""
    from gpd.core.phases import phase_add

    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        "### Phase 01 \u2014 Existing\n**Goal:** exist\n",
    )

    phase_add(tmp_path, "New Phase")

    roadmap = (tmp_path / "GPD" / "ROADMAP.md").read_text(encoding="utf-8")
    assert "### Phase 02 \u2014 New Phase" in roadmap
    assert "Phase 02:" not in roadmap


def test_phase_add_depends_on_uses_padded_form(tmp_path: Path) -> None:
    """Depends-on line should use the same padding as headings."""
    from gpd.core.phases import phase_add

    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ### Phase 01: Existing
        **Goal:** exist
        """,
    )

    phase_add(tmp_path, "New Phase")

    roadmap = (tmp_path / "GPD" / "ROADMAP.md").read_text(encoding="utf-8")
    assert "**Depends on:** Phase 01" in roadmap


def test_phase_insert_matches_heading_level(tmp_path: Path) -> None:
    """phase_insert should match existing heading level."""
    from gpd.core.phases import phase_insert

    _setup_project(tmp_path)
    _create_roadmap(
        tmp_path,
        """\
        ## Phase 1: First
        **Goal:** first

        ## Phase 2: Second
        **Goal:** second
        """,
    )

    phase_insert(tmp_path, "1", "Hotfix")

    roadmap = (tmp_path / "GPD" / "ROADMAP.md").read_text(encoding="utf-8")
    assert "## Phase 01.1" in roadmap
    assert "### Phase 01.1" not in roadmap


def test_phase_insert_depends_on_uses_normalized_form(tmp_path: Path) -> None:
    """phase_insert Depends-on should use normalized (padded) phase number."""
    from gpd.core.phases import phase_insert

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

    phase_insert(tmp_path, "1", "Urgent Fix")

    roadmap = (tmp_path / "GPD" / "ROADMAP.md").read_text(encoding="utf-8")
    # NOTE: phase_normalize always pads the top-level segment to 2 digits
    # (e.g., "1" -> "01"), so the Depends-on line says "Phase 01" even though
    # the ROADMAP uses unpadded headings ("Phase 1:").  This is a known
    # pre-existing inconsistency in phase_normalize's design, not a bug in
    # phase_insert.  Changing phase_normalize is out of scope for BUG-018.
    assert "**Depends on:** Phase 01" in roadmap
