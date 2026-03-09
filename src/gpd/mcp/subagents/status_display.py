"""Terminal status display for subagent operations.

Shows a compact one-line status during subagent operations with buffered
messages for expanded output. Uses Rich's Status spinner for the spinner.
"""

from __future__ import annotations

import logging
from collections.abc import Coroutine

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

from gpd.mcp.subagents.models import SubagentStatus

logger = logging.getLogger(__name__)


class SubagentDisplay:
    """Compact status display for subagent operations.

    Buffers all status messages and provides a one-line spinner display.
    After operation completes, can render the full expanded log.
    """

    def __init__(self, console: Console | None = None) -> None:
        self._console = console or Console()
        self._message_buffer: list[SubagentStatus] = []
        self._expand_requested: bool = False

    def on_status(self, status: SubagentStatus) -> None:
        """Buffer a status update (callback for SubagentSDK.spawn)."""
        self._message_buffer.append(status)

    def start_spinner(self, initial_message: str) -> object:
        """Return a Rich Status context manager for spinner display."""
        return self._console.status(initial_message, spinner="dots")

    def format_status_line(self, status: SubagentStatus) -> str:
        """Format a status update as a one-line string."""
        if status.is_subagent_message:
            return f"  [{status.agent_name}] {status.message[:80]}"
        return f"MCP Builder: {status.message[:100]}"

    def render_expanded_log(self) -> None:
        """Print all buffered messages as a Rich Panel."""
        if not self._message_buffer:
            self._console.print(Panel("[dim]No subagent activity recorded.[/dim]", title="Subagent Activity Log"))
            return

        lines = Text()
        for msg in self._message_buffer:
            prefix = f"[{msg.agent_name}]" if msg.is_subagent_message else "parent"
            lines.append(f"  {prefix} {msg.message}\n")

        self._console.print(Panel(lines, title="Subagent Activity Log"))

    def get_buffered_messages(self) -> list[SubagentStatus]:
        """Return copy of buffered messages (for testing)."""
        return list(self._message_buffer)

    def clear(self) -> None:
        """Clear buffer and reset state."""
        self._message_buffer.clear()
        self._expand_requested = False


async def run_with_status(
    display: SubagentDisplay,
    label: str,
    coro: Coroutine[object, object, object],
) -> object:
    """Run a coroutine with spinner display.

    Creates a spinner, runs the coroutine, and renders the expanded log
    if the operation failed or expansion was requested.
    """
    with display.start_spinner(label):
        result = await coro

    # Render expanded log on failure or if requested
    if display._expand_requested or (hasattr(result, "success") and not result.success):
        display.render_expanded_log()

    return result
