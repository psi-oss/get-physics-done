"""Session subcommand wiring for the unified GPD CLI."""

from __future__ import annotations

from datetime import datetime

import typer
from rich.console import Console

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


def _launch_or_exit(session_manager: SessionManager) -> None:
    """Launch the interactive session and propagate failures as CLI exits."""
    with graceful_shutdown(session_manager):
        try:
            exit_code = launch_session()
        except FileNotFoundError as exc:
            console.print(f"[bold red]{exc}[/]")
            raise typer.Exit(code=1) from None

    if exit_code:
        raise typer.Exit(code=exit_code)


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

    ensure_dirs()
    search_index = SearchIndex(DB_PATH)
    session_manager = SessionManager(SESSIONS_DIR, search_index)

    try:
        if search:
            results = search_index.search(search)
            display_search_results(console, results, search)
            raise typer.Exit()

        if history:
            sessions = session_manager.list_sessions()
            display_history(console, sessions)
            raise typer.Exit()

        command_count, agent_count = _content_counts()

        if resume or session_id:
            loaded = session_manager.load(session_id) if session_id else session_manager.get_latest_session()
            if loaded is None:
                console.print("[bold red]No session found to resume.[/]")
                raise typer.Exit(code=1)

            if not session_id:
                session_manager._active_session = loaded

            warnings = validate_resume(loaded, console)
            for warning in warnings:
                console.print(f"  [yellow]Warning:[/] {warning}")

            show_resume_banner(console, gpd.__version__, loaded.session_name)
            loaded.status = "active"
            session_manager.save(loaded)
            console.print(f"  Loaded {command_count} commands and {agent_count} agents", style="dim")
            _launch_or_exit(session_manager)
            return

        mcp_count = get_cached_mcp_count()
        refresh_mcp_count_background()

        latest = session_manager.get_latest_session()
        session_summary = build_session_card(latest) if latest else None

        show_full_logo(console, gpd.__version__, mcp_count, session_summary)
        console.print(f"  {command_count} built-in commands and {agent_count} agents ready", style="dim")

        session_manager.create(
            project_name="default",
            session_name=f"session-{datetime.now().strftime('%Y%m%d-%H%M')}",
        )
        _launch_or_exit(session_manager)
    finally:
        search_index.close()


@session_app.command("reindex")
def reindex() -> None:
    """Rebuild the FTS5 search index from session JSON files."""
    ensure_dirs()
    search_index = SearchIndex(DB_PATH)
    try:
        count = search_index.rebuild_index(SESSIONS_DIR)
        console.print(f"Rebuilt search index: {count} sessions indexed")
    finally:
        search_index.close()
