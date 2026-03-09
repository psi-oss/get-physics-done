"""Tests for the integrated session CLI exposed through gpd."""

from __future__ import annotations

import json
import time
from pathlib import Path
from unittest.mock import patch

from typer.testing import CliRunner

from gpd.cli import app

runner = CliRunner()


def _strip_ansi(text: str) -> str:
    """Remove ANSI escape codes from text."""
    import re

    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def test_session_help_is_exposed_from_main_cli() -> None:
    """The unified gpd CLI should expose the session subcommand."""
    result = runner.invoke(app, ["session", "--help"])
    assert result.exit_code == 0
    plain = _strip_ansi(result.output)
    assert "--resume" in plain
    assert "--history" in plain
    assert "reindex" in plain


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

    session = SessionState.new(
        session_id="resume001",
        project_name="get-physics-done",
        project_root=str(Path.cwd().resolve()),
        session_name="my-session",
    )
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


def test_session_resume_uses_latest_session_for_current_project(tmp_path: Path) -> None:
    """gpd session --resume should scope the implicit selection to the current project."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)
    project_dir = tmp_path / "project-alpha"
    project_dir.mkdir()

    from gpd.mcp.session.models import SessionState

    alpha = SessionState.new(
        session_id="alpha001",
        project_name="project-alpha",
        project_root=str(project_dir),
        session_name="alpha-run",
    )
    beta = SessionState.new(
        session_id="beta001",
        project_name="project-beta",
        project_root=str(tmp_path / "project-beta"),
        session_name="beta-run",
    )
    (sessions_dir / "alpha001.json").write_text(alpha.model_dump_json(indent=2), encoding="utf-8")
    time.sleep(0.05)
    (sessions_dir / "beta001.json").write_text(beta.model_dump_json(indent=2), encoding="utf-8")

    with (
        patch("gpd.mcp.cli.SESSIONS_DIR", sessions_dir),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
        patch("gpd.mcp.cli.list_commands", return_value=["cmd-a"]),
        patch("gpd.mcp.cli.list_agents", return_value=["agent-a"]),
        patch("gpd.mcp.cli.launch_session", return_value=0),
    ):
        result = runner.invoke(app, ["--cwd", str(project_dir), "session", "--resume"])
    assert result.exit_code == 0
    assert "alpha-run" in result.output
    assert "beta-run" not in result.output


def test_session_flag_loads_specific_session(tmp_path: Path) -> None:
    """gpd session --session should load a specific session by ID."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)

    from gpd.mcp.session.models import SessionState

    session = SessionState.new(
        session_id="specific01",
        project_name="test",
        project_root=str(tmp_path / "project"),
        session_name="specific-run",
    )
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


def test_session_flag_with_corrupt_file_exits_cleanly(tmp_path: Path) -> None:
    """gpd session --session should report corrupt session files without crashing."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)
    (sessions_dir / "broken01.json").write_text("{not-valid-json", encoding="utf-8")

    with (
        patch("gpd.mcp.cli.SESSIONS_DIR", sessions_dir),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
    ):
        result = runner.invoke(app, ["session", "--session", "broken01"])
    assert result.exit_code == 1
    assert "corrupt" in result.output.lower()


def test_session_search_flag_queries_history(tmp_path: Path) -> None:
    """gpd session --search should query the session index."""
    with (
        patch("gpd.mcp.cli.SESSIONS_DIR", tmp_path / "sessions"),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
    ):
        result = runner.invoke(app, ["session", "--search", "quantum"])
    assert result.exit_code == 0
    assert "No sessions found" in result.output


def test_session_search_flag_honors_raw_output(tmp_path: Path) -> None:
    """gpd --raw session --search should emit JSON."""
    with (
        patch("gpd.mcp.cli.SESSIONS_DIR", tmp_path / "sessions"),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
    ):
        result = runner.invoke(app, ["--raw", "session", "--search", "quantum"])
    assert result.exit_code == 0
    assert json.loads(result.output) == []


def test_session_history_flag_lists_sessions(tmp_path: Path) -> None:
    """gpd session --history should render history even when empty."""
    with (
        patch("gpd.mcp.cli.SESSIONS_DIR", tmp_path / "sessions"),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
    ):
        result = runner.invoke(app, ["session", "--history"])
    assert result.exit_code == 0
    assert "No sessions yet" in result.output


def test_session_history_flag_honors_raw_output(tmp_path: Path) -> None:
    """gpd --raw session --history should emit JSON."""
    with (
        patch("gpd.mcp.cli.SESSIONS_DIR", tmp_path / "sessions"),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
    ):
        result = runner.invoke(app, ["--raw", "session", "--history"])
    assert result.exit_code == 0
    assert json.loads(result.output) == []


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
    assert session.project_root == str(project_dir.resolve())
    assert session.status == "completed"


def test_session_fresh_launch_uses_current_project_for_startup_summary(tmp_path: Path) -> None:
    """Fresh session startup should show the most recent session for the current project only."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)
    project_dir = tmp_path / "project-alpha"
    project_dir.mkdir()

    from gpd.mcp.session.models import SessionState

    alpha = SessionState.new(
        session_id="alpha001",
        project_name="project-alpha",
        project_root=str(project_dir),
        session_name="alpha-run",
    )
    beta = SessionState.new(
        session_id="beta001",
        project_name="project-beta",
        project_root=str(tmp_path / "project-beta"),
        session_name="beta-run",
    )
    (sessions_dir / "alpha001.json").write_text(alpha.model_dump_json(indent=2), encoding="utf-8")
    time.sleep(0.05)
    (sessions_dir / "beta001.json").write_text(beta.model_dump_json(indent=2), encoding="utf-8")

    with (
        patch("gpd.mcp.cli.SESSIONS_DIR", sessions_dir),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
        patch("gpd.mcp.cli.list_commands", return_value=["cmd-a"]),
        patch("gpd.mcp.cli.list_agents", return_value=["agent-a"]),
        patch("gpd.mcp.cli.get_cached_mcp_count", return_value=5),
        patch("gpd.mcp.cli.refresh_mcp_count_background", return_value=None),
        patch("gpd.mcp.cli.build_session_card", side_effect=lambda session: f"summary:{session.session_name}") as build_card,
        patch("gpd.mcp.cli.show_full_logo") as show_full_logo,
        patch("gpd.mcp.cli.launch_session", return_value=0),
    ):
        result = runner.invoke(app, ["--cwd", str(project_dir), "session"])
    assert result.exit_code == 0
    assert build_card.call_args is not None
    assert build_card.call_args.args[0].session_name == "alpha-run"
    assert show_full_logo.call_args is not None
    assert show_full_logo.call_args.args[3] == "summary:alpha-run"


