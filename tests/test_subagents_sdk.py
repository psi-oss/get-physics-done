"""Tests for SubagentSDK wrapper module."""

from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gpd.mcp.subagents.models import SubagentResult, SubagentStatusKind
from gpd.mcp.subagents.sdk import SubagentSDK, _cleanup_symlinks, _get_short_cwd


def test_short_cwd_passthrough():
    """Verify _get_short_cwd returns cwd directly when path < 80 chars."""
    short_path = "/tmp/short"
    assert _get_short_cwd(short_path) == short_path


def test_short_cwd_creates_symlink_for_long_paths(tmp_path):
    """Verify _get_short_cwd creates a symlink for long paths."""
    long_path = str(tmp_path / ("a" * 100))
    # Create the actual directory so symlink target exists
    os.makedirs(long_path, exist_ok=True)
    result = _get_short_cwd(long_path)
    assert result != long_path
    assert len(result) <= 80
    assert Path(result).is_symlink()
    assert os.readlink(result) == long_path
    _cleanup_symlinks()


def test_cleanup_symlinks_removes_symlink_directory(tmp_path):
    """Cleanup should remove the temporary directory created for long paths."""
    long_path = str(tmp_path / ("b" * 100))
    os.makedirs(long_path, exist_ok=True)

    link_path = Path(_get_short_cwd(long_path))
    link_dir = link_path.parent

    assert link_dir.exists()
    _cleanup_symlinks()
    assert not link_dir.exists()


@pytest.mark.asyncio
async def test_spawn_returns_subagent_result():
    """Mock claude_agent_sdk.query to yield a fake ResultMessage, verify spawn returns proper SubagentResult."""

    @dataclass
    class FakeResultMessage:
        subtype: str = "result"
        duration_ms: int = 5000
        duration_api_ms: int = 4500
        is_error: bool = False
        num_turns: int = 3
        session_id: str = "sess-123"
        total_cost_usd: float = 0.05
        result: str = '{"success": true, "mcp_name": "openfoam"}'

    async def fake_query(prompt, options):
        yield FakeResultMessage()

    fake_module = MagicMock()
    fake_module.query = fake_query
    fake_module.ClaudeAgentOptions = MagicMock(return_value=MagicMock())
    fake_module.ResultMessage = FakeResultMessage
    fake_module.AssistantMessage = type("AssistantMessage", (), {})
    fake_module.TextBlock = type("TextBlock", (), {})
    fake_module.ToolUseBlock = type("ToolUseBlock", (), {})

    with patch.dict("sys.modules", {"claude_agent_sdk": fake_module}):
        sdk = SubagentSDK()
        result = await sdk.spawn(
            prompt="test prompt",
            agents={},
            allowed_tools=["Read"],
            cwd="/tmp",
            timeout_seconds=60,
        )

    assert isinstance(result, SubagentResult)
    assert result.success is True
    assert result.session_id == "sess-123"
    assert result.cost_usd == 0.05
    assert "openfoam" in result.result_text


@pytest.mark.asyncio
async def test_spawn_reports_status_updates():
    """Assistant text and tool calls should emit clear status events."""

    @dataclass
    class FakeTextBlock:
        text: str

    @dataclass
    class FakeToolUseBlock:
        name: str

    @dataclass
    class FakeAssistantMessage:
        content: list[object]

    @dataclass
    class FakeResultMessage:
        duration_ms: int = 1000
        is_error: bool = False
        session_id: str = "sess-456"
        total_cost_usd: float = 0.01
        result: str = "done"

    async def fake_query(prompt, options):
        yield FakeAssistantMessage(content=[FakeTextBlock("Thinking through the task\nmore"), FakeToolUseBlock("Read")])
        yield FakeResultMessage()

    fake_module = MagicMock()
    fake_module.query = fake_query
    fake_module.ClaudeAgentOptions = MagicMock(return_value=MagicMock())
    fake_module.ResultMessage = FakeResultMessage
    fake_module.AssistantMessage = FakeAssistantMessage
    fake_module.TextBlock = FakeTextBlock
    fake_module.ToolUseBlock = FakeToolUseBlock

    statuses = []
    with patch.dict("sys.modules", {"claude_agent_sdk": fake_module}):
        sdk = SubagentSDK()
        await sdk.spawn(
            prompt="test prompt",
            agents={},
            allowed_tools=["Read"],
            cwd="/tmp",
            timeout_seconds=60,
            on_status=statuses.append,
        )

    assert [status.source for status in statuses] == ["subagent", "Read"]
    assert [status.kind for status in statuses] == [SubagentStatusKind.UPDATE, SubagentStatusKind.TOOL]
    assert statuses[0].message == "Thinking through the task"
    assert statuses[1].message == "Tool call started"


@pytest.mark.asyncio
async def test_spawn_timeout_returns_failure():
    """Mock query to hang, verify timeout produces SubagentResult(success=False)."""

    async def slow_query(prompt, options):
        await asyncio.sleep(100)
        yield MagicMock()  # Never reached

    fake_module = MagicMock()
    fake_module.query = slow_query
    fake_module.ClaudeAgentOptions = MagicMock(return_value=MagicMock())
    fake_module.ResultMessage = type("ResultMessage", (), {})
    fake_module.AssistantMessage = type("AssistantMessage", (), {})
    fake_module.TextBlock = type("TextBlock", (), {})
    fake_module.ToolUseBlock = type("ToolUseBlock", (), {})

    with patch.dict("sys.modules", {"claude_agent_sdk": fake_module}):
        sdk = SubagentSDK()
        result = await sdk.spawn(
            prompt="test prompt",
            agents={},
            allowed_tools=["Read"],
            cwd="/tmp",
            timeout_seconds=0.1,  # Very short timeout
        )

    assert result.success is False
    assert "timed out" in result.result_text.lower()


@pytest.mark.asyncio
async def test_spawn_sdk_not_installed():
    """Patch import to raise ImportError, verify RuntimeError with install instructions."""
    with patch.dict("sys.modules", {"claude_agent_sdk": None}):
        sdk = SubagentSDK()
        with pytest.raises(RuntimeError, match="claude-agent-sdk not installed"):
            await sdk.spawn(
                prompt="test",
                agents={},
                allowed_tools=[],
                cwd="/tmp",
            )
