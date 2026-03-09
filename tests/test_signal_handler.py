"""Tests for SIGINT handler and adaptive checkpointing."""

from __future__ import annotations

import signal
import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import MagicMock

from gpd.mcp.signal_handler import graceful_shutdown


def _make_mock_manager() -> MagicMock:
    """Create a mock SessionManager for testing."""
    manager = MagicMock()
    manager.save_checkpoint = MagicMock()
    manager.close = MagicMock()
    return manager


class TestGracefulShutdown:
    """Tests for the graceful_shutdown context manager."""

    def test_installs_and_restores_signal_handler(self) -> None:
        manager = _make_mock_manager()
        original = signal.getsignal(signal.SIGINT)

        with graceful_shutdown(manager):
            # Inside context, handler should be different from original
            current = signal.getsignal(signal.SIGINT)
            assert current is not original

        # After context, handler should be restored
        restored = signal.getsignal(signal.SIGINT)
        assert restored is original

    def test_sigint_calls_save_checkpoint_in_subprocess(self, tmp_path: Path) -> None:
        """Test SIGINT handling in a subprocess to avoid killing the test runner."""
        marker = tmp_path / "sigint_handled.txt"
        script = textwrap.dedent(f"""\
            import signal
            import sys
            import os
            from pathlib import Path

            # Add package to path for subprocess
            sys.path.insert(0, "{Path(__file__).parent.parent / "src"}")

            from unittest.mock import MagicMock
            from gpd.mcp.signal_handler import graceful_shutdown

            manager = MagicMock()

            def fake_save_checkpoint(reason):
                Path("{marker}").write_text(f"checkpoint:{{reason}}")

            manager.save_checkpoint = fake_save_checkpoint
            manager.close = MagicMock()

            with graceful_shutdown(manager):
                # Send SIGINT to ourselves
                os.kill(os.getpid(), signal.SIGINT)
        """)

        result = subprocess.run(
            [sys.executable, "-c", script],
            capture_output=True,
            text=True,
            timeout=10,
        )

        # The handler calls sys.exit(0), so return code should be 0
        assert result.returncode == 0
        assert marker.exists()
        assert marker.read_text() == "checkpoint:interrupted"