def test_session_fresh_launch_does_not_persist_when_launch_fails(tmp_path: Path) -> None:
    """Fresh session metadata should not be written before launch succeeds."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)
    project_dir = tmp_path / "project-alpha"
    project_dir.mkdir()

    with (
        patch("gpd.mcp.cli.SESSIONS_DIR", sessions_dir),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
        patch("gpd.mcp.cli.list_commands", return_value=["cmd-a"]),
        patch("gpd.mcp.cli.list_agents", return_value=["agent-a"]),
        patch("gpd.mcp.cli.get_cached_mcp_count", return_value=5),
        patch("gpd.mcp.cli.refresh_mcp_count_background", return_value=None),
        patch("gpd.mcp.cli.launch_session", side_effect=FileNotFoundError("missing claude")),
    ):
        result = runner.invoke(app, ["--cwd", str(project_dir), "session"])
    assert result.exit_code == 1
    assert "missing claude" in result.output
    assert list(sessions_dir.glob("*.json")) == []


def test_session_resume_launch_failure_does_not_mutate_persisted_status(tmp_path: Path) -> None:
    """Resume should not rewrite persisted session state before launch succeeds."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)
    project_dir = tmp_path / "project-alpha"
    project_dir.mkdir()

    from gpd.mcp.session.models import SessionState

    session = SessionState.new(
        session_id="resume001",
        project_name="project-alpha",
        project_root=str(project_dir),
        session_name="my-session",
    )
    session.status = "paused"
    session_path = sessions_dir / "resume001.json"
    session_path.write_text(session.model_dump_json(indent=2), encoding="utf-8")

    with (
        patch("gpd.mcp.cli.SESSIONS_DIR", sessions_dir),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
        patch("gpd.mcp.cli.list_commands", return_value=["cmd-a"]),
        patch("gpd.mcp.cli.list_agents", return_value=["agent-a"]),
        patch("gpd.mcp.cli.launch_session", side_effect=FileNotFoundError("missing claude")),
    ):
        result = runner.invoke(app, ["--cwd", str(project_dir), "session", "--resume"])
    assert result.exit_code == 1
    assert SessionState.model_validate_json(session_path.read_text(encoding="utf-8")).status == "paused"


def test_session_reindex_subcommand(tmp_path: Path) -> None:
    """gpd session reindex should rebuild the stored session index."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)

    from gpd.mcp.session.models import SessionState

    session = SessionState.new(
        session_id="idx001",
        project_name="test",
        project_root=str(tmp_path / "project"),
        session_name="indexed",
    )
    (sessions_dir / "idx001.json").write_text(session.model_dump_json(indent=2), encoding="utf-8")

    with (
        patch("gpd.mcp.cli.SESSIONS_DIR", sessions_dir),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
    ):
        result = runner.invoke(app, ["session", "reindex"])
    assert result.exit_code == 0
    assert "1 sessions indexed" in result.output


def test_session_reindex_subcommand_honors_raw_output(tmp_path: Path) -> None:
    """gpd --raw session reindex should emit JSON."""
    sessions_dir = tmp_path / "sessions"
    sessions_dir.mkdir(parents=True)

    from gpd.mcp.session.models import SessionState

    session = SessionState.new(
        session_id="idx001",
        project_name="test",
        project_root=str(tmp_path / "project"),
        session_name="indexed",
    )
    (sessions_dir / "idx001.json").write_text(session.model_dump_json(indent=2), encoding="utf-8")

    with (
        patch("gpd.mcp.cli.SESSIONS_DIR", sessions_dir),
        patch("gpd.mcp.cli.DB_PATH", tmp_path / "search.db"),
    ):
        result = runner.invoke(app, ["--raw", "session", "reindex"])
    assert result.exit_code == 0
    assert json.loads(result.output) == {"count": 1}
