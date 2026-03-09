"""Tests for subagent status display."""

from __future__ import annotations

from rich.console import Console

from gpd.mcp.subagents.models import SubagentStatus, SubagentStatusKind
from gpd.mcp.subagents.status_display import SubagentDisplay


def _make_status(
    source: str = "worker",
    message: str = "working",
    kind: SubagentStatusKind | None = None,
) -> SubagentStatus:
    return SubagentStatus(source=source, message=message, kind=kind or SubagentStatusKind.UPDATE)


def test_on_status_buffers_messages():
    """Buffer 3 messages and verify count."""
    display = SubagentDisplay(console=Console(quiet=True))
    display.on_status(_make_status(message="msg1"))
    display.on_status(_make_status(message="msg2"))
    display.on_status(_make_status(message="msg3"))
    assert len(display.get_buffered_messages()) == 3


def test_format_status_line_parent_message():
    """Parent messages start with 'Subagent:'."""
    display = SubagentDisplay(console=Console(quiet=True))
    status = _make_status(source="subagent", message="diagnosing error")
    line = display.format_status_line(status)
    assert line.startswith("Subagent:")


def test_format_status_line_subagent_message():
    """Subagent messages start with indent + [agent_name]."""
    display = SubagentDisplay(console=Console(quiet=True))
    status = _make_status(source="worker", message="reading source", kind=SubagentStatusKind.TOOL)
    line = display.format_status_line(status)
    assert line.startswith("  [worker]")


def test_format_status_line_truncates_long_messages():
    """Long messages should be truncated."""
    display = SubagentDisplay(console=Console(quiet=True))
    long_msg = "x" * 200
    status = _make_status(source="subagent", message=long_msg)
    line = display.format_status_line(status)
    # "Subagent: " is 10 chars + 100 chars max message
    assert len(line) <= 110


def test_clear_resets_buffer():
    """Clear should empty the buffer."""
    display = SubagentDisplay(console=Console(quiet=True))
    display.on_status(_make_status())
    display.on_status(_make_status())
    display.clear()
    assert len(display.get_buffered_messages()) == 0


def test_request_expanded_log_sets_flag():
    """Explicit expansion requests should be tracked."""
    display = SubagentDisplay(console=Console(quiet=True))
    display.request_expanded_log()
    assert display.expand_requested is True


def test_legacy_status_fields_are_still_accepted():
    """Pre-cleanup status field names should still map correctly."""
    status = SubagentStatus(agent_name="worker", message="reading", is_subagent_message=True)
    assert status.source == "worker"
    assert status.kind == SubagentStatusKind.TOOL


def test_render_expanded_log_no_crash_on_empty():
    """Rendering with empty buffer should not crash."""
    display = SubagentDisplay(console=Console(quiet=True))
    display.render_expanded_log()  # Should not raise
