"""Session search display and history UI for GPD."""

from __future__ import annotations

import re

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from gpd.mcp.session.models import SessionState

_QUERY_TOKEN_RE = re.compile(r"\w+", re.UNICODE)
_FTS_OPERATOR_TOKENS = {"AND", "OR", "NOT", "NEAR"}


def format_elapsed(seconds: float) -> str:
    """Convert elapsed_seconds to human-readable format.

    <60s: "Ns", <3600: "Nm", <86400: "Nh Mm", else "Nd Nh".
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds // 60)}m"
    if seconds < 86400:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"
    days = int(seconds // 86400)
    hours = int((seconds % 86400) // 3600)
    return f"{days}d {hours}h"


def display_search_results(
    console: Console,
    results: list[dict[str, object]],
    query: str,
) -> None:
    """Display search results with highlighted query snippets.

    If no results, prints a dim "No sessions found" message.
    Otherwise renders a panel per result with session info and
    context snippet with the query term highlighted in bold yellow.
    """
    if not results:
        console.print(Text(f"No sessions found for '{query}'", style="dim"))
        return

    console.print(Text(f"Search results for '{query}' ({len(results)} matches)", style="bold"))
    console.print()

    highlight_terms = _query_terms(query)
    for result in results:
        session_name = result.get("session_name", "")
        project_name = result.get("project_name", "")
        snippet = str(result.get("context_snippet", ""))

        highlighted = Text(snippet)
        snippet_lower = snippet.lower()
        for term in highlight_terms:
            start = 0
            term_lower = term.lower()
            while True:
                idx = snippet_lower.find(term_lower, start)
                if idx == -1:
                    break
                highlighted.stylize("bold yellow", idx, idx + len(term))
                start = idx + len(term)

        body = Text()
        body.append(f"Project: {project_name}\n", style="cyan")
        body.append(f"Session: {session_name}\n")
        if snippet:
            body.append("\n")
            body.append(highlighted)

        console.print(Panel(body, border_style="dim"))


def display_history(
    console: Console,
    sessions: list[SessionState],
    group_by_project: bool = True,
) -> None:
    """Display session history with project grouping and ASCII timeline.

    Groups sessions by project_name with timeline markers:
      o  completed
      >  active
      ||  paused
      x  interrupted

    If group_by_project=False, lists all sessions in reverse chronological
    order (most recent first).
    """
    if not sessions:
        console.print("No sessions yet.", style="dim")
        return

    if not group_by_project:
        sorted_sessions = sorted(sessions, key=lambda s: s.created_at, reverse=True)
        for session in sorted_sessions:
            console.print(_history_line(session))
        return

    # Group by project
    groups: dict[str, list[SessionState]] = {}
    for session in sessions:
        groups.setdefault(session.project_name, []).append(session)

    for project_name, group_sessions in groups.items():
        console.print(Text(project_name, style="bold cyan"))
        # Sort ascending by created_at within each group
        group_sessions.sort(key=lambda s: s.created_at)
        for session in group_sessions:
            console.print(_history_line(session))
        console.print()


def _status_marker(status: str) -> str:
    """Return the ASCII timeline marker for a session status."""
    markers = {
        "completed": "o",
        "active": ">",
        "paused": "||",
        "interrupted": "x",
    }
    return markers.get(status, "?")


def _history_line(session: SessionState) -> Text:
    """Build one literal-safe history line."""
    marker = _status_marker(session.status)
    elapsed = format_elapsed(session.elapsed_seconds)
    date_str = session.created_at.strftime("%b %d")

    line = Text(f"  {marker}  ")
    line.append(session.session_name)
    line.append(f"  ({elapsed}, {date_str})  {session.status}")
    return line


def _query_terms(query: str) -> list[str]:
    """Extract highlight terms from a raw user search query."""
    terms = _QUERY_TOKEN_RE.findall(query)
    if len(terms) > 1:
        filtered_terms = [term for term in terms if term.upper() not in _FTS_OPERATOR_TOKENS]
        if filtered_terms:
            terms = filtered_terms
    return terms or ([query] if query else [])
