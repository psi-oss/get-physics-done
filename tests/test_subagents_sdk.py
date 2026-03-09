"""Tests for SubagentSDK wrapper module."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from gpd.mcp.subagents.models import SubagentResult
from gpd.mcp.subagents.sdk import SubagentSDK, _get_short_cwd


def test_short_cwd_passthrough():
    """Verify _get_short_cwd returns cwd directly when path < 80 chars."""
    short_path = "/tmp/short"
    assert _get_short_cwd(short_path) == short_path


def test_short_cwd_creates_symlink_for_long_paths(tmp_path):
    """Verify _get_short_cwd creates a symlink for long paths."""
    long_path = str(tmp_path / ("a" * 100))
    # Create the actual directory so symlink target exists
    import os

    os.makedirs(long_path, exist_ok=True)
    result = _get_short_cwd(long_path)
    assert result != long_path
    assert len(result) <= 80
    assert Path(result).is_symlink()
    assert os.readlink(result) == long_path


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
