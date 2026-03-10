"""Tests for gpd.core.context — context assembly for AI agent commands."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gpd.core.context import (
    _generate_slug,
    _is_phase_complete,
    _normalize_phase_name,
    init_execute_phase,
    init_map_theory,
    init_milestone_op,
    init_new_milestone,
    init_new_project,
    init_plan_phase,
    init_progress,
    init_quick,
    init_resume,
    init_todos,
    init_verify_work,
    load_config,
)
from gpd.core.errors import ConfigError, ValidationError

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


def _create_config(tmp_path: Path, config: dict) -> Path:
    """Write config.json and return its path."""
    config_path = tmp_path / ".gpd" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(config))
    return config_path


def _create_roadmap(tmp_path: Path, content: str) -> Path:
    """Write ROADMAP.md and return its path."""
    roadmap = tmp_path / ".gpd" / "ROADMAP.md"
    roadmap.parent.mkdir(parents=True, exist_ok=True)
    roadmap.write_text(content)
    return roadmap


# ─── Helper Tests ──────────────────────────────────────────────────────────────


class TestHelpers:
    def test_generate_slug(self) -> None:
        assert _generate_slug("Hello World!") == "hello-world"
        assert _generate_slug("") is None
        assert _generate_slug(None) is None
        assert _generate_slug("already-slug") == "already-slug"

    def test_normalize_phase_name(self) -> None:
        assert _normalize_phase_name("3") == "03"
        assert _normalize_phase_name("12") == "12"
        assert _normalize_phase_name("3.1") == "03.1"
        assert _normalize_phase_name("3.1.2") == "03.1.2"
        assert _normalize_phase_name("abc") == "abc"

    def test_is_phase_complete(self) -> None:
        assert _is_phase_complete(2, 2) is True
        assert _is_phase_complete(2, 3) is True
        assert _is_phase_complete(2, 1) is False
        assert _is_phase_complete(0, 0) is False


# ─── load_config ───────────────────────────────────────────────────────────────


class TestLoadConfig:
    def test_defaults_when_no_config(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        config = load_config(tmp_path)
        assert config["autonomy"] == "guided"
        assert config["research_mode"] == "balanced"
        assert config["commit_docs"] is True
        assert config["parallelization"] is True
        assert config["verifier"] is True

    def test_custom_config(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_config(tmp_path, {"autonomy": "yolo", "research_mode": "exploit"})
        config = load_config(tmp_path)
        assert config["autonomy"] == "yolo"
        assert config["research_mode"] == "exploit"

    def test_nested_config(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_config(tmp_path, {"workflow": {"research": False, "plan_checker": False}})
        config = load_config(tmp_path)
        assert config["research"] is False
        assert config["plan_checker"] is False

    def test_parallelization_bool(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_config(tmp_path, {"parallelization": False})
        config = load_config(tmp_path)
        assert config["parallelization"] is False

    def test_removed_mode_key_raises(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_config(tmp_path, {"mode": "yolo"})
        with pytest.raises(ConfigError, match="`mode` was removed; use `autonomy`"):
            load_config(tmp_path)

    def test_removed_parallelization_object_raises(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_config(tmp_path, {"parallelization": {"enabled": False}})
        with pytest.raises(
            ConfigError,
            match="`parallelization.enabled` object form was removed; set `parallelization` to true or false",
        ):
            load_config(tmp_path)

    def test_malformed_config_raises(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        config_path = tmp_path / ".gpd" / "config.json"
        config_path.write_text("not valid json {{{")
        with pytest.raises(ConfigError, match="Malformed config.json"):
            load_config(tmp_path)


# ─── init_execute_phase ────────────────────────────────────────────────────────


class TestInitExecutePhase:
    def test_basic(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "a-PLAN.md").write_text("plan")
        (phase_dir / "a-SUMMARY.md").write_text("summary")

        ctx = init_execute_phase(tmp_path, "1")
        assert ctx["phase_found"] is True
        assert ctx["phase_number"] in ("1", "01")  # depends on phases module normalization
        assert ctx["plan_count"] == 1
        assert ctx["incomplete_count"] == 0
        assert ctx["state_exists"] is False

    def test_missing_phase_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match="phase is required"):
            init_execute_phase(tmp_path, "")

    def test_includes_state(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_phase_dir(tmp_path, "01-setup")
        (tmp_path / ".gpd" / "STATE.md").write_text("# State\nstuff")

        ctx = init_execute_phase(tmp_path, "1", includes={"state"})
        assert ctx["state_content"] == "# State\nstuff"


# ─── init_plan_phase ──────────────────────────────────────────────────────────


class TestInitPlanPhase:
    def test_basic(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "02-analysis")
        (phase_dir / "RESEARCH.md").write_text("research")

        ctx = init_plan_phase(tmp_path, "2")
        assert ctx["phase_found"] is True
        assert ctx["has_research"] is True
        assert ctx["has_plans"] is False
        assert ctx["padded_phase"] == "02"

    def test_includes_research(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "02-analysis")
        (phase_dir / "RESEARCH.md").write_text("findings here")

        ctx = init_plan_phase(tmp_path, "2", includes={"research"})
        assert ctx["research_content"] == "findings here"


# ─── init_new_project ─────────────────────────────────────────────────────────


class TestInitNewProject:
    def test_empty_project(self, tmp_path: Path) -> None:
        ctx = init_new_project(tmp_path)
        assert ctx["has_research_files"] is False
        assert ctx["has_project_manifest"] is False
        assert ctx["has_existing_project"] is False
        assert ctx["planning_exists"] is False

    def test_detects_research_files(self, tmp_path: Path) -> None:
        (tmp_path / "calc.py").write_text("import numpy")
        ctx = init_new_project(tmp_path)
        assert ctx["has_research_files"] is True
        assert ctx["has_existing_project"] is True

    def test_detects_manifest(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]")
        ctx = init_new_project(tmp_path)
        assert ctx["has_project_manifest"] is True


# ─── init_new_milestone ───────────────────────────────────────────────────────


class TestInitNewMilestone:
    def test_basic(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        _create_roadmap(tmp_path, "## Milestone v1.0: Setup Phase\n")

        ctx = init_new_milestone(tmp_path)
        assert ctx["current_milestone"] == "v1.0"
        assert ctx["current_milestone_name"] == "Setup Phase"


# ─── init_quick ───────────────────────────────────────────────────────────────


class TestInitQuick:
    def test_first_quick_task(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        ctx = init_quick(tmp_path, "Fix tensor product calculation")
        assert ctx["next_num"] == 1
        assert ctx["slug"] is not None
        assert "fix" in ctx["slug"]
        assert ctx["task_dir"] is not None

    def test_increments_number(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        quick_dir = tmp_path / ".gpd" / "quick"
        quick_dir.mkdir()
        (quick_dir / "1-first-task").mkdir()
        (quick_dir / "2-second-task").mkdir()

        ctx = init_quick(tmp_path, "next task")
        assert ctx["next_num"] == 3

    def test_no_description(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        ctx = init_quick(tmp_path)
        assert ctx["slug"] is None
        assert ctx["task_dir"] is None


# ─── init_resume ──────────────────────────────────────────────────────────────


class TestInitResume:
    def test_no_interrupted_agent(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        ctx = init_resume(tmp_path)
        assert ctx["has_interrupted_agent"] is False
        assert ctx["interrupted_agent_id"] is None

    def test_with_interrupted_agent(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        (tmp_path / ".gpd" / "current-agent-id.txt").write_text("agent-123\n")

        ctx = init_resume(tmp_path)
        assert ctx["has_interrupted_agent"] is True
        assert ctx["interrupted_agent_id"] == "agent-123"


# ─── init_verify_work ─────────────────────────────────────────────────────────


class TestInitVerifyWork:
    def test_basic(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        phase_dir = _create_phase_dir(tmp_path, "01-setup")
        (phase_dir / "VERIFICATION.md").write_text("verified")

        ctx = init_verify_work(tmp_path, "1")
        assert ctx["phase_found"] is True
        assert ctx["has_verification"] is True

    def test_missing_phase_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValidationError, match="phase is required"):
            init_verify_work(tmp_path, "")


# ─── init_todos ───────────────────────────────────────────────────────────────


class TestInitTodos:
    def test_empty_todos(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        ctx = init_todos(tmp_path)
        assert ctx["todo_count"] == 0
        assert ctx["todos"] == []

    def test_finds_todos(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        pending = tmp_path / ".gpd" / "todos" / "pending"
        pending.mkdir(parents=True)
        (pending / "check-convergence.md").write_text(
            'title: "Check convergence"\narea: numerical\ncreated: 2026-03-01'
        )

        ctx = init_todos(tmp_path)
        assert ctx["todo_count"] == 1
        assert ctx["todos"][0]["title"] == "Check convergence"
        assert ctx["todos"][0]["area"] == "numerical"

    def test_area_filter(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        pending = tmp_path / ".gpd" / "todos" / "pending"
        pending.mkdir(parents=True)
        (pending / "a.md").write_text("title: A\narea: theory")
        (pending / "b.md").write_text("title: B\narea: numerical")

        ctx = init_todos(tmp_path, area="theory")
        assert ctx["todo_count"] == 1
        assert ctx["todos"][0]["title"] == "A"


# ─── init_milestone_op ────────────────────────────────────────────────────────


class TestInitMilestoneOp:
    def test_empty_project(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        ctx = init_milestone_op(tmp_path)
        assert ctx["phase_count"] == 0
        assert ctx["completed_phases"] == 0
        assert ctx["all_phases_complete"] is False

    def test_counts_phases(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        # Complete phase
        p1 = _create_phase_dir(tmp_path, "01-setup")
        (p1 / "a-PLAN.md").write_text("plan")
        (p1 / "a-SUMMARY.md").write_text("summary")
        # Incomplete phase
        p2 = _create_phase_dir(tmp_path, "02-analysis")
        (p2 / "b-PLAN.md").write_text("plan")

        ctx = init_milestone_op(tmp_path)
        assert ctx["phase_count"] == 2
        assert ctx["completed_phases"] == 1
        assert ctx["all_phases_complete"] is False


# ─── init_map_theory ──────────────────────────────────────────────────────────


class TestInitMapTheory:
    def test_no_maps(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        ctx = init_map_theory(tmp_path)
        assert ctx["has_maps"] is False
        assert ctx["existing_maps"] == []

    def test_existing_maps(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        map_dir = tmp_path / ".gpd" / "research-map"
        map_dir.mkdir()
        (map_dir / "theory.md").write_text("# Theory Map")

        ctx = init_map_theory(tmp_path)
        assert ctx["has_maps"] is True
        assert "theory.md" in ctx["existing_maps"]


# ─── init_progress ────────────────────────────────────────────────────────────


class TestInitProgress:
    def test_empty_project(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        ctx = init_progress(tmp_path)
        assert ctx["phase_count"] == 0
        assert ctx["current_phase"] is None
        assert ctx["next_phase"] is None
        assert ctx["paused_at"] is None

    def test_phase_statuses(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        # Complete phase
        p1 = _create_phase_dir(tmp_path, "01-setup")
        (p1 / "a-PLAN.md").write_text("plan")
        (p1 / "a-SUMMARY.md").write_text("summary")
        # In-progress phase
        p2 = _create_phase_dir(tmp_path, "02-analysis")
        (p2 / "b-PLAN.md").write_text("plan")
        # Pending phase
        _create_phase_dir(tmp_path, "03-synthesis")

        ctx = init_progress(tmp_path)
        assert ctx["phase_count"] == 3
        assert ctx["completed_count"] == 1
        assert ctx["in_progress_count"] == 1
        assert ctx["current_phase"]["number"] in ("2", "02")
        assert ctx["next_phase"]["number"] in ("3", "03")

    def test_detects_paused_state(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        (tmp_path / ".gpd" / "STATE.md").write_text(
            "# State\n**Status:** Paused\n**Stopped at:** 2026-03-01T12:00:00Z"
        )

        ctx = init_progress(tmp_path)
        assert ctx["paused_at"] == "2026-03-01T12:00:00Z"

    def test_includes_project(self, tmp_path: Path) -> None:
        _setup_project(tmp_path)
        (tmp_path / ".gpd" / "PROJECT.md").write_text("# My Project")

        ctx = init_progress(tmp_path, includes={"project"})
        assert ctx["project_content"] == "# My Project"


# ─── _extract_frontmatter_field ──────────────────────────────────────────────


class TestExtractFrontmatterField:
    """Regression: \\s* in the field regex must not match newlines."""

    def test_empty_value_does_not_bleed_into_next_line(self, tmp_path: Path) -> None:
        """When a field has an empty value (e.g. 'title:\\n'), the regex must
        NOT consume the newline and capture the next line's content."""
        from gpd.core.context import _extract_frontmatter_field

        content = "title:\narea: numerical\ncreated: 2026-03-01"
        # 'title' has no value on its line → should return None
        assert _extract_frontmatter_field(content, "title") is None

    def test_field_with_value_still_works(self, tmp_path: Path) -> None:
        from gpd.core.context import _extract_frontmatter_field

        content = "title: Check convergence\narea: numerical"
        assert _extract_frontmatter_field(content, "title") == "Check convergence"
        assert _extract_frontmatter_field(content, "area") == "numerical"

    def test_field_with_leading_spaces(self, tmp_path: Path) -> None:
        from gpd.core.context import _extract_frontmatter_field

        content = "title:   spaced value  \narea: numerical"
        assert _extract_frontmatter_field(content, "title") == "spaced value"

    def test_field_with_quoted_value(self, tmp_path: Path) -> None:
        from gpd.core.context import _extract_frontmatter_field

        content = 'title: "Quoted Title"\narea: theory'
        assert _extract_frontmatter_field(content, "title") == "Quoted Title"
