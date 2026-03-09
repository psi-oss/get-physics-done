"""Tests for the GPD+ CLI entry point."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from gpd.mcp.cli import app
from gpd.version import __version__

runner = CliRunner()


def test_version_flag_outputs_version() -> None:
    """--version flag outputs GPD+ version string."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "GPD+" in result.output
    assert __version__ in result.output


def test_main_no_gpd_prints_error_and_exits_1(tmp_path: Path) -> None:
    """main with no GPD installed prints error and exits with code 1."""
    with (
        patch("gpd.mcp.cli.find_gpd_install", return_value=None),
        patch("gpd.mcp.cli.SESSIONS_DIR", tmp_path / "sessions"),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
        patch("gpd.mcp.cli.launch_claude_session", return_value=0),
    ):
        result = runner.invoke(app, [])
    assert result.exit_code == 1
    assert "GPD not found" in result.output


def test_main_with_gpd_displays_logo(mock_gpd_install: Path, tmp_path: Path) -> None:
    """main with GPD installed displays the ASCII logo and discovery summary."""
    with (
        patch("gpd.mcp.cli.find_gpd_install", return_value=mock_gpd_install),
        patch("gpd.mcp.cli.SESSIONS_DIR", tmp_path / "sessions"),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
        patch("gpd.mcp.cli.launch_claude_session", return_value=0),
    ):
        result = runner.invoke(app, [])
    assert result.exit_code == 0
    # Logo should contain the GPD+ block characters
    assert "GPD+" in result.output or "\u2588" in result.output
    # Discovery summary should show commands and agents count
    assert "commands" in result.output
    assert "agents" in result.output


def test_main_resume_with_no_sessions_exits_1(mock_gpd_install: Path, tmp_path: Path) -> None:
    """--resume with no sessions prints error and exits 1."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)
    with (
        patch("gpd.mcp.cli.find_gpd_install", return_value=mock_gpd_install),
        patch("gpd.mcp.cli.SESSIONS_DIR", sessions_dir),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
        patch("gpd.mcp.cli.launch_claude_session", return_value=0),
    ):
        result = runner.invoke(app, ["--resume"])
    assert result.exit_code == 1
    assert "No session found" in result.output


def test_main_resume_loads_latest_session(mock_gpd_install: Path, tmp_path: Path) -> None:
    """--resume loads the latest session and shows resume banner."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)

    from gpd.mcp.session.models import SessionState

    session = SessionState.new(session_id="resume001", project_name="test", session_name="my-session")
    (sessions_dir / "resume001.json").write_text(session.model_dump_json(indent=2))

    with (
        patch("gpd.mcp.cli.find_gpd_install", return_value=mock_gpd_install),
        patch("gpd.mcp.cli.SESSIONS_DIR", sessions_dir),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
        patch("gpd.mcp.cli.launch_claude_session", return_value=0),
    ):
        result = runner.invoke(app, ["--resume"])
    assert result.exit_code == 0
    assert "Resuming" in result.output
    assert "my-session" in result.output


def test_main_session_flag_loads_specific_session(mock_gpd_install: Path, tmp_path: Path) -> None:
    """--session flag loads a specific session by ID."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)

    from gpd.mcp.session.models import SessionState

    session = SessionState.new(session_id="specific01", project_name="test", session_name="specific-run")
    (sessions_dir / "specific01.json").write_text(session.model_dump_json(indent=2))

    with (
        patch("gpd.mcp.cli.find_gpd_install", return_value=mock_gpd_install),
        patch("gpd.mcp.cli.SESSIONS_DIR", sessions_dir),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
        patch("gpd.mcp.cli.launch_claude_session", return_value=0),
    ):
        result = runner.invoke(app, ["--session", "specific01"])
    assert result.exit_code == 0
    assert "Resuming" in result.output
    assert "specific-run" in result.output


def test_search_flag_calls_search(tmp_path: Path) -> None:
    """--search queries the index and displays results."""
    with (
        patch("gpd.mcp.cli.SESSIONS_DIR", tmp_path / "sessions"),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
    ):
        result = runner.invoke(app, ["--search", "quantum"])
    assert result.exit_code == 0
    # With empty index, should show "No sessions found"
    assert "No sessions found" in result.output


def test_history_flag_lists_sessions(tmp_path: Path) -> None:
    """--history lists sessions and calls display_history."""
    with (
        patch("gpd.mcp.cli.SESSIONS_DIR", tmp_path / "sessions"),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
    ):
        result = runner.invoke(app, ["--history"])
    assert result.exit_code == 0
    # With no sessions, should show "No sessions yet"
    assert "No sessions yet" in result.output


def test_fresh_launch_creates_new_session(mock_gpd_install: Path, tmp_path: Path) -> None:
    """Fresh launch (no flags) creates a new session JSON file."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)
    with (
        patch("gpd.mcp.cli.find_gpd_install", return_value=mock_gpd_install),
        patch("gpd.mcp.cli.SESSIONS_DIR", sessions_dir),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
        patch("gpd.mcp.cli.launch_claude_session", return_value=0),
    ):
        result = runner.invoke(app, [])
    assert result.exit_code == 0
    json_files = list(sessions_dir.glob("*.json"))
    assert len(json_files) == 1


def test_fresh_launch_shows_mcp_count(mock_gpd_install: Path, tmp_path: Path) -> None:
    """Fresh launch shows MCP count from cache."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)
    with (
        patch("gpd.mcp.cli.find_gpd_install", return_value=mock_gpd_install),
        patch("gpd.mcp.cli.SESSIONS_DIR", sessions_dir),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
        patch("gpd.mcp.cli.get_cached_mcp_count", return_value=5),
        patch("gpd.mcp.cli.launch_claude_session", return_value=0),
    ):
        result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "5 MCP tools available" in result.output


def test_reindex_subcommand(tmp_path: Path) -> None:
    """reindex subcommand calls rebuild_index and prints count."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)

    # Write a session JSON file so rebuild finds it
    from gpd.mcp.session.models import SessionState

    session = SessionState.new(session_id="idx001", project_name="test", session_name="indexed")
    (sessions_dir / "idx001.json").write_text(session.model_dump_json(indent=2))

    with (
        patch("gpd.mcp.cli.SESSIONS_DIR", sessions_dir),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
    ):
        result = runner.invoke(app, ["reindex"])
    assert result.exit_code == 0
    assert "1 sessions indexed" in result.output


def test_version_mismatch_shows_warning(mock_gpd_install: Path, tmp_path: Path) -> None:
    """Version mismatch produces a visible warning panel."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)
    with (
        patch("gpd.mcp.cli.find_gpd_install", return_value=mock_gpd_install),
        patch("gpd.mcp.cli.check_gpd_version", return_value=(False, "99.0.0")),
        patch("gpd.mcp.cli.SESSIONS_DIR", sessions_dir),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
        patch("gpd.mcp.cli.launch_claude_session", return_value=0),
    ):
        result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Version Warning" in result.output or "mismatch" in result.output
