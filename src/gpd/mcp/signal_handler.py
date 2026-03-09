"""SIGINT handler context manager for graceful session save on Ctrl+C."""

from __future__ import annotations

import signal
import sys
from contextlib import contextmanager
from typing import TYPE_CHECKING

from rich.console import Console

if TYPE_CHECKING:
    from collections.abc import Generator

    from gpd.mcp.session.manager import SessionManager


@contextmanager
def graceful_shutdown(session_manager: SessionManager) -> Generator[None, None, None]:
    """Context manager that installs a SIGINT handler to save session state.

    On first Ctrl+C: saves a checkpoint with reason "interrupted", closes
    the session, prints a confirmation, and exits cleanly.

    On second Ctrl+C (while first handler is running): force exits
    immediately via sys.exit(1).

    Uses signal.signal(SIGINT) -- NOT atexit -- because atexit handlers
    do NOT run on raw SIGINT.
    """
    original_handler = signal.getsignal(signal.SIGINT)
    shutdown_requested = [False]
    console = Console()

    def handler(signum: int, frame: object) -> None:
        if shutdown_requested[0]:
            # Second Ctrl+C: force exit
            sys.exit(1)

        shutdown_requested[0] = True
        session_manager.save_checkpoint("interrupted")
        session_manager.close()
        console.print("[bold yellow]Session saved. Exiting...[/]")
        sys.exit(0)

    signal.signal(signal.SIGINT, handler)
    try:
        yield
    finally:
        signal.signal(signal.SIGINT, original_handler)
