"""Tests for subagent status display."""

from __future__ import annotations

from rich.console import Console

from gpd.mcp.subagents.models import SubagentStatus
from gpd.mcp.subagents.status_display import SubagentDisplay


def _make_status(agent: str = "mcp-builder", message: str = "working", is_sub: bool = False) -> SubagentStatus:
    return SubagentStatus(agent_name=agent, message=message, is_subagent_message=is_sub)


def test_on_status_buffers_messages():
    """Buffer 3 messages and verify count."""
    display = SubagentDisplay(console=Console(quiet=True))
    display.on_status(_make_status(message="msg1"))
    display.on_status(_make_status(message="msg2"))
    display.on_status(_make_status(message="msg3"))
    assert len(display.get_buffered_messages()) == 3


def test_format_status_line_parent_message():
    """Parent messages start with 'MCP Builder:'."""
    display = SubagentDisplay(console=Console(quiet=True))
    status = _make_status(message="diagnosing error", is_sub=False)
    line = display.format_status_line(status)
    assert line.startswith("MCP Builder:")


def test_format_status_line_subagent_message():
    """Subagent messages start with indent + [agent_name]."""
    display = SubagentDisplay(console=Console(quiet=True))
    status = _make_status(agent="mcp-builder", message="reading source", is_sub=True)
    line = display.format_status_line(status)
    assert line.startswith("  [mcp-builder]")


def test_format_status_line_truncates_long_messages():
    """Long messages should be truncated."""
    display = SubagentDisplay(console=Console(quiet=True))
    long_msg = "x" * 200
    status = _make_status(message=long_msg, is_sub=False)
    line = display.format_status_line(status)
    # "MCP Builder: " is 14 chars + 100 chars max message
    assert len(line) <= 114


def test_clear_resets_buffer():
    """Clear should empty the buffer."""
    display = SubagentDisplay(console=Console(quiet=True))
    display.on_status(_make_status())
    display.on_status(_make_status())
    display.clear()
    assert len(display.get_buffered_messages()) == 0


def test_render_expanded_log_no_crash_on_empty():
    """Rendering with empty buffer should not crash."""
    display = SubagentDisplay(console=Console(quiet=True))
    display.render_expanded_log()  # Should not raise
