"""Typer CLI application for GPD+."""

from __future__ import annotations

from datetime import datetime

import typer
from rich.console import Console
from rich.panel import Panel

import gpd
from gpd.mcp.config import DB_PATH, SESSIONS_DIR, ensure_dirs
from gpd.mcp.gpd_bridge.discovery import discover_agents, discover_commands, find_gpd_install
from gpd.mcp.gpd_bridge.version import GPD_REQUIRED_VERSION, check_gpd_version, format_version_warning
from gpd.mcp.history import display_history, display_search_results
from gpd.mcp.launch import (
    build_session_card,
    get_cached_mcp_count,
    launch_claude_session,
    refresh_mcp_count_background,
    show_full_logo,
    show_resume_banner,
    validate_resume,
)
from gpd.mcp.pipeline import app as pipeline_app
from gpd.mcp.session import SearchIndex, SessionManager
from gpd.mcp.signal_handler import graceful_shutdown
from gpd.mcp.viewer.cli import viewer_app

app = typer.Typer(
    name="gpd+",
    help="GPD+ -- Physics research orchestrator with MCP tools",
    no_args_is_help=False,
    add_completion=True,
)

# Register pipeline subcommands (discover, plan, execute, paper, compile)
app.add_typer(pipeline_app, name="pipeline", help="Research pipeline stages")

# Register viewer subcommand (gpd+ view)
app.add_typer(viewer_app, name="view", help="MCP simulation frame viewer")

console = Console()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    resume: bool = typer.Option(False, "--resume", "-r", help="Resume last session"),
    session: str = typer.Option("", "--session", "-s", help="Resume specific session by ID"),
    search: str = typer.Option("", "--search", help="Search session history"),
    history: bool = typer.Option(False, "--history", help="Show session history"),
    version: bool = typer.Option(False, "--version", "-v", help="Show version"),
) -> None:
    """Launch GPD+ research session."""
    if ctx.invoked_subcommand is not None:
        return

    if version:
        _show_version()
        raise typer.Exit()

    # Ensure .gpdplus/ directory structure exists
    ensure_dirs()

    # Initialize search index and session manager
    search_index = SearchIndex(DB_PATH)
    session_manager = SessionManager(SESSIONS_DIR, search_index)

    try:
        # --search: query FTS5 index and display results
        if search:
            results = search_index.search(search)
            display_search_results(console, results, search)
            raise typer.Exit()

        # --history: list sessions and display project-grouped timeline
        if history:
            sessions = session_manager.list_sessions()
            display_history(console, sessions)
            raise typer.Exit()

        # Discover GPD installation (required — GPD+ extends GPD)
        gpd_dir = find_gpd_install()
        if gpd_dir is None:
            console.print(
                "[bold red]GPD not found.[/] Install GPD first: https://github.com/anthropics/get-physics-done",
                highlight=False,
            )
            raise typer.Exit(code=1)

        commands: list[object] = []
        agents: list[object] = []
        installed_version = "not installed"

        if gpd_dir is not None:
            is_compatible, installed_version = check_gpd_version(gpd_dir)
            if not is_compatible:
                warning_text = format_version_warning(installed_version, GPD_REQUIRED_VERSION)
                console.print(Panel(warning_text, title="Version Warning", border_style="yellow"))
            commands = discover_commands(gpd_dir)
            agents = discover_agents(gpd_dir)

        # --resume or --session: load and validate existing session
        if resume or session:
            if session:
                loaded = session_manager.load(session)
            else:
                loaded = session_manager.get_latest_session()

            if loaded is None:
                console.print("[bold red]No session found to resume.[/]")
                raise typer.Exit(code=1)

            # If loaded from get_latest_session, set as active
            if not session:
                session_manager._active_session = loaded

            warnings = validate_resume(loaded, console)
            for warning in warnings:
                console.print(f"  [yellow]Warning:[/] {warning}")

            show_resume_banner(console, gpd.__version__, loaded.session_name)
            loaded.status = "active"
            session_manager.save(loaded)

            if gpd_dir is not None:
                console.print(
                    f"  Found {len(commands)} commands, {len(agents)} agents from GPD v{installed_version}",
                    style="dim",
                )

            # Launch interactive Claude Code session
            with graceful_shutdown(session_manager):
                try:
                    launch_claude_session()
                except FileNotFoundError as exc:
                    console.print(f"[bold red]{exc}[/]")
                    raise typer.Exit(code=1) from None

        # Fresh launch: no flags
        else:
            mcp_count = get_cached_mcp_count()
            refresh_mcp_count_background()

            # Get last session summary card
            latest = session_manager.get_latest_session()
            session_summary = build_session_card(latest) if latest else None

            show_full_logo(console, gpd.__version__, mcp_count, session_summary)

            if gpd_dir is not None:
                console.print(
                    f"  Found {len(commands)} commands, {len(agents)} agents from GPD v{installed_version}",
                    style="dim",
                )

            # Create new session
            session_manager.create(
                project_name="default",
                session_name=f"session-{datetime.now().strftime('%Y%m%d-%H%M')}",
            )

            # Launch interactive Claude Code session
            with graceful_shutdown(session_manager):
                try:
                    launch_claude_session()
                except FileNotFoundError as exc:
                    console.print(f"[bold red]{exc}[/]")
                    raise typer.Exit(code=1) from None

    finally:
        search_index.close()


@app.command()
def reindex() -> None:
    """Rebuild the FTS5 search index from session JSON files."""
    ensure_dirs()
    search_index = SearchIndex(DB_PATH)
    try:
        count = search_index.rebuild_index(SESSIONS_DIR)
        console.print(f"Rebuilt search index: {count} sessions indexed")
    finally:
        search_index.close()


def _show_version() -> None:
    """Print GPD+ and GPD version information."""
    console.print(f"GPD+ v{gpd.__version__}")
    gpd_dir = find_gpd_install()
    if gpd_dir is not None:
        _, installed_version = check_gpd_version(gpd_dir)
        console.print(f"GPD  v{installed_version}")
    else:
        console.print("GPD  not installed")
