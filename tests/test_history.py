"""Tests for session search display, history UI, and launch helpers."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from rich.console import Console

from gpd.mcp.history import display_history, display_search_results, format_elapsed
from gpd.mcp.launch import (
    build_session_card,
    get_cached_mcp_count,
    validate_resume,
)
from gpd.mcp.session.models import MilestoneState, SessionState


def _make_session(
    session_id: str = "test001",
    project_name: str = "physics",
    session_name: str = "session-1",
    status: str = "active",
    elapsed_seconds: float = 0.0,
) -> SessionState:
    """Create a test session with specified fields."""
    session = SessionState.new(
        session_id=session_id,
        project_name=project_name,
        session_name=session_name,
    )
    session.status = status
    session.elapsed_seconds = elapsed_seconds
    return session


class TestFormatElapsed:
    """Tests for format_elapsed time formatting."""

    def test_seconds(self) -> None:
        assert format_elapsed(45) == "45s"

    def test_minutes(self) -> None:
        assert format_elapsed(60) == "1m"
        assert format_elapsed(125) == "2m"

    def test_hours_and_minutes(self) -> None:
        assert format_elapsed(3661) == "1h 1m"
        assert format_elapsed(7200) == "2h 0m"

    def test_days_and_hours(self) -> None:
        assert format_elapsed(90000) == "1d 1h"

    def test_zero(self) -> None:
        assert format_elapsed(0) == "0s"


class TestDisplaySearchResults:
    """Tests for search results rendering."""

    def test_empty_results_prints_no_sessions(self) -> None:
        console = Console(record=True, width=80)
        display_search_results(console, [], "quantum")
        output = console.export_text()
        assert "No sessions found for 'quantum'" in output

    def test_results_render_panels(self) -> None:
        console = Console(record=True, width=80)
        results = [
            {
                "session_id": "abc",
                "project_name": "quantum-gravity",
                "session_name": "run-1",
                "context_snippet": "found graviton emission pattern",
                "rank": -1.5,
            },
        ]
        display_search_results(console, results, "graviton")
        output = console.export_text()
        assert "Search results for 'graviton'" in output
        assert "1 matches" in output
        assert "quantum-gravity" in output

    def test_multiple_results_all_shown(self) -> None:
        console = Console(record=True, width=80)
        results = [
            {
                "session_id": f"id{i}",
                "project_name": f"proj-{i}",
                "session_name": f"sess-{i}",
                "context_snippet": f"snippet {i}",
                "rank": float(-i),
            }
            for i in range(3)
        ]
        display_search_results(console, results, "snippet")
        output = console.export_text()
        assert "3 matches" in output

    def test_query_with_rich_markup_is_rendered_literally(self) -> None:
        console = Console(record=True, width=80)
        display_search_results(console, [], "[quantum]")
        output = console.export_text()
        assert "[quantum]" in output


class TestDisplayHistory:
    """Tests for history display with project grouping."""

    def test_groups_by_project(self) -> None:
        console = Console(record=True, width=80)
        sessions = [
            _make_session(
                session_id="a1",
                project_name="project-alpha",
                session_name="run-1",
                status="completed",
                elapsed_seconds=3600,
            ),
            _make_session(
                session_id="b1",
                project_name="project-beta",
                session_name="run-2",
                status="active",
                elapsed_seconds=120,
            ),
        ]
        display_history(console, sessions, group_by_project=True)
        output = console.export_text()
        assert "project-alpha" in output
        assert "project-beta" in output

    def test_timeline_markers(self) -> None:
        console = Console(record=True, width=80)
        sessions = [
            _make_session(session_id="c1", status="completed"),
            _make_session(session_id="c2", status="active"),
            _make_session(session_id="c3", status="paused"),
            _make_session(session_id="c4", status="interrupted"),
        ]
        display_history(console, sessions, group_by_project=True)
        output = console.export_text()
        assert "o  session-1" in output  # completed
        assert ">  session-1" in output  # active
        assert "||  session-1" in output  # paused
        assert "x  session-1" in output  # interrupted

    def test_no_sessions_prints_message(self) -> None:
        console = Console(record=True, width=80)
        display_history(console, [])
        output = console.export_text()
        assert "No sessions yet" in output

    def test_ungrouped_reverse_chronological(self) -> None:
        console = Console(record=True, width=80)
        s1 = _make_session(session_id="e1", session_name="first")
        s2 = _make_session(session_id="e2", session_name="second")
        # Ensure s2 has a later timestamp
        from datetime import timedelta

        s2.created_at = s1.created_at + timedelta(hours=1)
        display_history(console, [s1, s2], group_by_project=False)
        output = console.export_text()
        lines = [line for line in output.split("\n") if line.strip()]
        # Most recent (second) should come before first
        second_idx = next(i for i, line in enumerate(lines) if "second" in line)
        first_idx = next(i for i, line in enumerate(lines) if "first" in line)
        assert second_idx < first_idx

    def test_project_names_with_markup_are_rendered_literally(self) -> None:
        console = Console(record=True, width=80)
        sessions = [_make_session(project_name="[project-alpha]", session_name="run-1")]

        display_history(console, sessions, group_by_project=True)

        output = console.export_text()
        assert "[project-alpha]" in output


class TestGetCachedMcpCount:
    """Tests for MCP count cache reading."""

    def test_returns_zero_no_cache_file(self, tmp_path: Path, monkeypatch: object) -> None:
        import gpd.mcp.discovery.sources as sources_mod
        import gpd.mcp.launch as launch_mod

        monkeypatch.setattr(launch_mod, "CACHE_DIR", tmp_path / "nonexistent")
        # Prevent synchronous discovery fallback from finding real tools
        monkeypatch.setattr(sources_mod, "load_sources_config", lambda: (_ for _ in ()).throw(OSError("mocked")))
        assert get_cached_mcp_count() == 0

    def test_reads_valid_cache(self, tmp_path: Path, monkeypatch: object) -> None:
        import gpd.mcp.launch as launch_mod

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "mcp_count.json").write_text(json.dumps({"count": 42}))
        monkeypatch.setattr(launch_mod, "CACHE_DIR", cache_dir)
        assert get_cached_mcp_count() == 42

    def test_returns_zero_on_corrupt_cache(self, tmp_path: Path, monkeypatch: object) -> None:
        import gpd.mcp.launch as launch_mod

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        (cache_dir / "mcp_count.json").write_text("not json!")
        monkeypatch.setattr(launch_mod, "CACHE_DIR", cache_dir)
        assert get_cached_mcp_count() == 0


class TestBuildSessionCard:
    """Tests for session card formatting."""

    def test_no_milestones(self) -> None:
        session = _make_session(elapsed_seconds=120)
        card = build_session_card(session)
        assert "No milestones yet" in card
        assert "session-1" in card
        assert "2m" in card

    def test_with_milestones(self) -> None:
        session = _make_session(elapsed_seconds=7200)
        session.milestones = [
            MilestoneState(name="setup", status="complete"),
            MilestoneState(name="data-collection", status="complete"),
            MilestoneState(name="analysis", status="in_progress"),
            MilestoneState(name="report", status="pending"),
        ]
        card = build_session_card(session)
        assert "50%" in card
        assert "2/4 milestones" in card


class TestValidateResume:
    """Tests for resume validation."""

    def test_healthy_session_returns_empty(self) -> None:
        session = _make_session()
        warnings = validate_resume(session)
        assert warnings == []

    def test_session_with_errors_warns(self) -> None:
        session = _make_session()
        session.error_messages.append("Something failed")
        warnings = validate_resume(session)
        assert len(warnings) == 1
        assert "error" in warnings[0].lower()

    def test_session_with_missing_mcp_tools_warns(self) -> None:
        session = _make_session()
        session.mcp_tools_used.extend(["openfoam", "lammps"])

        with patch("gpd.utils.mcp_registry.get_available_mcps", return_value={"lammps": {"description": "ok"}}):
            warnings = validate_resume(session)

        assert len(warnings) == 1
        assert "openfoam" in warnings[0]
