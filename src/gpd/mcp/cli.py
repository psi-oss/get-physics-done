"""Session subcommand wiring for the unified GPD CLI."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import typer
from rich.console import Console
from rich.text import Text

import gpd
from gpd.mcp.config import DB_PATH, SESSIONS_DIR, ensure_dirs
from gpd.mcp.history import display_history, display_search_results
from gpd.mcp.launch import (
    build_session_card,
    get_cached_mcp_count,
    launch_session,
    refresh_mcp_count_background,
    show_full_logo,
    show_resume_banner,
    validate_resume,
)
from gpd.mcp.session import SearchIndex, SessionManager
from gpd.mcp.signal_handler import graceful_shutdown
from gpd.registry import list_agents, list_commands

session_app = typer.Typer(
    name="session",
    help="Launch an interactive GPD research session with MCP orchestration",
    no_args_is_help=False,
    add_completion=True,
)

console = Console()


def _content_counts() -> tuple[int, int]:
    """Return the number of bundled GPD commands and agents."""
    return len(list_commands()), len(list_agents())


def _raw_requested(ctx: typer.Context | None) -> bool:
    """Return whether the root CLI requested raw JSON output."""
    if ctx is None:
        return False
    root = ctx.find_root()
    return bool(root.params.get("raw", False))


def _print_json(payload: object) -> None:
    """Render a JSON payload to stdout."""
    console.print_json(json.dumps(payload, default=str))


def _print_error(message: str, *, raw_output: bool) -> None:
    """Render a session CLI error consistently."""
    if raw_output:
        _print_json({"error": message})
        return
    console.print(Text(message, style="bold red"))


def _launch_or_exit(session_manager: SessionManager, cwd: Path, *, raw_output: bool) -> None:
    """Launch the interactive session and propagate failures as CLI exits."""
    try:
        with graceful_shutdown(session_manager):
            exit_code = launch_session(cwd=cwd)
    except OSError as exc:
        session_manager.discard_active_session()
        _print_error(str(exc), raw_output=raw_output)
        raise typer.Exit(code=1) from None

    if exit_code == 0:
        session_manager.finalize("paused")
        return

    session_manager.finalize("interrupted")
    raise typer.Exit(code=exit_code)


def _resolve_working_directory(ctx: typer.Context) -> Path:
    """Resolve the requested working directory from the root CLI context."""
    root_params = ctx.parent.params if ctx.parent is not None else {}
    requested = root_params.get("cwd", ".")
    return Path(str(requested)).expanduser().resolve()


def _default_project_name(cwd: Path) -> str:
    """Use the working directory name as the session project label."""
    if cwd.name:
        return cwd.name
    return "default"


@session_app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    resume: bool = typer.Option(False, "--resume", "-r", help="Resume the latest session"),
    session_id: str = typer.Option("", "--session", "-s", help="Resume a specific session by ID"),
    search: str = typer.Option("", "--search", help="Search session history"),
    history: bool = typer.Option(False, "--history", help="Show session history"),
) -> None:
    """Launch or inspect GPD research sessions."""
    if ctx.invoked_subcommand is not None:
        return

    working_dir = _resolve_working_directory(ctx)
    project_name = _default_project_name(working_dir)
    raw_output = _raw_requested(ctx)
    ensure_dirs()
    search_index = SearchIndex(DB_PATH)
    session_manager = SessionManager(SESSIONS_DIR, search_index)

    try:
        if search:
            results = search_index.search(search)
            if raw_output:
                _print_json(results)
            else:
                display_search_results(console, results, search)
            raise typer.Exit()

        if history:
            sessions = session_manager.list_sessions()
            if raw_output:
                _print_json([session.model_dump(mode="json") for session in sessions])
            else:
                display_history(console, sessions)
            raise typer.Exit()

        command_count, agent_count = _content_counts()

        if resume or session_id:
            try:
                loaded = session_manager.load(session_id) if session_id else session_manager.get_latest_session(project_name)
            except FileNotFoundError:
                _print_error(f"No session found with ID '{session_id}'.", raw_output=raw_output)
                raise typer.Exit(code=1) from None
            except ValueError as exc:
                _print_error(str(exc), raw_output=raw_output)
                raise typer.Exit(code=1) from None
            if loaded is None:
                _print_error(f"No session found to resume for project '{project_name}'.", raw_output=raw_output)
                raise typer.Exit(code=1)

            session_manager.activate(loaded)

            warnings = validate_resume(loaded)
            if not raw_output:
                for warning in warnings:
                    console.print(Text(f"  Warning: {warning}", style="yellow"))

            loaded.status = "active"
            if not raw_output:
                show_resume_banner(console, gpd.__version__, loaded.session_name)
                console.print(f"  Loaded {command_count} commands and {agent_count} agents", style="dim")
            _launch_or_exit(session_manager, working_dir, raw_output=raw_output)
            return

        mcp_count = get_cached_mcp_count()
        refresh_mcp_count_background()

        latest = session_manager.get_latest_session(project_name)
        session_summary = build_session_card(latest) if latest else None

        if not raw_output:
            show_full_logo(console, gpd.__version__, mcp_count, session_summary)
            console.print(f"  {command_count} built-in commands and {agent_count} agents ready", style="dim")

        session_manager.create(
            project_name=project_name,
            session_name=f"session-{datetime.now().strftime('%Y%m%d-%H%M')}",
            persist=False,
        )
        _launch_or_exit(session_manager, working_dir, raw_output=raw_output)
    finally:
        search_index.close()


@session_app.command("reindex")
def reindex(ctx: typer.Context) -> None:
    """Rebuild the FTS5 search index from session JSON files."""
    ensure_dirs()
    raw_output = _raw_requested(ctx)
    search_index = SearchIndex(DB_PATH)
    try:
        count = search_index.rebuild_index(SESSIONS_DIR)
        if raw_output:
            _print_json({"count": count})
        else:
            console.print(f"Rebuilt search index: {count} sessions indexed")
    finally:
        search_index.close()
