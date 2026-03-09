"""Tests for the integrated session CLI exposed through gpd."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from gpd.cli import app

runner = CliRunner()


def test_session_help_is_exposed_from_main_cli() -> None:
    """The unified gpd CLI should expose the session subcommand."""
    result = runner.invoke(app, ["session", "--help"])
    assert result.exit_code == 0
    assert "--resume" in result.output
    assert "--history" in result.output
    assert "reindex" in result.output


def test_session_resume_with_no_sessions_exits_1(tmp_path: Path) -> None:
    """gpd session --resume should fail cleanly when no sessions exist."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)
    with (
        patch("gpd.mcp.cli.SESSIONS_DIR", sessions_dir),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
        patch("gpd.mcp.cli.list_commands", return_value=["cmd-a", "cmd-b"]),
        patch("gpd.mcp.cli.list_agents", return_value=["agent-a"]),
    ):
        result = runner.invoke(app, ["session", "--resume"])
    assert result.exit_code == 1
    assert "No session found" in result.output


def test_session_resume_loads_latest_session(tmp_path: Path) -> None:
    """gpd session --resume should load the latest saved session."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)

    from gpd.mcp.session.models import SessionState

    session = SessionState.new(session_id="resume001", project_name="test", session_name="my-session")
    (sessions_dir / "resume001.json").write_text(session.model_dump_json(indent=2), encoding="utf-8")

    with (
        patch("gpd.mcp.cli.SESSIONS_DIR", sessions_dir),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
        patch("gpd.mcp.cli.list_commands", return_value=["cmd-a", "cmd-b", "cmd-c"]),
        patch("gpd.mcp.cli.list_agents", return_value=["agent-a", "agent-b"]),
        patch("gpd.mcp.cli.launch_session", return_value=0),
    ):
        result = runner.invoke(app, ["session", "--resume"])
    assert result.exit_code == 0
    assert "Resuming" in result.output
    assert "my-session" in result.output
    assert "Loaded 3 commands and 2 agents" in result.output


def test_session_flag_loads_specific_session(tmp_path: Path) -> None:
    """gpd session --session should load a specific session by ID."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)

    from gpd.mcp.session.models import SessionState

    session = SessionState.new(session_id="specific01", project_name="test", session_name="specific-run")
    (sessions_dir / "specific01.json").write_text(session.model_dump_json(indent=2), encoding="utf-8")

    with (
        patch("gpd.mcp.cli.SESSIONS_DIR", sessions_dir),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
        patch("gpd.mcp.cli.list_commands", return_value=["cmd-a"]),
        patch("gpd.mcp.cli.list_agents", return_value=["agent-a"]),
        patch("gpd.mcp.cli.launch_session", return_value=0),
    ):
        result = runner.invoke(app, ["session", "--session", "specific01"])
    assert result.exit_code == 0
    assert "Resuming" in result.output
    assert "specific-run" in result.output


def test_session_flag_missing_id_exits_cleanly(tmp_path: Path) -> None:
    """gpd session --session should fail cleanly for a missing session ID."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)

    with (
        patch("gpd.mcp.cli.SESSIONS_DIR", sessions_dir),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
    ):
        result = runner.invoke(app, ["session", "--session", "missing-id"])
    assert result.exit_code == 1
    assert "No session found with ID 'missing-id'" in result.output


def test_session_search_flag_queries_history(tmp_path: Path) -> None:
    """gpd session --search should query the session index."""
    with (
        patch("gpd.mcp.cli.SESSIONS_DIR", tmp_path / "sessions"),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
    ):
        result = runner.invoke(app, ["session", "--search", "quantum"])
    assert result.exit_code == 0
    assert "No sessions found" in result.output


def test_session_history_flag_lists_sessions(tmp_path: Path) -> None:
    """gpd session --history should render history even when empty."""
    with (
        patch("gpd.mcp.cli.SESSIONS_DIR", tmp_path / "sessions"),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
    ):
        result = runner.invoke(app, ["session", "--history"])
    assert result.exit_code == 0
    assert "No sessions yet" in result.output


def test_session_fresh_launch_creates_new_session(tmp_path: Path) -> None:
    """gpd session should create a new session without any separate entrypoint."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)
    project_dir = tmp_path / "project-alpha"
    project_dir.mkdir()
    with (
        patch("gpd.mcp.cli.SESSIONS_DIR", sessions_dir),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
        patch("gpd.mcp.cli.list_commands", return_value=["cmd-a", "cmd-b", "cmd-c"]),
        patch("gpd.mcp.cli.list_agents", return_value=["agent-a", "agent-b"]),
        patch("gpd.mcp.cli.get_cached_mcp_count", return_value=5),
        patch("gpd.mcp.cli.refresh_mcp_count_background", return_value=None),
        patch("gpd.mcp.cli.launch_session", return_value=0) as launch_session,
    ):
        result = runner.invoke(app, ["--cwd", str(project_dir), "session"])
    assert result.exit_code == 0
    assert len(list(sessions_dir.glob("*.json"))) == 1
    assert "GPD v" in result.output or "█" in result.output
    assert "5 MCP tools available" in result.output
    assert "3 built-in commands and 2 agents ready" in result.output
    launch_session.assert_called_once_with(cwd=project_dir.resolve())

    from gpd.mcp.session.models import SessionState

    session_file = next(sessions_dir.glob("*.json"))
    session = SessionState.model_validate_json(session_file.read_text(encoding="utf-8"))
    assert session.project_name == "project-alpha"


def test_session_reindex_subcommand(tmp_path: Path) -> None:
    """gpd session reindex should rebuild the stored session index."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)

    from gpd.mcp.session.models import SessionState

    session = SessionState.new(session_id="idx001", project_name="test", session_name="indexed")
    (sessions_dir / "idx001.json").write_text(session.model_dump_json(indent=2), encoding="utf-8")

    with (
        patch("gpd.mcp.cli.SESSIONS_DIR", sessions_dir),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
    ):
        result = runner.invoke(app, ["session", "reindex"])
    assert result.exit_code == 0
    assert "1 sessions indexed" in result.output
